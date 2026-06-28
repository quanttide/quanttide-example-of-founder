---
name: product-blueprint
description: >
  产品蓝图，从产品、设计、技术三个视角对代码进行解释和校验。
  用于 AI 写代码后的多视角文档生成。三个视角文件在同一目录下：
  product.md、design.md、architecture.md。
argument-hint: "[product|design|architecture]"
---

# 产品蓝图 (Product Blueprint)

产品蓝图是"AI 写代码 → dev 文档解释 → 反馈回蓝图"循环的中枢。每个视角回答一个核心问题：

```
               ┌──────────────┐
               │  产品蓝图     │
               └──────┬───────┘
                      │ 驱动
                      ▼
            ┌─────────────────────┐
            │  AI 写代码 / 改代码 │
            └──────────┬──────────┘
                       │ 触发
                       ▼
         ┌──────────────────────────┐
         │  多视角解释（校验回蓝图） │
         │  product.md  ← 做的是用户要的？│
         │  design.md   ← 体验到位？     │
         │  architecture.md ← 技术对？   │
         └──────────┬───────────────┘
                    │ 反馈/修正
                    ▼
               产品蓝图 迭代
```

## 视角文件

| 视角 | 文件 | 核心问题 |
|------|------|---------|
| 产品 | `product.md` | 做的是不是用户要的？ |
| 设计 | `design.md` | 体验是否到位？ |
| 设计语言 | `design-language.md` | 布局与交互原则是什么？ |
| 技术 | `architecture.md` | 做得对不对？ |

## 使用方式

对当前源码执行单个视角的分析：

```
使用 product-blueprint product SKILL      → 输出 docs/dev/product.md
使用 product-blueprint design SKILL       → 输出 docs/dev/design.md
使用 product-blueprint architecture SKILL  → 输出 docs/dev/architecture.md
```

不指定参数时默认输出三个视角的完整蓝图，全部写入 `docs/dev/`。

每次循环的分析产物是对应于当前代码快照的 dev 文档，反映的是**这一轮**的实现状态。

## 维护说明

每次循环迭代后，如蓝图定义发生变化（新增视角、调整维度、修改自检项），直接编辑对应 `.md` 文件。
