#!/usr/bin/env python3
"""
实验: 差距分析 — 量化理想情绪与现实情绪的差距

理想水平 = 小说中表达的情感世界（想要什么）
现实水平 = 日记中记录的情绪状态（发生了什么）
差距 = 理想 - 现实
叙事的作用 = 小说是否在缩小这个差距？
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

EMOTION_PROMPT = """从以下文本中提取所有出现的**情绪词**，按类型归类。

输出 JSON：
{{
  "positive_emotions": [{{"word": "情绪词", "intensity": 0-1, "context": "出现语境（10字）"}}],
  "negative_emotions": [{{"word": "情绪词", "intensity": 0-1, "context": "出现语境（10字）"}}],
  "valence": -3到3（整体愉悦度）,
  "arousal": 0-5（整体激活度）,
  "dominant_mood": "主导情绪标签"
}}
纯 JSON。"""

GAP_PROMPT = """以下是一周内创始人的日记和小说数据：

=== 第 {week} 周 ===
日记情绪分布: {diary_emotions}
（dominant: {diary_dominant}, valence: {diary_valence}, arousal: {diary_arousal}）

小说情感世界: {fiction_emotions}
（dominant: {fiction_dominant}, valence: {fiction_valence}, arousal: {fiction_arousal}）

请分析差距：
1. 现实（日记）vs 理想（小说）之间的情绪差距有多大？
2. 差距的性质是什么？（方向相反/强度不同/领域不同？）
3. 如果这是连续周中的一周，差距是在缩小还是扩大？

