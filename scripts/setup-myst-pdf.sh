#!/bin/bash

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME="$(eval echo "~$REAL_USER")"
MYST_DIR="${MYST_DIR:-$REAL_HOME/.local/bin}"
TECTONIC_VERSION="0.16.9"

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
    "/opt/homebrew/bin"
  )
  for p in "${search_paths[@]}"; do
    [ -x "$p/$1" ] && return 0
  done
  return 1
}

find_bin() {
  command -v "$1" 2>/dev/null || {
    local search_paths=(
      "$HOME/.local/bin"
      "/home/iguo/.local/bin"
      "/usr/local/bin"
      "/usr/bin"
    )
    for p in "${search_paths[@]}"; do
      [ -x "$p/$1" ] && { echo "$p/$1"; return 0; }
    done
    return 1
  }
}

check_sudo() {
  sudo -n true 2>/dev/null
}

install_tectonic_binary() {
  info "Downloading tectonic ${TECTONIC_VERSION} binary..."
  local url="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-gnu.tar.gz"
  local tmpdir
  tmpdir=$(mktemp -d)

  if ! curl -fL --progress-bar "$url" -o "$tmpdir/tectonic.tar.gz"; then
    rm -rf "$tmpdir"
    fail "Download failed (no network?). Install manually: sudo apt install tectonic"
  fi

  tar -xzf "$tmpdir/tectonic.tar.gz" -C "$tmpdir" 2>/dev/null || {
    rm -rf "$tmpdir"
    fail "Extraction failed"
  }

  if [ ! -f "$tmpdir/tectonic" ]; then
    # might be in a subdirectory
    local tbin
    tbin=$(find "$tmpdir" -name "tectonic" -type f 2>/dev/null | head -1)
    [ -n "$tbin" ] || { rm -rf "$tmpdir"; fail "tectonic binary not found in archive"; }
    mv "$tbin" "$tmpdir/tectonic"
  fi

  mkdir -p "$MYST_DIR"
  mv "$tmpdir/tectonic" "$MYST_DIR/tectonic"
  chmod +x "$MYST_DIR/tectonic"
  rm -rf "$tmpdir"
  ok "tectonic installed to $MYST_DIR/tectonic"
}

install_tectonic() {
  if has tectonic; then
    local tbin
    tbin=$(find_bin tectonic)
    ok "tectonic already installed ($tbin): $($tbin --version 2>&1)"
    return
  fi

  # try apt first (requires sudo)
  if check_sudo && sudo apt install -y tectonic 2>/dev/null; then
    has tectonic && { ok "tectonic: $(tectonic --version 2>&1)"; return; }
  fi

  # fallback: download binary
  if has curl; then
    install_tectonic_binary
  else
    fail "tectonic not found."
  fi

  # add to PATH for current session if needed
  case ":$PATH:" in
    *":$MYST_DIR:"*) ;;
    *) export PATH="$MYST_DIR:$PATH" ;;
  esac

  has tectonic || fail "tectonic installation failed ($MYST_DIR/tectonic not in PATH)"
  ok "tectonic: $(tectonic --version 2>&1)"
}

check_myst() {
  local myst_bin
  myst_bin=$(find_bin myst) || true
  if [ -z "$myst_bin" ]; then
    fail "myst not found. Install via: npm install -g mystmd"
  fi
  local ver
  ver=$("$myst_bin" --version 2>/dev/null)
  ok "myst ($myst_bin): $ver"
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
    warn "No Chinese fonts detected. PDF may have rendering issues."
    warn "Install with: sudo apt install fonts-noto-cjk"
  fi
}

main() {
  echo ""
  echo "  Myst PDF Environment Setup"
  echo "  =========================="
  echo ""

  check_myst
  check_pandoc
  install_tectonic
  check_chinese_fonts

  echo ""
  info "Setting tectonic as LaTeX engine..."
  export TECTONIC=true
  if [ -f "myst.yml" ] || [ -f "myst.yaml" ]; then
    info "myst.yml found in current directory"
  fi

  echo ""
  echo "  =========================="
  echo "  Setup complete."
  echo ""
  echo "  Build PDF with:"
  echo "    myst build --pdf"
  echo ""
  echo "  Or specify tectonic explicitly:"
  echo "    myst build --pdf --latex-engine tectonic"
  echo "  =========================="
  echo ""
}

main "$@"
