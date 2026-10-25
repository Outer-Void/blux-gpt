#!/usr/bin/env bash
set -euo pipefail

# install.sh — BluxGPT installer.
# Safe to re-run. Does not recreate the virtualenv if it is already usable.
#
# Optional developer-tool installs (off by default):
#   BLUXGPT_INSTALL_CLAUDE_CODE=1 ./install.sh   # installs @anthropic-ai/claude-code via npm
#   BLUXGPT_INSTALL_CODEX=1 ./install.sh          # installs @openai/codex via npm
#
# These are optional helpers — not required for core blux functionality.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$REPO_ROOT"

VENV_DIR="$REPO_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

echo "[bluxgpt] Installing BluxGPT v2.0"
echo "[bluxgpt] Repo root: $REPO_ROOT"

# Step 1: dependency check
echo "[bluxgpt] Checking dependencies..."
bash "$REPO_ROOT/scripts/check_deps.sh"

# Step 2: Python venv — create only if not already usable
if [[ -x "$VENV_PYTHON" ]] && "$VENV_PYTHON" -c "import sys; sys.exit(0)" 2>/dev/null; then
  echo "[bluxgpt] Virtual environment already exists and is usable — skipping creation."
else
  echo "[bluxgpt] Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Activate
# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

# Step 3: install/upgrade packages
# Always run so requirements drift is caught on re-runs.
echo "[bluxgpt] Installing/upgrading Python packages..."
pip install --upgrade pip --quiet
pip install -e "$REPO_ROOT" --quiet

# Step 4: user config
echo "[bluxgpt] Setting up user config..."
mkdir -p "$HOME/.config/bluxgpt"
if [[ ! -f "$HOME/.config/bluxgpt/.env" ]]; then
  cp "$REPO_ROOT/config/.env.example" "$HOME/.config/bluxgpt/.env"
  echo "[bluxgpt] Config created: ~/.config/bluxgpt/.env"
  echo "[bluxgpt] Add your API keys before running bluxgpt."
else
  echo "[bluxgpt] Config already exists: ~/.config/bluxgpt/.env"
fi

# Step 5: shell overlay
echo "[bluxgpt] Installing shell overlay..."
bash "$REPO_ROOT/scripts/install_shell.sh"

# Step 6: optional developer tools (npm-based, off by default)
# Returns 0 on success, 1 on skip (npm missing) or install error.
_install_npm_tool() {
  local label="$1"
  local cmd="$2"
  if ! command -v npm >/dev/null 2>&1; then
    echo "[bluxgpt] SKIP: npm not found — cannot install ${label}." >&2
    echo "[bluxgpt]       Install Node.js/npm first, then run: ${cmd}" >&2
    return 1
  fi
  echo "[bluxgpt] Optional: installing ${label}..."
  if eval "${cmd}"; then
    echo "[bluxgpt] ${label} installed."
    return 0
  else
    echo "[bluxgpt] WARN: ${label} install returned non-zero — check npm output above." >&2
    return 1
  fi
}

_CLAUDE_CODE_STATUS="not requested"
_CODEX_STATUS="not requested"

if [[ "${BLUXGPT_INSTALL_CLAUDE_CODE:-0}" == "1" ]]; then
  if _install_npm_tool "Claude Code" "npm install -g @anthropic-ai/claude-code"; then
    _CLAUDE_CODE_STATUS="installed"
  else
    _CLAUDE_CODE_STATUS="skipped"
  fi
fi

if [[ "${BLUXGPT_INSTALL_CODEX:-0}" == "1" ]]; then
  if _install_npm_tool "OpenAI Codex" "npm i -g @openai/codex"; then
    _CODEX_STATUS="installed"
  else
    _CODEX_STATUS="skipped"
  fi
fi

echo
echo "[bluxgpt] ────────────────────────────────"
echo "[bluxgpt]  core install   done"
echo "[bluxgpt]  claude-code    ${_CLAUDE_CODE_STATUS}"
echo "[bluxgpt]  codex          ${_CODEX_STATUS}"
echo "[bluxgpt] ────────────────────────────────"
echo
echo "  1. Add API keys:  ~/.config/bluxgpt/.env"
echo "  2. Reload shell:  source ~/.zshrc"
echo "  3. Verify:        bluxgpt status && bluxgpt check"
echo "  4. Try it:        bluxgpt ask \"your question\"            # blux-main by default"
echo "  5. With BLUX:     blux generate blux-main \"your question\""
