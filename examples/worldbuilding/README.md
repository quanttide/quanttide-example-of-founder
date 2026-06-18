# 实验 3.1: 小说世界观抽取

## 目标

用 `qtadmin knowl extract` 从小说片段中自动抽取结构化世界观要素，验证 CLI 抽取工具在虚构叙事分析场景下的效果。

## 文件

| 文件 | 用途 |
|------|------|
| `fiction.yaml` | 示例小说片段（悬空城塞世界观） |
| `ontology.yaml` | 世界观模型声明（cosmology, geography, societies, characters, magic_system, history, tensions） |

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

| 类别 | 示例 |
|------|------|
| cosmology | 群星是巨兽鳞片、星能衰竭、深空观测禁忌 |
| geography | 碎星群岛、悬空城塞鸦巢、银渊陨坑 |
| societies | 鸦巢议事团、军需派、渔民派、老学者派 |
| characters | 埃莉斯（城主）、维托（军需官） |
| magic_system | 祈星术、星锚、星能核心、符文阵图 |
| history | 初代城主钉星锚（300年前）、银渊陨落（50年前） |
| tensions | 生存 vs 禁忌、传统 vs 变革 |

## 扩展

替换 `fiction.yaml` 中的内容为你自己的小说片段，重新运行即可获得世界观图谱。

修改 `ontology.yaml` 中的 `fields` 定义可自定义抽取维度——CLI 会自动编译为 JSON Schema 约束 LLM 输出格式。
