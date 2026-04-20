from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import os
import subprocess


@dataclass
class BluxContext:
    platform: str
    blux10k_version: str
    axiom_version: str
    bluxgpt_version: str
    cwd: str
    home: str
    shell: str
    git_branch: str
    git_status: str
    term: str
    user: str


def _run(cmd: list) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _detect_platform() -> str:
    """Return a meaningful platform string consistent with AXIOM's naming."""
    # Termux native
    if os.getenv("TERMUX_VERSION") or os.path.isdir("/data/data/com.termux"):
        # Check if we're inside a proot-distro Debian session
        if os.path.exists("/etc/debian_version") and os.getenv("PROOT_DISTRIBUTION"):
            return "proot-debian"
        return "termux"
    # WSL
    if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
        return "wsl"
    if os.getenv("WSL_DISTRO_NAME") or os.getenv("WSL_INTEROP"):
        return "wsl"
    # Debian/Ubuntu
    if os.path.exists("/etc/debian_version"):
        return "debian"
    # macOS
    try:
        import platform as _platform
        if _platform.system() == "Darwin":
            return "macos"
    except Exception:
        pass
    return "linux"


def build_context() -> BluxContext:
    return BluxContext(
        platform=_detect_platform(),
        blux10k_version=os.getenv("BLUX10K_VERSION", ""),
        axiom_version=os.getenv("AXIOM_VERSION", ""),
        bluxgpt_version=os.getenv("BLUXGPT_VERSION", "1.0.0"),
        cwd=str(Path.cwd()),
        home=str(Path.home()),
        shell=os.getenv("SHELL", ""),
        git_branch=_run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        git_status=_run(["git", "status", "--short"]),
        term=os.getenv("TERM", ""),
        user=os.getenv("USER", os.getenv("LOGNAME", "")),
    )


def render_context_block() -> str:
    ctx = asdict(build_context())
    lines = ["[BluxGPT environment context]"]
    for key, value in ctx.items():
        if value:  # skip empty fields
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = """\
You are BluxGPT — the advisory AI companion for the JADIS terminal environment (BLUX).
You run inside the BLUX trifecta: blux10k v{blux10k_version} / AXIOM v{axiom_version} / BluxGPT v{bluxgpt_version}.
Platform: {platform}. Current directory: {cwd}. Shell: {shell}. User: {user}.

Core rules you never violate:
- You are advisory only. You suggest. You do not execute.
- You never auto-run your own output.
- You never write to ~/.zshrc directly.
- You are direct, honest, no filler, no performance.
- When you don't know, you say so.
""".strip()


def render_system_prompt(ctx: BluxContext | None = None) -> str:
    if ctx is None:
        ctx = build_context()
    return SYSTEM_PROMPT_TEMPLATE.format(
        blux10k_version=ctx.blux10k_version or "unknown",
        axiom_version=ctx.axiom_version or "not installed",
        bluxgpt_version=ctx.bluxgpt_version,
        platform=ctx.platform,
        cwd=ctx.cwd,
        shell=ctx.shell or "unknown",
        user=ctx.user or "unknown",
    )
