"""What BluxGPT tells a model about its environment.

1.0 sent the current directory, home path, user name, shell and `git status` to the provider with every
question, by default. 2.0 sends nothing unless asked: `--context` (or BLUXGPT_CONTEXT=basic) adds only the
platform and the BLUX tool versions, never paths, user names or repository contents.
"""

from __future__ import annotations

import os

from bluxgpt import __version__

SYSTEM_PROMPT = """\
You are BluxGPT, an advisory assistant for the BLUX terminal environment.
You suggest; you never execute. Your output is never run automatically.
Be direct and honest; when you do not know, say so.""".strip()


def platform_name() -> str:
    if os.getenv("TERMUX_VERSION") or os.path.isdir("/data/data/com.termux"):
        return "proot-debian" if os.path.exists("/etc/debian_version") and os.getenv("PROOT_DISTRIBUTION") else "termux"
    if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop") or os.getenv("WSL_DISTRO_NAME"):
        return "wsl"
    if os.path.exists("/etc/debian_version"):
        return "debian"
    import platform

    return "macos" if platform.system() == "Darwin" else "linux"


def basic_context() -> dict[str, str]:
    lines = [f"platform: {platform_name()}", f"bluxgpt: {__version__}"]
    for name, var in (("blux10k", "BLUX10K_VERSION"), ("axiom", "AXIOM_VERSION")):
        if os.getenv(var):
            lines.append(f"{name}: {os.getenv(var)}")
    return {"kind": "environment", "title": "BLUX environment", "content": "\n".join(lines)}
