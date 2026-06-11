#!/usr/bin/env python3
"""
实验 2.2 + 2.3: 从 fiction 中识别母题模式和风格特征 (LLM 版)

用法: python3 extract.py [fiction_dir] [--output <dir>]
环境变量: DEEPSEEK_API_KEY
"""

import os
import sys
import json
import yaml
from pathlib import Path
from openai import OpenAI

MOTIF_PROMPT = """你是一个叙事分析助手。从小说片段中识别母题 (Motif)。

母题分类：
- theme: 主题母题 — 贯穿全文的核心主题（如"重逢"、"守护"、"成长"）
- image: 意象母题 — 反复出现的意象（如"雨"、"路灯"、"咖啡"）
- plot: 情节母题 — 重复出现的情节模式（如"雨天重逢"、"酒吧表白"、"夜市约会"）
- character: 人物母题 — 特定人物类型或关系模式（如"暗恋者"、"青梅竹马"）

输出 JSON 数组，每个元素：
{
  "motif_name": "母题名",
  "motif_type": "theme|image|plot|character",
  "motif_subtype": "子类型标签",
  "description": "简述",
  "excerpt": "最能体现该母题的原文片段（50字以内）"
}

规则：
- 每个片段识别 1-5 个母题
- 母题要有实质内容，不泛泛而谈
- 输出纯 JSON 数组，不要 markdown"""

STYLE_PROMPT = """你是一个文体分析助手。分析以下小说片段的风格特征。

输出 JSON 对象：
{
  "style_name": "风格名称（如'细腻心理描写'、'轻快对话风'）",
  "tags": ["风格标签数组"],
  "features": {
    "avg_sentence_length": 平均句长（字符数，浮点数）,
    "dialogue_ratio": 对话占比（0-1，浮点数）,
    "lexical_diversity": 词汇多样性（估算，0-1）,
    "rhetorical_density": 修辞密度（估算，0-1）
  }
}

规则：
- 基于原文实际统计，不编造数字
- 输出纯 JSON，不要 markdown"""


def load_fiction_files(data_dir):
    data_dir = Path(data_dir)
    files = []
    for ext in ["*.md"]:
        for f in sorted(data_dir.rglob(ext)):
            if f.name in ("README.md", "CHANGELOG.md", "ROADMAP.md"):
                continue
            files.append(f)
    return files


def chunk_text(text, max_chars=3000):
    paragraphs = text.strip().split("\n\n")
    chunks = []
    current = []
    current_len = 0
    for p in paragraphs:
        p = p.strip()
        if not p or p.startswith("# "):
            continue
        if current_len + len(p) > max_chars and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(p)
        current_len += len(p)
    if current:
        chunks.append("\n\n".join(current))
    return chunks if chunks else [text]


def call_llm(prompt, text, client, model="deepseek-chat"):
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096,
        )
        content = resp.choices[0].message.content.strip()
        data = json.loads(content)
        return data
    except Exception as e:
        print(f"  LLM 调用失败: {e}", file=sys.stderr)
        return {}


def extract_motifs(text, client, model):
    data = call_llm(MOTIF_PROMPT, text, client, model)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["motifs", "results", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def extract_style(text, client, model):
    data = call_llm(STYLE_PROMPT, text, client, model)
    if isinstance(data, dict) and "style_name" not in data and "name" in data:
        data["style_name"] = data.pop("name")
    return data


def main():
    import argparse

    parser = argparse.ArgumentParser(description="从 fiction 中识别母题与风格")
    parser.add_argument("fiction_dir", nargs="?",
                        default=os.path.join(os.path.dirname(__file__), "../../data/fiction"),
                        help="fiction 目录路径")
    parser.add_argument("--output", "-o", default="output", help="输出目录")
    parser.add_argument("--model", default="deepseek-chat", help="模型名")
    parser.add_argument("--mode", choices=["motif", "style", "both"], default="both")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = load_fiction_files(args.fiction_dir)
    print(f"找到 {len(files)} 个 fiction 文件\n")

    all_motifs = []
    all_styles = []
    seq = [0]

    for f in files:
        rel = f.relative_to(args.fiction_dir) if args.fiction_dir else f.name
        text = f.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        print(f"  {rel} ({len(chunks)} 块)...")

        file_motifs = []
        file_style = None

        for ci, chunk in enumerate(chunks):
            if args.mode in ("motif", "both"):
                motifs = extract_motifs(chunk, client, args.model)
                for m in motifs:
                    seq[0] += 1
                    m["id"] = f"m-{seq[0]:03d}"
                    m["source"] = str(rel)
                    m["chunk"] = ci + 1
                file_motifs.extend(motifs)
                print(f"    块 {ci+1}: {len(motifs)} 个母题")

            if args.mode in ("style", "both") and not file_style:
                style = extract_style(chunk, client, args.model)
                if style:
                    style["id"] = f"st-{seq[0]:03d}"
                    style["source"] = str(rel)
                    file_style = style
                    print(f"    风格: {style.get('style_name', '?')}")

        all_motifs.extend(file_motifs)
        if file_style:
            all_styles.append(file_style)
        print(f"  → 共 {len(file_motifs)} 个母题\n")

    if args.mode in ("motif", "both"):
        out = output_dir / "motifs.yaml"
        with open(out, "w", encoding="utf-8") as f:
            yaml.dump({"motifs": all_motifs}, f, allow_unicode=True, sort_keys=False)
        print(f"母题结果: {out} ({len(all_motifs)} 条)")

    if args.mode in ("style", "both"):
        out = output_dir / "styles.yaml"
        with open(out, "w", encoding="utf-8") as f:
            yaml.dump({"styles": all_styles}, f, allow_unicode=True, sort_keys=False)
        print(f"风格结果: {out} ({len(all_styles)} 条)")


if __name__ == "__main__":
    main()
