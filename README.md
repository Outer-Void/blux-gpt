# BluxGPT v1.0

> Advisory AI CLI for the BLUX environment.  
> Part of the trifecta: **blux10k** · **AXIOM** · **BluxGPT**

---

## Model stack

| Lane | Key | Provider |
|---|---|---|
| Default | `gpt-5-mini` | OpenAI |
| Cheap | `deepseek-chat` | DeepSeek |
| Fast/light | `claude-haiku-4.5` | Anthropic |
| Reasoning | `deepseek-reasoner` | DeepSeek |

You only need API keys for models you intend to use.

**Aliases:** `claude`, `haiku`, `fast`, `deepseek`, `cheap`, `reasoner`, `reason`, `openai`, `gpt`

---

## Core rules

- Advisory only — suggests, never executes
- Never auto-runs its own output
- Never writes to `~/.zshrc` directly
- Installs through `~/.zshrc.local` overlay only
- Requires blux10k v2.0+ with `BLUX10K_READY=1` and a verifiable `check_version.sh`
- API keys are masked (`****last4`) in all logs

---

## Requirements

- blux10k v2.0 installed and active (`BLUX10K_READY=1`)
- Python >= 3.8

---

## Install

```bash
# blux10k must be installed first and your shell reloaded
./install.sh
source ~/.zshrc
blux status
```

Safe to re-run. The virtualenv is not recreated if it is already usable.

---

## Commands

```bash
blux version                             # BluxGPT version
blux status                              # configuration status (not live connectivity)
blux models                              # list models and aliases

blux ask "your question"                 # one-shot query (default model)
blux ask --model claude "..."            # use fast/light lane
blux ask --model deepseek-chat "..."     # use cheap lane
blux ask --model deepseek-reasoner "..." # use reasoning lane
blux ask --no-context "..."              # skip environment context injection

blux history                             # show recent history
blux history --raw                       # raw JSON output
blux history --limit 50                  # show more entries
blux history --clear                     # wipe history

blux uninstall                           # remove BLUXGPT OVERLAY from ~/.zshrc.local
```

---

## Config

User config: `~/.config/bluxgpt/.env`

Created automatically on first install from `config/.env.example`. Add your API keys there.

```bash
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
```

API model names are defined in the model registry (`bluxgpt/core/models.py`) and are not overridable via env vars. Lane selection (`BLUXGPT_DEFAULT_MODEL`, etc.) and API credentials are the only user-configurable values.

---

## blux status

`blux status` shows **Configuration Status** only. It does not make any API calls or verify provider connectivity.

- **"set"** means the key is present in your config file
- **"missing"** means the key is absent
- Neither implies the key is valid or the provider is reachable

---

## Context injection

By default, each request includes a system prompt with:

- Platform (`termux` / `proot-debian` / `debian` / `wsl` / `macos`)
- blux10k and AXIOM versions (if present)
- Current working directory, git branch and status
- Shell and user

Disable per-query with `--no-context`.

---

## blux10k dependency

BluxGPT requires blux10k v2.0+ to be installed and active. The dependency gate checks for `BLUX10K_READY=1` in your environment and requires `check_version.sh` to be present and executable.

Default install root: `~/.blux10k`

If blux10k is installed elsewhere, set `BLUX10K_INSTALL_DIR` before running the installer:

```bash
BLUX10K_INSTALL_DIR=/path/to/blux10k ./install.sh
```

---

## Optional developer tools

BluxGPT can optionally install Claude Code and OpenAI Codex during setup. These are not required for any core blux functionality.

```bash
BLUXGPT_INSTALL_CLAUDE_CODE=1 ./install.sh
BLUXGPT_INSTALL_CODEX=1 ./install.sh

# Both at once:
BLUXGPT_INSTALL_CLAUDE_CODE=1 BLUXGPT_INSTALL_CODEX=1 ./install.sh
```

Requires Node.js and npm. If npm is not present, the step is skipped cleanly.

Install commands used:

```bash
npm install -g @anthropic-ai/claude-code
npm i -g @openai/codex
```

---

## AXIOM integration

When AXIOM is installed and `AXIOM_READY=1`:

- `ax ai "question"` proxies to `blux ask`
- BluxGPT writes run logs to `$AXIOM_REPO_ROOT/cockpit/runs/`

---

## Logging

Local logs: `~/.config/bluxgpt/logs/<timestamp>_query.json`

---

## Running tests

Tests use **pytest**. `python -m unittest` is not supported.

```bash
source .venv/bin/activate
pytest
```

---

## Project layout

```
blux-gpt/
├── VERSION
├── install.sh
├── pyproject.toml
├── requirements.txt
├── config/
│   └── .env.example
├── bluxgpt/
│   ├── cli.py
│   ├── adapters/       OpenAI, DeepSeek, Claude
│   ├── core/           config, client, context, history, logger, models
│   └── shell/          blux() function and .zshrc.local overlay template
├── scripts/
│   ├── check_deps.sh
│   └── install_shell.sh
└── tests/
```

---

**JADIS — Just A Dude In Space**  
[Outer-Void/blux-gpt](https://github.com/Outer-Void/blux-gpt)
