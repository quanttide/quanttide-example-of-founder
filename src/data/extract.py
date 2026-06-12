#!/usr/bin/env python3
"""
标注确认 — 从 cognition.yaml 生成可编辑标记文件，支持双向同步

用法:
  python3 extract.py           # 生成 ANNOTATION.md
  python3 extract.py --apply   # 读取标记变更，输出确认结果
"""

import os
import sys
import re
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict

MARKERS = {"[ ]", "[x]", "[-]", "[?]", "[~]"}


def load_cognition(think_dir):
    path = think_dir / "cognition.yaml"
    if not path.exists():
        print(f"请先运行 think/extract.py")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate(segments, out_path, date_str):
    """生成带标记的标注文件"""
    all_intents = []
    all_ideas = []

    for seg in segments:
        for item in seg.get("intentions", []):
            content = item.get("content", "").strip()
            if content:
                all_intents.append(content)
        for item in seg.get("ideas", []):
            content = item.get("content", "").strip()
            if content:
                all_ideas.append(content)

    # 去重
    intents = list(dict.fromkeys(all_intents))
    ideas = list(dict.fromkeys(all_ideas))

    lines = [f"# 标注确认 — {date_str}\n"]
    lines.append(f"标记说明：`[ ]`待确认 `[x]`已采纳 `[-]`已废弃 `[?]`待决策 `[~]`已修改\n\n")

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

    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"已生成: {out_path}")
    print(f"  意图: {len(intents)} 条")
    print(f"  想法: {len(ideas)} 条")
    print(f"\n编辑标记后运行: python3 extract.py --apply")


def apply(out_path):
    """读取标记变更，输出确认结果"""
    if not out_path.exists():
        print(f"未找到 {out_path}，请先生成")
        return

    with open(out_path, encoding="utf-8") as f:
        content = f.read()

    adopted = []    # [x]
    discarded = []  # [-]
    pending_q = []  # [?]
    modified = []   # [~]
    untouched = []  # [ ]

    for line in content.split("\n"):
        line_stripped = line.strip()
        # 检测行级标记
        for marker in MARKERS:
            if line_stripped.startswith(marker):
                text = line_stripped[len(marker):].strip()
                if text:
                    if marker == "[x]":
                        adopted.append(text)
                    elif marker == "[-]":
                        discarded.append(text)
                    elif marker == "[?]":
                        pending_q.append(text)
                    elif marker == "[~]":
                        modified.append(text)
                    elif marker == "[ ]":
                        untouched.append(text)
                break

    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "summary": {
            "total": len(adopted) + len(discarded) + len(pending_q) + len(modified) + len(untouched),
            "adopted": len(adopted),
            "discarded": len(discarded),
            "pending": len(pending_q),
            "modified": len(modified),
            "untouched": len(untouched),
        },
        "adopted": adopted,
        "discarded": discarded,
        "pending": pending_q,
        "modified": modified,
    }

    out = out_path.parent / "confirmed.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, sort_keys=False)

    print(f"确认结果: {out}")
    s = result["summary"]
    print(f"  总计: {s['total']} 条")
    print(f"  ✅ 已采纳: {s['adopted']}")
    print(f"  ❌ 已废弃: {s['discarded']}")
    print(f"  ❓ 待决策: {s['pending']}")
    print(f"  ✏️ 已修改: {s['modified']}")
    print(f"  ⬜ 未处理: {s['untouched']}")

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--think-output", default=None)
    parser.add_argument("--apply", action="store_true", help="读取标记变更")
    args = parser.parse_args()

    base_dir = Path(os.path.dirname(__file__))
    think_dir = Path(args.think_output) if args.think_output else \
        base_dir / "../think/output"
    anno_path = base_dir / "ANNOTATION.md"

    if args.apply:
        apply(anno_path)
        return

    segments = load_cognition(think_dir).get("segments", [])
    date_str = datetime.now().strftime("%Y-%m-%d")
    generate(segments, anno_path, date_str)


if __name__ == "__main__":
    main()
