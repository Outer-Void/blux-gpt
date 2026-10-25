# Audit of BluxGPT 1.0 (Stage 09)

| # | finding | 2.0 |
|---|---|---|
| 1 | **The overlay defined `blux()`.** It shadowed the BLUX command line in every shell that loaded it. Throughout Stages 02–08, `blux` ran BluxGPT instead of BLUX. | The overlay installs `bluxgpt` and runs `unfunction blux`. |
| 2 | **Applications picked vendor models.** `gpt-5-mini`, `claude-haiku-4.5` and `deepseek-chat` were named directly; the routing table lived in code. | Logical models (`blux-main` …) and a `blux.model-routes` table. |
| 3 | **No timeout, retry, streaming or normalized errors.** Provider exceptions surfaced raw, and the Anthropic adapter capped output at 1,024 tokens. | Deadline-bound transport, retries with backoff, SSE streaming, one error shape. |
| 4 | **Request logging was on by default.** It wrote every prompt and response, plus the last four characters of each API key, to `~/.config/bluxgpt/logs`, and copied them into AXIOM run directories. | No content log. History is local and can be switched off; no key fragments anywhere. |
| 5 | **Context injection sent personal data to providers by default.** Current directory, home path, user name, shell and `git status` went with every question. | Off by default; `--context` sends only the platform and tool versions. |
| 6 | **`blux status` printed key fragments** (`****last4`). | Presence only. |
| 7 | **Heavy dependencies:** typer, rich, the openai and anthropic SDKs, python-dotenv. | Standard library only. |
| 8 | **No CI;** three tests covered the model table and history. | CI, with tests for providers, transport, routing, backend protocol, CLI, secrets and conformance. |
| 9 | **Package metadata declared no licence** (credits UNR-013). | `license = "Apache-2.0"`, matching LICENSE. Relicensing remains the owner's decision (UNR-008). |
