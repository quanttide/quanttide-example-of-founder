#!/usr/bin/env python3
"""
抽取工具 — 本体 YAML → 结构化产物
Model 约束驱动：`--model` 指定模型声明 YAML，自动编译 JSON schema 约束 LLM 输出。

用法:
  python3 -m knowl.extract --input <cognition.yaml> --model data/knowl/cognition.yaml --type cognition  --output out/
  python3 -m knowl.extract --input <journal.yaml>   --model data/knowl/cognition.yaml --type cognition  --output out/ --consume
  python3 -m knowl.extract --input <journal.yaml>   --model data/knowl/cognition.yaml --type todo       --output out/
  python3 -m knowl.extract --input <fiction.yaml>    --model data/knowl/motif.yaml     --type motif      --output out/
  python3 -m knowl.extract --input <journal.yaml>    --model data/knowl/cognition.yaml --type annotate   --output out/
"""

import os
import sys
import json
import yaml
import time
from pathlib import Path
from datetime import datetime
from openai import OpenAI


# ── Schema 编译 ──────────────────────────────────────────────

TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "float": "number",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
    "enum": "string",
}


def _compile_field(field: dict) -> dict:
    """将 YAML field 定义编译为 JSON Schema 片段"""
    name = field["name"]
    ftype = field["type"]
    desc = field.get("description", "")
    schema_type = TYPE_MAP.get(ftype, "string")

    prop = {"description": desc}

    if ftype == "enum":
        prop["type"] = "string"
        prop["enum"] = field.get("values", [])
    elif ftype == "array":
        prop["type"] = "array"
        items = field.get("items", {})
        if "fields" in items:
            # items 有子字段结构，编译成对象 schema
            item_schema = {"type": "object", "properties": {}, "additionalProperties": False}
            for sf in items.get("fields", []):
                item_field = _compile_field(sf)
                item_schema["properties"][sf["name"]] = item_field
                # 把 items 的 description 提上来
                if sf.get("description") and "description" not in item_schema:
                    item_schema["description"] = sf["description"]
            prop["items"] = item_schema
        elif "name" in items:
            prop["items"] = _compile_field(items)
        else:
            prop["items"] = {"type": "string"}
    elif ftype == "object":
        prop["type"] = "object"
        prop["properties"] = {}
        for sf in field.get("fields", []):
            schema = _compile_field(sf)
            prop["properties"][sf["name"]] = schema
        # 所有子字段默认可选（LLM 输出时不需要全部填）
        prop["additionalProperties"] = False
    else:
        prop["type"] = schema_type
        # 允许 null: string | null 语法
        if "| null" in field.get("type", ""):
            prop["type"] = [schema_type, "null"]
        if "range" in field:
            r = field["range"]
            if "minimum" not in prop:
                prop["minimum"] = r[0]
            if "maximum" not in prop:
                prop["maximum"] = r[1]

    prop.setdefault("type", "string")
    return prop


def compile_schema(model_data: dict, top_key: str = None) -> dict:
    """从 YAML 模型声明编译 JSON Schema。

    model_data 结构:
      top_key:
        description: ...
        fields: [...]
        example: [...]

    返回 JSON Schema dict，包含 description + properties。
    """
    # 找到顶层 key
    keys = [top_key] if top_key else list(model_data.keys())
    key = keys[0] if keys else None
    if not key or key not in model_data:
        raise ValueError(f"模型声明未找到顶层 key '{top_key or list(model_data.keys())[0]}'")

    model = model_data[key]
    schema = {
        "type": "object",
        "description": model.get("description", ""),
        "properties": {},
        "additionalProperties": False,
    }

    for field in model.get("fields", []):
        schema["properties"][field["name"]] = _compile_field(field)

    return schema


