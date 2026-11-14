#!/usr/bin/env bash
# ==============================================================================
# Tenda HG7 Controller Turnkey System Installer
# Author: Dulith Divisekara
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "  Tenda HG7 Router Controller — Production Installer"
echo "========================================================================"

# 1. Verify Python 3.10+
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python 3 is required but was not found on your system." >&2
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "[ERROR] Python 3.10 or higher is required. Found Python $PY_VER." >&2
    exit 1
fi
echo "[✓] Python $PY_VER detected."

# 2. Verify Pip
if ! python3 -m pip --version &>/dev/null; then
    echo "[ERROR] python3-pip is not installed." >&2
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install -y python3-pip" >&2
    exit 1
fi
echo "[✓] Pip detected."

# 3. Determine Pip Install Flags (PEP 668 & Virtualenv handling)
PIP_FLAGS=()
if [ -n "${VIRTUAL_ENV:-}" ]; then
    echo "[i] Active virtual environment detected ($VIRTUAL_ENV)."
else
    PIP_FLAGS+=("--user")
    if python3 -m pip install --help 2>&1 | grep -q -- "--break-system-packages"; then
        PIP_FLAGS+=("--break-system-packages")
    fi
fi

# 4. Install Package & Dependencies
echo "[i] Installing slt-fiber-tenda-controller in editable mode..."
python3 -m pip install "${PIP_FLAGS[@]}" -e "$SCRIPT_DIR"

# 5. Ensure ~/.local/bin is in PATH and clean legacy binaries
LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"
rm -f "$LOCAL_BIN/tenda-cli"

add_to_shell_rc() {
    local rc_file="$1"
    if [ -f "$rc_file" ]; then
        if ! grep -q "$LOCAL_BIN" "$rc_file" 2>/dev/null; then
            echo "" >> "$rc_file"
            echo "# Added by Tenda HG7 Controller installer" >> "$rc_file"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc_file"
            echo "[✓] Added ~/.local/bin to $rc_file"
        fi
    fi
}

add_to_shell_rc "$HOME/.bashrc"
add_to_shell_rc "$HOME/.zshrc"
add_to_shell_rc "$HOME/.profile"

# Ensure current script session has ~/.local/bin in PATH
export PATH="$LOCAL_BIN:$PATH"

# 6. Verification
echo ""
echo "========================================================================"
echo "  Verification & Binary Status"
echo "========================================================================"

if command -v tenda-ctl &>/dev/null; then
    echo "[✓] tenda-ctl is ready at: $(which tenda-ctl)"
else
    echo "[!] Notice: tenda-ctl installed to $LOCAL_BIN/tenda-ctl"
    echo "    Reload your shell or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "Installation complete! Try running:"
echo "  tenda-ctl status"
echo "  tenda-ctl pon"
echo "  tenda-ctl devices"
echo "  tenda-ctl --help"
echo "========================================================================"
