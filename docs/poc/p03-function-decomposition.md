# p03 职能拆分解耦

## 来源

日志 2026-05-31：业务拆分为课程、咨询、产品等标准职能。

## 验证目标

将业务拆分为标准职能，各自独立且可组合，验证职能粒度是否合理。

## 验收标准

1. 职能定义 DSL 可用
2. 至少定义 3 种职能（课程/咨询/产品）
3. 组合规则可执行（如：课程+咨询 = 培训方案）
4. 依赖检查：循环依赖检测、缺失依赖告警
5. 每个职能可独立产出交付物

## 关键问题

- 职能的最小粒度是什么？是否有必要继续拆？
- 职能之间如何传递上下文？
- COO/CTO/秘书处办对应哪些职能？

## 数据模型

```
Function {
  id: string
  name: string
  type: 'course' | 'consulting' | 'product' | 'market' | 'tech'
  // course=课程研发, consulting=咨询服务, product=产品开发
  // market=市场推广, tech=技术支持（operation 拆分为 market + tech）
  inputs: Resource[]
  outputs: Deliverable[]
  dependencies: string[]  // function ids
  status: 'active' | 'deprecated'
}

BusinessFlow {
  functions: Function[]
  composition: Rule[]
}
```

## 原型产出

`examples/p03-function-decomposition/` — 职能编辑器 + 依赖图
