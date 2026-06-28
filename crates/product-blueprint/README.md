# 产品蓝图工具

多视角产品定义框架，用于 AI 写代码后的校验与迭代循环。

## 核心思想

每个产品同时存在三个视角，各自回答一个核心问题：

| 视角 | 核心问题 | 文件 |
|------|---------|------|
| 产品 | 做的是不是用户要的？ | `product.md` |
| 设计 | 体验是否到位？ | `design.md` |
| 设计语言 | 布局与交互原则是什么？ | `design-language.md` |
| 技术 | 做得对不对？ | `architecture.md` |

三个视角共同定义产品，缺一不可。单视角决策一定会出问题。

## 工作循环

```
产品蓝图（多视角定义）
    → AI 写代码
    → 多视角 dev 文档解释（校验回蓝图）
    → 反馈修正蓝图或代码
    → ...
```

每次循环的产出是 `docs/dev/` 下的三个文件，对应当前代码快照的分析。

## 使用方式

产品蓝图是一组规范文档，由 Agent Skill 调用：

```
skill: product-blueprint product      → 输出 docs/dev/product.md
skill: product-blueprint design       → 输出 docs/dev/design.md
skill: product-blueprint architecture → 输出 docs/dev/architecture.md
```

不指定参数时输出完整三视角蓝图。

## 来源

此框架源自 [qtgame-weiqi](https://github.com/quanttide/qtgame-weiqi) 项目的开发实践，作为 Skill 封装在 `.agents/product-blueprint/` 中使用。本目录为独立后的工具版本。
