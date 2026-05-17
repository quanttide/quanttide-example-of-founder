# 内核更新修复指南

## 背景

每次 `apt upgrade` 安装新内核后，旧内核的驱动配置失效，需要重新编译/加载驱动：

- **NVIDIA**: 模块在 `/lib/modules/<kernel>/kernel/nvidia-535/`，不在 `depmod` 默认扫描路径
- **AIC8800**: 内核模块需重新编译安装
- **r8168**: 闭源网卡驱动需重新加载

## 一键修复

```bash
bash ~/scripts/repair.sh
```

支持 sudo 免密码执行。

## 脚本说明

| 脚本 | 作用 |
|------|------|
| `repair.sh` | 一键修复 NVIDIA + AIC8800 + dpkg 包状态 |
| `install_aic8800.sh` | 仅安装 AIC8800 驱动（被 repair.sh 调用） |

## 修复内容

### 1. NVIDIA

将 nvidia 模块复制到 `updates/dkms/`，执行 `depmod` 后加载。

### 2. AIC8800 无线网卡

- 安装固件和 udev 规则（`install_setup.sh`）
- 编译驱动模块
- 安装到内核目录，更新模块依赖
- 加载 `aic_load_fw` 和 `aic8800_fdrv`

### 3. dpkg 包状态修复 (`aic8800d80fdrvpackage`)

如果该包状态异常（触发 rebuild），尝试重新编译安装；若编译失败则 bypass postinst 标记为已配置。

## 验证

```bash
# NVIDIA
lsmod | grep nvidia
nvidia-smi

# AIC8800
lsmod | grep aic8800
ip link show
```
