#!/usr/bin/env python3
"""
实验: 加工深度分析 — 四个写作阶段对情绪的加工差异

1_片段 → 2_脚本 → 3_初稿 → 4_改稿

假设：加工越深，原始情绪被叙事转化的程度越高（距离感越强、美学化越深、情绪复杂度越高）。
"""

import os
import sys
import json
import yaml
from pathlib import Path
from openai import OpenAI

ANALYZE_PROMPT = """分析以下小说文本的加工特征。

输出 JSON：
{{
  "stage": "片段/脚本/初稿/改稿",
  "raw_emotion_directness": 0-1,  # 情绪是否被直接表达（越高越直接）
  "narrative_distance": 0-1,      # 叙事距离感（越高越有距离）
  "aesthetic_refinement": 0-1,    # 美学修饰程度
  "emotional_complexity": 0-1,    # 情绪复杂度（越高越混合）
  "dominant_emotion": "主导情绪",
  "valence": -3~3,
  "arousal": 0~5,
  "evidence": "判断依据（20字内，引用原文片段）",
  "description": "一句话概括加工特征"
}}
纯 JSON。"""

COMPARE_PROMPT = """比较同一主题在不同写作阶段的加工差异。

主题：{topic}

{fragment}
{f_script}
{f_draft}
{f_final}

分析加工深度的变化：从片段到改稿，情绪发生了什么变化？
- 原始情绪是什么？在哪个阶段被转化了？
- 叙事距离如何变化？
- 美学化和情绪复杂度如何递增？

输出 JSON：
{{
  "topic": "{topic}",
  "raw_emotion": "片段中的原始情绪",
  "transformation_chain": [
    {{"stage": "1_片段", "emotion": "", "distance": 0, "aesthetic": 0, "complexity": 0, "valence": 0}},
    {{"stage": "2_脚本", "emotion": "", "distance": 0, "aesthetic": 0, "complexity": 0, "valence": 0}},
    {{"stage": "3_初稿", "emotion": "", "distance": 0, "aesthetic": 0, "complexity": 0, "valence": 0}},
    {{"stage": "4_改稿", "emotion": "", "distance": 0, "aesthetic": 0, "complexity": 0, "valence": 0}}
  ],
  "turning_point": "转化的关键发生在哪一阶段",
  "summary": "一句话概括加工链"
}}
纯 JSON。"""


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


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fiction-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/fiction/职场言情"))
    parser.add_argument("--output", "-o", default="output")
    parser.add_argument("--model", default="deepseek-chat")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr); sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    base = Path(args.fiction_path)

    # 加载四个阶段的数据
    stages = ["1_片段", "2_脚本", "3_初稿", "4_改稿"]
    stage_data = {}

    for stage in stages:
        dir_path = base / stage
        if not dir_path.exists():
            print(f"  {stage}: 目录不存在")
            continue
        files = []
        for f in sorted(dir_path.glob("*.md")):
            if f.name in ("README.md",):
                continue
            content = f.read_text(encoding="utf-8").strip()
            if content:
                files.append({"name": f.stem, "content": content[:3000]})
        stage_data[stage] = files
        print(f"  {stage}: {len(files)} 文件")

    # 分析每个文件的加工特征
    print("\n逐文件分析...")
    all_analyses = {}
    for stage, files in stage_data.items():
        stage_analyses = []
        for f in files:
            r = call_llm(client, ANALYZE_PROMPT, f["content"], args.model)
            r["file"] = f["name"]
            r["stage"] = stage
            stage_analyses.append(r)
            print(f"  {stage}/{f['name']}: 直接度={r.get('raw_emotion_directness','')} 距离={r.get('narrative_distance','')} 美学={r.get('aesthetic_refinement','')} 复杂度={r.get('emotional_complexity','')}")
        all_analyses[stage] = stage_analyses

    # 按阶段聚合统计
    print("\n阶段聚合统计...")
    stage_stats = {}
    for stage in stages:
        analyses = all_analyses.get(stage, [])
        if not analyses:
            continue
        n = len(analyses)
        avg_direct = sum(a.get("raw_emotion_directness", 0) or 0 for a in analyses) / n
        avg_dist = sum(a.get("narrative_distance", 0) or 0 for a in analyses) / n
        avg_aes = sum(a.get("aesthetic_refinement", 0) or 0 for a in analyses) / n
        avg_complex = sum(a.get("emotional_complexity", 0) or 0 for a in analyses) / n
        avg_val = sum(a.get("valence", 0) or 0 for a in analyses) / n
        stage_stats[stage] = {
            "count": n,
            "avg_raw_emotion_directness": round(avg_direct, 2),
            "avg_narrative_distance": round(avg_dist, 2),
            "avg_aesthetic_refinement": round(avg_aes, 2),
            "avg_emotional_complexity": round(avg_complex, 2),
            "avg_valence": round(avg_val, 2),
        }
        print(f"  {stage}: 直接度={avg_direct:.2f} 距离={avg_dist:.2f} 美学={avg_aes:.2f} 复杂度={avg_complex:.2f} 愉悦度={avg_val:.2f}")

    # 寻找跨阶段匹配的主题链
    print("\n主题链分析...")
    chains = []
    for final_file in stage_data.get("4_改稿", []):
        fname = final_file["name"]
        # 尝试在其他阶段找到同名或主题相似的文件
        chain = {"topic": fname, "files": {}}
        for stage in stages:
            for f in stage_data.get(stage, []):
                if f["name"] == fname or fname.startswith(f["name"]) or f["name"].startswith(fname):
                    chain["files"][stage] = f
                    break
        if len(chain["files"]) >= 2:
            chains.append(chain)
            stages_found = list(chain["files"].keys())
            print(f"  {fname}: {stages_found}")

    if chains:
        print(f"\n主题链对比分析 ({len(chains)} 条)...")
        chain_results = []
        for chain in chains:
            inp = {"topic": chain["topic"]}
            for stage in stages:
                f = chain["files"].get(stage)
                if f:
                    inp[stage.replace("1_", "").replace("2_", "").replace("3_", "").replace("4_", "")] = f["content"]
                    inp["has_" + stage[:1]] = True
                else:
                    inp[stage[:3]] = ""
                    inp["has_" + stage[:1]] = False
            inp["fragment"] = f"=== 1_片段 ===\n{chain['files'].get('1_片段', {}).get('content', '(无)')}\n=== 结束 ==="
            inp["f_script"] = f"=== 2_脚本 ===\n{chain['files'].get('2_脚本', {}).get('content', '(无)')}\n=== 结束 ===" if "2_脚本" in chain["files"] else ""
            inp["f_draft"] = f"=== 3_初稿 ===\n{chain['files'].get('3_初稿', {}).get('content', '(无)')}\n=== 结束 ===" if "3_初稿" in chain["files"] else ""
            inp["f_final"] = f"=== 4_改稿 ===\n{chain['files'].get('4_改稿', {}).get('content', '(无)')}\n=== 结束 ==="

            prompt = COMPARE_PROMPT.format(**inp)
            r = call_llm(client, prompt, f"分析 {chain['topic']} 加工链", args.model, max_tokens=4096)
            r["topic"] = chain["topic"]
            chain_results.append(r)
            tc = r.get("transformation_chain", [])
            print(f"  {chain['topic']}:")
            for t in tc:
                print(f"    {t.get('stage','')}: 情绪={t.get('emotion','')} 距离={t.get('distance','')}")
            print(f"    转折: {r.get('turning_point','')}")

    # 结论
    print("\n结论...")
    conclusions = []
    if stage_stats:
        stages_ordered = [s for s in stages if s in stage_stats]
        if len(stages_ordered) >= 2:
            first = stages_ordered[0]
            last = stages_ordered[-1]
            d1 = stage_stats[first]["avg_raw_emotion_directness"]
            d2 = stage_stats[last]["avg_raw_emotion_directness"]
            dist1 = stage_stats[first]["avg_narrative_distance"]
            dist2 = stage_stats[last]["avg_narrative_distance"]

            if d2 < d1:
                conclusions.append(f"加工深度增加，情绪直接度降低 ({d1}→{d2})")
            if dist2 > dist1:
                conclusions.append(f"叙事距离增加 ({dist1}→{dist2})")
            if stage_stats[last]["avg_valence"] > stage_stats[first]["avg_valence"]:
                conclusions.append("愉悦度提升（负面情绪被叙事转化）")

    result = {
        "stages_analyzed": list(stage_stats.keys()),
        "stage_summary": stage_stats,
        "chains_found": len(chains),
        "chain_details": chain_results if chains else [],
        "conclusions": conclusions,
    }

    out = output_dir / "depth_result.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, sort_keys=False)
    print(f"\n结果: {out}")
    for c in conclusions:
        print(f"  • {c}")


if __name__ == "__main__":
    main()
