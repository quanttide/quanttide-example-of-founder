# 产品蓝图 CLI — 路线图

产品蓝图目前已有一套多视角定义文档（product/design/architecture），通过 Agent Skill 调用。下一步升级为独立命令行工具。

## Phase 0 — 当前状态

Markdown 定义文件 + Agent Skill 调用。依赖 AI 代理理解框架并生成对应文档。

- `skills/product-blueprint/`：三视角规范文档
- 使用方式：`skill: product-blueprint product`（Agent 层）
- 局限：无独立 CLI，依赖特定 Agent 环境

## Phase 1 — CLI 基础

MVP：一个可执行的 CLI 工具，支持蓝图文件的初始化和基本生成。

目标验证：蓝图框架脱离 Agent 环境也能使用。

```
product-blueprint init                    → 创建 product.md / design.md / architecture.md
product-blueprint generate product       → 从模板生成产品视角分析文档
product-blueprint generate design        → 从模板生成设计视角分析文档
product-blueprint generate architecture  → 从模板生成技术视角分析文档
product-blueprint generate all           → 生成完整三视角蓝图
```

产出：
- 可执行二进制，发布到 GitHub Releases
- `init` 子命令：在目标项目目录初始化蓝图文件
- `generate` 子命令：从规范文件生成分析文档骨架

## Phase 2 — 代码分析集成

CLI 读取源码目录，输出结构化的分析文档，减少人工编写负担。

```
product-blueprint scan src/              → 分析源码结构，输出项目摘要
product-blueprint generate architecture  → 基于 scan 结果填充技术视角
```

能力：
- 解析项目文件树、识别技术栈
- 识别组件/模块结构（按语言适配）
- 将分析结果填入 architecture.md 的对应章节

## Phase 3 — 蓝图 diff 与版本追踪

每次迭代跟踪蓝图变化，支持增量更新。

```
product-blueprint diff                   → 对比当前代码与上一轮 blueprint 的差距
product-blueprint update                 → 按 diff 结果更新 blueprint 文件
```

能力：
- 记录每次 blueprint 快照
- 跨版本对比：哪些章节变了、哪些承诺未兑现
- 迭代历史可回溯

## Phase 4 — 多项目管理

支持在同一 CLI 中管理多个产品的蓝图。

```
product-blueprint list                   → 列出所有受管理的产品项目
product-blueprint switch <project>       → 切换当前产品上下文
product-blueprint init --project <name>  → 为新项目初始化蓝图
```

能力：
- 配置文件统一管理多个产品目录
- 每个产品独立维护 blueprint 版本
- 跨产品视角复用（如共享 design-language）

---

## 里程碑

| Phase | 产出 | 验证标准 |
|-------|------|---------|
| 1 | CLI 可用，支持 init + generate | 在 qtgame-weiqi 上跑通 init + generate all |
| 2 | scan 可输出项目结构 | architecture.md 的技术栈/模块部分自动填充 |
| 3 | diff 可追踪版本变化 | 两次迭代后能看出蓝图哪部分过时 |
| 4 | 支持 3+ 产品同时管理 | qtgame-weiqi / qtgame-war / 其他项目统一管理 |

## 非目标

- 不替代人工撰写 product.md（产品的用户价值和决策取舍必须由人定义）
- 不生成代码，只生成分析文档
- 不做项目管理或工单追踪