def format_schema_for_prompt(schema: dict, indent: int = 0) -> str:
    """将 JSON Schema 格式化为人类可读的输出格式定义（嵌入 prompt）"""
    prefix = "  " * indent
    lines = [f"{prefix}输出 JSON 格式（严格遵循以下 schema）："]

    def _fmt_prop(name, prop, depth=1):
        pad = "  " * depth
        ptype = prop.get("type", "string")
        desc = prop.get("description", "")
        if isinstance(ptype, list):
            ptype_str = " | ".join(ptype)
        else:
            ptype_str = ptype
        line = f"{pad}- {name}: {ptype_str}"
        if desc:
            line += f"  # {desc}"
        lines.append(line)

        if ptype == "object" or (isinstance(ptype, list) and "object" in ptype):
            for sub_name, sub_prop in prop.get("properties", {}).items():
                _fmt_prop(sub_name, sub_prop, depth + 1)
        elif ptype == "array":
            items = prop.get("items", {})
            items_type = items.get("type", "string")
            if isinstance(items_type, list):
                items_type_str = " | ".join(items_type)
            else:
                items_type_str = items_type
            if items_type == "object":
                lines.append(f"{pad}  items: object")
                for sub_name, sub_prop in items.get("properties", {}).items():
                    _fmt_prop(sub_name, sub_prop, depth + 2)
            elif items_type_str != "string":
                lines.append(f"{pad}  items: {items_type_str}")
            elif items.get("enum"):
                lines.append(f"{pad}  items: enum [{', '.join(items['enum'])}]")
            else:
                lines.append(f"{pad}  items: {items.get('type', 'string')}")
        if "enum" in prop:
            lines.append(f"{pad}  enum: [{', '.join(prop['enum'])}]")

    for name, prop in schema.get("properties", {}).items():
        _fmt_prop(name, prop, 1)

    lines.append("")
    lines.append(f"{prefix}规则：")
    return "\n".join(lines)


# ── 通用工具 ──────────────────────────────────────────────

def get_client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def call_llm(prompt: str, text: str, client: OpenAI = None,
             model: str = "deepseek-chat", json_mode: bool = True,
             max_tokens: int = 4096, temperature: float = 0.1) -> dict:
    client = client or get_client()
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content.strip()
    return json.loads(content)


def read_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_yaml(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)


