#!/usr/bin/env python3
"""
实验: 情绪需求打包 — 哪些情绪需求可以共存于同一个叙事容器

不预设任何场景特征，只看情绪需求本身的兼容性。
"""

import os
import sys
import json
import yaml
from pathlib import Path
from openai import OpenAI

EXTRACT_PROMPT = """从以下文本中提取核心情绪需求。

文本内容：
{content}

输出 JSON：
{{
  "fragment": "{fname}",
  "need": "一句话描述需求",
  "need_type": "陪伴/安全感/被理解/掌控感/希望/温暖/认同/释放",
  "valence": -3~3,
  "arousal": 0~5,
  "compatible_with": ["可共存的需求类型列表"],
  "conflicts_with": ["冲突的需求类型列表"]
}}
纯 JSON。"""

BUNDLE_PROMPT = """以下是一组情绪需求，判断它们能否被同一个叙事容器承载：

{needs}

无需考虑任何场景设定（时间、地点、人物），只分析情绪层面：
1. 这些需求之间有情绪冲突吗？（焦虑+焦虑可以共存，焦虑+平静可以构成弧线）
2. 它们可以构成一条自然的情绪走向吗？
3. 如果能共存，最佳的情绪走向是什么？

输出 JSON：
{{
  "compatible": true/false,
  "confidence": 0-1,
  "emotional_flow": "情绪走向描述",
  "arc_type": "单一情绪/情绪转化/情绪叠加/情绪对冲",
  "capacity_needed": "需要的容器容量 1-5"
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

    # 提取每个片段的需求
    print("\n提取情绪需求...")
    needs = []
    for f in fragments:
        r = call_llm(client, EXTRACT_PROMPT.format(fname=f["name"], content=f["content"]),
                     f["content"], args.model)
        r["fragment"] = f["name"]
        needs.append(r)
        print(f"  {f['name']}: {r.get('need_type','')} (v={r.get('valence','')}, a={r.get('arousal','')})")

    # 按需求类型分组
    from collections import defaultdict
    by_type = defaultdict(list)
    for n in needs:
        by_type[n.get("need_type", "其他")].append(n)

    print(f"\n需求类型分布:")
    for t, items in sorted(by_type.items()):
        print(f"  {t}: {len(items)} 个片段")

    # 分析跨类型的自然组合
    print("\n寻找自然情绪组合...")
    type_list = list(by_type.keys())
    natural_bundles = []

    # 两两类型组合
    for i in range(len(type_list)):
        for j in range(i, len(type_list)):
            t1, t2 = type_list[i], type_list[j]
            sample = by_type[t1][:2] + by_type[t2][:2]
            needs_text = json.dumps([{"fragment": s["fragment"], "need": s.get("need", ""),
                                       "need_type": s.get("need_type", ""),
                                       "valence": s.get("valence", 0), "arousal": s.get("arousal", 0)}
                                      for s in sample], ensure_ascii=False, indent=2)
            r = call_llm(client, BUNDLE_PROMPT.format(needs=needs_text),
                         f"组合 {t1}+{t2}", args.model)
            r["types"] = (t1, t2)
            natural_bundles.append(r)
            status = "✓" if r.get("compatible") else "✗"
            print(f"  {status} {t1} + {t2}: arc={r.get('arc_type','')} 容量={r.get('capacity_needed','')}")

    # 三类型组合（只分析最有潜力的）
    print(f"\n三类型组合分析...")
    triple_bundles = []
    for i in range(len(type_list)):
        for j in range(i+1, len(type_list)):
            for k in range(j+1, len(type_list)):
                t1, t2, t3 = type_list[i], type_list[j], type_list[k]
                sample = by_type[t1][:1] + by_type[t2][:1] + by_type[t3][:1]
                needs_text = json.dumps([{"fragment": s["fragment"], "need": s.get("need", ""),
                                           "need_type": s.get("need_type", ""),
                                           "valence": s.get("valence", 0), "arousal": s.get("arousal", 0)}
                                          for s in sample], ensure_ascii=False, indent=2)
                r = call_llm(client, BUNDLE_PROMPT.format(needs=needs_text),
                             f"组合 {t1}+{t2}+{t3}", args.model)
                r["types"] = (t1, t2, t3)
                triple_bundles.append(r)
                status = "✓" if r.get("compatible") else "✗"
                print(f"  {status} {t1}+{t2}+{t3}: {r.get('arc_type','')}")

    # 结论
    result = {
        "needs": needs,
        "type_distribution": {t: len(items) for t, items in by_type.items()},
        "pair_bundles": [{"types": b["types"], "compatible": b.get("compatible"),
                          "arc_type": b.get("arc_type"), "emotional_flow": b.get("emotional_flow"),
                          "capacity_needed": b.get("capacity_needed")} for b in natural_bundles],
        "triple_bundles": [{"types": b["types"], "compatible": b.get("compatible"),
                            "arc_type": b.get("arc_type")} for b in triple_bundles],
    }

    out = output_dir / "bundle_result.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(result, f, allow_unicode=True, sort_keys=False)
    print(f"\n结果: {out}")


if __name__ == "__main__":
    main()
