# 实验 3.1: 小说世界观抽取

## 目标

用 `qtadmin knowl extract` 从职场言情小说片段中自动抽取结构化世界观要素，验证 CLI 抽取工具在叙事分析场景下的效果。

## 文件

| 文件 | 用途 |
|------|------|
| `fiction.yaml` | 小说片段（职场言情·海边再散步） |
| `ontology.yaml` | 世界观模型声明（characters, relationship, setting, emotional_geography, timeline, themes, tensions） |
| `story.yaml` | 合并后的完整抽取结果（含 worldbuilding + motifs + style） |
| `story.json` | 同上，JSON 格式 |
| `index.html` | 可视化展示 |

## 用法

```bash
# 1. 世界观抽取
qtadmin knowl extract --type worldbuilding \
  --input examples/worldbuilding/fiction.yaml \
  --model examples/worldbuilding/ontology.yaml \
  --output out/worldbuilding

# 2. 母题抽取
qtadmin knowl extract --type motif \
  --input examples/worldbuilding/fiction.yaml \
  --output out/motif
```

## 扩展

替换 `fiction.yaml` 中的内容为你自己的小说片段，重新运行即可获得世界观和母题结果。

修改 `ontology.yaml` 中的 `fields` 定义可自定义抽取维度——CLI 会自动编译为 JSON Schema 约束 LLM 输出格式。