def write_markdown(text: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ── 抽取实现 ──────────────────────────────────────────────

def extract_by_type(data: dict, output: Path, extract_type: str, model_schema: dict = None, limit=None):
    """按 type 分发到不同的抽取实现"""
    dispatch = {
        "cognition": _extract_cognition,
        "todo": _extract_todo,
        "motif": _extract_motif,
        "annotate": _extract_annotate,
    }
    fn = dispatch.get(extract_type)
    if not fn:
        available = ", ".join(sorted(dispatch.keys()))
        print(f"错误: 未知抽取类型 '{extract_type}'，可用: {available}", file=sys.stderr)
        sys.exit(1)
    fn(data, output, model_schema, limit)


# ── cognition: journal → cognition.yaml ──────────────────

EXTRACT_PROMPT_BASE = """从以下日记段落中提取结构化认知要素，包含图式。

{format_instructions}

规则：
- situation 从原文推断，不编造
- intentions 只提取有行动导向的内容（想要/打算/决定/需要）
- ideas 只提取认知产出（发现/想到/怀疑/感觉）
- schemas 识别本段触发的重复认知模式（图式），每个图式包含名称+所属领域+触发情境+响应
  - domain 标注所属领域（如"叙事工程"、"系统架构"、"团队管理"）
  - 图式名称用已有认知模式名（如"团队脆弱期的收缩策略"、"讲故事传递意图"）
  - 如果是未见过的模式，用概括性名称命名
  - 不需要跨段验证，只关注本段触发的模式
- 如果某类不存在，输出空数组或null
- 纯 JSON。"""


def _extract_cognition(data: dict, output: Path, model_schema: dict = None, limit=None):
    entries = data.get("entries", [])
    if limit:
        entries = entries[:limit]

    # 构建 prompt
    if model_schema:
        fmt = format_schema_for_prompt(model_schema)
        prompt = EXTRACT_PROMPT_BASE.format(format_instructions=fmt)
    else:
        prompt = EXTRACT_PROMPT_BASE.format(
            format_instructions="""输出 JSON：
{
  "situation": {
    "time": {"raw": "时间表述或null", "inferred_date": "推断日期或null"},
    "location": "地点或null",
    "participants": ["参与者列表"],
    "activity": "活动概括（15字）",
    "mood": {"raw": "情绪词或null", "valence": -3~3, "arousal": 0~5}
  },
  "intentions": [
    {"type": "goal/motive/plan/commitment", "content": "意图原文"}
  ],
  "ideas": [
    {"type": "insight/hypothesis/question/analogy", "content": "想法原文"}
  ]
}"""
        )

    done_file = output / "_done.txt"
    done_set = set()
    if done_file.exists():
        with open(done_file, encoding="utf-8") as f:
            done_set = set(line.strip() for line in f if line.strip())
        print(f"\n  发现断点: 已处理 {len(done_set)}/{len(entries)} 段")

    out_file = output / "cognition.yaml"
    existing = []
    if out_file.exists():
        data_loaded = read_yaml(out_file)
        existing = data_loaded.get("segments", [])

    total = len(entries)
    new_results = []
    for idx, entry in enumerate(entries, 1):
        seg_id = f"{idx:03d}"
        if seg_id in done_set:
            continue
        print(f"\r  处理中: {idx}/{total} ({idx*100//total}%)", end="", file=sys.stderr)
        result = call_llm(prompt, entry["text"], max_tokens=1024)
        result["_source"] = entry.get("source", "")
        result["_raw"] = entry["text"][:100]
        new_results.append(result)

        with open(done_file, "a", encoding="utf-8") as f:
            f.write(f"{seg_id}\n")
        write_yaml({"segments": existing + new_results}, out_file)

    done_file.unlink(missing_ok=True)
    all_results = existing + new_results

    total_intentions = sum(len(r.get("intentions", [])) for r in all_results)
    total_ideas = sum(len(r.get("ideas", [])) for r in all_results)
    total_situations = sum(1 for r in all_results if r.get("situation"))

    print(f"\r  处理完成: {len(all_results)}/{len(all_results)} (100%)", file=sys.stderr)
    print(f"\n结果:")
    print(f"  有情境的段落: {total_situations}/{len(all_results)}")
    print(f"  意图总数: {total_intentions}")
    print(f"  想法总数: {total_ideas}")
    print(f"\n意图清单:")
    for r in all_results:
        for intent in r.get("intentions", []):
            print(f"  [{intent.get('type','')}] {intent.get('content','')[:50]}")
    print(f"\n想法清单:")
    for r in all_results:
        for idea in r.get("ideas", []):
            print(f"  [{idea.get('type','')}] {idea.get('content','')[:50]}")


# ── todo: journal → TODO.md ──────────────────────────────

EXTRACT_INTENT_PROMPT_BASE = r"""从以下日记段落中提取情境和行动计划类的意图。

{format_instructions}

规则：
- 只提取 plan（计划）和 commitment（承诺）类型的意图
- 从原文中找出有行动导向的内容
- 如果不存在，输出空数组
- 纯 JSON。"""

JUDGE_PROMPT = """判断以下意图是否可执行，并给出领域分类。

情境：{situation}
意图：{intent}

规则：
- 可执行：有明确动词+具体对象，知道第一步做什么
- 模糊方向：有方向但缺具体动作或对象
- 不可执行：纯意图/战略/价值观/元认知

领域分类根据情境判断——从对话背景（活动描述）推断该意图属于哪个领域。

输出 JSON：
{{
  "verdict": "可执行/模糊方向/不可执行",
  "first_step": "如果是可执行，建议的第一步（15字）",
  "domain": "系统架构/小说创作/团队管理/工具链/实验验证/数据/方法论",
  "reason": "判断理由（10字）"
}}
纯 JSON。"""


def _extract_todo(data: dict, output: Path, model_schema: dict = None, limit=None):
    entries = data.get("entries", [])
    if limit:
        entries = entries[:limit]

    # 构建 prompt——todo 只关心 intentions，不用完整的 cognition schema
    if model_schema:
        # 只取 intentions 部分
        props = model_schema.get("properties", {})
        intent_schema = props.get("intentions", {})
        if intent_schema:
            # 构建一个简化 schema
            simple_schema = {
                "type": "object",
                "properties": {
                    "activity": {"type": "string", "description": "活动概括（15字）"},
                    "intentions": intent_schema
                },
                "additionalProperties": False,
            }
            fmt = format_schema_for_prompt(simple_schema)
        else:
            fmt = format_schema_for_prompt(model_schema)
        prompt = EXTRACT_INTENT_PROMPT_BASE.format(format_instructions=fmt)
    else:
        prompt = EXTRACT_INTENT_PROMPT_BASE.format(
            format_instructions="""输出 JSON：
{
  "activity": "活动概括（15字）",
  "intentions": [
    {"type": "plan/commitment", "content": "意图原文"}
  ]
}"""
        )

    ready = []
    total = len(entries)
    for idx, entry in enumerate(entries, 1):
        text = entry["text"]
        print(f"\r  处理中: {idx}/{total} ({idx*100//total}%)", end="", file=sys.stderr)

        extract_result = call_llm(prompt, text, max_tokens=1024)
        activity = extract_result.get("activity", text[:200])
        intentions = extract_result.get("intentions", [])

        for intent in intentions:
            content = intent.get("content", "").strip()
            if not content:
                continue
            jprompt = JUDGE_PROMPT.format(situation=activity, intent=content)
            result = call_llm(jprompt, f"意图：{content}", max_tokens=256)
            if result.get("verdict") == "可执行":
                ready.append((content, result.get("first_step", "")))

    todo_path = output / "TODO.md"
    date_str = datetime.now().strftime("%Y-%m-%d")

    existing = set()
    if todo_path.exists():
        with open(todo_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- [x] ") or line.startswith("- [ ] "):
                    existing.add(line[6:].strip())

    new_items = [(t, s) for t, s in ready if t not in existing]
    new_count = 0

    if new_items:
        with open(todo_path, "a" if todo_path.exists() else "w", encoding="utf-8") as f:
            if not todo_path.exists():
                f.write("# TODO\n\n")
            f.write(f"## {date_str}\n\n")
            for text, step in new_items:
                f.write(f"- [ ] {text}\n")
                if step:
                    f.write(f"  第一步：{step}\n")
            f.write("\n")
            new_count = len(new_items)

    print(f"\n可执行: {len(ready)}")
    for text, step in ready:
        print(f"  [ ] {text}  → {step}")
    print(f"\n已更新: {todo_path}")
    print(f"  新增: {new_count} 条")


# ── motif: 小说 → motifs.yaml / styles.yaml ──────────────

MOTIF_PROMPT_BASE = """你是一个叙事分析助手。从小说片段中识别母题 (Motif)。

{format_instructions}

规则：
- 每个片段识别 1-5 个母题
- 母题要有实质内容，不泛泛而谈
- 输出纯 JSON 数组，不要 markdown"""

STYLE_PROMPT_BASE = """你是一个文体分析助手。分析以下小说片段的风格特征。

{format_instructions}

规则：
- 基于原文实际统计，不编造数字
- 输出纯 JSON，不要 markdown"""


def _extract_motif(data: dict, output: Path, model_schema: dict = None, limit=None):
    entries = data.get("entries", [])
    if limit:
        entries = entries[:limit]

    # 构建 prompt——motif.yaml 包含 motif 和 style 两个顶层 key
    if model_schema:
        # motif schema
        motif_schema = {"type": "array", "items": model_schema}
        motif_fmt = format_schema_for_prompt(motif_schema)
        # style schema
        style_fmt = "无需格式约束"
    else:
        motif_fmt = """输出 JSON 数组，每个元素：
{
  "motif_name": "母题名",
  "motif_type": "theme|image|plot|character",
  "motif_subtype": "子类型标签",
  "description": "简述",
  "excerpt": "最能体现该母题的原文片段（50字以内）"
}"""
        style_fmt = """输出 JSON 对象：
{
  "style_name": "风格名称",
  "tags": ["风格标签数组"],
  "features": {
    "avg_sentence_length": 平均句长（字符数，浮点数）,
    "dialogue_ratio": 对话占比（0-1，浮点数）,
    "lexical_diversity": 词汇多样性（估算，0-1）,
    "rhetorical_density": 修辞密度（估算，0-1）
  }
}"""

    motif_prompt = MOTIF_PROMPT_BASE.format(format_instructions=motif_fmt)
    style_prompt = STYLE_PROMPT_BASE.format(format_instructions=style_fmt)

    all_motifs = []
    all_styles = []
    seq = [0]

    for entry in entries:
        text = entry["text"]
        source = entry.get("source", "")

        # 分段（旧逻辑：每 3000 字符切一块）
        paragraphs = text.strip().split("\n\n")
        chunks = []
        current = []
        current_len = 0
        for p in paragraphs:
            p = p.strip()
            if not p or p.startswith("# "):
                continue
            if current_len + len(p) > 3000 and current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            current.append(p)
            current_len += len(p)
        if current:
            chunks.append("\n\n".join(current))
        if not chunks:
            chunks = [text]

        file_motifs = []
        file_style = None

        for ci, chunk in enumerate(chunks):
            motif_data = call_llm(motif_prompt, chunk, max_tokens=4096)
            motifs = []
            if isinstance(motif_data, list):
                motifs = motif_data
            elif isinstance(motif_data, dict):
                for key in ["motifs", "results", "items"]:
                    if key in motif_data and isinstance(motif_data[key], list):
                        motifs = motif_data[key]
                        break
            for m in motifs:
                seq[0] += 1
                m["id"] = f"m-{seq[0]:03d}"
                m["source"] = source
                m["chunk"] = ci + 1
            file_motifs.extend(motifs)
            print(f"  {source} 块 {ci+1}: {len(motifs)} 个母题")

            if not file_style:
                style = call_llm(style_prompt, chunk, max_tokens=4096)
                if style:
                    if "style_name" not in style and "name" in style:
                        style["style_name"] = style.pop("name")
                    style["id"] = f"st-{seq[0]:03d}"
                    style["source"] = source
                    file_style = style
                    print(f"    风格: {style.get('style_name', '?')}")

        all_motifs.extend(file_motifs)
        if file_style:
            all_styles.append(file_style)

    if all_motifs:
        out = output / "motifs.yaml"
        write_yaml({"motifs": all_motifs}, out)
        print(f"母题结果: {out} ({len(all_motifs)} 条)")

    if all_styles:
        out = output / "styles.yaml"
        write_yaml({"styles": all_styles}, out)
        print(f"风格结果: {out} ({len(all_styles)} 条)")


# ── annotate: cognition → ANNOTATION.md ──────────────────

MARKERS = {"[ ]", "[x]", "[-]", "[?]", "[~]"}


def _extract_annotate(data: dict, output: Path, model_schema: dict = None, limit=None):
    entries = data.get("entries", [])
    if limit:
        entries = entries[:limit]

    # 从 entries 中提取意图和想法
    all_intents = []
    all_ideas = []
    for entry in entries:
        text = entry.get("text", "")
        # 简单规则：从 cognition 数据提取（兼容旧格式）
        if isinstance(entry, dict) and "intentions" in entry:
            for item in entry.get("intentions", []):
                content = item.get("content", "").strip()
                if content:
                    all_intents.append(content)
            for item in entry.get("ideas", []):
                content = item.get("content", "").strip()
                if content:
                    all_ideas.append(content)

    intents = list(dict.fromkeys(all_intents))
    ideas = list(dict.fromkeys(all_ideas))

    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# 标注确认 — {date_str}\n"]
    lines.append("标记说明：`[ ]`待确认 `[x]`已采纳 `[-]`已废弃 `[?]`待决策 `[~]`已修改\n\n")

    if intents:
        lines.append("## 意图 [ ]\n\n")
        for item in intents:
            lines.append(f"- [ ] {item}\n")
        lines.append("\n")

    if ideas:
        lines.append("## 想法 [ ]\n\n")
        for item in ideas:
            lines.append(f"- [ ] {item}\n")
        lines.append("\n")

    anno_path = output / "ANNOTATION.md"
    write_markdown("".join(lines), anno_path)
    print(f"已生成: {anno_path}")
    print(f"  意图: {len(intents)} 条")
    print(f"  想法: {len(ideas)} 条")
    print(f"\n编辑标记后运行: python3 -m knowl.extract --input {anno_path} --type annotate --apply")


# ── CLI ────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="抽取：本体 YAML → 结构化产物")
    parser.add_argument("--input", "-i", required=True, help="本体 YAML 路径")
    parser.add_argument("--type", "-t", required=True, help="抽取类型 (cognition, todo, ...)")
    parser.add_argument("--model", "-m", default=None, help="模型声明 YAML 路径（约束 LLM 输出）")
    parser.add_argument("--output", "-o", default="output", help="输出目录")
    parser.add_argument("--limit", type=int, default=None, help="限制处理段数（测试用）")
    parser.add_argument("--watch", "-w", action="store_true", help="监听模式")
    parser.add_argument("--consume", action="store_true", help="MQ 消费者模式")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    # 读取输入数据
    raw = read_yaml(Path(args.input))
    data = raw.get("data", raw)
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                data = {"entries": v}
                break

    # 读取模型声明，编译 schema
    model_schema = None
    if args.model:
        model_raw = read_yaml(Path(args.model))
        # 尝试从顶层 key 提取（cognition.yaml 的顶层是 'cognition'）
        top_keys = ["cognition", "motif", "style", "situation"]
        model_key = None
        for k in top_keys:
            if k in model_raw:
                model_key = k
                break
        # 如果没有匹配的，用第一个非描述性 key
        if not model_key:
            for k in model_raw:
                if k not in ("description", "example"):
                    model_key = k
                    break
        if model_key:
            try:
                model_schema = compile_schema(model_raw, model_key)
                print(f"模型: {args.model} (key: {model_key})")
            except ValueError as e:
                print(f"警告: schema 编译失败: {e}", file=sys.stderr)

    extract_by_type(data, output, args.type, model_schema, args.limit)


if __name__ == "__main__":
    main()
