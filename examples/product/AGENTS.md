# AGENTS.md

## 项目文档

| 文档 | 用途 |
|------|------|
| `README.md` | 项目概述、核心思想、工作循环 |
| `ROADMAP.md` | 路线图（Phase 0-4） |
| `TODO.md` | Phase 1 实现任务清单 |

## 目录结构

```
product/
├── Cargo.toml              # Rust 项目配置（name = "product-blueprint"）
├── src/main.rs             # CLI 入口
├── README.md               # 项目说明
├── ROADMAP.md              # 路线图
├── TODO.md                 # Phase 1 任务清单
└── skills/product-blueprint/   # 三视角规范文档（模板源）
    ├── SKILL.md
    ├── product.md
    ├── design.md
    ├── design-language.md
    └── architecture.md
```

## 核心概念

产品蓝图 = 三视角定义 + AI 写代码 + dev 文档校验的迭代循环。

每个视角回答一个核心问题：

| 视角 | 文件 | 核心问题 |
|------|------|---------|
| 产品 | `product.md` | 做的是不是用户要的？ |
| 设计 | `design.md` | 体验是否到位？ |
| 设计语言 | `design-language.md` | 布局与交互原则是什么？ |
| 技术 | `architecture.md` | 做得对不对？ |

## 当前阶段

Phase 1 — CLI 基础。从 Agent Skill 升级为独立的命令行工具。

核心任务（详见 `TODO.md`）：
- `init` 子命令：在目标项目初始化蓝图文件
- `generate` 子命令：从规范生成分析文档骨架
- Rust + clap 实现，内嵌模板

## Git 规范

- 提交类型：`feat` / `docs` / `chore`
- 本目录属于 `examples/default` 子模块，提交后需更新主仓库引用

## 重要提示

- 规范文档在 `skills/product-blueprint/` 下，Rust 二进制内嵌为模板
- init 写入目标项目目录，generate 输出到 `docs/dev/`
- 不替代人工撰写 product.md（用户价值和决策取舍必须由人定义）
