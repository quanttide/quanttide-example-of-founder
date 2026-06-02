# p02 写作云 HTML PoC

UI 分解验证序列。

## 层级

```
基础组件（单文件，零依赖）
├── layout.html        三栏 flex 布局 + 分隔条拖动
├── editor.html        Markdown 编辑 + 块级预览切换
├── dashboard.html     3R 阶段机（Review→Reflect→Rewrite 禁用链）
├── review.html        评审报告卡片（空隙列表 + 风格条 + 评分）
├── situation.html     情境引导卡片 + 上/下条导航
└── gap-markers.html   空隙标记圆点 + 悬停 tooltip + 点击跳转

组合验证（依赖基础组件）
└── index.html         合成工作台：layout + gap-markers + dashboard + review + situation
```

## 设计约定

所有 PoC 共用以下设计 token，Flutter 版直接映射为 ThemeData：

```css
:root {
  --bg: #1a1b1e;        /* 背景 */
  --surface: #25262b;   /* 面板底色 */
  --surface2: #2c2e33;  /* 卡片/输入区底色 */
  --border: #373a40;    /* 分隔线 */
  --text: #c1c2c5;      /* 正文 */
  --text-dim: #909296;  /* 次要文字 */
  --accent: #7c9bff;    /* Review / 主色 */
  --accent2: #69db7c;   /* Rewrite / 完成色 */
  --accent3: #ffd43b;   /* 警告 / 中优先级 */
  --red: #ff6b6b;       /* 低优先级 */
  /* 布局 */
  --panel-min: 120px;   /* 左栏最小宽 */
  --situ-min: 180px;    /* 右栏最小宽 */
  --line-h: 1.8;        /* 编辑器行高 */
  --font-size: 15px;    /* 编辑器字号 */
}
```

## 验证记录

| 文件 | 已验证 | 未通过项 |
|------|--------|---------|
| layout.html | flex 三栏、分隔条拖动 | — |
| gap-markers.html | 圆点渲染、悬停 tooltip、点击跳行 | — |
| dashboard.html | Review→Reflect→Rewrite 禁用链 | — |
| review.html | 空隙列表、风格进度条 | — |
| situation.html | 引导卡片、导航 | — |
| editor.html | Markdown 编辑、块级预览 | — |
