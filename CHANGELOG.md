# Changelog

## Unreleased

- **Fixed (OV-64, F141).** `install.sh` created `~/.config/bluxgpt/.env`, the file it asks you to put API keys in,
  with the default umask (usually 0644: readable by other users). The config step is now
  `scripts/setup_config.sh`: a new file is 0600 in a 0700 directory, and an existing file that others can read
  gets a warning with the `chmod 600` command; it is never changed.
- **Fixed (OV-64, F118).** An OpenAI-compatible server running a reasoning model without a reasoning parser
  (for example Qwen3 on llama-server) returns its chain of thought as a leading `<think>…</think>` block. That
  text reached the answer and BLUX sessions unchanged. A leading `<think>` or `<thinking>` block is now dropped,
  in full responses and while streaming; an unclosed block leaves no answer text. A tag later in the answer is
  kept.
- **License.** The BLUX Proprietary License applies from 2026-10-25
  (Copyright (c) 2026 Outer-Void / Justadudeinspace (JADIS); contact outervoid.blux@gmail.com, fallback
  theoutervoid@outlook.com). Package metadata declares the matching `LicenseRef`. Copies and releases
  obtained before that date keep the Apache License 2.0.

## 2.0.0 (Stage 09)

BluxGPT becomes the provider gateway behind the BLUX Model API v1.

- **Logical models.** `blux-main`, `blux-fast`, `blux-reason` and `blux-code`, resolved through a
  `blux.model-routes` table. 1.0 lane names are mapped, with a notice.
- **Providers:**
  - OpenAI (Chat Completions), DeepSeek, and any OpenAI-compatible server (llama.cpp's `llama-server`,
    vLLM …);
  - Anthropic (Messages API; structured output via a forced tool);
  - a deterministic `mock` provider for tests and demos.
- **Transport.** Standard library only, deadline-bound. Retries with exponential backoff and `Retry-After`
  on rate limits, 5xx, network errors and timeouts. SSE streaming. One normalized error vocabulary,
  identical to BLUX's, including `PROVIDER_QUOTA_EXCEEDED` (found against real accounts with no balance).
- **Normalization.** Text, structured JSON, tool calls (returned, never executed), usage (input, output,
  reasoning and cached tokens), finish reasons, provider request ids. Provider reasoning text is discarded.
- **`bluxgpt blux-model-backend`.** BLUX's model-backend protocol: request on stdin, stream events on
  stdout.
- **Standalone client.** It keeps the same routing semantics, so `bluxgpt ask` targets logical models and
  reports every attempt.
- **CLI:** `ask` (`--stream`, `--json`, `--json-schema`, `--deterministic`, `--context`, `--no-fallback`),
  `models`, `status`, `check [--real]`, `history`, `uninstall`, `version`.
- **Privacy:**
  - no `blux` shell function (it shadowed the BLUX CLI);
  - no content logging;
  - no key fragments;
  - environment context is opt-in and minimal.
- **Tests:** mocked HTTP fixtures, the backend protocol and schema conformance, plus a separate REAL
  acceptance suite (`BLUXGPT_REAL_PROVIDERS=1`).
- **Dependencies:** none at runtime; it no longer needs typer, rich, openai, anthropic or python-dotenv.
- **Package metadata** declares Apache-2.0, matching LICENSE.

## 1.0.0

Initial advisory CLI (see docs/AUDIT-1.0.md).
