#!/usr/bin/env python3
"""
日记变更监听 — journal 提交后自动触发轻量处理

检测新日志 → 单篇 think → 健康检查 → 增量 execute
"""

import os
import sys
import json
import subprocess
import hashlib
import time
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
规则：situation 从原文推断；intentions 只提取有行动导向的内容；ideas 只提取认知产出。
纯 JSON。"""

MOOD_PROMPT = """从以下日记内容判断情绪状态。

输出 JSON：
{{
  "mood": "主导情绪",
  "valence": -3~3,
  "arousal": 0~5,
  "needs": ["情绪需求"],
  "summary": "一句话概括"
}}
纯 JSON。"""


def get_last_processed(repo_path):
    """获取最后处理的 journal 文件 hash"""
    marker = Path(os.path.dirname(__file__)) / ".last_journal"
    if marker.exists():
        return marker.read_text().strip()
    return ""


def save_last_processed(hash_val):
    marker = Path(os.path.dirname(__file__)) / ".last_journal"
    marker.write_text(hash_val)


def get_latest_journal(repo_path):
    """获取最新的 journal 文件 hash 和内容"""
    result = subprocess.run(
        ["git", "-C", repo_path, "-c", "core.quotepath=false",
         "log", "--max-count=20", "--name-only", "--format=%H"],
        capture_output=True, text=True
    )
    journal_files = []
    current_hash = None
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if len(line) == 40:
            current_hash = line
        elif line.endswith(".md") and "journal" in line and current_hash:
            journal_files.append((current_hash, line))

    if not journal_files:
        return None, None

    latest_hash, latest_file = journal_files[0]
    content = subprocess.run(
        ["git", "-C", repo_path, "show", f"HEAD:{latest_file}"],
        capture_output=True, text=True, timeout=5
    )
    if content.returncode != 0 or not content.stdout.strip():
        return None, None

    return latest_hash, content.stdout[:3000]


def process_journal(text, model="deepseek-chat"):
    """处理单篇 journal，返回提取结果和情绪状态"""
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )

    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0.1, max_tokens=1024,
    )
    cognition = json.loads(r.choices[0].message.content.strip())

    r2 = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": MOOD_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0.1, max_tokens=256,
    )
    mood = json.loads(r2.choices[0].message.content.strip())

    return cognition, mood


def check_threshold(mood):
    """检查情绪是否触及预警阈值"""
    valence = mood.get("valence", 0)
    needs = mood.get("needs", [])
    signals = []

    if valence < 0:
        signals.append(f"愉悦度偏低 ({valence})")
    if valence < -2:
        signals.append("⚠ 愉悦度低于预警阈值")
    if "孤独" in str(needs) or "焦虑" in str(needs):
        signals.append(f"检测到需求: {needs}")

    return signals


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/memory"))
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--loop", action="store_true", help="持续监听")
    parser.add_argument("--interval", type=int, default=60, help="检测间隔（秒）")
    parser.add_argument("--once", action="store_true", help="单次检测后退出")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)

    def check_once():
        repo_path = args.memory_path
        last = get_last_processed(repo_path)
        latest_hash, content = get_latest_journal(repo_path)

        if not latest_hash or not content:
            print("未找到 journal 文件")
            return

        if latest_hash == last:
            if args.once or not args.loop:
                print("无新日志")
            return

        print(f"检测到新日志: {latest_hash[:8]}")
        save_last_processed(latest_hash)

        cognition, mood = process_journal(content, args.model)

        mood_text = f"{mood.get('mood','?')} (愉悦度 {mood.get('valence',0)})"
        needs = mood.get("needs", [])
        signals = check_threshold(mood)

        print(f"\n情绪: {mood_text}")
        if needs:
            print(f"需求: {needs}")
        if signals:
            print("信号:")
            for s in signals:
                print(f"  {s}")

        intentions = cognition.get("intentions", [])
        ideas = cognition.get("ideas", [])
        plans = [i.get("content","") for i in intentions if i.get("type") in ("plan","commitment")]
        if plans:
            print(f"\n新计划 ({len(plans)} 条):")
            for p in plans[:5]:
                print(f"  [ ] {p}")
            if len(plans) > 5:
                print(f"  ...及其他 {len(plans)-5} 条")
        else:
            print("\n无可执行计划")

    if args.once:
        check_once()
        return

    if args.loop:
        print(f"持续监听中 (每 {args.interval} 秒)...")
        while True:
            check_once()
            time.sleep(args.interval)
    else:
        check_once()


if __name__ == "__main__":
    main()
