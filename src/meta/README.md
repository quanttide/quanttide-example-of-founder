# meta — 编排层

journal 变更后自动触发 think → health → execute 完整链路。

## 架构

```
producer (journal 变更检测)
  └→ RabbitMQ (topic: journal.new)
       └→ consumer (单篇 think → 情绪检测 → 增量 execute)
```

## 用法

```bash
python3 meta.py --consume    # 终端 1：启动消费者
python3 meta.py --publish    # 终端 2：手动发布消息
```
