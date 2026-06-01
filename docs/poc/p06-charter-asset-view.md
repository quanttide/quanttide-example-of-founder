# p06 章程多维资产视图

## 来源

日志 2026-05-31：章程作为资产、写作、知识的多维观察。

## 验证目标

同一份章程从多个视角维护，验证多视角框架是否提升维护效率。

## 验收标准

1. 至少 3 个视角：资产视图、写作视图、知识视图
2. 视角切换不丢状态
3. 跨视角关联：资产修改 → 写作视图自动标记待更新
4. 版本管理：每个视角独立版本
5. 差异对比：同一章程不同视角间差异可查看

## 关键问题

- 视角之间如何定义关联规则？
- 冲突时以哪个视角为准？
- 视角是否需要权限隔离？

## 视角模型

```
Charter {
  id: string
  content: string
  views: {
    asset: AssetView {
      owner: string
      value: number
      lifecycle: 'draft' | 'active' | 'archived'
    },
    writing: WritingView {
      author: string
      style: string
      revision: number
      status: 'editing' | 'reviewing' | 'published'
    },
    knowledge: KnowledgeView {
      tags: string[]
      references: Link[]
      relatedConcepts: Concept[]
      status: 'verified' | 'unverified'
    }
  },
  versions: Version[]
}
```

## 原型产出

`examples/p06-charter-asset-view/` — 多视角切换阅读器
