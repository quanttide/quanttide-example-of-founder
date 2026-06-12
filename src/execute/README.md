# execute — 待办提取与日记监听

| 工具 | 功能 |
|------|------|
| extract.py | 从 think 数据中筛选可执行待办 |
| watch.py | 日记变更监听（RabbitMQ） |

## extract.py

从 think 模块提取的意图中筛选可执行条目。

```bash
python3 src/think/extract.py
python3 src/execute/extract.py
```

## watch.py

journal 提交后通过 RabbitMQ 触发轻量处理。

### 架构

```
producer (journal 变更检测)
  └→ RabbitMQ (topic: journal.new)
       └→ consumer (think + health + execute)
```

### 用法

```bash
python3 src/execute/watch.py --consume    # 终端 1：启动消费者
python3 src/execute/watch.py --publish    # 终端 2：手动发布消息
```
