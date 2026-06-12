#!/usr/bin/env python3
"""
TODO 生成 — 从 think 提取的认知要素中筛选可执行条目，利用情境判断领域

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
from collections import defaultdict
from openai import OpenAI

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


def load_cognition(think_dir):
    path = think_dir / "cognition.yaml"
    if not path.exists():
        print(f"请先运行 think/extract.py 生成 {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("segments", [])


def extract_plans(segments):
    """从认知数据中提取 plan/commitment，保留情境上下文"""
    items = []
    seen = set()
    for seg in segments:
        situation = seg.get("situation", {})
        activity = (situation.get("activity") or "") if situation else ""
        source = seg.get("_source", "")
        raw = seg.get("_raw", "")[:200]

        for intent in seg.get("intentions", []):
            content = intent.get("content", "").strip()
            if not content or intent.get("type") not in ("plan", "commitment"):
                continue
            if content in seen:
                continue
            seen.add(content)
            items.append({
                "content": content,
                "activity": activity,
                "source": source,
                "raw": raw,
            })
    return items


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--think-output", default=None)
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--consume", action="store_true", help="通过 MQ 消费 cognition.ready")
    args = parser.parse_args()

    base_dir = Path(os.path.dirname(__file__))
    think_dir = Path(args.think_output) if args.think_output else \
        base_dir / "../think/output"

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    if args.consume:
        sys.path.insert(0, str(base_dir.parent))
        from meta.meta import connect

        def on_message(ch, method, properties, body):
            msg = json.loads(body.decode())
            segments = msg.get("segments", [])
            plans = extract_plans(segments)
            ready = []
            for p in plans:
                prompt = JUDGE_PROMPT.format(situation=p["activity"], intent=p["content"])
                r = client.chat.completions.create(
                    model=args.model,
                    messages=[{"role": "system", "content": prompt}, {"role": "user", "content": p["content"]}],
                    response_format={"type": "json_object"}, temperature=0.1, max_tokens=256,
                )
                result = json.loads(r.choices[0].message.content.strip())
                if result.get("verdict") == "可执行":
                    ready.append((p["content"], result.get("first_step", "")))
            if ready:
                print(f"  可执行: {len(ready)} 条")
                for text, step in ready:
                    print(f"    [ ] {text} → {step}")
            else:
                print("  无可执行计划")
            ch.basic_ack(delivery_tag=method.delivery_tag)

        conn = connect()
        ch = conn.channel()
        ch.queue_declare(queue="cognition.ready", durable=True)
        ch.basic_consume(queue="cognition.ready", on_message_callback=on_message)
        print("监听 cognition.ready (Ctrl+C 退出)", file=sys.stderr)
        try:
            ch.start_consuming()
        except KeyboardInterrupt:
            conn.close()
        return

    segments = load_cognition(think_dir)
    plans = extract_plans(segments)
    print(f"plan/commitment 总数: {len(plans)}")

    ready = []
    skip = []

    total_plans = len(plans)
    for pi, p in enumerate(plans, 1):
        print(f"\r  判断中: {pi}/{total_plans} ({pi*100//total_plans}%)", end="", file=sys.stderr)
        prompt = JUDGE_PROMPT.format(situation=p["activity"], intent=p["content"])
        r = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"意图：{p['content']}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=256,
        )
        result = json.loads(r.choices[0].message.content.strip())
        verdict = result.get("verdict", "不可执行")
        step = result.get("first_step", "")
        domain = result.get("domain", "其他")

        if verdict == "可执行":
            ready.append((p["content"], step))
        else:
            skip.append(p["content"])

    print(f"  可执行: {len(ready)}")

    # 生成 TODO.md（只输出可执行条目）
    todo_path = base_dir / "TODO.md"
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

    print(f"\n=== 可执行 ===")
    for text, step in ready:
        print(f"  [ ] {text}  → {step}")

    print(f"\n已更新: {todo_path}")
    print(f"  新增: {new_count} 条")


if __name__ == "__main__":
    main()
