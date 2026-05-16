架构设计方案

1. 核心状态模型

整个系统只维护一个核心状态：意图模型。它是人类意图的外化表示，同时作为AI上下文注入和BRD导出。

```typescript
interface IntentModel {
  goal: string;        // 目标
  exploration: string; // 当前探索
  constraints: string; // 约束
  state: string;       // 状态
  updatedAt: number;   // 最后修改时间戳
}
```

所有其他UI状态（如移动端的折叠状态、对话历史）均为衍生或临时状态，不参与业务逻辑。

2. 数据流架构

系统由三层组成，数据单向流动，状态变更统一走状态层。

```
┌──────────────┐
│   UI层       │  渲染意图模型，发送用户输入，接收AI回复
│ - 桌面双栏   │
│ - 移动端面板 │
└──────┬───────┘
       │ 用户消息/编辑意图模型
       ▼
┌──────────────┐
│  通信层      │  管理对话上下文，调用LLM，解析结果
│ - 上下文组装 │
│ - 意图更新解析│
└──────┬───────┘
       │ 更新意图模型状态
       ▼
┌──────────────┐
│  状态层      │  持有唯一真相源 IntentModel
│ - 读/写意图 │
│ - 发布变更事件 │
└──────────────┘
```

关键约束：UI不允许直接修改通信层行为，通信层不直接操作UI，所有状态变更必须经过状态层。

3. 通信层设计

3.1 请求组装

每次向LLM发送请求前，通信层从状态层获取当前 IntentModel，将其格式化为系统提示片段，插入到对话上下文顶部。

示例系统提示模板：

```
你是意图澄清助手。当前我们共同维护的意图模型如下：
## 目标
{goal}
## 当前探索
{exploration}
## 约束
{constraints}
## 状态
{state}

你的行为必须与此意图模型对齐。在回复末尾，如果你判断意图模型发生了结构性变化，请以如下格式输出更新：
[INTENT_UPDATE]
field: goal|exploration|constraints|state
content: 新内容（单行，无换行）

否则不要输出任何 [INTENT_UPDATE] 块。
```

3.2 响应解析

通信层接收LLM回复后，分离普通文本回复与意图更新指令：

· 检测 [INTENT_UPDATE] 块，若存在且解析成功，则调用状态层接口更新对应字段。
· 移除意图更新块，将纯净的文本回复传递给UI层展示。
· 若没有更新块，则无状态变更。

意图更新规则：只有结构性变化（方向切换、假设推翻、新增约束、阶段转换）才触发更新。细节微调不会出现在更新块中。LLM通过指令中的措辞理解“结构性变化”。

4. 状态层实现

状态层提供两个接口：

```typescript
// 获取当前意图模型
getIntent(): IntentModel

// 更新意图模型（部分更新）
updateIntent(patch: Partial<IntentModel>): void
```

当更新发生时，状态层向UI层发布事件，使UI重新渲染意图模型区域。

人类手动编辑：UI层直接调用 updateIntent，更新后通信层下一次请求自动携带最新模型。

AI提案更新：通信层解析出更新指令后调用 updateIntent，更新后UI刷新并在对话中显示“意图已更新”提示。

5. UI层设计

UI层职责：展示对话、展示意图模型、处理用户输入和编辑。

5.1 桌面端组件树

```
App
├── LeftPanel
│   ├── ChatHistory
│   │   ├── Message (user/AI)
│   │   └── IntentUpdateNotice (系统提示)
│   └── InputBox
└── RightPanel
    ├── IntentSection (目标，可编辑)
    ├── IntentSection (探索，可编辑)
    ├── IntentSection (约束，可编辑)
    ├── IntentSection (状态，可编辑)
    └── ExportButton
```

5.2 移动端组件树

```
App
├── IntentPanel (可折叠，含四个可编辑字段)
├── ChatHistory
│   ├── Message
│   └── IntentUpdateNotice
├── InputBox
└── ExportButton (固定于输入框旁)
```

所有可编辑字段使用 contenteditable 或轻量文本编辑器，失焦自动保存，调用 updateIntent。

6. 导出机制

导出按钮触发函数 exportBRD()，从状态层获取当前意图模型，生成Markdown：

```
# 意图文档
生成时间：{timestamp}

## 目标
{goal}

## 当前探索
{exploration}

## 约束
{constraints}

## 状态
{state}
```

复制到剪贴板或下载，无额外处理。

7. 架构优势

· 单一真相源：意图模型是唯一状态，所有组件与之同步。
· 人与AI对等协作：二者通过同一状态接口进行修改，AI提案即状态更新，人类编辑即状态覆盖。
· 无状态冲突：更新顺序由时间戳解决（后写入覆盖前写入），但实际并发概率极低。
· 可扩展：未来可新增意图模型维度（如风险、假设），只需扩展 IntentModel 字段和UI渲染。
· 平台无关：桌面和移动端共享同一状态层和通信层，仅UI渲染不同。

8. 实现路径

1. 实现状态层：简单的内存对象 + 发布订阅。
2. 实现通信层：封装LLM API，注入系统提示，解析 [INTENT_UPDATE]。
3. 实现桌面端UI：React/Vue 或其他，双栏布局。
4. 实现移动端UI：适配窄屏，顶部可折叠面板。
5. 集成导出。

核心复杂度集中在AI的意图更新判断质量上，可通过调整系统提示中的示例和阈值来优化。