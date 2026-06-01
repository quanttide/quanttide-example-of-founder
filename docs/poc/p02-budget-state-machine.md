# p02 财务预算状态机

## 来源

日志 2026-05-28：财务预算模块，业务研发的规划任务。

## 验证目标

预算模块的核心状态流转，验证状态机设计是否覆盖主要业务场景。

## 验收标准

1. 状态流转图可执行：编制 → 审批 → 执行 → 决算
2. 预算额度实时控制，超支告警
3. 支持预算调整（追加/调减/调剂）
4. 多版本管理（草稿 vs 正式）

## 关键问题

- 预算周期如何设计？月度/季度/年度？
- 超支后是否允许走特批流程？
- 预算调整是否需要重新审批？
- **审批角色未定**：PoC 阶段状态图不含角色属性，但设计中需标注为待定参数。小预算（≤5万）与大预算（>50万）的审批人可能不同，后续需引入角色矩阵

## 状态机（PoC 版：不含角色认证）

```
states: draft -> pending_approval -> approved -> executing -> closing -> closed
        |        |                  |             |           |
        v        v                  v             v           v
     rejected  rejected          adjusted     overrun    archived

events:
  submit: draft -> pending_approval
  approve: pending_approval -> approved
  reject: pending_approval -> draft
  adjust: approved -> pending_approval
  execute: approved -> executing
  overrun: executing -> alert
  close: executing -> closing
  archive: closing -> closed
```

### 审批角色矩阵（待定参数，PoC 阶段不做实现）

| 预算类型 | 金额范围 | 审批人 | 签批模式 |
|---------|---------|-------|---------|
| 运营 | ≤ 5 万 | COO | 单人 |
| 运营 | > 5 万 | COO + CTO | 会签 |
| 项目 | ≤ 50 万 | CTO | 单人 |
| 项目 | > 50 万 | 三办合议 | 会签 |
```

### 审批角色矩阵（待定参数，PoC 阶段不做实现）

| 预算类型 | 金额范围 | 审批人 | 签批模式 |
|---------|---------|-------|---------|
| 运营 | ≤ 5 万 | COO | 单人 |
| 运营 | > 5 万 | COO + CTO | 会签 |
| 项目 | ≤ 50 万 | CTO | 单人 |
| 项目 | > 50 万 | 三办合议 | 会签 |

```
states: draft -> pending_approval -> approved -> executing -> closing -> closed
        |        |                  |             |           |
        v        v                  v             v           v
     rejected  rejected          adjusted     overrun    archived

events:
  submit: draft -> pending_approval
  approve: pending_approval -> approved
  reject: pending_approval -> draft
  adjust: approved -> pending_approval
  execute: approved -> executing
  overrun: executing -> alert
  close: executing -> closing
  archive: closing -> closed
```

## 原型产出

`examples/p02-budget-state-machine/` — 状态机可视化 + 交互面板
