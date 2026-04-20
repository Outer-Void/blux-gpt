#!/usr/bin/env bash
set -euo pipefail

# Check BLUX10K_READY
if [[ "${BLUX10K_READY:-0}" != "1" ]]; then
  echo "BluxGPT requires blux10k v2.0 (BLUX10K_READY not set)" >&2
  exit 1
fi

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 is required" >&2
  exit 1
fi

echo "Dependencies OK"
