#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

# --- blux10k readiness ---
if [[ "${BLUX10K_READY:-0}" != "1" ]]; then
  echo "[check_deps] ERROR: BLUX10K_READY is not set." >&2
  echo "[check_deps] BluxGPT requires blux10k v2.0 to be installed and active." >&2
  echo "[check_deps] Install blux10k: https://github.com/Outer-Void/blux10k" >&2
  exit 1
fi

# --- blux10k version gate ---
BLUX10K_ROOT="${HOME}/.blux10k"
CHECK_VERSION="${BLUX10K_ROOT}/scripts/check_version.sh"
REQUIRED_VERSION="2.0.0"

if [[ -x "$CHECK_VERSION" ]]; then
  if ! "$CHECK_VERSION" "$REQUIRED_VERSION" 2>/dev/null; then
    echo "[check_deps] ERROR: blux10k version requirement not met (need >= ${REQUIRED_VERSION})." >&2
    exit 1
  fi
else
  # Fallback: check BLUX10K_VERSION env var
  installed="${BLUX10K_VERSION:-}"
  if [[ -z "$installed" ]]; then
    echo "[check_deps] WARN: check_version.sh not found and BLUX10K_VERSION not set." >&2
    echo "[check_deps] Assuming version requirement met — proceeding." >&2
  else
    # Simple semver check: split on dots
    IFS='.' read -r -a inst_parts <<< "$installed"
    IFS='.' read -r -a req_parts <<< "$REQUIRED_VERSION"
    meets=1
    for i in 0 1 2; do
      inst_n="${inst_parts[$i]:-0}"
      req_n="${req_parts[$i]:-0}"
      if [[ "$inst_n" -lt "$req_n" ]]; then
        meets=0
        break
      elif [[ "$inst_n" -gt "$req_n" ]]; then
        break
      fi
    done
    if [[ "$meets" == "0" ]]; then
      echo "[check_deps] ERROR: BLUX10K_VERSION=${installed} does not meet >= ${REQUIRED_VERSION}." >&2
      exit 1
    fi
  fi
fi

# --- Python 3.8+ ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "[check_deps] ERROR: python3 not found in PATH." >&2
  exit 1
fi

py_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
py_major="$(python3 -c 'import sys; print(sys.version_info.major)')"
py_minor="$(python3 -c 'import sys; print(sys.version_info.minor)')"

if [[ "$py_major" -lt 3 ]] || { [[ "$py_major" -eq 3 ]] && [[ "$py_minor" -lt 8 ]]; }; then
  echo "[check_deps] ERROR: Python >= 3.8 required. Found: ${py_version}" >&2
  exit 1
fi

echo "[check_deps] OK — blux10k ready, Python ${py_version}"
