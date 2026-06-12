#!/usr/bin/env python3
"""
实验: 中介分析 — 本周叙事是否改变了情绪认知的走向？

链条：本周日记情绪 → 本周小说叙事 → 下周日记情绪
问题：小说是否改写了情绪的轨迹？
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

CHAIN_PROMPT = """你研究叙事如何改变认知。以下是连续两周的数据：

=== 第 N 周 ===
日记情绪图式: {d_n}
小说叙事母题: {f_n}

=== 第 N+1 周 ===
日记情绪图式: {d_n1}

请分析：小说（第 N 周）是否改变了情绪认知的轨迹？

对比两个场景：
- 场景 A（无小说干预）：第 N+1 周的日记情绪应该是第 N 周日记情绪的自然延续
- 场景 B（有小说干预）：第 N+1 周的日记情绪受到了第 N 周小说的影响

回答以下问题：
1. **自然延续**：第 N+1 周的日记情绪与第 N 周日记情绪相比，是延续还是转变？
2. **小说影响**：第 N+1 周的日记情绪中，有没有第 N 周小说中出现但第 N 周日记中没有的情绪或主题？
3. **转变机制**：如果有转变，小说在其中扮演了什么角色？（放大/转化/补偿/中和？）

输出 JSON：
{{
  "natural_continuation": {{"exists": true/false, "evidence": "", "details": ""}},
  "fiction_influence": {{"exists": true/false, "new_elements_in_diary": [], "originated_from_fiction": "", "details": ""}},
  "transformation_role": "放大/转化/补偿/中和/无",
  "summary": "一句话总结小说对情绪认知的影响"
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

    print("\n提取每周数据...")
    ws = {}
    wm = {}
    for week in recent:
        w = weekly[week]
        if w["diary"]:
            ws[week] = extract_elements(client, SCHEMA_PROMPT, "\n\n".join(w["diary"]), args.model)
        else:
            ws[week] = []
        if w["fiction"]:
            wm[week] = extract_elements(client, MOTIF_PROMPT, "\n\n".join(w["fiction"]), args.model)
        else:
            wm[week] = []
        s = len(ws[week])
        m = len(wm[week])
        print(f"  {week}: {s} 图式 {m} 母题{' ★' if s and m else ''}")

    # 找有效链条：diary_N + fiction_N + diary_N+1 都存在的周对
    print("\n有效链条（本周日记+本周小说+下周日记）:")
    chains = []
    for i in range(len(recent) - 1):
        wn, wn1 = recent[i], recent[i+1]
        if ws[wn] and wm[wn] and ws[wn1]:
            chains.append((wn, wn1))
            print(f"  {wn} → {wn1}: diary({len(ws[wn])})+fiction({len(wm[wn])}) → diary({len(ws[wn1])})")

    if not chains:
        print("  无有效链条")
        return

    # 中介分析
    print("\n中介分析...")
    results = []
    for wn, wn1 in chains:
        inp = {
            "d_n": json.dumps(ws[wn][:8], ensure_ascii=False, indent=2),
            "f_n": json.dumps(wm[wn][:8], ensure_ascii=False, indent=2),
            "d_n1": json.dumps(ws[wn1][:8], ensure_ascii=False, indent=2),
        }
        prompt = CHAIN_PROMPT.format(**inp)
        r = call_llm(client, prompt, f"分析 {wn}→{wn1} 链条", args.model, max_tokens=4096)
        r["chain"] = f"{wn}→{wn1}"
        results.append(r)

        nat = r.get("natural_continuation", {})
        fic_inf = r.get("fiction_influence", {})
        role = r.get("transformation_role", "?")
        print(f"  {wn}→{wn1}:")
        print(f"    自然延续: {nat.get('exists')} | 小说影响: {fic_inf.get('exists')} | 角色: {role}")
        print(f"    总结: {r.get('summary', '')[:60]}")

    # 聚合
    out = output_dir / "mediation_result.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump({"chains_analyzed": len(chains), "details": results}, f, allow_unicode=True, sort_keys=False)
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
