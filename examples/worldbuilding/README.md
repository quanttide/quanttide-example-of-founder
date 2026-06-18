# 实验 3.1: 小说世界观抽取

## 目标

用 `qtadmin knowl extract` 从职场言情小说片段中自动抽取结构化世界观要素，验证 CLI 抽取工具在叙事分析场景下的效果。

## 文件

| 文件 | 用途 |
|------|------|
| `fiction.yaml` | 小说片段（职场言情·海边再散步） |
| `ontology.yaml` | 世界观模型声明（characters, relationship, setting, emotional_geography, timeline, themes, tensions） |

## 用法

```bash
# 1. 确保 qtadmin CLI 已安装且 DEEPSEEK_API_KEY 已设置
export DEEPSEEK_API_KEY=sk-your-key

# 2. 运行抽取
qtadmin knowl extract --type worldbuilding \
  --input examples/worldbuilding/fiction.yaml \
  --model examples/worldbuilding/ontology.yaml \
  --output out/worldbuilding

# 3. 查看结果
cat out/worldbuilding/worldbuilding.yaml
```

## 预期产出

`out/worldbuilding/worldbuilding.yaml` 包含以下分类的结构化世界观要素：

| 类别 | 说明 |
|------|------|
| characters | 陆知微、林远亭：身份、性格、动机与弧光 |
| relationship | 恋人关系动态、十年的错过与重逢 |
| setting | 海边栈桥、阳光碧海的氛围与意义 |
| emotional_geography | 海边与孤独记忆、陪伴的绑定 |
| timeline | 十年前→低谷期→现在的关系演变 |
| themes | 治愈、错过、勇气、温柔 |
| tensions | 自卑vs勇气、过去vs现在、错过vs重逢 |

## 扩展

替换 `fiction.yaml` 中的内容为你自己的小说片段，重新运行即可获得世界观图谱。

修改 `ontology.yaml` 中的 `fields` 定义可自定义抽取维度——CLI 会自动编译为 JSON Schema 约束 LLM 输出格式。