输出 JSON：
{{
  "week": "{week}",
  "reality": {{"dominant": "", "valence": 0, "arousal": 0}},
  "ideal": {{"dominant": "", "valence": 0, "arousal": 0}},
  "gap": {{
    "valence_gap": 0,
    "arousal_gap": 0,
    "description": "差距描述（30字）"
  }},
  "gap_nature": "方向相反/强度不同/领域不同",
  "trend": "缩小/扩大/持平/单周无趋势"
}}
纯 JSON。"""


def git_show_file(repo_path, commit_hash, filepath):
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "show", f"{commit_hash}:{filepath}"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return r.stdout[:3000]
    except:
        pass
    return ""


def get_daily_content(repo_path, max_commits=1000):
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
        for c in commits[:5]:
            for f in c["files"][:5]:
                content = git_show_file(repo_path, c["hash"], f)
                if content:
                    texts.append(content[:2000])
        if texts:
            daily[date] = "\n\n".join(texts)
    return daily


def iso_week(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def call_llm(client, prompt, text, model="deepseek-chat", max_tokens=1024):
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:4000]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1, max_tokens=max_tokens,
        )
        return json.loads(resp.choices[0].message.content.strip())
    except Exception as e:
        return {}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/memory"))
    parser.add_argument("--fiction-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/fiction"))
    parser.add_argument("--output", "-o", default="output")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--max-commits", type=int, default=1000)
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("获取 daily content...")
    mem = get_daily_content(args.memory_path, args.max_commits)
    fic = get_daily_content(args.fiction_path, args.max_commits)
    print(f"  memory: {len(mem)} 天, fiction: {len(fic)} 天")

    weekly = defaultdict(lambda: {"diary": [], "fiction": []})
    for date, text in mem.items():
        weekly[iso_week(date)]["diary"].append(f"[{date}] {text[:2000]}")
    for date, text in fic.items():
        weekly[iso_week(date)]["fiction"].append(f"[{date}] {text[:2000]}")

    all_weeks = sorted(weekly.keys())

    # 提取每周的情绪分布
    print("\n提取情绪分布...")
    weekly_diary_emotion = {}
    weekly_fiction_emotion = {}

    for week in all_weeks:
        w = weekly[week]
        if w["diary"]:
            r = call_llm(client, EMOTION_PROMPT, "\n\n".join(w["diary"]), args.model)
            weekly_diary_emotion[week] = r
        if w["fiction"]:
            r = call_llm(client, EMOTION_PROMPT, "\n\n".join(w["fiction"]), args.model)
            weekly_fiction_emotion[week] = r
        d = "✓" if week in weekly_diary_emotion else " "
        f = "✓" if week in weekly_fiction_emotion else " "
        print(f"  {week}: 日记[{d}] {weekly_diary_emotion.get(week,{}).get('dominant_mood','')}  小说[{f}] {weekly_fiction_emotion.get(week,{}).get('dominant_mood','')}")

    # 差距分析：对同时有日记和小说的周
    print("\n差距分析...")
    gap_results = []

    for week in all_weeks:
        if week not in weekly_diary_emotion or week not in weekly_fiction_emotion:
            continue

        de = weekly_diary_emotion[week]
        fe = weekly_fiction_emotion[week]

        inp = {
            "week": week,
            "diary_emotions": json.dumps(de.get("positive_emotions", [])[:5] + de.get("negative_emotions", [])[:5], ensure_ascii=False),
            "diary_dominant": de.get("dominant_mood", ""),
            "diary_valence": de.get("valence", 0),
            "diary_arousal": de.get("arousal", 0),
            "fiction_emotions": json.dumps(fe.get("positive_emotions", [])[:5] + fe.get("negative_emotions", [])[:5], ensure_ascii=False),
            "fiction_dominant": fe.get("dominant_mood", ""),
            "fiction_valence": fe.get("valence", 0),
            "fiction_arousal": fe.get("arousal", 0),
        }

        prompt = GAP_PROMPT.format(**inp)
        r = call_llm(client, prompt, f"分析 {week} 的差距", args.model, max_tokens=2048)
        gap_results.append(r)

        d_val = r.get("reality", {}).get("valence", "?")
        i_val = r.get("ideal", {}).get("valence", "?")
        v_gap = r.get("gap", {}).get("valence_gap", "?")
        print(f"  {week}: 现实愉悦度={d_val}  理想愉悦度={i_val}  差距={v_gap}  ({r.get('gap_nature','')})")

    # 统计
    if gap_results:
        val_gaps = [r.get("gap", {}).get("valence_gap", 0) for r in gap_results]
        aro_gaps = [r.get("gap", {}).get("arousal_gap", 0) for r in gap_results]
        natures = Counter(r.get("gap_nature", "") for r in gap_results)

        # 看趋势：连续周差距是否缩小
        trend_weeks = [(r["week"], r.get("gap", {}).get("valence_gap", 0)) for r in gap_results]
        trend_weeks.sort()
        narrowing = all(trend_weeks[i][1] >= trend_weeks[i+1][1] for i in range(len(trend_weeks)-1)) if len(trend_weeks) >= 2 else None

    # 输出
    result = {
        "total_weeks": len(all_weeks),
        "diary_weeks": len(weekly_diary_emotion),
        "fiction_weeks": len(weekly_fiction_emotion),
        "overlap_weeks": len(gap_results),
        "weekly_gaps": [{
            "week": r["week"],
            "reality_valence": r.get("reality", {}).get("valence"),
            "ideal_valence": r.get("ideal", {}).get("valence"),
            "valence_gap": r.get("gap", {}).get("valence_gap"),
            "arousal_gap": r.get("gap", {}).get("arousal_gap"),
            "gap_nature": r.get("gap_nature", ""),
            "description": r.get("gap", {}).get("description", ""),
        } for r in gap_results],
        "summary": {
            "avg_valence_gap": round(sum(val_gaps)/len(val_gaps), 2) if val_gaps else 0,
            "avg_arousal_gap": round(sum(aro_gaps)/len(aro_gaps), 2) if aro_gaps else 0,
            "dominant_gap_nature": natures.most_common(1)[0][0] if natures else "",
            "narrowing_trend": narrowing,
        },
        "conclusion": "",
    }

    if result["summary"]["avg_valence_gap"] > 0:
        result["conclusion"] = "理想（小说）的愉悦度高于现实（日记），小说提供了情绪补偿"
    elif result["summary"]["avg_valence_gap"] < 0:
        result["conclusion"] = "理想的愉悦度低于现实，小说反而更消极（异常）"
    else:
        result["conclusion"] = "理想与现实愉悦度接近"

    if result["summary"]["narrowing_trend"]:
        result["conclusion"] += "，且差距在逐渐缩小（叙事在起作用）"
    elif result["summary"]["narrowing_trend"] == False:
        result["conclusion"] += "，但差距没有缩小趋势"

    out = output_dir / "gap_result.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, sort_keys=False)
    print(f"\n结果: {out}")
    print(f"  重叠周: {len(gap_results)}")
    print(f"  平均愉悦度差距: {result['summary']['avg_valence_gap']}")
    print(f"  主导差距性质: {result['summary']['dominant_gap_nature']}")
    print(f"  缩小趋势: {result['summary']['narrowing_trend']}")
    print(f"  结论: {result['conclusion']}")


if __name__ == "__main__":
    main()
