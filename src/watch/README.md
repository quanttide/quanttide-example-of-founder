# watch — 日记变更监听（RabbitMQ）

journal 提交后通过消息队列触发轻量处理。

## 架构

```
producer (journal 变更检测)
  └→ RabbitMQ (topic: journal.new)
       └→ consumer (think + health + execute)
```

## 用法

```bash
# 终端 1：启动消费者（持续监听）
python3 watch.py --consume

# 终端 2：手动发布消息（模拟 journal 变更）
python3 watch.py --publish

# 或通过 git hook 自动触发
# .git/hooks/post-commit: python3 /path/to/watch.py --publish
```
