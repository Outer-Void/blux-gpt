import json
from pathlib import Path
from unittest.mock import patch
import tempfile
import pytest

from bluxgpt.core import history as hist_module


@pytest.fixture(autouse=True)
def isolated_history(tmp_path):
    """Redirect history to a temp directory for each test."""
    fake_dir = tmp_path / "bluxgpt"
    fake_file = fake_dir / "history.jsonl"
    with (
        patch.object(hist_module, "HISTORY_DIR", fake_dir),
        patch.object(hist_module, "HISTORY_FILE", fake_file),
    ):
        yield fake_dir, fake_file


def test_ensure_history_dir_creates(isolated_history):
    fake_dir, _ = isolated_history
    hist_module.ensure_history_dir()
    assert fake_dir.exists()


def test_append_and_read(isolated_history):
    hist_module.append_history("gpt-5-mini", "hello", "world")
    entries = hist_module.read_history()
    assert len(entries) == 1
    assert entries[0]["model"] == "gpt-5-mini"
    assert entries[0]["prompt"] == "hello"
    assert entries[0]["response"] == "world"
    assert "timestamp" in entries[0]


def test_append_multiple(isolated_history):
    for i in range(5):
        hist_module.append_history("claude-haiku-4.5", f"q{i}", f"a{i}")
    entries = hist_module.read_history(limit=3)
    assert len(entries) == 3
    # should return last 3
    assert entries[-1]["prompt"] == "q4"


def test_clear_history(isolated_history):
    hist_module.append_history("deepseek-r2", "q", "a")
    hist_module.clear_history()
    entries = hist_module.read_history()
    assert entries == []


def test_read_empty(isolated_history):
    entries = hist_module.read_history()
    assert entries == []


def test_read_handles_corrupt_lines(isolated_history):
    _, fake_file = isolated_history
    hist_module.ensure_history_dir()
    fake_file.write_text(
        '{"model":"ok","prompt":"p","response":"r","timestamp":"t"}\n'
        'not valid json\n'
        '{"model":"ok2","prompt":"p2","response":"r2","timestamp":"t2"}\n',
        encoding="utf-8",
    )
    entries = hist_module.read_history()
    assert len(entries) == 2
