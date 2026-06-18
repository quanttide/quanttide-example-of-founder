# 实验 4.1: 场景关联图谱

## 目标

从多场景小说中提取场景之间的引用关系和叙事结构：前文回
调、前传依赖、时间线、情感回响。

## 文件

| 文件 | 用途 |
|------|------|
| `fiction.yaml` | 4 个关联场景（海边→动物园→咖啡馆→家，含交叉引用和前传） |
| `ontology.yaml` | 场景关联模型（scenes, forward_references, timeline_relationship, emotional_echoes） |

## 用法

```bash
qtadmin knowl extract --type scene-graph \
  --input examples/scene-graph/fiction.yaml \
  --model examples/scene-graph/ontology.yaml \
  --output out/scene-graph
```

## 场景关联概览

```
s001 海边（现在）──┬── 回 call back ── 三年前雨夜分手（off_screen）
                    ├── 情感回响 ── 同一地点，痛→暖
                    │
s002 动物园 ────────┬── 回调 ── s001 暴雨（角色提到）
                    ├── 前传 ── 十年前春游（off_screen）
                    │
s003 咖啡馆 ────────┬── 回 call back ── 三年前偶遇（off_screen）
                    ├── 回调 ── s002 动物园（"小王子的故事"）
                    │
s004 家 ────────────┬── 回调 ── s002 动物园（卡片提到企鹅）
                    ├── 回调 ── s003 咖啡馆（"小王子的故事"）
                    └── 情感回响 ── 卡片+合照 → 弥补空白
```
