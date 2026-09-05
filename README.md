# 量潮创始人实验室

将方法论翻译为可执行程序的实验场。

## 核心模型

仓库按「规格—数据—实现」三层组织：

| 层 | 位置 | 性质 |
|----|------|------|
| 规格 | `docs/` | 待翻译为代码的方法论。每篇描述明确的输入输出与处理规则，是实现的依据 |
| 数据 | `data/` | 程序的输入与运行数据。按主题分组（fiction / agent / work），结构化是演进方向 |
| 实现 | `src/` | 代码。以 `docs/` 为规格实现，以 `data/` 为输入运行验证 |

## 目录结构

```
docs/
  fiction/   素材转化、精修等方法论
  work/      工作习惯等行为规则
  agent/     情绪结构化处理流程
data/
  fiction/   情节线、人物弧光等工作数据
  agent/     推演实例、反思素材
  work/      工作方式语料
src/         CLI 骨架与各工具实现
```

## 当前状态

- 双入口架构：`lab`（CLI，无显示环境可用）与 `lab-gui`（eframe/egui），领域逻辑统一在 `laboratory_core`（`src/lib.rs`）
- 「前言精修」已实现：经 quanttide-agent 接入 LLM，规格 `docs/fiction/fiction-revision.md`
  - CLI：`lab revision <文件路径>`（传 `-` 从 stdin 读取）
  - GUI：`lab-gui` 粘贴文本评估
- 「素材改编」下一个实现：规格 `docs/fiction/fiction-adaptation.md`
- `data/knowl/` 模型约束、其余篇目待排期

## 工作方式

1. 修改方法论：先改 `docs/`，再评估代码影响
2. 补充素材：直接进 `data/` 对应主题目录
3. 实现功能：以 `docs/` 对应篇目为验收标准
4. 实验过程记录到实验日志，保持文档与实际进展一致
