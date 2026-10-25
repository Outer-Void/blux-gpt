#!/usr/bin/env bash
# Install the BluxGPT shell overlay into ~/.zshrc.local (replacing any earlier BLUXGPT OVERLAY block).
#
# 2.0 puts a `bluxgpt` executable on PATH (a link in $BLUXGPT_HOME/bin to the venv's console script), so
# both your shell and BLUX (which runs `bluxgpt blux-model-backend`) can find it. It no longer defines a
# `blux` shell function: in 1.0 that function shadowed the BLUX command line itself.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
ZSH_LOCAL="$HOME/.zshrc.local"
BLUXGPT_HOME="${BLUXGPT_HOME:-$HOME/.config/bluxgpt}"
BLOCK_START="### >>> BLUXGPT OVERLAY >>>"
BLOCK_END="### <<< BLUXGPT OVERLAY <<<"

if [[ ! -x "$REPO_ROOT/.venv/bin/bluxgpt" ]]; then
  echo "[install_shell] ERROR: $REPO_ROOT/.venv/bin/bluxgpt not found; run ./install.sh first" >&2
  exit 1
fi
mkdir -p "$BLUXGPT_HOME/bin"
ln -sf "$REPO_ROOT/.venv/bin/bluxgpt" "$BLUXGPT_HOME/bin/bluxgpt"

touch "$ZSH_LOCAL"
TMP_FILE="$(mktemp)"
awk -v start="$BLOCK_START" -v end="$BLOCK_END" '
  $0 == start { skip=1; next }
  $0 == end   { skip=0; next }
  skip != 1   { print }
' "$ZSH_LOCAL" > "$TMP_FILE"
{
  printf '\n%s\n' "$BLOCK_START"
  printf '# BluxGPT 2.0 shell overlay. Managed by BluxGPT; remove with: bluxgpt uninstall\n'
  printf 'export BLUXGPT_VERSION="2.0.0"\n'
  printf 'export BLUXGPT_HOME="%s"\n' "$BLUXGPT_HOME"
  printf 'export BLUXGPT_READY=1\n'
  printf 'case ":$PATH:" in *":%s/bin:"*) ;; *) export PATH="%s/bin:$PATH" ;; esac\n' "$BLUXGPT_HOME" "$BLUXGPT_HOME"
  printf '# 1.0 defined a blux() function here; it shadowed the BLUX CLI. Remove it if this shell still has it.\n'
  printf 'unfunction blux 2>/dev/null || true\n'
  printf '%s\n' "$BLOCK_END"
} >> "$TMP_FILE"
mv "$TMP_FILE" "$ZSH_LOCAL"
echo "[install_shell] BluxGPT overlay installed to ~/.zshrc.local (bluxgpt on PATH via $BLUXGPT_HOME/bin)"
