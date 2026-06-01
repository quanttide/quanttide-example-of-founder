# p01 招聘筛选网关

## 来源

日志 2026-05-28：人事云，用系统对抗低质量招聘。

## 验证目标

用系统自动过滤低质量简历，引导愿意投入的候选人完成完整申请流程。

## 验收标准

1. 简历评分规则可配置（关键词/完整性/岗位匹配度）
2. 低质量投递自动拒绝或标记
3. 候选人有清晰的引导流程
4. 统计面板：过滤率、通过率、转化率

## 关键问题

- 如何定义"低质量"？仅简历信息过少算不算？
- 引导流程是否应该区分主动投递和被动搜索？
- 评分阈值谁来设置？是否需要分岗位设置不同阈值？

## 数据模型

```
Candidate {
  id: string
  name: string
  resume: Resume
  score: number
  status: 'pending' | 'screened' | 'rejected' | 'contacted' | 'interviewing'
  source: 'active' | 'passive'
  appliedPosition: string
}

Resume {
  completeness: number
  keywords: string[]
  experience: Experience[]
  education: Education[]
}
```

## 原型产出

`examples/p01-recruitment-filter/` — 可交互的筛选面板原型
