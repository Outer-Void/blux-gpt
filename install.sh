#!/usr/bin/env bash
set -euo pipefail

echo "Installing BluxGPT..."

# Step 1: deps
bash scripts/check_deps.sh

# Step 2: venv
python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# Step 3: config
mkdir -p "$HOME/.config/bluxgpt"
if [[ ! -f "$HOME/.config/bluxgpt/.env" ]]; then
  cp config/.env.example "$HOME/.config/bluxgpt/.env"
fi

# Step 4: shell
bash scripts/install_shell.sh

echo "Done. Restart shell and run: blux version"
