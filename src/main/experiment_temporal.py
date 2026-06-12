#!/usr/bin/env python3
"""
实验 4: 时间序列法 — 寻找认知与叙事相互影响的证据

不再评分，改为从时间序列中发现具体的影响证据。
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

SCHEMA_PROMPT = """从以下日记内容中提取**情绪图式**。每条：
- name: 情绪图式名（如"失败焦虑"）
- emotion: 情绪标签（如"焦虑/欣慰/孤独/兴奋"）
- trigger: 触发情境（10字内）
- valence: 愉悦度 -3~3
- quote: 体现该情绪的原文片段（30字内）

输出 JSON 数组。纯 JSON。"""

MOTIF_PROMPT = """从以下小说片段中识别叙事母题。每条：
- name: 母题名（如"雨天重逢"）
- type: theme|image|plot|character
- emotion_tag: 该母题携带的主导情绪（如"期待/苦涩/温暖/遗憾"），null 若无
- quote: 体现该母题的原文片段（30字内）

输出 JSON 数组。纯 JSON。"""

EVIDENCE_PROMPT = """你是一名认知科学研究者。以下是连续两周的数据：

=== 第 W 周 ===
日记情绪图式: {w_schemas}
小说叙事母题: {w_motifs}

=== 第 W+1 周 ===
日记情绪图式: {w1_schemas}
小说叙事母题: {w1_motifs}

请寻找前一周影响后一周的证据。考虑以下 4 种路径：

路径 A — 情绪延续（前一周日记情绪 → 后一周日记情绪）
路径 B — 认知外溢（前一周日记情绪 → 后一周小说母题）
路径 C — 叙事延续（前一周小说母题 → 后一周小说母题）
路径 D — 叙事内化（前一周小说母题 → 后一周日记情绪）

对每条路径，如果有证据则输出，无证据则跳过。

输出 JSON：
{{
  "evidence": [
    {{
      "path": "A/B/C/D",
      "from_week": "W",
      "to_week": "W+1",
      "from_item": "前一周的具体条目名",
      "to_item": "后一周的具体条目名",
      "match_type": "情绪一致/主题相关/触发情境相似/结构对应",
      "strength": "强/中/弱",
      "reason": "具体说明依据（30字内）"
    }}
  ]
}}

纯 JSON，没有证据时输出 {{"evidence": []}}。"""


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
        combined = "\n\n".join(texts)
        if combined:
            daily[date] = combined
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


def extract_elements(client, prompt, text, model):
    result = call_llm(client, prompt, text, model)
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

    weekly = defaultdict(lambda: {"schemas_texts": [], "motifs_texts": []})
    for date, text in mem.items():
        weekly[iso_week(date)]["schemas_texts"].append(f"[{date}] {text}")
    for date, text in fic.items():
        weekly[iso_week(date)]["motifs_texts"].append(f"[{date}] {text}")

    all_weeks = sorted(weekly.keys())
    recent = all_weeks[-args.weeks:]
    print(f"分析 {args.weeks} 周: {recent[0]} → {recent[-1]}")

    print("\n每周提取...")
    ws = {}
    wm = {}
    for week in recent:
        w = weekly[week]
        if w["schemas_texts"]:
            ws[week] = extract_elements(client, SCHEMA_PROMPT, "\n\n".join(w["schemas_texts"]), args.model)
        else:
            ws[week] = []
        if w["motifs_texts"]:
            wm[week] = extract_elements(client, MOTIF_PROMPT, "\n\n".join(w["motifs_texts"]), args.model)
        else:
            wm[week] = []
        print(f"  {week}: schemas={len(ws[week])} motifs={len(wm[week])}")

    print("\n寻找影响证据...")
    all_evidence = []
    for i in range(len(recent) - 1):
        w, w1 = recent[i], recent[i+1]
        inp = {
            "w_schemas": json.dumps(ws[w][:10], ensure_ascii=False, indent=2),
            "w_motifs": json.dumps(wm[w][:10], ensure_ascii=False, indent=2),
            "w1_schemas": json.dumps(ws[w1][:10], ensure_ascii=False, indent=2),
            "w1_motifs": json.dumps(wm[w1][:10], ensure_ascii=False, indent=2),
        }
        prompt = EVIDENCE_PROMPT.format(**inp)
        r = call_llm(client, prompt,
                     f"分析 {w} → {w1} 的影响证据", args.model, max_tokens=2048)
        ev = r.get("evidence", [])
        for e in ev:
            e["from_week"] = w
            e["to_week"] = w1
            if "from_item" not in e or e["from_item"] is None:
                e["from_item"] = ""
            if "to_item" not in e or e["to_item"] is None:
                e["to_item"] = ""
        all_evidence.extend(ev)
        print(f"  {w} → {w1}: {len(ev)} 条证据")
        for e in ev:
            print(f"    [{e.get('path','?')}] {str(e.get('from_item',''))[:15]} → {str(e.get('to_item',''))[:15]} ({e.get('strength','?')})")

    # 按路径聚合
    by_path = defaultdict(list)
    for e in all_evidence:
        by_path[e["path"]].append(e)

    result = {
        "weeks": recent,
        "total_evidence": len(all_evidence),
        "evidence_by_path": {k: len(v) for k, v in by_path.items()},
        "evidence": all_evidence,
    }

    out = output_dir / "temporal_result.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, sort_keys=False)
    print(f"\n结果: {out}")
    print(f"  总证据: {len(all_evidence)} 条")
    for path, items in sorted(by_path.items()):
        labels = {"A": "情绪延续", "B": "认知外溢", "C": "叙事延续", "D": "叙事内化"}
        strong = sum(1 for x in items if x.get("strength") == "强")
        print(f"  路径{path}({labels.get(path,'?')}): {len(items)} 条 (强{strong})")


if __name__ == "__main__":
    main()
