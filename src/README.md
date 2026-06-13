# src

| 目录 | 说明 |
|------|------|
| knowl | 知识抽取工具（模型约束 LLM 输出） |
| health | 健康检查 |

## knowl 快速开始

```bash
# 认知抽取（带模型约束）
python3 -m knowl.extract --input <data> --model ../data/knowl/cognition.yaml --type cognition --output out/

# TODO 抽取
python3 -m knowl.extract --input <data> --model ../data/knowl/cognition.yaml --type todo --output out/

# 母题识别
python3 -m knowl.extract --input <data> --model ../data/knowl/motif.yaml --type motif --output out/
```
