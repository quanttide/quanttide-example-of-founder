#!/bin/bash

info()  { printf "\033[36m[INFO]\033[0m %s\n" "$*"; }
ok()    { printf "\033[32m[OK]\033[0m   %s\n" "$*"; }
warn()  { printf "\033[33m[WARN]\033[0m %s\n" "$*"; }
fail()  { printf "\033[31m[FAIL]\033[0m %s\n" "$*"; exit 1; }

has() {
  command -v "$1" >/dev/null 2>&1 && return 0
  local search_paths=(
    "$HOME/.local/bin"
    "/home/iguo/.local/bin"
    "/usr/local/bin"
    "/usr/bin"
  )
  for p in "${search_paths[@]}"; do
    [ -x "$p/$1" ] && return 0
  done
  return 1
}

check_sudo() {
  sudo -n true 2>/dev/null
}

fix_broken_driver() {
  local driver_dir="/usr/src/AIC8800/drivers/aic8800"
  local pkg="aic8800d80fdrvpackage"
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    return
  fi
  if dpkg -s "$pkg" 2>/dev/null | grep -q "Status.*install ok installed"; then
    return
  fi
  info "Fixing broken Wi-Fi driver ($pkg)..."
  sudo make -C "$driver_dir" clean >/dev/null 2>&1 || true
  if sudo make -C "$driver_dir" EXTRA_CFLAGS="-Wno-error" >/dev/null 2>&1; then
    sudo make -C "$driver_dir" install EXTRA_CFLAGS="-Wno-error" >/dev/null 2>&1 || true
  fi
  sudo dpkg --configure -a
  if dpkg -s "$pkg" 2>/dev/null | grep -q "Status.*install ok installed"; then
    ok "Wi-Fi driver fixed"
  else
    warn "Wi-Fi driver still broken, proceeding anyway..."
  fi
}

install_texlive() {
  local pkgs=(
    texlive-xetex
    texlive-lang-chinese
    latexmk
  )

  for pkg in "${pkgs[@]}"; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
      ok "$pkg already installed"
    else
      info "Installing $pkg..."
      sudo apt install -y "$pkg" || fail "Failed to install $pkg"
      ok "$pkg installed"
    fi
  done
}

check_latexmk() {
  has latexmk || fail "latexmk not found after installation"
  ok "latexmk: $(latexmk --version 2>&1 | head -1)"
}

check_xelatex() {
  has xelatex || fail "xelatex not found after installation"
  ok "xelatex: $(xelatex --version 2>&1 | head -1)"
}

check_myst() {
  has myst || fail "myst not found. Install via: npm install -g mystmd"
  ok "myst: $(myst --version 2>&1)"
}

check_pandoc() {
  if has pandoc; then
    ok "pandoc: $(pandoc --version 2>&1 | head -1)"
  fi
}

check_chinese_fonts() {
  local fonts
  fonts=$(fc-list :lang=zh 2>/dev/null | head -3)
  if [ -n "$fonts" ]; then
    ok "Chinese fonts found"
  else
    warn "No Chinese system fonts detected."
    warn "Install with: sudo apt install fonts-noto-cjk"
  fi
}

main() {
  echo ""
  echo "  Myst PDF Environment Setup (texlive)"
  echo "  ===================================="
  echo ""

  check_sudo || fail "sudo required for apt install"

  check_myst
  check_pandoc
  fix_broken_driver
  install_texlive
  check_latexmk
  check_xelatex
  check_chinese_fonts

  local build_cmd="myst build --pdf index.md"

  echo ""
  echo "  ===================================="
  echo "  Setup complete."
  echo ""
  echo "  Build PDF with:"
  echo "    cd <project-dir-with-myst.yml>"
  echo "    $build_cmd"
  echo "  ===================================="
  echo ""

  # offer to run a quick test
  local project_dir="."
  if [ -f "myst.yml" ]; then
    read -r -p "  Run test build now? [Y/n] " reply
    case "$reply" in
      [nN]|[nN][oO]) ;;
      *)
        echo ""
        info "Running: $build_cmd"
        echo ""
        $build_cmd 2>&1
        local ret=$?
        echo ""
        if [ $ret -eq 0 ] && ls _build/exports/index.pdf >/dev/null 2>&1; then
          ok "PDF generated: _build/exports/index.pdf"
        else
          warn "Build finished with issues. Check output above."
        fi
        ;;
    esac
  fi
}

main "$@"
