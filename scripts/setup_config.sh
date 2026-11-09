#!/usr/bin/env bash
# User config for BluxGPT: ~/.config/bluxgpt/.env holds provider API keys, so it is created private
# (directory 0700, file 0600). An existing file is never changed; if others can read it, say how to fix it.
# OV-64 (F141): install.sh used to copy the example with the default umask (usually 0644).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CONFIG_DIR="$HOME/.config/bluxgpt"
CONFIG="$CONFIG_DIR/.env"

if [[ ! -d "$CONFIG_DIR" ]]; then
  mkdir -p "$(dirname "$CONFIG_DIR")"
  mkdir -m 700 "$CONFIG_DIR"
fi
if [[ ! -f "$CONFIG" ]]; then
  install -m 600 "$REPO_ROOT/config/.env.example" "$CONFIG"
  echo "[bluxgpt] Config created: ~/.config/bluxgpt/.env (mode 600)"
  echo "[bluxgpt] Add your API keys before running bluxgpt."
else
  echo "[bluxgpt] Config already exists: ~/.config/bluxgpt/.env"
  mode="$(stat -c '%a' "$CONFIG" 2>/dev/null || stat -f '%Lp' "$CONFIG")"
  if [[ "${mode: -2}" != "00" ]]; then
    echo "[bluxgpt] WARNING: ~/.config/bluxgpt/.env (mode $mode) can be read by other users and may hold API keys."
    echo "[bluxgpt]          Fix it with: chmod 600 ~/.config/bluxgpt/.env"
  fi
fi
