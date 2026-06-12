# watch — 日记变更监听

journal 提交后自动触发轻量处理。

## 用法

```bash
python3 watch.py                     # 检测新日志并处理
python3 watch.py --loop              # 持续监听（每 60 秒检测一次）
python3 watch.py --loop --interval 30  # 每 30 秒检测
```

## 处理流程

```
新 journal 提交
  └→ 轻量 think（只跑新文件）
      ├→ 健康检查（情绪变化检测）
      └→ 增量 execute（新增可执行条目）
```

全量重跑（10 篇）仍用 `think/extract.py` + `execute/extract.py`。
