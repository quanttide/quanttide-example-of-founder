# Myst PDF 编译环境配置

## 环境

- OS: Ubuntu 24.04
- myst: v1.8.3 (npm)
- TeX: TeX Live 2023 (xelatex + latexmk)
- 中文支持: ctex 宏包 + Noto CJK 字体

## 安装步骤

```bash
# 1. 安装 myst
npm install -g mystmd

# 2. 安装 TeX Live 中文支持
sudo apt install texlive-xetex texlive-lang-chinese latexmk

# 3. 安装中文字体
sudo apt install fonts-noto-cjk
```

## 编译命令

```bash
cd <项目目录>   # 包含 myst.yml 的目录
myst build --pdf index.md
```

输出文件：`_build/exports/index.pdf`

## 中文支持

myst 默认模板使用 `article` 文档类，不含中文宏包。需要在模板中添加 `\usepackage{ctex}`：

文件：`_build/templates/tex/myst/plain_latex/template.tex`

```diff
 \documentclass{article}
 \usepackage{hyperref}
 \usepackage{datetime}
 \usepackage{graphicx}
 \usepackage{natbib}
+\usepackage{ctex}
 \bibliographystyle{abbrvnat}
```

> 注意：模板位于构建缓存目录，myst 更新模板时会被覆盖，届时需重新添加。

## 相关脚本

| 脚本 | 用途 |
|------|------|
| `scripts/setup-myst-pdf.sh` | 一键安装 TeX Live 环境 |
| `scripts/fix-wifi-driver.sh` | 修复 AIC8800 Wi-Fi 驱动编译问题 |

## 常见问题

### 中文字体显示为方块

原因：模板未加载中文宏包。解决方法见上方「中文支持」。

### latexmk: not found

原因：未安装 latexmk。运行 `sudo apt install latexmk`。

### texlive-xetex 安装失败

原因：系统存在损坏的软件包阻塞 apt。运行 `sudo dpkg --configure -a` 修复后再试。
