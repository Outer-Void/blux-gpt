# BluxGPT 2.0

BluxGPT is the provider gateway behind the **BLUX Model API v1**, and a small advisory CLI.

Applications ask BLUX for a **logical model** (`blux-main`, `blux-fast`, `blux-reason`, `blux-code`). BLUX
routes the request to a provider route, and BluxGPT does the provider work:

| BluxGPT owns | BluxGPT does not own |
|---|---|
| provider transport (OpenAI, Anthropic, DeepSeek, any OpenAI-compatible server such as llama.cpp's `llama-server`, and a deterministic `mock`) | an agent loop: tool calls are returned, never executed |
| retries with backoff and `Retry-After` | ecosystem orchestration |
| streaming (Server-Sent Events -> Model API stream events) | device control |
| timeouts and cancellation | capability authority: BLUX policy decides who may call a model |
| normalizing responses, usage, tool calls, structured output and errors | routing across providers: BLUX's router does that |

It needs no third-party Python packages: standard library only, Python 3.10+. It imports nothing from BLUX;
its documents are checked against BLUX's published schemas in CI.

## Install

```bash
./install.sh          # venv, ~/.config/bluxgpt/.env, and `bluxgpt` on PATH via ~/.zshrc.local
source ~/.zshrc
bluxgpt status        # which credentials are set (never their values)
bluxgpt check         # offline self-check with the mock provider
bluxgpt check --real  # one tiny prompt per real route (uses a little credit)
```

**Upgrading from 1.0.** 1.0's overlay defined a `blux` shell function, which shadowed the BLUX command
line. 2.0 installs `bluxgpt` instead and removes that function. Run `./install.sh` again to replace the
overlay. 1.0 lane names (`gpt-5-mini`, `claude`, `deepseek` …) still work with `-m` and in
`BLUXGPT_DEFAULT_MODEL`, mapped to logical models with a notice.

## Use

```bash
bluxgpt ask "how do I find large files?"               # blux-main
bluxgpt ask -m blux-fast "one-line summary of tar flags" --stream
bluxgpt ask -m blux-reason "plan a database migration" --json      # full blux.model-response
bluxgpt ask -m blux-code "write a jq filter" --json-schema schema.json
bluxgpt models                                          # logical models -> routes
bluxgpt history
```

Through BLUX, which adds policy, routing, fallback and receipts:

```bash
blux generate blux-main "how do I find large files?"
```

BLUX starts `bluxgpt blux-model-backend` for each route attempt; see BLUX `docs/model-api/v1.md`.

## Routing and failures

Routes come from `BLUXGPT_ROUTES` or the packaged default (`bluxgpt/data/routes.json`, the same
`blux.model-routes` format BLUX uses).

- **Order.** Routes are tried in order. A route that lacks a capability the request needs (streaming,
  tools, structured output) is skipped.
- **Fallback.** A failure moves to the next route only when the error allows it. Rate limits, outages,
  5xx, timeouts, missing credentials and exhausted billing all allow it. A provider's content-filter
  refusal never does.
- **Transparency.** Every response lists every attempt, and `degraded` is set when a fallback served it.
- **Total failure.** When nothing works, the error is `ALL_ROUTES_FAILED` with each attempt's code.

## Privacy

- **Credentials.** Credentials live in `~/.config/bluxgpt/.env` or the environment. They are sent only to
  their own provider, in a request header. They are never printed (not even the last four characters) and
  are scrubbed from every error message.
- **Context.** Environment context is off. `--context` adds only the platform and BLUX tool versions. 1.0
  sent your current directory, home path, user name and `git status` with every question.
- **History.** History stays local, and `BLUXGPT_HISTORY=0` turns it off. 1.0 also wrote every prompt,
  response and key fragment to a log directory by default; 2.0 has no such log.
- **Provider reasoning.** Reasoning text that providers return (DeepSeek `reasoning_content`, Anthropic
  thinking blocks) is discarded. Only its token count is kept.

## Tests

`pytest` covers:
- providers against local HTTP fixtures;
- transport retries and error mapping;
- streaming;
- routing and fallback;
- the backend protocol;
- the CLI;
- secret hygiene;
- schema conformance.

Tests that need real credentials run only with `BLUXGPT_REAL_PROVIDERS=1`, and their output says
**REAL**. Everything else is **mocked**, against local servers and fixtures that are documented as
hand-written, never captured traffic.

See [docs/AUDIT-1.0.md](docs/AUDIT-1.0.md) and [CHANGELOG.md](CHANGELOG.md). Licence: Apache-2.0
([LICENSE](LICENSE)).
