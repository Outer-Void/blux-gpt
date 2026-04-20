# BluxGPT v1.0

> Advisory AI CLI for the BLUX environment.  
> Part of the trifecta: **blux10k** · **AXIOM** · **BluxGPT**

---

## Model stack

| Lane | Key | Provider | Notes |
|---|---|---|---|
| Default | `gpt-5-mini` | OpenAI | Balanced |
| Cheap | `deepseek-r2` | DeepSeek | Cost-efficient |
| Fast/light | `claude-haiku-4.5` | Anthropic | Low latency |

Aliases: `claude`, `haiku`, `fast`, `deepseek`, `cheap`, `openai`, `gpt`

---

## Core rules

- Advisory only — suggests, never executes
- Never auto-runs its own output
- Never writes to `~/.zshrc` directly
- Installs through `~/.zshrc.local` overlay only
- Requires `BLUX10K_READY=1` (blux10k v2.0+)
- All API keys masked in logs

---

## Requirements

- blux10k v2.0 installed and active (`BLUX10K_READY=1`)
- Python >= 3.8

---

## Install

```bash
# blux10k must already be installed and your shell reloaded
./install.sh
source ~/.zshrc
blux status
```

---

## Commands

```bash
blux version                           # print BluxGPT + trifecta versions
blux status                            # config and API key health
blux models                            # list all models and aliases

blux ask "your question"               # one-shot query (default model)
blux ask --model deepseek-r2 "..."    # use cheap lane
blux ask --model claude "..."         # use fast lane (alias works)
blux ask --no-context "..."           # skip env context injection

blux history                           # show recent history (formatted)
blux history --raw                     # raw JSON output
blux history --limit 50                # more entries
blux history --clear                   # wipe history

blux uninstall                         # remove BLUXGPT OVERLAY from ~/.zshrc.local
```

---

## Config

User config file: `~/.config/bluxgpt/.env`

Created automatically on first install from `config/.env.example`.

```bash
# Set your API keys:
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=...
OPENAI_API_KEY=sk-...
```

You only need to set keys for models you intend to use.

---

## Context injection

By default, BluxGPT injects a system prompt that includes:

- Platform (`proot-debian` / `termux` / `debian` / `wsl` / `macos`)
- blux10k version, AXIOM version
- Current working directory
- Git branch and status (if in a repo)
- Shell, user, terminal

This makes responses aware of your environment without you having to explain it.  
Disable per-query with `--no-context`.

---

## AXIOM integration

When `AXIOM_READY=1` is set:

- `ax ai "question"` proxies directly to `blux ask`
- BluxGPT writes run logs to `$AXIOM_REPO_ROOT/cockpit/runs/`
- Overwatch AI panel uses BluxGPT as its backend

---

## Logging

Local logs: `~/.config/bluxgpt/logs/<timestamp>_query.json`  
AXIOM runs: `$AXIOM_REPO_ROOT/cockpit/runs/<timestamp>_ai_bluxgpt/` (when AXIOM present)

API keys are always masked (`****last4`) in all log files.

---

## Project layout

```
blux-gpt/
├── VERSION
├── install.sh
├── requirements.txt
├── pyproject.toml
├── config/
│   └── .env.example
├── bluxgpt/
│   ├── cli.py              entry point
│   ├── adapters/           model adapters (OpenAI, DeepSeek, Claude)
│   ├── core/               config, client, context, history, logger, models
│   └── shell/              .zshrc.local overlay template and blux() function
├── scripts/
│   ├── check_deps.sh       blux10k gate + Python version check
│   └── install_shell.sh    injects BLUXGPT OVERLAY into ~/.zshrc.local
└── tests/
```

---

## What's not in v1.0

- Streaming responses
- Interactive chat sessions (`blux chat`)
- AXIOM Overwatch panel wiring (backend detection is ready; panel UI is in AXIOM)
- Richer `ax doctor` BluxGPT section

These are v1.1+ scope.

---

[**JADIS — Just A Dude In Space**](https://github.com/Outer-Void/Justadudeinspace)
[Outer-Void](https://github.com/Outer-Void/blux-gpt)
