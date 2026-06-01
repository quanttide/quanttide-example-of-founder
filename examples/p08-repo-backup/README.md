# p08 仓库备份网关 — 实验方案

## 实验目的

验证跨 GitHub 组织的自动化只读备份是否可行。手动备份太慢，不备份又怕误删。

## 背景

日志 2026-06-01：

> "命令行删库比较容易，就是说它既带来了便利也带来了风险"
> "只读备份这件事情要提上日程，要不然，而且仓库很多，手动操作会比较麻烦，需要自动操作"
> "分发代码也是一种备份，就是说把这个版本的代码固定下来"

现在有 7+ 个实验室仓库分布在 `quanttide` 组织下，全部手动备份不现实。需要一个自动化的只读备份方案。

## 实验假设

1. GitHub Actions 定时任务 + `gh` CLI 可以实现组织间镜像，无需第三方服务或额外成本
2. 配置驱动（一个 YAML 文件）比脚本驱动更易维护，新增仓库只需改配置
3. 备份目标仓库设为 `--private` 只读，即使源仓库被误删也能从备份恢复

## 实验设计

### 阶段 1：单仓库备份

从 `quanttide` 组织备份一个仓库到备份组织。操作步骤：

```bash
# 1. 在备份组织中创建同名仓库（private, template=false）
gh repo create quanttide-backup/quanttide-laboratory-of-game-developing \
  --private --description "备份: quanttide-laboratory-of-game-developing"

# 2. 镜像推送
git clone --mirror https://github.com/quanttide/quanttide-laboratory-of-game-developing.git
cd quanttide-laboratory-of-game-developing.git
git remote add backup https://github.com/quanttide-backup/quanttide-laboratory-of-game-developing.git
git push --mirror backup
```

### 阶段 2：批量配置

定义仓库清单 YAML：

```yaml
# backup-config.yaml
backup:
  source_org: quanttide
  target_org: quanttide-backup
  schedule: "0 2 * * *"  # 每天 UTC 2:00
  repos:
    - quanttide-laboratory-of-game-developing
    - quanttide-laboratory-of-human-resources
    - quanttide-laboratory-of-organization
    - quanttide-laboratory-of-execution
    - quanttide-laboratory-of-business-entity
    - quanttide-laboratory-of-innovation
    - quanttide-example-of-founder
    - quanttide-founder
```

GitHub Actions 工作流读取此配置，循环执行备份。

### 阶段 3：灾难恢复模拟

1. 删除源仓库中的一个分支（模拟误操作）
2. 从备份仓库恢复被删除的分支
3. 验证恢复后的仓库与备份时一致

### 阶段 4：增量优化

- 跳过已备份且无新提交的仓库
- 备份日志记录每次运行结果
- 失败告警（邮件 / 飞书通知）

## 测试用例

| 用例 | 操作 | 预期 |
|------|------|------|
| 新仓库备份 | 在配置中新增仓库名 | 创建备份仓库 + 全量镜像 |
| 重复备份 | 同一仓库第二次运行 | 增量推送，不重复创建 |
| 源仓库删除 | 删除源仓库 | 备份仓库仍存在，可读 |
| 分支恢复 | 从备份仓库 fetch 被删分支 | 分支完整恢复 |

## 评价标准

| 指标 | 合格线 | 优秀线 |
|------|--------|--------|
| 单仓库备份 | 1 个仓库成功 | 1 个仓库成功 |
| 批量备份 | 5 个仓库通过 | 全部仓库通过 |
| 配置修改 | 改 YAML 后生效 | PR merge 后自动触发 |
| 灾难恢复 | 仓库 + 默认分支完整 | 所有分支 + tags 完整 |
| 备份耗时（每仓库） | < 5 min | < 2 min |

## 产出物

1. `backup-config.yaml` — 仓库清单配置
2. `.github/workflows/backup.yml` — 备份工作流
3. `scripts/restore.sh` — 恢复脚本
4. `docs/backup-log.md` — 备份日志和运行记录

## 实验记录

每次运行后记录：

- 备份的仓库列表和耗时
- 失败的仓库及原因
- 备份仓库大小变化
- 配置变更历史

## 下一步

备份跑通后，接入 webhook 实现新增仓库自动加入备份列表；增加备份完整性校验（SHA 摘要比对）。
