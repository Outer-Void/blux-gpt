# Changelog

## Unreleased

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
