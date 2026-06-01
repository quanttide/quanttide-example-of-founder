# p08 仓库备份网关 — 实验方案

## 实验目的

验证跨 GitHub 组织的自动化只读备份是否可行、配置是否简单、恢复是否可靠。

## 背景

日志 2026-06-01："命令行删库比较容易，既带来了便利也带来了风险"、"只读备份这件事情要提上日程"、"分发代码也是一种备份"。

## 实验假设

1. 用 GitHub Actions + `gh` CLI 可以实现组织间定时镜像，无需第三方服务
2. 备份目标仓库设为 `--private` 只读，源仓库删除后可从备份恢复
3. 配置驱动而非脚本驱动，新增仓库只需修改配置文件

## 实验设计

### 场景 1：单仓库备份

将 `quanttide-laboratory-of-game-developing` 从 `quanttide` 组织镜像到备份组织 `quanttide-backup`，验证：

- repo 创建（含描述、license）
- git 全量镜像（所有分支、tags）
- Actions artifacts 不备份
- 备份仓库设为 `--private --template` 只读

### 场景 2：批量配置

定义一个 YAML 配置文件，列出所有需备份的仓库：

```yaml
# backup-config.yaml
source_org: quanttide
target_org: quanttide-backup
repos:
  - quanttide-laboratory-of-game-developing
  - quanttide-laboratory-of-human-resources
  - quanttide-laboratory-of-organization
  - quanttide-laboratory-of-execution
  - quanttide-laboratory-of-business-entity
  - quanttide-laboratory-of-innovation
  - quanttide-example-of-founder
  - quanttide-founder
schedule: daily
```

### 场景 3：模拟灾难恢复

- 模拟源仓库被删除
- 从备份仓库恢复到新组织
- 验证所有内容（分支、tags、issues？）完整

## 评价标准

| 指标 | 合格线 | 优秀线 |
|------|--------|--------|
| 单仓库备份 | 成功 | 成功 |
| 批量配置 | 5 个仓库 | 全部仓库 |
| 备份耗时 | < 5min | < 2min |
| 灾难恢复 | 仓库 + 分支完整 | tags 也完整 |
| 配置变更 | 手动改配置 | PR 触发自动同步 |

## 原型实现

不写 UI，产出为：

1. `backup-config.yaml` — 配置文件模板
2. `.github/workflows/backup.yml` — GitHub Actions 工作流
3. `scripts/restore.sh` — 恢复脚本
4. `docs/backup.md` — 操作手册

## 下一步

备份跑通后，加入仓库创建 webhook，实现新增仓库自动加入备份列表。
