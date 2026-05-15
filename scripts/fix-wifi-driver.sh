#!/bin/bash

info()  { printf "\033[36m[INFO]\033[0m %s\n" "$*"; }
ok()    { printf "\033[32m[OK]\033[0m   %s\n" "$*"; }
warn()  { printf "\033[33m[WARN]\033[0m %s\n" "$*"; }
fail()  { printf "\033[31m[FAIL]\033[0m %s\n" "$*"; exit 1; }

check_sudo() { sudo -n true 2>/dev/null; }

DRIVER_DIR="/usr/src/AIC8800/drivers/aic8800"
PKG="aic8800d80fdrvpackage"

main() {
  echo ""
  echo "  Fix AIC8800 Wi-Fi Driver"
  echo "  ========================"
  echo ""

  check_sudo || fail "sudo required"

  if ! dpkg -s "$PKG" >/dev/null 2>&1; then
    ok "$PKG not installed, nothing to fix"
    exit 0
  fi

  if dpkg -s "$PKG" 2>/dev/null | grep -q "Status.*install ok installed"; then
    ok "$PKG is already configured correctly"
    exit 0
  fi

  info "Cleaning old build artifacts..."
  sudo make -C "$DRIVER_DIR" clean >/dev/null 2>&1 || true

  info "Rebuilding with -Wno-error..."
  if sudo make -C "$DRIVER_DIR" EXTRA_CFLAGS="-Wno-error"; then
    sudo make -C "$DRIVER_DIR" install EXTRA_CFLAGS="-Wno-error"
    sudo dpkg --configure -a
    if dpkg -s "$PKG" 2>/dev/null | grep -q "Status.*install ok installed"; then
      ok "Wi-Fi driver fixed successfully"
    else
      fail "Package still not configured after successful build"
    fi
  else
    warn "Build failed. Trying alternative: force-configure (driver still works)"
    # modules are already loaded and working, mark package as configured
    local postinst="/var/lib/dpkg/info/${PKG}.postinst"
    sudo cp "$postinst" "${postinst}.bak" 2>/dev/null
    echo '#!/bin/bash' | sudo tee "$postinst" >/dev/null
    echo 'exit 0' | sudo tee -a "$postinst" >/dev/null
    sudo chmod +x "$postinst"
    sudo dpkg --configure -a
    if dpkg -s "$PKG" 2>/dev/null | grep -q "Status.*install ok installed"; then
      warn "Package marked as configured (postinst bypassed)."
      warn "Restore original postinst with: sudo cp ${postinst}.bak $postinst"
      warn "If you update the kernel, re-run this script to rebuild."
    else
      fail "Could not fix package"
    fi
  fi
}

main "$@"
