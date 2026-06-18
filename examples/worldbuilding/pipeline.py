#!/usr/bin/env python3
"""
故事抽取流水线：小说原文 → 结构化故事数据

用法:
  ./pipeline.py fiction.yaml --model ontology.yaml -o story.yaml

流程:
  1. 世界观抽取 (worldbuilding) — 人物/场景/时间线/主题/张力/情感地理
  2. 母题抽取 (motif) — 叙事重复模式
  3. 合并 → story.yaml + story.json
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import yaml


def run_extract(input_path: Path, output_dir: Path, extract_type: str, model: Path | None = None):
    cmd = ["qtadmin", "knowl", "extract",
           "--input", str(input_path),
           "--type", extract_type,
           "--output", str(output_dir)]
    if model:
        cmd += ["--model", str(model)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"抽取失败 ({extract_type}): {result.stderr}")
    print(result.stderr, end="", file=sys.stderr)


def merge(source_yaml: str, wb_dir: Path, motif_dir: Path) -> dict:
    story = {"source": source_yaml}

    # 世界观抽取结果
    wb_file = wb_dir / "worldbuilding.yaml"
    if wb_file.exists():
        data = yaml.safe_load(wb_file.read_text())
        if data and "worldbuilding" in data and len(data["worldbuilding"]) > 0:
            record = data["worldbuilding"][0]
            for key in ["characters", "setting", "emotional_geography",
                        "timeline", "themes", "tensions"]:
                if key in record:
                    story[key] = record[key]

    # 母题抽取结果
    motif_file = motif_dir / "motifs.yaml"
    if motif_file.exists():
        data = yaml.safe_load(motif_file.read_text())
        if data and "motifs" in data:
            story["motifs"] = []
            for m in data["motifs"]:
                story["motifs"].append({
                    "name": m.get("motif") or m.get("motif_name", ""),
                    "type": m.get("motif_type", ""),
                    "sub_type": m.get("motif_subtype", ""),
                    "description": m.get("description", ""),
                    "excerpt": m.get("excerpt", ""),
                })

    # 风格
    style_file = motif_dir / "styles.yaml"
    if style_file.exists():
        data = yaml.safe_load(style_file.read_text())
        if data and "styles" in data and len(data["styles"]) > 0:
            s = data["styles"][0]
            story["style"] = {
                "name": s.get("style_name", ""),
                "tags": s.get("tags", []),
            }

    return story


def main():
    parser = argparse.ArgumentParser(description="故事抽取流水线")
    parser.add_argument("input", type=Path, help="小说 YAML 文件 (entries 格式)")
    parser.add_argument("--model", "-m", type=Path, default=None, help="ontology 模型文件")
    parser.add_argument("--output", "-o", type=Path, default=Path("story.yaml"), help="输出文件")
    args = parser.parse_args()

    source_name = args.input.name

    with tempfile.TemporaryDirectory(prefix="storypipe_") as tmp:
        tmp_dir = Path(tmp)
        wb_dir = tmp_dir / "worldbuilding"
        motif_dir = tmp_dir / "motif"

        print("1/3 世界观抽取...", file=sys.stderr)
        run_extract(args.input, wb_dir, "worldbuilding", args.model)

        print("2/3 母题抽取...", file=sys.stderr)
        run_extract(args.input, motif_dir, "motif")

        print("3/3 合并...", file=sys.stderr)
        story = merge(source_name, wb_dir, motif_dir)

    out_path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.dump(story, allow_unicode=True, sort_keys=False))

    json_path = out_path.with_suffix(".json")
    json_path.write_text(json.dumps(story, ensure_ascii=False, indent=2))

    print(f"完成: {out_path} + {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
