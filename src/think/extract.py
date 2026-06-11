#!/usr/bin/env python3
"""
实验 1.1.3: 从 memory 中识别情境

用法: python3 extract.py <memory_dir> [--output <output_dir>]
"""

import re
import sys
import os
import yaml
from pathlib import Path
from datetime import datetime

SITUATION_SCHEMA_PATH = Path(__file__).parent / "situation.yaml"


def load_memory_files(memory_dir):
    """加载所有 memory 文件路径"""
    memory_dir = Path(memory_dir)
    files = []
    for ext in ["*.md"]:
        for f in sorted(memory_dir.rglob(ext)):
            if f.name in ("README.md", "AGENTS.md", "CHANGELOG.md"):
                continue
            files.append(f)
    return files


def infer_date_from_filename(filepath):
    """从文件名推断日期 (journal/YYYY-MM-DD.md -> 日期)"""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", str(filepath))
    if m:
        return m.group(1)
    return None


def detect_time(text):
    """检测时间表述"""
    patterns = [
        (r"今天(上午|下午|晚上|中午|早上|傍晚|凌晨)?", lambda m: f"今天{m.group(1) or ''}"),
        (r"明天(上午|下午|晚上|中午|早上)?", lambda m: f"明天{m.group(1) or ''}"),
        (r"(上午|下午|晚上|中午|早上|凌晨)\s*\d+[点时]", lambda m: m.group(0)),
        (r"\d{1,2}:\d{2}", lambda m: m.group(0)),
    ]
    for pattern, formatter in patterns:
        m = re.search(pattern, text)
        if m:
            return formatter(m)
    return None


def detect_mood(text):
    """检测情绪表述"""
    positive = ["高兴", "开心", "不错", "很好", "满意", "有信心", "调节过来", "轻松"]
    negative = ["不安", "担心", "焦虑", "疲惫", "累", "冲击", "压力", "困难", "烦", "没信心"]
    high_arousal = ["冲击", "紧张", "兴奋", "急", "快速"]
    low_arousal = ["休息", "睡觉", "放松", "缓", "消化"]

    found_valence = 0
    found_arousal = 1
    raw_terms = []

    for w in positive:
        if w in text:
            found_valence += 1
            raw_terms.append(w)
    for w in negative:
        if w in text:
            found_valence -= 1
            raw_terms.append(w)

    for w in high_arousal:
        if w in text:
            found_arousal += 2
            raw_terms.append(w)
    for w in low_arousal:
        if w in text:
            found_arousal = max(0, found_arousal - 1)
            raw_terms.append(w)

    found_valence = max(-3, min(3, found_valence))
    found_arousal = max(0, min(5, found_arousal))

    return {
        "raw": "、".join(set(raw_terms)) if raw_terms else None,
        "valence": found_valence,
        "arousal": found_arousal,
    }


def extract_situations(filepath, inferred_date):
    """从单个文件中提取情境"""
    text = filepath.read_text(encoding="utf-8")
    paragraphs = re.split(r"\n\s*\n", text.strip())

    situations = []
    for pi, para in enumerate(paragraphs):
        para = para.strip()
        if not para or len(para) < 10:
            continue

        lines = para.split("\n")
        mood = detect_mood(para)
        time_raw = detect_time(para)

        situation = {
            "id": f"s-{inferred_date}-{pi+1:03d}" if inferred_date else f"s-{pi+1:03d}",
            "source": {
                "file": str(filepath),
                "line_start": 1,
                "line_end": 1 + len(lines),
            },
            "time": {
                "raw": time_raw,
                "inferred_date": inferred_date,
            },
            "location": None,
            "participants": [],
            "activity": para[:80] + ("..." if len(para) > 80 else ""),
            "mood": mood,
            "_raw": para,
        }

        # 简单参与者检测
        people_patterns = [
            r"(?:团队|大家|同事|合伙人|秘书|总裁|技术|财务|人事|秘书长|副秘书长)",
            r"(?:我|我们|他们|他|她)",
        ]
        found_people = set()
        for pat in people_patterns:
            for m in re.finditer(pat, para):
                found_people.add(m.group(0))
        if found_people:
            situation["participants"] = sorted(found_people)

        # 地点检测
        loc_patterns = [
            r"(?:在|到|去)(\w+(?:办公室|会议室|家|实验室|公司|云|现场))",
            r"(?:\w+(?:办公室|会议室|家|实验室|公司))",
        ]
        for pat in loc_patterns:
            m = re.search(pat, para)
            if m:
                situation["location"] = m.group(0) if m.lastindex else m.group(0)
                break

        situations.append(situation)

    return situations


def main():
    import argparse

    parser = argparse.ArgumentParser(description="从 memory 中识别情境")
    parser.add_argument("memory_dir", nargs="?", default=os.path.join(os.path.dirname(__file__), "../../data"), help="memory 目录路径 (默认: ../../data)")
    parser.add_argument("--output", "-o", default="output", help="输出目录 (默认: output)")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = load_memory_files(args.memory_dir)
    print(f"找到 {len(files)} 个 memory 文件")

    all_situations = []
    for f in files:
        inferred_date = infer_date_from_filename(f)
        situations = extract_situations(f, inferred_date)
        all_situations.extend(situations)
        print(f"  {f.relative_to(args.memory_dir) if args.memory_dir else f.name}: {len(situations)} 个情境")

    # 清理 _raw 字段，输出完整结果
    clean = []
    for s in all_situations:
        s.pop("_raw", None)
        clean.append(s)

    output_file = output_dir / "situations.yaml"
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump({"situations": clean}, f, allow_unicode=True, sort_keys=False)
    print(f"\n结果已输出: {output_file}")
    print(f"共识别 {len(clean)} 个情境")


if __name__ == "__main__":
    main()
