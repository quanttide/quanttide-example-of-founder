# health — 创作健康模块

基于 5 组实验验证的创作-情绪模型，提取为可复用的健康检测工具。

## 工具

| 工具 | 功能 | 来源实验 |
|------|------|---------|
| check.py | 每周情绪健康检查 | 差距分析 + 周内关联 |
| profile.py | 个人情绪基线与趋势 | 中介分析 + 加工深度 |

## 用法

```bash
python3 check.py                    # 本周情绪检查
python3 check.py --weeks 4          # 近 4 周趋势
python3 profile.py                  # 生成情绪基线
```
