#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root regardless of where this script is called from
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$REPO_ROOT"

echo "[bluxgpt] Installing BluxGPT v1.0..."
echo "[bluxgpt] Repo root: $REPO_ROOT"

# Step 1: dependency check
echo "[bluxgpt] Checking dependencies..."
bash "$REPO_ROOT/scripts/check_deps.sh"

# Step 2: Python venv
echo "[bluxgpt] Creating Python virtual environment..."
python3 -m venv "$REPO_ROOT/.venv"

# Activate — compatible with bash/zsh and proot/Termux
# shellcheck disable=SC1091
. "$REPO_ROOT/.venv/bin/activate"

echo "[bluxgpt] Installing Python packages..."
pip install --upgrade pip --quiet
pip install -r "$REPO_ROOT/requirements.txt" --quiet

# Step 3: user config
echo "[bluxgpt] Setting up user config..."
mkdir -p "$HOME/.config/bluxgpt"
if [[ ! -f "$HOME/.config/bluxgpt/.env" ]]; then
  cp "$REPO_ROOT/config/.env.example" "$HOME/.config/bluxgpt/.env"
  echo "[bluxgpt] Config created: ~/.config/bluxgpt/.env"
  echo "[bluxgpt] Set your API keys there before running blux."
else
  echo "[bluxgpt] Config already exists: ~/.config/bluxgpt/.env"
fi

# Step 4: shell overlay
echo "[bluxgpt] Installing shell overlay..."
bash "$REPO_ROOT/scripts/install_shell.sh"

echo
echo "[bluxgpt] Installation complete."
echo
echo "  Next steps:"
echo "    1. Set API keys in ~/.config/bluxgpt/.env"
echo "    2. source ~/.zshrc  (or open a new terminal)"
echo "    3. blux status"
echo "    4. blux ask \"your question\""
