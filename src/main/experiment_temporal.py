#!/usr/bin/env python3
"""
实验: 周时间序列 — 挖掘认知与叙事的演变模式

从 git 历史获取 5 周数据，每周提取情绪图式（日记）和叙事母题（小说），
让 LLM 自由发现时间轴上的模式。
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
- emotion: 情绪标签（如焦虑/欣慰/孤独/兴奋）
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

PATTERN_PROMPT = """以下是一个创始人连续 5 周的时间轴。每周包含日记中的情绪图式，以及当周创作的小说中的叙事母题。

{timeline}

请分析这个时间轴，回答以下问题：

1. **情绪弧线**：5 周的情绪如何演变？有无转折点？
2. **共鸣时刻**：哪一周日记和小说之间的情绪/主题最接近？具体是什么？
3. **跨域流动**：有没有某个主题或情绪先在日记中出现，后在小说中出现？或者反过来？
4. **整体叙事**：如果把这 5 周看作一个完整的故事，它的主线是什么？

对每个问题，引用具体的条目和原文片段作为依据。输出为结构化 JSON：

{{
  "emotional_arc": {{
    "summary": "情绪演变概括（50字内）",
    "turning_points": [{{"week": "周", "description": "转折说明", "evidence": "具体条目"}}]
  }},
  "resonance_moments": [{{"week": "周", "diary_item": "情绪图式名", "fiction_item": "母题名", "connection": "具体关联说明"}}],
  "cross_domain_flow": [{{"direction": "日记→小说/小说→日记/双向", "theme": "流动的主题", "from_week": "源周", "to_week": "目标周", "evidence": "具体条目对"}}],
  "overall_narrative": "主线概括（80字内）"
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
        ["git", "-C", repo_path, "log", f"--max-count={max_commits}",
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


def format_weekly(w, schemas, motifs):
    lines = [f"=== 第 {w} 周 ==="]
    if schemas:
        lines.append("日记情绪图式:")
        for s in schemas:
            q = s.get("quote", "")[:20]
            lines.append(f"  - {s.get('name','')} ({s.get('emotion','')}, valence={s.get('valence','')}) trigger={s.get('trigger','')} quote=\"{q}\"")
    else:
        lines.append("日记: (无数据)")
    if motifs:
        lines.append("小说叙事母题:")
        for m in motifs:
            q = m.get("quote", "")[:20]
            lines.append(f"  - {m.get('name','')} ({m.get('type','')}) emotion={m.get('emotion_tag','null')} quote=\"{q}\"")
    else:
        lines.append("小说: (无数据)")
    lines.append("")
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
    print(f"分析 {args.weeks} 周: {recent[0]} → {recent[-1]}")

    print("\n提取每周情绪图式与叙事母题...")
    weekly_schemas = {}
    weekly_motifs = {}

    for week in recent:
        w = weekly[week]
        if w["diary"]:
            weekly_schemas[week] = extract_elements(
                client, SCHEMA_PROMPT, "\n\n".join(w["diary"]), args.model)
        else:
            weekly_schemas[week] = []
        if w["fiction"]:
            weekly_motifs[week] = extract_elements(
                client, MOTIF_PROMPT, "\n\n".join(w["fiction"]), args.model)
        else:
            weekly_motifs[week] = []
        print(f"  {week}: {len(weekly_schemas[week])} 图式, {len(weekly_motifs[week])} 母题")

    # 构造时间轴文本
    timeline_parts = []
    for week in recent:
        timeline_parts.append(format_weekly(week, weekly_schemas[week], weekly_motifs[week]))
    timeline_text = "\n".join(timeline_parts)

    # 可选：保存时间轴文本到文件
    with open(output_dir / "timeline.txt", "w", encoding="utf-8") as f:
        f.write(timeline_text)
    print(f"\n时间轴已保存: {output_dir / 'timeline.txt'}")

    # LLM 模式分析
    print("\n分析模式...")
    result = call_llm(client, PATTERN_PROMPT, timeline_text, args.model, max_tokens=4096)

    out = output_dir / "temporal_result.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, sort_keys=False)

    print(f"\n结果: {out}")
    print(f"情绪弧线: {result.get('emotional_arc', {}).get('summary', '无')}")
    print(f"共鸣时刻: {len(result.get('resonance_moments', []))} 个")
    print(f"跨域流动: {len(result.get('cross_domain_flow', []))} 条")
    print(f"整体叙事: {result.get('overall_narrative', '无')[:60]}")


if __name__ == "__main__":
    main()
