# p02 写作云 HTML PoC

UI 分解验证序列。每个文件验证一个独立交互，互不依赖。

## PoC 列表

| # | 文件 | 验证目标 | 行数 |
|---|------|---------|------|
| 1 | `layout.html` | 三栏 Grid + 面板可拖动 resize（无 JS 逻辑） |
| 2 | `gutter.html` | 空隙标记：编辑器左侧圆点显示可写位置，悬停看详情，点击跳转 |
| 3 | `dashboard.html` | 3R 阶段机 + 仪表盘（Review → Reflect → Rewrite 推进） |
| 4 | `review.html` | 评审报告卡片：空隙列表 + 风格进度条 + 综合评分 |
| 5 | `situation.html` | 情境引导语展示 + 多引导切换 |
| 6 | `editor.html` | Markdown 编辑 + 块级感知预览切换 |

## 设计原则

- 每个文件 ≤ 150 行，单文件零依赖
- 无共享状态，无跨文件耦合
- 验证通过后，Flutter 版直接复用交互模型
