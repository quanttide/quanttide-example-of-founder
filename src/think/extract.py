#!/usr/bin/env python3
"""
认知提取 — 从 journal 中提取情境、意图、想法

情境：认知发生的容器（时间/地点/参与者/活动/情绪）
意图：行动导向（目标/动机/计划/承诺）
想法：认知产出（洞察/假设/问题/类比）
"""

import os
import sys
import json
import yaml
import subprocess
import re
from pathlib import Path
from datetime import datetime
from openai import OpenAI

EXTRACT_PROMPT = """从以下日记段落中提取结构化认知要素。

输出 JSON：
{{
  "situation": {{
    "time": {{"raw": "时间表述或null", "inferred_date": "推断日期或null"}},
    "location": "地点或null",
    "participants": ["参与者列表"],
    "activity": "活动概括（15字）",
    "mood": {{"raw": "情绪词或null", "valence": -3~3, "arousal": 0~5}}
  }},
  "intentions": [
    {{"type": "goal/motive/plan/commitment", "content": "意图原文"}}
  ],
  "ideas": [
    {{"type": "insight/hypothesis/question/analogy", "content": "想法原文"}}
  ]
}}

规则：
- situation 从原文推断，不编造
- intentions 只提取有行动导向的内容（想要/打算/决定/需要）
- ideas 只提取认知产出（发现/想到/怀疑/感觉）
- 如果某类不存在，输出空数组或null
- 纯 JSON。"""


def get_journal_text(repo_path, max_commits=200):
    result = subprocess.run(
        ["git", "-C", repo_path, "-c", "core.quotepath=false",
         "log", f"--max-count={max_commits}",
         "--name-only", "--format=%H"],
        capture_output=True, text=True
    )
    journal_files = set()
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if "/" in line and line.endswith(".md") and "journal" in line:
            journal_files.add(line)

    texts = {}
    for f in sorted(journal_files)[-10:]:
        r = subprocess.run(
            ["git", "-C", repo_path, "show", f"HEAD:{f}"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            texts[f] = r.stdout[:3000]
    return texts


def segment_text(text):
    segments = re.split(r"\n\s*\n", text.strip())
    result = []
    for s in segments:
        s = s.strip()
        if len(s) < 20 or len(s) > 500:
            continue
        if s.startswith("#"):
            continue
        result.append(s)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/memory"))
    parser.add_argument("--output", "-o", default="output")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    base_dir = Path(os.path.dirname(__file__))
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    if args.date:
        p = Path(args.memory_path) / "journal" / f"{args.date}.md"
        alt = Path(args.memory_path) / "journal" / args.date[:4] / f"{args.date}.md"
        texts = {}
        for path in [p, alt]:
            if path.exists():
                texts[str(path)] = path.read_text(encoding="utf-8")[:4000]
                break
        if not texts:
            print(f"未找到 {args.date}"); return
    else:
        texts = get_journal_text(args.memory_path)

    all_segments = []
    for fname, text in texts.items():
        segments = segment_text(text)
        for seg in segments:
            all_segments.append({"file": fname, "text": seg})

    print(f"分段: {len(all_segments)} 段")

    results = []
    total = len(all_segments)
    for idx, seg in enumerate(all_segments, 1):
        print(f"\r  处理中: {idx}/{total} ({idx*100//total}%)", end="", file=sys.stderr)
        r = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": seg["text"]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=1024,
        )
        data = json.loads(r.choices[0].message.content.strip())
        data["_source"] = seg["file"]
        data["_raw"] = seg["text"][:100]
        results.append(data)

    # 统计
    total_intentions = sum(len(r.get("intentions", [])) for r in results)
    total_ideas = sum(len(r.get("ideas", [])) for r in results)
    total_situations = sum(1 for r in results if r.get("situation"))

    print(f"\r  处理完成: {total}/{total} (100%)", file=sys.stderr)
    print(f"\n结果:")
    print(f"  有情境的段落: {total_situations}/{len(results)}")
    print(f"  意图总数: {total_intentions}")
    print(f"  想法总数: {total_ideas}")

    # 输出
    out = output_dir / "cognition.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump({"segments": results}, f, allow_unicode=True, sort_keys=False)
    print(f"  已保存: {out}")

    # 摘要展示
    print("\n意图清单:")
    for r in results:
        for intent in r.get("intentions", []):
            print(f"  [{intent.get('type','')}] {intent.get('content','')[:50]}")

    print("\n想法清单:")
    for r in results:
        for idea in r.get("ideas", []):
            print(f"  [{idea.get('type','')}] {idea.get('content','')[:50]}")


if __name__ == "__main__":
    main()
