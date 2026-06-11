#!/usr/bin/env python3
"""
实验 1.1.3: 从 memory 中识别情境 (LLM 版)

用法: python3 extract.py [memory_dir] [--output <dir>]
环境变量: DEEPSEEK_API_KEY
"""

import os
import sys
import json
import yaml
from pathlib import Path

from openai import OpenAI

SYSTEM_PROMPT = """你是一个认知抽取助手。从用户的日记/笔记中识别"情境"。

情境定义：一段连续的认知活动单元，包含时间、地点、参与者、活动、情绪状态。

输出 JSON 数组，每个元素格式：
{
  "id": "唯一标识",
  "time": {"raw": "原文时间表述", "inferred_date": "推断日期 YYYY-MM-DD"},
  "location": "地点或 null",
  "participants": ["参与者列表"],
  "activity": "活动描述（20字以内概括）",
  "mood": {"raw": "情绪关键词或 null", "valence": -3到3的整数, "arousal": 0到5的整数}
}

规则：
- 严格按原文信息输出，不编造
- 可推断的补充（如日期从文件名来）在 inferred_date 中体现
- 没有明确信息的字段设为 null 或空列表
- 一条文本可能包含多个情境，分别输出
- 输出纯 JSON，不要 markdown 包裹"""


def load_memory_files(data_dir):
    data_dir = Path(data_dir)
    files = []
    for ext in ["*.md"]:
        for f in sorted(data_dir.rglob(ext)):
            if f.name in ("README.md", "AGENTS.md", "CHANGELOG.md"):
                continue
            files.append(f)
    return files


def infer_date_from_filename(filepath):
    import re
    m = re.search(r"(\d{4}-\d{2}-\d{2})", str(filepath))
    return m.group(1) if m else None


def chunk_text(text, max_chars=2000):
    """按段落分块，每块不超过 max_chars"""
    paragraphs = text.strip().split("\n\n")
    chunks = []
    current = []
    current_len = 0
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if current_len + len(p) > max_chars and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(p)
        current_len += len(p)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def extract_with_llm(text, inferred_date, client, model="deepseek-chat"):
    """调用 LLM 从文本中抽取情境"""
    user_prompt = f"""从以下文本中识别情境。日期推断基准: {inferred_date or "未知"}

文本：
{text}
"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096,
        )
        content = resp.choices[0].message.content.strip()
        data = json.loads(content)
        situations = data if isinstance(data, list) else data.get("situations", [])
        return situations
    except Exception as e:
        print(f"  LLM 调用失败: {e}", file=sys.stderr)
        return []


def build_source_ref(filepath, base_dir, chunk_idx, chunk_count):
    try:
        rel = str(Path(filepath).relative_to(base_dir))
    except ValueError:
        rel = str(filepath)
    return {
        "file": rel,
        "chunk": f"{chunk_idx + 1}/{chunk_count}",
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LLM 从 memory 中识别情境")
    parser.add_argument("memory_dir", nargs="?",
                        default=os.path.join(os.path.dirname(__file__), "../../data"),
                        help="memory 目录路径")
    parser.add_argument("--output", "-o", default="output", help="输出目录")
    parser.add_argument("--model", default="deepseek-chat", help="模型名")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = load_memory_files(args.memory_dir)
    print(f"找到 {len(files)} 个 memory 文件\n")

    all_situations = []
    seq = 0

    for f in files:
        inferred_date = infer_date_from_filename(f)
        text = f.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        file_situations = []

        rel_path = f.relative_to(args.memory_dir) if args.memory_dir else f.name
        print(f"  {rel_path} ({len(chunks)} 块)...")

        for ci, chunk in enumerate(chunks):
            situations = extract_with_llm(chunk, inferred_date, client, args.model)
            for s in situations:
                seq += 1
                date_part = inferred_date or "unknown"
                s["id"] = f"s-{date_part}-{seq:03d}"
                s["source"] = build_source_ref(f, args.memory_dir, ci, len(chunks))
                if inferred_date and not s.get("time", {}).get("inferred_date"):
                    s.setdefault("time", {})["inferred_date"] = inferred_date
            file_situations.extend(situations)
            print(f"    块 {ci+1}/{len(chunks)}: {len(situations)} 个情境")

        all_situations.extend(file_situations)
        print(f"  → 共 {len(file_situations)} 个情境\n")

    output_file = output_dir / "situations.yaml"
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump({"situations": all_situations}, f, allow_unicode=True, sort_keys=False)
    print(f"结果已输出: {output_file}")
    print(f"共识别 {len(all_situations)} 个情境 (来自 {len(files)} 个文件)")


if __name__ == "__main__":
    main()
