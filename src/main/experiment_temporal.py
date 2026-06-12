#!/usr/bin/env python3
"""
实验: 周内关联分析 — 同一周的日记情绪与小说母题如何关联
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

SCHEMA_PROMPT = """从日记内容中提取情绪图式。每条：
- name: 图式名
- emotion: 情绪标签
- trigger: 触发情境（10字内）
- valence: 愉悦度 -3~3
- quote: 原文片段（30字内）
输出 JSON 数组。"""

MOTIF_PROMPT = """从小说片段中识别母题。每条：
- name: 母题名
- type: theme|image|plot|character
- emotion_tag: 主导情绪或null
- quote: 原文片段（30字内）
输出 JSON 数组。"""

WITHIN_WEEK_PROMPT = """以下是一周内创始人的日记情绪图式和小说叙事母题。

{week_data}

请分析同一周内日记和小说之间的关系：

1. **情绪共鸣**：日记中的情绪图式与小说母题的情感基调是否一致？具体哪些条目对应？
2. **主题映射**：日记中关切的主题是否在小说中以隐喻或变形的方式出现？
3. **独特信号**：有哪些只出现在日记或只出现在小说中的情绪/主题？为什么？
4. **整体判断**：这一周，日记和小说之间的关系是什么？（同频/互补/无关/冲突？）

为每个问题引用具体条目名和原文片段作为依据。

输出 JSON：
{{
  "week": "{week}",
  "emotional_resonance": [{{"diary_item": "", "fiction_item": "", "connection": ""}}],
  "theme_mapping": [{{"diary_theme": "", "fiction_motif": "", "how_mapped": ""}}],
  "unique_signals": {{"diary_only": [], "fiction_only": []}},
  "overall_judgment": "同频/互补/无关/冲突",
  "summary": "一句话总结"
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


def call_llm(client, prompt, text, model="deepseek-chat", max_tokens=2048):
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


def extract_elements(client, prompt, text, model):
    result = call_llm(client, prompt, text, model, max_tokens=1024)
    if isinstance(result, list):
        return result
    for key in ["elements", "schemas", "motifs", "items", "results"]:
        if key in result and isinstance(result[key], list):
            return result[key]
    return []


def format_week(week, schemas, motifs):
    lines = [f"=== 第 {week} 周 ==="]
    if schemas:
        lines.append("日记情绪图式:")
        for s in schemas:
            q = s.get("quote", "")[:30]
            lines.append(f"  - {s.get('name','')} (emotion={s.get('emotion','')}, valence={s.get('valence','')}) trigger={s.get('trigger','')} q=\"{q}\"")
    if motifs:
        lines.append("小说叙事母题:")
        for m in motifs:
            q = m.get("quote", "")[:30]
            lines.append(f"  - {m.get('name','')} (type={m.get('type','')}, emotion={m.get('emotion_tag','null')}) q=\"{q}\"")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/memory"))
    parser.add_argument("--fiction-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/fiction"))
    parser.add_argument("--output", "-o", default="output")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--weeks", type=int, default=5)
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
    recent = all_weeks[-args.weeks:]

    print(f"\n提取最近 {args.weeks} 周数据...")
    weekly_schemas = {}
    weekly_motifs = {}
    for week in recent:
        w = weekly[week]
        if w["diary"]:
            weekly_schemas[week] = extract_elements(client, SCHEMA_PROMPT, "\n\n".join(w["diary"]), args.model)
        else:
            weekly_schemas[week] = []
        if w["fiction"]:
            weekly_motifs[week] = extract_elements(client, MOTIF_PROMPT, "\n\n".join(w["fiction"]), args.model)
        else:
            weekly_motifs[week] = []
        s = len(weekly_schemas[week])
        m = len(weekly_motifs[week])
        print(f"  {week}: {s} 图式 {m} 母题{' ★ 同时有日记和小说' if s and m else ''}")

    # 分析每周的周内关联（只分析同时有日记和小说的周）
    print("\n周内关联分析...")
    results = []
    for week in recent:
        schemas = weekly_schemas[week]
        motifs = weekly_motifs[week]
        if not schemas or not motifs:
            print(f"  {week}: 跳过（缺少日记或小说数据）")
            continue

        week_text = format_week(week, schemas, motifs)
        prompt = WITHIN_WEEK_PROMPT.format(week_data=week_text, week=week)
        r = call_llm(client, prompt, week_text, args.model, max_tokens=4096)
        r["week"] = week
        results.append(r)
        print(f"  {week}: {r.get('overall_judgment','?')} — {r.get('summary','')[:50]}")

    # 聚合
    judgments = [r.get("overall_judgment", "?") for r in results]
    from collections import Counter
    judgment_dist = Counter(judgments)

    out = output_dir / "temporal_result.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump({"weeks_analyzed": len(results), "judgment_distribution": dict(judgment_dist), "weekly_details": results}, f, allow_unicode=True, sort_keys=False)

    print(f"\n结果: {out}")
    print(f"  分析周数: {len(results)}")
    print(f"  关系分布: {dict(judgment_dist)}")


if __name__ == "__main__":
    main()
