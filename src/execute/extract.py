#!/usr/bin/env python3
"""
TODO 生成 — 从 think 模块提取的意图中筛选可执行条目并建议分解

工作流：
1. python3 src/think/extract.py
2. python3 src/execute/extract.py
"""

import os
import sys
import json
import yaml
from pathlib import Path
from datetime import datetime
from openai import OpenAI

JUDGE_PROMPT = """判断以下意图是否是**可执行的TODO**。

规则：
- 可执行：有明确动词+具体对象，知道第一步做什么
- 模糊方向：有方向但缺具体动作或对象
- 不可执行：纯意图/战略/价值观/元认知

输出 JSON：
{{
  "verdict": "可执行/模糊方向/不可执行",
  "first_step": "如果是可执行，建议的第一步（15字）",
  "reason": "判断理由（10字）"
}}
纯 JSON。"""


def load_cognition(think_dir):
    path = think_dir / "cognition.yaml"
    if not path.exists():
        print(f"请先运行 think/extract.py 生成 {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    items = []
    for seg in data.get("segments", []):
        for intent in seg.get("intentions", []):
            content = intent.get("content", "").strip()
            if content and intent.get("type") in ("plan", "commitment"):
                items.append(content)
    return list(dict.fromkeys(items))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--think-output", default=None)
    parser.add_argument("--model", default="deepseek-chat")
    args = parser.parse_args()

    base_dir = Path(os.path.dirname(__file__))
    think_dir = Path(args.think_output) if args.think_output else \
        base_dir / "../think/output"

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    plans = load_cognition(think_dir)
    print(f"plan/commitment 总数: {len(plans)}")

    # LLM 判断每条的可执行性
    ready = []
    fuzzy = []
    skip = []

    for p in plans:
        r = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": p},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=256,
        )
        result = json.loads(r.choices[0].message.content.strip())
        verdict = result.get("verdict", "不可执行")
        step = result.get("first_step", "")
        if verdict == "可执行":
            ready.append((p, step))
        elif verdict == "模糊方向":
            fuzzy.append((p, step))
        else:
            skip.append(p)

    print(f"  可执行: {len(ready)}")
    print(f"  模糊方向: {len(fuzzy)}")
    print(f"  不可执行: {len(skip)}")

    # 生成 TODO.md
    todo_path = base_dir / "TODO.md"
    date_str = datetime.now().strftime("%Y-%m-%d")

    existing = set()
    if todo_path.exists():
        with open(todo_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- [x] ") or line.startswith("- [ ] "):
                    existing.add(line[6:].strip())

    new_count = 0
    with open(todo_path, "a" if todo_path.exists() else "w", encoding="utf-8") as f:
        if not todo_path.exists():
            f.write("# TODO\n\n")

        sections = [("可执行", ready), ("需分解", fuzzy)]
        has_new = False
        for label, items in sections:
            new_items = [t for t in items if t[0] not in existing]
            if not new_items:
                continue
            if not has_new:
                f.write(f"## {date_str}\n\n")
                has_new = True
            f.write(f"### {label}\n\n")
            for text, step in new_items:
                f.write(f"- [ ] {text}\n")
                if step:
                    f.write(f"  第一步：{step}\n")
            f.write("\n")
            new_count += len(new_items)

    # 展示结果
    print(f"\n=== 可执行 ===")
    for text, step in ready:
        print(f"  [ ] {text}")
        if step:
            print(f"       → {step}")

    print(f"\n=== 需分解 ===")
    for text, step in fuzzy:
        print(f"  [ ] {text}")
        if step:
            print(f"       → {step}")

    print(f"\n=== 不可执行（已跳过）===")
    for text in skip:
        print(f"  {text[:40]}")

    print(f"\n已更新: {todo_path}")
    print(f"  新增: {new_count} 条")


if __name__ == "__main__":
    main()
