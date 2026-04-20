#!/usr/bin/env bash
set -euo pipefail

ZSH_LOCAL="$HOME/.zshrc.local"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.."; pwd -P)"

BLOCK_START="### >>> BLUXGPT OVERLAY >>>"
BLOCK_END="### <<< BLUXGPT OVERLAY <<<"

OVERLAY=$(cat <<EOF
$BLOCK_START
export BLUXGPT_VERSION="1.0.0"
export BLUXGPT_REPO_ROOT="$REPO_ROOT"
export BLUXGPT_READY=1

blux() {
  "$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/bluxgpt/cli.py" "\$@"
}
$BLOCK_END
EOF
)

# Ensure file exists
touch "$ZSH_LOCAL"

# Remove existing block
sed -i "/$BLOCK_START/,/$BLOCK_END/d" "$ZSH_LOCAL"

# Append new block
echo "$OVERLAY" >> "$ZSH_LOCAL"

echo "BluxGPT overlay installed"
