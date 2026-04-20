### >>> BLUXGPT OVERLAY >>>
# BluxGPT v1.0 shell overlay
# Managed by BluxGPT. Remove with: blux uninstall
export BLUXGPT_VERSION="1.0.0"
export BLUXGPT_HOME="${BLUXGPT_HOME:-$HOME/.config/bluxgpt}"
export BLUXGPT_REPO_ROOT="__BLUXGPT_REPO_ROOT__"
export BLUXGPT_READY=1

blux() {
  local _venv="${BLUXGPT_REPO_ROOT}/.venv/bin/python"
  local _cli="${BLUXGPT_REPO_ROOT}/bluxgpt/cli.py"

  if [[ -z "${BLUXGPT_REPO_ROOT:-}" ]]; then
    echo "blux: BLUXGPT_REPO_ROOT is not set. Re-run: source ~/.zshrc" >&2
    return 1
  fi

  if [[ ! -f "$_venv" ]]; then
    echo "blux: venv not found at ${_venv}" >&2
    echo "blux: Re-run: cd ${BLUXGPT_REPO_ROOT} && ./install.sh" >&2
    return 1
  fi

  if [[ ! -f "$_cli" ]]; then
    echo "blux: cli.py not found at ${_cli}" >&2
    return 1
  fi

  "$_venv" "$_cli" "$@"
}
### <<< BLUXGPT OVERLAY <<<
