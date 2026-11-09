"""OV-64 (F141): the installer creates the file it asks you to put API keys in; it must not be world-readable.

Before OV-64, install.sh copied config/.env.example with the default umask (usually 0644) and then said
"Add your API keys". Now the config step (scripts/setup_config.sh) creates the file as 0600 in a 0700 directory,
and warns, without changing anything, when an existing file is readable by others.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "setup_config.sh"


def run(home: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False)


def test_a_new_config_is_private(tmp_path: Path) -> None:
    old = os.umask(0o022)
    try:
        p = run(tmp_path)
    finally:
        os.umask(old)
    assert p.returncode == 0, p.stderr
    cfg = tmp_path / ".config" / "bluxgpt" / ".env"
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o600
    assert stat.S_IMODE(cfg.parent.stat().st_mode) == 0o700
    assert cfg.read_text() == (ROOT / "config" / ".env.example").read_text()


def test_an_existing_readable_config_is_reported_not_changed(tmp_path: Path) -> None:
    cfg = tmp_path / ".config" / "bluxgpt" / ".env"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("OPENAI_API_KEY=x\n")
    cfg.chmod(0o644)
    p = run(tmp_path)
    assert p.returncode == 0
    assert "chmod 600" in p.stdout + p.stderr
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o644 and cfg.read_text() == "OPENAI_API_KEY=x\n"


def test_install_sh_uses_the_config_step() -> None:
    text = (ROOT / "install.sh").read_text()
    assert "scripts/setup_config.sh" in text
    assert 'cp "$REPO_ROOT/config/.env.example"' not in text
