#!/bin/bash
set -e

info()  { printf "\033[36m[INFO]\033[0m %s\n" "$*"; }
ok()    { printf "\033[32m[OK]\033[0m   %s\n" "$*"; }
warn()  { printf "\033[33m[WARN]\033[0m %s\n" "$*"; }
fail()  { printf "\033[31m[FAIL]\033[0m %s\n" "$*"; }

echo "===== 内核更新修复脚本 ====="
echo "内核: $(uname -r)"
echo

# ---- NVIDIA 驱动 ----
echo "--- NVIDIA 驱动 ---"
KVER=$(uname -r)
SRCDIR="/lib/modules/$KVER/kernel/nvidia-535"
if [ -d "$SRCDIR" ]; then
    sudo mkdir -p "/lib/modules/$KVER/updates/dkms"
    sudo cp "$SRCDIR"/*.ko "/lib/modules/$KVER/updates/dkms/"
    sudo chmod 644 "/lib/modules/$KVER/updates/dkms/"*.ko
    sudo depmod -a
    sudo modprobe nvidia 2>&1 || true
    if lsmod | grep -q nvidia; then
        ok "NVIDIA 驱动修复成功"
    else
        warn "NVIDIA 模块加载失败"
    fi
else
    info "NVIDIA 模块源不存在，跳过"
fi

# ---- AIC8800 无线网卡 ----
echo
echo "--- AIC8800 无线网卡 ---"
SCRIPT_DIR="/home/iguo/scripts"
if [ -f "$SCRIPT_DIR/install_aic8800.sh" ]; then
    bash "$SCRIPT_DIR/install_aic8800.sh"
else
    if [ -d "/home/iguo/repos/aic8800d80/drivers/aic8800" ]; then
        cd /home/iguo/repos/aic8800d80
        sudo bash install_setup.sh
        cd drivers/aic8800
        make clean 2>/dev/null || true
        make -j$(nproc)
        sudo make install
        sudo depmod -a
        sudo modprobe cfg80211 2>/dev/null || true
        sudo modprobe aic_load_fw
        sudo modprobe aic8800_fdrv
        if lsmod | grep -q aic8800; then
            ok "AIC8800 驱动安装成功"
        else
            warn "AIC8800 模块加载失败"
        fi
    else
        warn "AIC8800 源码目录不存在,跳过"
    fi
fi

# ---- AIC8800 dpkg 包状态修复 (fix-wifi-driver.sh 逻辑) ----
PKG="aic8800d80fdrvpackage"
if dpkg -s "$PKG" 2>/dev/null | grep -q "Status.*install ok installed"; then
    ok "$PKG 已正确配置"
elif dpkg -s "$PKG" 2>/dev/null | grep -q "Status.*install"; then
    echo
    echo "--- $PKG 包状态异常，尝试修复 ---"
    DRIVER_DIR="/usr/src/AIC8800/drivers/aic8800"
    if [ -d "$DRIVER_DIR" ]; then
        sudo make -C "$DRIVER_DIR" clean >/dev/null 2>&1 || true
        if sudo make -C "$DRIVER_DIR" EXTRA_CFLAGS="-Wno-error"; then
            sudo make -C "$DRIVER_DIR" install EXTRA_CFLAGS="-Wno-error"
            sudo dpkg --configure -a
            if dpkg -s "$PKG" 2>/dev/null | grep -q "Status.*install ok installed"; then
                ok "$PKG 修复成功"
            else
                warn "$PKG 配置仍有问题"
            fi
        else
            warn "编译失败，bypass postinst 标记为已配置"
            postinst="/var/lib/dpkg/info/${PKG}.postinst"
            sudo cp "$postinst" "${postinst}.bak" 2>/dev/null
            echo '#!/bin/bash; exit 0' | sudo tee "$postinst" >/dev/null
            sudo chmod +x "$postinst"
            sudo dpkg --configure -a
            warn "已绕过 postinst，下次内核更新需重新执行本脚本"
        fi
    fi
fi

echo
echo "===== 修复完成，建议重启: sudo reboot ====="
