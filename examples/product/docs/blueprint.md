# product-blueprint 蓝图

## 核心转变

review.md 揭示的关键洞察：代码的 "AI 监督人" 方向反了，应该是 **"AI 做事人审"**。

当前 generate 只产空骨架，LLM 调用缺失。check 在审空气。

## 改造方案

### generate 改 AI 生成

- 加 `--brief` 参数，接受产品简介
- 调用 LLM，传入完整模板 + brief，直接输出初稿
- 删除 `skeleton_from`（AI 不需要空骨架）
- 文件已存在时询问是否覆盖

### check 改辅助审查

不再质检打分，改为：

1. 逻辑矛盾或前后不一致
2. 模板要求但遗漏的内容
3. 明显不合理的技术/设计选型

### 工作流

```
init       → 释放模板（规则）
generate   → AI 读取模板 + brief，生成 docs/dev/ 初稿
人审        → 打开文件阅读修改
check      → 可选，AI 辅助找漏洞
```

### 已实现（2026-06-28）

- `generate` 接收 `--brief`，调用 LLM，输出到 `docs/dev/`
- `skeleton_from` 已删除
- `check` 提示词改辅助审查
- `--brief` 测试通过：围棋助手 demo 产出 196 行初稿
- 4 个 bug 修复：check 传模板、check 直出文本、路径统一用常量、init 删死代码

### 不变

- `init` 逻辑不变
- 模板文件（skills/product-blueprint/）不变
- Rust + clap 结构不变
