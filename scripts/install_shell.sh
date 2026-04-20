#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
ZSH_LOCAL="$HOME/.zshrc.local"
BLOCK_START="### >>> BLUXGPT OVERLAY >>>"
BLOCK_END="### <<< BLUXGPT OVERLAY <<<"

# Ensure .zshrc.local exists
mkdir -p "$(dirname "$ZSH_LOCAL")"
touch "$ZSH_LOCAL"

# Read blux_fn.sh content
BLUX_FN_SH="$REPO_ROOT/bluxgpt/shell/blux_fn.sh"
if [[ ! -f "$BLUX_FN_SH" ]]; then
  echo "[install_shell] ERROR: blux_fn.sh not found at $BLUX_FN_SH" >&2
  exit 1
fi

# Strip existing block (awk is portable — no sed -i quoting differences)
TMP_FILE="$(mktemp)"
awk -v start="$BLOCK_START" -v end="$BLOCK_END" '
  $0 == start { skip=1; next }
  $0 == end   { skip=0; next }
  skip != 1   { print }
' "$ZSH_LOCAL" > "$TMP_FILE"

# Append new block — use printf to avoid echo portability issues
# Substitute __BLUXGPT_REPO_ROOT__ in blux_fn.sh with real path
BLUX_FN_CONTENT="$(sed "s|__BLUXGPT_REPO_ROOT__|${REPO_ROOT}|g" "$BLUX_FN_SH")"

printf '\n%s\n' "$BLOCK_START" >> "$TMP_FILE"
printf 'export BLUXGPT_VERSION="1.0.0"\n' >> "$TMP_FILE"
printf 'export BLUXGPT_HOME="${BLUXGPT_HOME:-$HOME/.config/bluxgpt}"\n' >> "$TMP_FILE"
printf 'export BLUXGPT_REPO_ROOT="%s"\n' "$REPO_ROOT" >> "$TMP_FILE"
printf 'export BLUXGPT_READY=1\n' >> "$TMP_FILE"
printf '\n' >> "$TMP_FILE"
printf '%s\n' "$BLUX_FN_CONTENT" >> "$TMP_FILE"
printf '%s\n' "$BLOCK_END" >> "$TMP_FILE"

mv "$TMP_FILE" "$ZSH_LOCAL"

echo "[install_shell] BluxGPT overlay installed to ~/.zshrc.local"
