#!/usr/bin/env bash
# 实验 1.1.1: 收集 memory 样本，确定输入格式
# 用法: ./collect.sh [memory_path]
# 默认 memory 路径: ../../data

MEMORY_PATH="${1:-../../data}"

echo "=== Memory 样本收集 ==="
echo "路径: $(cd "$MEMORY_PATH" && pwd)"
echo ""

echo "--- journal/ (日记) ---"
find "$MEMORY_PATH/journal" -name "*.md" -type f | sort | while read -r f; do
    lines=$(wc -l < "$f")
    words=$(wc -m < "$f")
    echo "  $f  ($lines 行, $words 字符)"
done

echo ""
echo "--- memo/ (笔记) ---"
find "$MEMORY_PATH/memo" -name "*.md" -type f | sort | while read -r f; do
    lines=$(wc -l < "$f")
    words=$(wc -m < "$f")
    echo "  $f  ($lines 行, $words 字符)"
done

echo ""
echo "--- 总计 ---"
total_files=$(find "$MEMORY_PATH" -name "*.md" -type f | wc -l)
echo "  Memory 文件数: $total_files"
