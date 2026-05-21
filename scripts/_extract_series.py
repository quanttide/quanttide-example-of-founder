#!/usr/bin/env python3
"""
按故事系列合并抽取知识库。

将同一故事系列的所有 .md 文件合并送入 LLM，
避免每文件独立成一 domain 导致碎片化。
"""

import json
import os
import sys
import uuid
from pathlib import Path

# 目标输出目录
OUTPUT_DIR = Path(__file__).parent

# 项目根
PROJECT = Path(__file__).parent.parent.parent.parent

# 故事系列定义：名称 -> (源文件列表, 描述)
SERIES = {
    "night-market-dating": {
        "files": [
            "职场言情/4_成稿/4_2_夜市约会.md",
            "职场言情/4_成稿/2_3_傍晚小龙虾.md",
            "职场言情/4_成稿/4_1_便利店闲坐.md",
            "职场言情/4_成稿/4_3_互相问早.md",
            "职场言情/4_成稿/9_1_家里吃火锅.md",
            "职场言情/4_成稿/6_2_海边散步.md",
            "职场言情/4_成稿/8_2_公园拥抱.md",
        ],
        "label": "夜市约会系列",
        "desc": "都市职场言情系列，讲述陆知微和林远亭（他/她）从重逢到相恋的日常故事，涵盖夜市约会、小龙虾、便利店闲坐、海边散步等温馨场景。",
    },
    "late-night-insomnia": {
        "files": [
            "职场言情/4_成稿/1_2_深夜失眠.md",
            "职场言情/4_成稿/2_1_展会再遇.md",
        ],
        "label": "深夜失眠",
        "desc": "十年前暗恋与重逢后的深夜失眠，双视角叙事，细腻心理描写。",
    },
    "chenggao": {
        "files": [
            "职场言情/4_成稿/10_1_书房陪伴.md",
        ],
        "label": "成稿",
        "desc": "书房陪伴——女主角在书房帮男主角整理书桌时发现了一封写给19岁自己的信，深受感动。",
    },
    "workplace-sample": {
        "files": [
            "职场言情/1_样文/咖啡厅重逢.md",
            "职场言情/1_样文/赏雪谈心.md",
            "职场言情/1_样文/男主分享.md",
            "职场言情/1_样文/男主日记.md",
            "职场言情/1_样文/女主吐槽.md",
            "职场言情/1_样文/同事评价男主.md",
        ],
        "label": "职场言情样文",
        "desc": "职场言情系列的样文片段，包含咖啡厅重逢、赏雪谈心、男主日记等不同场景的写作尝试。",
    },
    "workplace-outline": {
        "files": [
            "职场言情/2_提纲/2_1_行业论坛.md",
            "职场言情/2_提纲/行业论坛.md",
            "职场言情/2_提纲/会议室辩论.md",
            "职场言情/2_提纲/未来工作日常.md",
        ],
        "label": "职场言情提纲",
        "desc": "职场言情系列的提纲设计，包括行业论坛、会议室辩论、未来工作日常等情节规划。",
    },
    "campus-romance": {
        "files": [
            "校园言情/3_初稿/4_第四章.md",
            "校园言情/3_初稿/5_第五章.md",
            "校园言情/3_初稿/6_第六章.md",
        ],
        "label": "校园言情",
        "desc": "以鹭岛大学（原型厦大）为背景的校园恋爱故事，女主林栀（新传院花），男主逸神（经院学术天才），因医院偶遇结缘。",
    },
}


def load_series_content(series_name: str, files: list[str]) -> str:
    """加载系列所有文件内容"""
    parts = []
    for rel_path in files:
        fp = PROJECT / "docs" / "fiction" / rel_path
        if not fp.exists():
            print(f"  [WARN] 文件不存在: {fp}", file=sys.stderr)
            continue
        content = fp.read_text(encoding="utf-8")
        title = fp.stem
        parts.append(f"## 文件: {rel_path}\n\n{content}\n")
    return "\n\n---\n\n".join(parts)


def main():
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get(
        "LLM_BASE_URL", "https://api.openai.com/v1"
    )
    model = os.environ.get("LLM_MODEL", "gpt-4o")

    if not api_key:
        print("错误: 需要设置 OPENAI_API_KEY 或 LLM_API_KEY", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)

    for series_name, info in SERIES.items():
        out_dir = OUTPUT_DIR / series_name
        out_dir.mkdir(parents=True, exist_ok=True)

        # 如果已有结果则跳过
        if (out_dir / "domain.json").exists():
            print(f"[跳过] {series_name} 已存在")
            continue

        print(f"\n[抽取] {series_name} ({info['label']})...")

        content = load_series_content(series_name, info["files"])
        if not content.strip():
            print(f"  [WARN] 无内容，跳过")
            continue

        prompt = f"""你是一个小说知识抽取专家。请从以下小说文件中提取结构化知识，输出 JSON 格式。

领域信息：
- name: {series_name}
- label: {info["label"]}
- description: {info["desc"]}

要求：
1. 分析所有文件内容，识别出统一的角色、物品、地点、情感、事件等实体
2. 本体(ontologies)是实体类型，每个 ontology 包含: id (UUID), name, label, description
3. 实例(instances)是具体的实体，每个 instance 包含: id (UUID), name, label, description
4. 关系(relations)描述实例之间的关联，每个 relation 包含: id (UUID), name, label, description, source (源实例id), target (目标实例id)

请输出以下 JSON 结构：
{{
  "domain": {{
    "id": "UUID",
    "name": "{series_name}",
    "label": "{info["label"]}",
    "description": "{info["desc"]}"
  }},
  "ontologies": [...],
  "instances": [...],
  "relations": [...]
}}

注意事项：
- 不同文件中出现的同一角色/物品应合并为同一个实例（使用相同 name）
- 跨文件的同一关系也应合并
- 如果两个文件描述同一场景的不同视角，应整合成一个完整视图
- 语言使用中文
- id 用 UUID4 格式
"""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的知识工程助手。请严格按 JSON 格式输出，不要包含任何额外文字。",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "text",
                            "text": f"\n\n以下是源文件内容：\n\n{content[:80000]}",
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        result_text = response.choices[0].message.content
        if not result_text:
            print(f"  [FAIL] LLM 返回空", file=sys.stderr)
            continue

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            print(f"  [FAIL] JSON 解析失败", file=sys.stderr)
            print(f"  原始响应: {result_text[:200]}", file=sys.stderr)
            continue

        # 写入文件
        domain = result.get("domain", {})
        ontologies = result.get("ontologies", [])
        instances = result.get("instances", [])
        relations = result.get("relations", [])

        with open(out_dir / "domain.json", "w", encoding="utf-8") as f:
            json.dump(domain, f, ensure_ascii=False, indent=2)

        with open(out_dir / "ontologies.json", "w", encoding="utf-8") as f:
            json.dump({"ontologies": ontologies}, f, ensure_ascii=False, indent=2)

        with open(out_dir / "instances.json", "w", encoding="utf-8") as f:
            json.dump({"instances": instances}, f, ensure_ascii=False, indent=2)

        with open(out_dir / "relations.json", "w", encoding="utf-8") as f:
            json.dump({"relations": relations}, f, ensure_ascii=False, indent=2)

        print(
            f"  [OK] {len(ontologies)} 本体, {len(instances)} 实例, {len(relations)} 关系"
        )

    print(f"\n全部完成。输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
