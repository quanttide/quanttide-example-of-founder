#!/bin/bash
# 从备份组织恢复仓库到源组织
# 用法: ./restore.sh <repo-name>
# 示例: ./restore.sh quanttide-laboratory-of-game-developing

set -e

SOURCE_ORG="${SOURCE_ORG:-quanttide}"
TARGET_ORG="${TARGET_ORG:-quanttide-backup}"
REPO="$1"

if [ -z "$REPO" ]; then
  echo "用法: $0 <repo-name>"
  echo "示例: $0 quanttide-laboratory-of-game-developing"
  exit 1
fi

echo "从 $TARGET_ORG/$REPO 恢复到 $SOURCE_ORG/$REPO"

# 检查备份是否存在
if ! gh repo view "$TARGET_ORG/$REPO" &>/dev/null; then
  echo "错误: 备份仓库 $TARGET_ORG/$REPO 不存在"
  exit 1
fi

# 检查是否需要重新创建源仓库
if ! gh repo view "$SOURCE_ORG/$REPO" &>/dev/null; then
  echo "源仓库不存在，正在创建..."
  gh repo create "$SOURCE_ORG/$REPO" --public --description "Recovered from $TARGET_ORG/$REPO"
fi

# 镜像恢复
echo "克隆备份..."
git clone --mirror "https://github.com/$TARGET_ORG/$REPO.git" "/tmp/restore-$REPO.git"
cd "/tmp/restore-$REPO.git"

echo "推送到源组织..."
git remote add source "https://github.com/$SOURCE_ORG/$REPO.git"
git push --mirror source

cd /tmp
rm -rf "/tmp/restore-$REPO.git"

echo "恢复完成: $SOURCE_ORG/$REPO"
echo ""
echo "注意:"
echo "  - GitHub Pages 和 Actions 配置需要手动重新设置"
echo "  - Issues 和 Discussions 不在镜像范围内"
