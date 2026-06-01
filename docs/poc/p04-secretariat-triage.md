# p04 秘书处任务分诊

## 来源

日志 2026-05-31：秘书处分工、执行管理、COO办/CTO办/秘书处办三办分工。

## 验证目标

任务自动分类、优先级排序、分派到对应办公室，验证分诊逻辑是否覆盖实际场景。

## 验收标准

1. 任务分类模型：按类型/紧急度/重要性自动归类
2. 优先级矩阵可配（如 Eisenhower 矩阵）
3. 三办路由：COO办（前期商务）/ CTO办（验收成本）/ 秘书处办（中间过程）
4. 分诊结果可人工干预和修正
5. 统计看板：各办负载、平均处理时间

## 关键问题

- 跨办任务如何协作？
- 优先级矩阵的权重谁来确定？
- 秘书长在流程中的角色？

## 数据模型

```
Task {
  id: string
  title: string
  description: string
  type: '商务' | '技术' | '行政' | '管理'
  urgency: 1-5
  importance: 1-5
  priority: 'critical' | 'high' | 'medium' | 'low'
  assignedTo: 'coo' | 'cto' | 'secretariat'
  status: 'pending' | 'processing' | 'done'
  source: string
}
```

## 原型产出

`examples/p04-secretariat-triage/` — 分诊面板 + 各办看板
