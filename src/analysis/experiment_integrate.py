#!/usr/bin/env python3
"""
实验: 片段整合分析 — 哪些片段可以共享同一个场景

核心问题：多个片段表达的情绪需求是否可以共存于一个场景中？
"""

import os
import sys
import json
import yaml
from pathlib import Path
from openai import OpenAI

ANALYZE_PROMPT = """从以下片段中提取核心特征：

{content}

输出 JSON：
{{
  "fragment": "{fname}",
  "core_emotion": "核心情绪",
  "emotional_need": "需求",
  "setting_clue": "暗示的场景设定（夜晚/白天/室内/室外/独处/共处）",
  "has_action": true/false,
  "action_description": "如果有动作，是什么",
  "tone": "严肃/轻盈/压抑/温柔/焦虑/平静"
}}
纯 JSON。"""

PAIR_PROMPT = """判断以下两个片段是否可以整合到**同一个场景**中：

片段 A: {a_content}
片段 B: {b_content}

分析维度：
1. 情绪冲突：两者的情绪是否兼容（焦虑+温暖可以，焦虑+焦虑可能冲突）
2. 设定一致：场景设定是否同一套（都是夜晚室内，或都是白天室外）
3. 动作互补：A的动作+B的动作能否构成一个完整的互动
4. 情绪梯度：如果共存，情绪走向是怎样的（A的孤独→B的安慰，就是好梯度）

输出 JSON：
{{
  "frag_a": "{a_name}",
  "frag_b": "{b_name}",
  "compatible": true/false,
  "confidence": 0-1,
  "shared_setting": "可能的共同场景设定",
  "emotional_arc": "场景内的情绪走向",
  "integration_approach": "如何整合（A先B后/交织/对话驱动/动作驱动）",
  "risk": "整合风险",
  "scene_hint": "一句话描述这个可能的场景"
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
    frag_dir = base / "1_片段"

    fragments = []
    for f in sorted(frag_dir.glob("*.md")):
        if f.name in ("README.md",):
            continue
        content = f.read_text(encoding="utf-8").strip()
        if content:
            fragments.append({"name": f.stem, "content": content[:2000]})

    print(f"片段: {len(fragments)} 个")

    # 分析每个片段
    print("\n分析每个片段特征...")
    frag_features = {}
    for f in fragments:
        r = call_llm(client, ANALYZE_PROMPT.format(fname=f["name"], content=f["content"]),
                     f["content"], args.model)
        frag_features[f["name"]] = r
        print(f"  {f['name']}: {r.get('core_emotion','')} | 设定={r.get('setting_clue','')} | 有动作={r.get('has_action','')}")

    # 两两配对分析
    print(f"\n两两配对分析 ({len(fragments)} 选 2 = {len(fragments)*(len(fragments)-1)//2} 对)...")
    pairs = []
    for i in range(len(fragments)):
        for j in range(i+1, len(fragments)):
            a, b = fragments[i], fragments[j]
            inp = {
                "a_name": a["name"], "a_content": a["content"],
                "b_name": b["name"], "b_content": b["content"],
            }
            r = call_llm(client, PAIR_PROMPT.format(**inp),
                         f"分析 {a['name']} + {b['name']}", args.model)
            r["pair"] = f"{a['name']} + {b['name']}"
            pairs.append(r)
            status = "✓" if r.get("compatible") else "✗"
            print(f"  {status} {a['name']} + {b['name']}: 置信度={r.get('confidence','')} | {r.get('scene_hint','')[:40]}")

    # 聚合：找到兼容度最高的分组
    compatible_pairs = [p for p in pairs if p.get("compatible")]
    incompatible_pairs = [p for p in pairs if not p.get("compatible")]

    print(f"\n兼容对: {len(compatible_pairs)}/{len(pairs)}")
    print(f"不兼容对: {len(incompatible_pairs)}/{len(pairs)}")

    # 找最佳三重组合（三个片段可共存于同一场景）
    print("\n寻找三重组合...")
    triples = []
    pair_names = {(p["frag_a"], p["frag_b"]): p for p in compatible_pairs}

    names = [f["name"] for f in fragments]
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            for k in range(j+1, len(names)):
                n1, n2, n3 = names[i], names[j], names[k]
                if (n1, n2) in pair_names and (n1, n3) in pair_names and (n2, n3) in pair_names:
                    triples.append((n1, n2, n3))

    print(f"  可三合一的组合: {len(triples)} 组")
    for t in triples:
        print(f"    {t[0]} + {t[1]} + {t[2]}")
        # 评分最高的兼容对
        top = max(
            [pair_names.get((t[0], t[1]), {}), pair_names.get((t[0], t[2]), {}), pair_names.get((t[1], t[2]), {})],
            key=lambda x: x.get("confidence", 0) or 0
        )
        if top:
            print(f"    场景: {top.get('scene_hint', '')}")

    result = {
        "fragments_analyzed": len(fragments),
        "total_pairs": len(pairs),
        "compatible_pairs": len(compatible_pairs),
        "incompatible_pairs": len(incompatible_pairs),
        "triple_combinations": len(triples),
        "compatible_details": [{
            "pair": p["pair"],
            "confidence": p.get("confidence"),
            "shared_setting": p.get("shared_setting"),
            "emotional_arc": p.get("emotional_arc"),
            "scene_hint": p.get("scene_hint"),
        } for p in sorted(compatible_pairs, key=lambda x: x.get("confidence", 0) or 0, reverse=True)[:8]],
        "triples": [{"fragments": list(t)} for t in triples],
    }

    out = output_dir / "integrate_result.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, sort_keys=False)
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
