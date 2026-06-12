#!/usr/bin/env python3
"""
健康跟踪 — 每周情绪数据持久化存储

从 git 提取本周情绪数据，追加到 HEALTH.csv。
支持趋势分析和可视化。
"""

import os
import sys
import json
import csv
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from openai import OpenAI

EXTRACT_PROMPT = """从以下文本中提取情绪状态。

输出 JSON：
{{
  "dominant_mood": "主导情绪",
  "valence": -3~3,
  "arousal": 0~5,
  "warning_signs": ["预警信号"]
}}
纯 JSON。"""

CSV_HEADER = [
    "week", "date",
    "diary_present", "diary_mood", "diary_valence", "diary_arousal",
    "fiction_present", "fiction_mood", "fiction_valence", "fiction_arousal",
    "gap", "warning_signals",
]


def get_week_content(repo_path, days=7):
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    result = subprocess.run(
        ["git", "-C", repo_path, "-c", "core.quotepath=false",
         "log", f"--since={since}", "--max-count=50",
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description="每周情绪数据持久化")
    parser.add_argument("--memory-path", default=None)
    parser.add_argument("--fiction-path", default=None)
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--show", action="store_true", help="显示历史数据")
    args = parser.parse_args()

    base_dir = Path(os.path.dirname(__file__))
    memory_path = Path(args.memory_path) if args.memory_path else \
        base_dir / "../../../../docs/memory"
    fiction_path = Path(args.fiction_path) if args.fiction_path else \
        base_dir / "../../../../docs/fiction"

    csv_path = base_dir / "HEALTH.csv"

    # 显示模式
    if args.show:
        if not csv_path.exists():
            print("暂无数据")
            return
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"共 {len(rows)} 周记录\n")
        print(f"{'周':<8} {'日期':<12} {'日记':<8} {'小说':<8} {'差距':<6} {'信号'}")
        print("-" * 60)
        for r in rows[-10:]:
            gap = r.get("gap", "")
            signals = r.get("warning_signals", "")[:20]
            print(f"{r['week']:<8} {r['date']:<12} {r['diary_valence']:<8} {r['fiction_valence']:<8} {gap:<6} {signals}")
        # 趋势
        vals = [float(r.get("diary_valence", 0)) for r in rows if r.get("diary_valence")]
        fic_vals = [float(r.get("fiction_valence", 0)) for r in rows if r.get("fiction_valence")]
        if len(vals) >= 2:
            print(f"\n日记均值: {sum(vals)/len(vals):.2f} (共 {len(vals)} 周)")
        if len(fic_vals) >= 2:
            print(f"小说均值: {sum(fic_vals)/len(fic_vals):.2f} (共 {len(fic_vals)} 周)")
        return

    # 记录模式
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    today = datetime.now()
    week_label = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    date_str = today.strftime("%Y-%m-%d")

    # 获取内容
    diary = get_week_content(memory_path)
    fiction = get_week_content(fiction_path)

    # 提取状态
    def extract(text):
        if not text:
            return {"dominant_mood": "", "valence": "", "arousal": "", "warning_signs": []}
        r = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": text[:4000]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=512,
        )
        return json.loads(r.choices[0].message.content.strip())

    d = extract(diary)
    f = extract(fiction)

    d_val = d.get("valence")
    f_val = f.get("valence")
    gap = (f_val - d_val) if isinstance(d_val, (int, float)) and isinstance(f_val, (int, float)) else ""

    row = {
        "week": week_label,
        "date": date_str,
        "diary_present": "1" if diary else "0",
        "diary_mood": d.get("dominant_mood", ""),
        "diary_valence": d_val if isinstance(d_val, (int, float)) else "",
        "diary_arousal": d.get("arousal", ""),
        "fiction_present": "1" if fiction else "0",
        "fiction_mood": f.get("dominant_mood", ""),
        "fiction_valence": f_val if isinstance(f_val, (int, float)) else "",
        "fiction_arousal": f.get("arousal", ""),
        "gap": gap,
        "warning_signals": "; ".join(f.get("warning_signals", []))[:100],
    }

    # 写入 CSV
    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    print(f"已记录 {week_label} → {csv_path}")
    print(f"  日记: {row['diary_mood']} ({row['diary_valence']})  小说: {row['fiction_mood']} ({row['fiction_valence']})  差距: {gap}")


if __name__ == "__main__":
    main()
