#!/usr/bin/env python3
"""
健康检查 — 每周情绪状态与创作健康度

从 journal 和 fiction 的最新内容提取情绪状态，检测：
1. 本周主导情绪
2. 情绪赤字（理想与现实的差距）
3. 补偿是否足够（小说是否在补现实）
4. 预警信号（连续负面、补偿不足）
"""

import os
import sys
import json
import yaml
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from openai import OpenAI

EXTRACT_PROMPT = """从以下文本中提取情绪状态。

输出 JSON：
{{
  "dominant_mood": "主导情绪",
  "valence": -3~3,
  "arousal": 0~5,
  "emotional_needs": ["需要的情绪需求列表"],
  "warning_signs": ["预警信号，如持续焦虑、孤独感加重等"]
}}
纯 JSON。"""

CHECK_PROMPT = """以下是本周的情绪检查数据：

日记（现实）：
{diary_summary}

小说（创作）：
{fiction_summary}

参考基线：
- 你的平均愉悦度基线: {baseline_valence}
- 小说通常比日记高: {typical_gap} 点

请评估：
1. 本周情绪健康度（与基线比）
2. 小说是否在发挥补偿作用
3. 是否存在预警信号
4. 给出一条建议

输出 JSON：
{{
  "health_score": 0-10,
  "status": "良好/一般/需关注/预警",
  "compensation_active": true/false,
  "signals": [],
  "advice": "一条建议"
}}
纯 JSON。"""


def get_latest_content(repo_path, days=7, max_commits=100):
    """获取最近 N 天的日记或小说内容"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    result = subprocess.run(
        ["git", "-C", repo_path, "-c", "core.quotepath=false",
         "log", f"--since={since}", f"--max-count={max_commits}",
         "--format=%H|%ai|%s", "--name-only"],
        capture_output=True, text=True
    )
    texts = []
    current = None
    for line in result.stdout.strip().split("\n"):
        if "|" in line and len(line.split("|")[0]) == 40:
            if current:
                for f in current["files"][:2]:
                    r = subprocess.run(
                        ["git", "-C", repo_path, "show", f"{current['hash']}:{f}"],
                        capture_output=True, text=True, timeout=5
                    )
                    if r.returncode == 0 and r.stdout.strip():
                        texts.append(f"[{current['date'][:10]}] {r.stdout[:2000]}")
                        break
            parts = line.split("|", 2)
            current = {"hash": parts[0], "date": parts[1], "files": []}
        elif current and line.strip():
            current["files"].append(line.strip())
    if current:
        for f in current["files"][:2]:
            r = subprocess.run(
                ["git", "-C", repo_path, "show", f"{current['hash']}:{f}"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and r.stdout.strip():
                texts.append(f"[{current['date'][:10]}] {r.stdout[:2000]}")
                break
    return "\n\n".join(texts[:5])


def get_baseline():
    """从已有数据获取基线（简化版：使用预设值"""
    return {"valence": 0.5, "typical_gap": 1.3}


def get_cli_args():
    import argparse
    parser = argparse.ArgumentParser(description="每周情绪健康检查")
    parser.add_argument("--memory-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/memory"))
    parser.add_argument("--fiction-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/fiction"))
    parser.add_argument("--days", type=int, default=7,
                        help="检查最近几天的数据")
    parser.add_argument("--model", default="deepseek-chat")
    return parser.parse_args()


def main():
    args = get_cli_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    print(f"获取最近 {args.days} 天的内容...")
    diary = get_latest_content(args.memory_path, args.days)
    fiction = get_latest_content(args.fiction_path, args.days)

    if not diary:
        print("  日记: 无数据")
    else:
        print(f"  日记: {len(diary)} 字符")

    if not fiction:
        print("  小说: 无数据")
    else:
        print(f"  小说: {len(fiction)} 字符")

    if not diary and not fiction:
        print(f"\n最近 {args.days} 天内无数据。")
        return

    # 提取情绪
    if diary:
        diary_r = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": diary[:4000]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=1024,
        )
        diary_state = json.loads(diary_r.choices[0].message.content.strip())
    else:
        diary_state = {"dominant_mood": "无数据", "valence": 0, "arousal": 0, "emotional_needs": [], "warning_signs": []}

    if fiction:
        fic_r = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": fiction[:4000]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=1024,
        )
        fiction_state = json.loads(fic_r.choices[0].message.content.strip())
    else:
        fiction_state = {"dominant_mood": "无数据", "valence": 0, "arousal": 0, "emotional_needs": [], "warning_signs": []}

    # 展示结果
    print(f"\n=== 本周情绪状态 ===")
    d_val = diary_state.get("valence", 0)
    f_val = fiction_state.get("valence", 0)
    gap = f_val - d_val
    print(f"现实情绪（日记）: {diary_state.get('dominant_mood', '?')} (愉悦度 {d_val})")
    print(f"创作情绪（小说）: {fiction_state.get('dominant_mood', '?')} (愉悦度 {f_val})")
    print(f"补偿差距: {gap:+.1f}")

    baseline = get_baseline()
    inp = {
        "diary_summary": json.dumps(diary_state, ensure_ascii=False),
        "fiction_summary": json.dumps(fiction_state, ensure_ascii=False),
        "baseline_valence": baseline["valence"],
        "typical_gap": baseline["typical_gap"],
    }
    check = client.chat.completions.create(
        model=args.model,
        messages=[
            {"role": "system", "content": CHECK_PROMPT.format(**inp)},
            {"role": "user", "content": f"本周: 日记={d_val} 小说={f_val} 差距={gap}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.1, max_tokens=1024,
    )
    result = json.loads(check.choices[0].message.content.strip())

    print(f"\n健康评分: {result.get('health_score', '?')}/10")
    print(f"状态: {result.get('status', '?')}")
    print(f"补偿运行中: {result.get('compensation_active', '?')}")
    if result.get("signals"):
        print(f"信号: {result['signals']}")
    print(f"建议: {result.get('advice', '')}")


if __name__ == "__main__":
    main()
