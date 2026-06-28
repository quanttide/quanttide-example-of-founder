# Phase 1 TODO

## CLI 脚手架

- [ ] 引入 clap，定义子命令结构（init / generate）
- [ ] 实现 `--help` 输出完整的命令说明
- [ ] 实现版本号输出（`--version`，从 Cargo.toml 读取）

## init 子命令

- [ ] 实现 `product-blueprint init`：在当前目录创建蓝图文件
  - 输出 `product.md`、`design.md`、`design-language.md`、`architecture.md`
  - 内容来自嵌入的规范模板
- [ ] 支持 `--path` 参数：指定目标目录（默认为当前目录）
- [ ] 支持 `--force` 参数：覆盖已有文件

## generate 子命令

- [ ] 实现 `product-blueprint generate product`：输出产品视角分析文档骨架
- [ ] 实现 `product-blueprint generate design`：输出设计视角分析文档骨架
- [ ] 实现 `product-blueprint generate architecture`：输出技术视角分析文档骨架
- [ ] 实现 `product-blueprint generate all`：输出完整三视角文档
- [ ] generate 输出写入 `docs/dev/` 目录
- [ ] 如果 `docs/dev/` 已有同名文件，提示是否覆盖

## 模板管理

- [ ] 将 `skills/product-blueprint/` 下的四个规范文件内嵌到二进制（`include_str!` 或 embed 机制）
- [ ] init 命令从内嵌模板写入目标目录
- [ ] generate 命令从规范文件生成骨架（不是复制模板，是按章节结构生成填空模板）

## 工程基建

- [ ] `cargo build` 无 warning 通过
- [ ] `cargo clippy` 通过
- [ ] 基本集成测试：init → 文件存在 → generate → docs/dev/ 文件存在
- [ ] `cargo test` 通过
- [ ] `.gitignore` 添加 `target/`

## CI / 发布

- [ ] GitHub Actions：PR 时运行 `cargo test && cargo clippy`
- [ ] GitHub Actions：tag 时构建 release binary 并上传
- [ ] Release 流程接入 `qtcloud-devops release publish`

## 验证

- [ ] 在 qtgame-weiqi 项目目录执行 `product-blueprint init && product-blueprint generate all`
  - 产出 `product.md` / `design.md` / `architecture.md` 三个文件
  - 生成到 `docs/dev/` 目录
