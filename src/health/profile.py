#!/usr/bin/env python3
"""
情绪基线 — 分析个人情绪模式，生成可对照的基线

从 git 历史中提取情绪分布，计算：
1. 平均愉悦度、情绪波动幅度
2. 常见情绪需求类型
3. 补偿模式（现实差时写什么）
4. 预警阈值（什么情况下需要干预）
"""

import os
import sys
import json
import yaml
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from openai import OpenAI

EXTRACT_PROMPT = """从以下文本中提取情绪特征。

输出 JSON：
{{
  "dominant_mood": "主导情绪",
  "valence": -3~3,
  "arousal": 0~5,
  "emotional_needs": ["需求列表"]
}}
纯 JSON。"""


def get_daily_content(repo_path, max_commits=500):
    result = subprocess.run(
        ["git", "-C", repo_path, "-c", "core.quotepath=false",
         "log", f"--max-count={max_commits}",
         "--format=%H|%ai|%s", "--name-only"],
        capture_output=True, text=True
    )
    days = defaultdict(list)
    current = None
    for line in result.stdout.strip().split("\n"):
        if "|" in line and len(line.split("|")[0]) == 40:
            if current:
                days[current["date"][:10]].append(current)
            parts = line.split("|", 2)
            current = {"hash": parts[0], "date": parts[1], "files": []}
        elif current and line.strip():
            current["files"].append(line.strip())
    if current:
        days[current["date"][:10]].append(current)

    daily = {}
    for date, commits in sorted(days.items()):
        texts = []
        for c in commits[:3]:
            for f in c["files"][:3]:
                r = subprocess.run(
                    ["git", "-C", repo_path, "show", f"{c['hash']}:{f}"],
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0 and r.stdout.strip():
                    texts.append(r.stdout[:2000])
                    break
        if texts:
            daily[date] = "\n\n".join(texts)
    return daily


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成个人情绪基线")
    parser.add_argument("--memory-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/memory"))
    parser.add_argument("--fiction-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/fiction"))
    parser.add_argument("--output", "-o", default="output")
    parser.add_argument("--model", default="deepseek-chat")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("获取历史数据...")
    mem = get_daily_content(args.memory_path)
    fic = get_daily_content(args.fiction_path)
    print(f"  日记: {len(mem)} 天, 小说: {len(fic)} 天")

    # 采样（避免 API 调用过多）
    mem_sample = list(mem.items())[:20]
    fic_sample = list(fic.items())[:20]

    print("\n分析情绪分布...")
    diary_vals = []
    fiction_vals = []
    diary_needs = Counter()
    fiction_needs = Counter()

    for date, text in mem_sample:
        r = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": text[:3000]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=512,
        )
        state = json.loads(r.choices[0].message.content.strip())
        v = state.get("valence")
        if v is not None:
            diary_vals.append(v)
        for n in state.get("emotional_needs", []):
            diary_needs[n] += 1
        print(f"  日记{date}: valence={v}")

    for date, text in fic_sample:
        r = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": text[:3000]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=512,
        )
        state = json.loads(r.choices[0].message.content.strip())
        v = state.get("valence")
        if v is not None:
            fiction_vals.append(v)
        for n in state.get("emotional_needs", []):
            fiction_needs[n] += 1
        print(f"  小说{date}: valence={v}")

    # 统计
    if diary_vals:
        d_avg = sum(diary_vals) / len(diary_vals)
        d_std = (sum((v - d_avg)**2 for v in diary_vals) / len(diary_vals))**0.5
    else:
        d_avg, d_std = 0, 0

    if fiction_vals:
        f_avg = sum(fiction_vals) / len(fiction_vals)
    else:
        f_avg = 0

    typical_gap = f_avg - d_avg

    profile = {
        "baseline": {
            "diary_avg_valence": round(d_avg, 2),
            "diary_volatility": round(d_std, 2),
            "fiction_avg_valence": round(f_avg, 2),
            "typical_gap": round(typical_gap, 2),
            "sample_size": {"diary": len(diary_vals), "fiction": len(fiction_vals)},
        },
        "common_needs": {
            "diary": [{"need": k, "count": v} for k, v in diary_needs.most_common(5)],
            "fiction": [{"need": k, "count": v} for k, v in fiction_needs.most_common(5)],
        },
        "thresholds": {
            "warning_if_valence_below": round(d_avg - d_std, 2) if d_std else -2,
            "warning_if_gap_negative": "小说愉悦度低于日记时需关注",
            "warning_if_no_fiction": "连续 7 天无小说创作时需关注",
        },
    }

    out = output_dir / "profile.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, allow_unicode=True, sort_keys=False)
    print(f"\n基线已生成: {out}")
    print(f"  日记平均愉悦度: {d_avg:.2f} (波动 {d_std:.2f})")
    print(f"  小说平均愉悦度: {f_avg:.2f}")
    print(f"  典型补偿差距: {typical_gap:+.2f}")
    print(f"  预警阈值: 愉悦度低于 {d_avg - d_std:.2f}")


if __name__ == "__main__":
    main()
