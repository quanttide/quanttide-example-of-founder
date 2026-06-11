#!/usr/bin/env python3
"""
实验 3: 认知-叙事反馈循环

依赖: think/output/situations.yaml + write/output/motifs.yaml
用法: python3 feedback.py [--think-output <dir>] [--write-output <dir>] [--output <dir>]
"""

import os
import sys
import json
import yaml
from pathlib import Path
from openai import OpenAI

RECOMMEND_PROMPT = """你是一个认知-叙事匹配助手。你的任务是将"认知情境"匹配到"叙事母题"。

认知情境包含：活动描述、参与者、情绪状态。
叙事母题包含：母题名、类型、描述。

对每个情境，从母题列表中选出最匹配的 1-3 个母题，输出 JSON 数组：
[{
  "situation_id": "情境ID",
  "situation_activity": "情境活动",
  "matched_motif_ids": ["母题ID列表"],
  "reason": "为什么匹配（20字内）",
  "confidence": 0-1的置信度
}]

如果没有匹配的母题，matched_motif_ids 为空数组。
输出纯 JSON 数组。"""

CONFLICT_PROMPT = """你是一个认知-叙事冲突检测助手。分析以下成对的"认知情境"与"叙事母题"是否存在冲突。

冲突类型：
- value_conflict: 值冲突 — 图式预期 vs 叙事实际相反（如"团队协同" vs "孤独主题"）
- none: 无冲突 — 情境与母题和谐或无关

对每组输出：
{
  "situation_id": "情境ID",
  "motif_id": "母题ID",
  "conflict_type": "冲突类型或null",
  "description": "冲突描述或null",
  "severity": 0-1的严重程度（0=无冲突）
}

输出 JSON 数组。"""


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def call_llm(prompt, data_json, client, model="deepseek-chat"):
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": data_json},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=4096,
        )
        content = resp.choices[0].message.content.strip()
        data = json.loads(content)
        if isinstance(data, list):
            return data
        for key in ["results", "matches", "conflicts", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    except Exception as e:
        print(f"  LLM 调用失败: {e}", file=sys.stderr)
        return []


def main():
    import argparse

    parser = argparse.ArgumentParser(description="认知-叙事反馈循环")
    parser.add_argument("--think-output", default=None,
                        help="think 输出目录 (默认: ../think/output)")
    parser.add_argument("--write-output", default=None,
                        help="write 输出目录 (默认: ../write/output)")
    parser.add_argument("--output", "-o", default="output", help="输出目录")
    parser.add_argument("--model", default="deepseek-chat", help="模型名")
    args = parser.parse_args()

    base = Path(__file__).parent
    think_dir = Path(args.think_output) if args.think_output else base / "../think/output"
    write_dir = Path(args.write_output) if args.write_output else base / "../write/output"
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误: 请设置 DEEPSEEK_API_KEY", file=sys.stderr)
        sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    # 加载数据
    sit_path = think_dir / "situations.yaml"
    mot_path = write_dir / "motifs.yaml"
    if not sit_path.exists() or not mot_path.exists():
        print(f"错误: 找不到输入文件\n  {sit_path}\n  {mot_path}", file=sys.stderr)
        sys.exit(1)

    sit_data = load_yaml(sit_path)["situations"]
    mot_data = load_yaml(mot_path)["motifs"]
    print(f"加载 {len(sit_data)} 个情境, {len(mot_data)} 个母题\n")

    # --- 实验 3.1: 图式驱动的母题推荐 ---
    print("=== 实验 3.1: 母题推荐 ===")
    # 选取最近的 journal 情境（有情绪、有活动），避免 memo 类抽象情境
    candidates = [s for s in sit_data if s["mood"].get("raw") or s.get("participants")]
    if len(candidates) > 10:
        candidates = candidates[:10]

    input_data = {
        "situations": [{"id": s["id"], "activity": s["activity"],
                        "participants": s.get("participants", []),
                        "mood": s["mood"]} for s in candidates],
        "motifs": [{"id": m["id"], "motif_name": m["motif_name"],
                    "motif_type": m["motif_type"],
                    "description": m["description"]} for m in mot_data],
    }
    recommendations = call_llm(RECOMMEND_PROMPT, json.dumps(input_data, ensure_ascii=False), client, args.model)
    print(f"  推荐结果: {len(recommendations)} 条")

    rec_path = output_dir / "recommendations.yaml"
    with open(rec_path, "w", encoding="utf-8") as f:
        yaml.dump({"recommendations": recommendations}, f, allow_unicode=True, sort_keys=False)

    # 统计
    matched = sum(1 for r in recommendations if r.get("matched_motif_ids"))
    avg_conf = sum(r.get("confidence", 0) for r in recommendations) / max(len(recommendations), 1)
    print(f"  有匹配: {matched}/{len(recommendations)}, 平均置信度: {avg_conf:.2f}")

    # --- 实验 3.2: 冲突检测 ---
    print("\n=== 实验 3.2: 冲突检测 ===")
    conflict_pairs = []
    for r in recommendations:
        for mid in r.get("matched_motif_ids", []):
            conflict_pairs.append({
                "situation_id": r["situation_id"],
                "situation_activity": r["situation_activity"],
                "motif_id": mid,
            })
    if conflict_pairs:
        conflicts = call_llm(CONFLICT_PROMPT, json.dumps(conflict_pairs[:20], ensure_ascii=False), client, args.model)
    else:
        conflicts = []
    print(f"  冲突检测: {len(conflicts)} 对")

    conf_path = output_dir / "conflicts.yaml"
    with open(conf_path, "w", encoding="utf-8") as f:
        yaml.dump({"conflicts": conflicts}, f, allow_unicode=True, sort_keys=False)

    real_conflicts = sum(1 for c in conflicts if c.get("conflict_type") and c["conflict_type"] != "none")
    print(f"  有冲突: {real_conflicts}/{len(conflicts)}")

    # --- 实验 3.3: 评估 ---
    print("\n=== 实验 3.3: 评估 ===")
    coverage = matched / max(len(candidates), 1)
    novelty = sum(1 for r in recommendations if r.get("confidence", 0) < 0.7) / max(len(recommendations), 1)
    consistency = sum(1 for r in recommendations if r.get("confidence", 0) >= 0.7) / max(len(recommendations), 1)

    eval_result = {
        "summary": {
            "total_situations": len(sit_data),
            "total_motifs": len(mot_data),
            "sampled_situations": len(candidates),
        },
        "experiment_3.1_recommendation": {
            "matched": matched,
            "total": len(recommendations),
            "average_confidence": round(avg_conf, 2),
        },
        "experiment_3.2_conflict": {
            "conflicts_found": real_conflicts,
            "pairs_checked": len(conflicts),
        },
        "experiment_3.3_evaluation": {
            "consistency": round(consistency, 2),
            "novelty": round(novelty, 2),
            "coverage": round(coverage, 2),
        },
    }

    eval_path = output_dir / "evaluation.yaml"
    with open(eval_path, "w", encoding="utf-8") as f:
        yaml.dump(eval_result, f, allow_unicode=True, sort_keys=False)

    print(f"\n一致性: {consistency:.2f}")
    print(f"新颖性: {novelty:.2f}")
    print(f"覆盖率: {coverage:.2f}")
    print(f"\n全部结果已输出到: {output_dir}/")
    print(f"  recommendations.yaml")
    print(f"  conflicts.yaml")
    print(f"  evaluation.yaml")


if __name__ == "__main__":
    main()
