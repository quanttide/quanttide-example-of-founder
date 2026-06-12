#!/usr/bin/env python3
"""
待办提取 — 从原始日志中提炼待办、计划、承诺和决策

输入：journal 原始文本
输出：结构化待办列表
"""

import os
import sys
import json
import yaml
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from openai import OpenAI

EXTRACT_PROMPT = """你是一名执行意图提取助手。从以下日记文本中识别所有**待办事项**。

待办类型：
- plan: 明确计划要做的事（"明天打算…"、"准备…"）
- intent: 意图/想法（"需要…"、"应该…"、"想要…"）
- decision: 已做的决定（"决定…"、"不…了"）
- risk: 风险/担忧（"担心…"、"怕…"）
- question: 待决策问题（"要不要…"、"怎么…"）

输出 JSON 数组，每条：
{{
  "type": "plan/intent/decision/question",
  "raw": "原文完整句子（逐字摘录，不改写）",
  "status": "pending/in_progress/done/cancelled"
}}

规则：
- raw 必须是原文中连续出现的句子，不能概括、不能压缩、不能改写
- 只提取有明确执行含义的内容，忽略纯反思和情绪描述
- 纯 JSON 输出。"""


def get_journal_text(repo_path, max_commits=200):
    """从 git 最近提交中获取 journal 文件"""
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="从 journal 提取待办")
    parser.add_argument("--memory-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/memory"))
    parser.add_argument("--output", "-o", default="output")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--date", default=None, help="指定日期文件 (YYYY-MM-DD)")
    args = parser.parse_args()

    base_dir = Path(os.path.dirname(__file__))
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")

    print("获取 journal 内容...")
    if args.date:
        # 读取指定日期的 journal 文件
        repo_path = Path(args.memory_path)
        journal_path = repo_path / "journal" / args.date[:4] / f"{args.date}.md"
        alt_path = repo_path / "journal" / f"{args.date}.md"
        for p in [journal_path, alt_path]:
            if p.exists():
                texts = {str(p): p.read_text(encoding="utf-8")[:4000]}
                print(f"  文件: {p}")
                break
        else:
            print(f"  未找到 {args.date} 的 journal 文件")
            texts = {}
    else:
        texts = get_journal_text(args.memory_path)

    if not texts:
        print("无内容"); return

    all_items = []
    for fname, text in texts.items():
        print(f"\n分析: {fname} ({len(text)} 字符)")
        r = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=2048,
        )
        items = json.loads(r.choices[0].message.content.strip())
        if isinstance(items, dict):
            for key in ["items", "todos", "results"]:
                if key in items and isinstance(items[key], list):
                    items = items[key]
                    break
            else:
                items = [items]

        for item in items:
            item["source"] = fname
        all_items.extend(items)

        type_count = defaultdict(int)
        for item in items:
            type_count[item.get("type", "?")] += 1
        print(f"  提取 {len(items)} 条: {dict(type_count)}")

    # 生成 TODO.md（增量模式：保留已有标记，只追加新条目）
    todo_path = base_dir / "TODO.md"
    existing_items = set()

    # 读取已有 TODO.md，保留已完成的标记
    if todo_path.exists():
        with open(todo_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 提取已有条目文本
                if line.startswith("- [x] ") or line.startswith("- [ ] "):
                    existing_items.add(line[6:].strip())

    # 只追加尚未存在的条目
    new_lines = []
    new_count = 0
    for item in all_items:
        raw = item.get("raw", "").strip()
        if not raw:
            continue
        if raw in existing_items:
            continue
        status = item.get("status", "pending")
        prefix = "- [x] " if status == "done" else "- [ ] "
        new_lines.append(f"{prefix}{raw}\n")
        new_count += 1

    if new_lines:
        # 读现有内容，追加新条目
        if todo_path.exists():
            with open(todo_path, encoding="utf-8") as f:
                content = f.read()
            # 在文件末尾追加
            with open(todo_path, "a", encoding="utf-8") as f:
                f.write(f"\n## 新增 ({date_str})\n")
                f.writelines(new_lines)
        else:
            lines = ["# TODO\n", f"> 首次生成 ({date_str})\n"]
            for t_label, t_type in [("Pod", "pending"), ("进行中", "in_progress"), ("已完成", "done")]:
                items = [x for x in all_items if x.get("status") == t_type and x.get("raw", "").strip()]
                if not items:
                    continue
                lines.append(f"\n## {t_label}\n")
                for item in items:
                    raw = item.get("raw", "").strip()
                    prefix = "- [x] " if t_type == "done" else "- [ ] "
                    lines.append(f"{prefix}{raw}\n")
            with open(todo_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
    else:
        print("  无新条目")

    print(f"已更新: {todo_path}")
    print(f"  新增: {new_count} 条")
    # 统计
    with open(todo_path, encoding="utf-8") as f:
        content = f.read()
    pending = content.count("- [ ] ")
    done = content.count("- [x] ")
    print(f"  待办: {pending} 条  已完成: {done} 条")


if __name__ == "__main__":
    main()
