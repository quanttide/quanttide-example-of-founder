#!/usr/bin/env python3
"""
待办提取 — 先切段，逐段判断是否包含待办

输入：journal 原始文本
输出：TODO.md（增量更新）
"""

import os
import sys
import json
import subprocess
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from openai import OpenAI

SEGMENT_PROMPT = """判断以下段落是否包含明确的待办事项。

规则：
- plan: 有执行动词（打算/准备/要……），有明确结果
- decision: 已做决定（决定/不……了/改成/用……替代）
- 以下情况不是待办：纯反思、观察判断、模糊想法、条件句、疑问句

输出 JSON：
{{"has_todo": true/false, "type": "plan/decision/null", "raw": "原文完整句子", "status": "pending/in_progress/done"}}
如果 has_todo 为 false，type 为 null。纯 JSON。"""


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
    for f in sorted(journal_files)[-5:]:
        r = subprocess.run(
            ["git", "-C", repo_path, "show", f"HEAD:{f}"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            texts[f] = r.stdout[:4000]
    return texts


def segment_text(text):
    """按空行切段，过滤太短（<15字）和太长（>500字）的段"""
    segments = re.split(r"\n\s*\n", text.strip())
    result = []
    for s in segments:
        s = s.strip()
        if len(s) < 15 or len(s) > 500:
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
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    base_dir = Path(os.path.dirname(__file__))
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    date_str = datetime.now().strftime("%Y-%m-%d")

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

    print(f"日记文件: {len(texts)} 个")

    all_todos = []
    for fname, text in texts.items():
        segments = segment_text(text)
        print(f"\n  {fname}: {len(segments)} 段")
        for si, seg in enumerate(segments):
            r = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": SEGMENT_PROMPT},
                    {"role": "user", "content": seg},
                ],
                response_format={"type": "json_object"},
                temperature=0.1, max_tokens=256,
            )
            result = json.loads(r.choices[0].message.content.strip())
            if result.get("has_todo") and result.get("type"):
                raw = result.get("raw", "").strip()
                if raw:
                    all_todos.append({
                        "type": result["type"],
                        "raw": raw,
                        "status": result.get("status", "pending"),
                    })
                    print(f"    ✓ [{result['type']}] {raw[:40]}")

    # 生成 TODO.md（增量）
    todo_path = base_dir / "TODO.md"
    existing = set()
    if todo_path.exists():
        with open(todo_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- [x] ") or line.startswith("- [ ] "):
                    existing.add(line[6:].strip())

    new_items = [t for t in all_todos if t["raw"] not in existing]
    if not new_items:
        print("\n无新条目"); return

    sections = {"进行中": [], "待办": [], "已完成": []}
    for t in new_items:
        if t["status"] == "in_progress":
            sections["进行中"].append(t["raw"])
        elif t["status"] == "done":
            sections["已完成"].append(t["raw"])
        else:
            sections["待办"].append(t["raw"])

    with open(todo_path, "a" if todo_path.exists() else "w", encoding="utf-8") as f:
        if not todo_path.exists():
            f.write("# TODO\n\n")
        f.write(f"## {date_str}\n\n")
        for label, items in sections.items():
            if items:
                for raw in items:
                    prefix = "- [x] " if label == "已完成" else "- [ ] "
                    f.write(f"{prefix}{raw}\n")
                f.write("\n")

    print(f"\n已更新: {todo_path}")
    total_todos = sum(len(v) for v in sections.values())
    print(f"  新增: {total_todos} 条")
    with open(todo_path, encoding="utf-8") as f:
        c = f.read()
    print(f"  总计: 待办 {c.count('- [ ] ')} 条  已完成 {c.count('- [x] ')} 条")


if __name__ == "__main__":
    main()
