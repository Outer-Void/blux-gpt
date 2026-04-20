import os
from bluxgpt.core.context import build_context, render_context_block, render_system_prompt


def test_context_builds():
    ctx = build_context()
    assert hasattr(ctx, "cwd")
    assert hasattr(ctx, "user")
    assert hasattr(ctx, "platform")
    assert hasattr(ctx, "bluxgpt_version")


def test_context_cwd_is_string():
    ctx = build_context()
    assert isinstance(ctx.cwd, str)
    assert len(ctx.cwd) > 0


def test_context_bluxgpt_version_fallback():
    # Even without BLUXGPT_VERSION in env, should return a value
    original = os.environ.pop("BLUXGPT_VERSION", None)
    try:
        ctx = build_context()
        assert ctx.bluxgpt_version == "1.0.0"
    finally:
        if original is not None:
            os.environ["BLUXGPT_VERSION"] = original


def test_render_context_block_returns_string():
    block = render_context_block()
    assert isinstance(block, str)
    assert "BluxGPT environment context" in block


def test_render_system_prompt_contains_rules():
    prompt = render_system_prompt()
    assert "advisory only" in prompt.lower()
    assert "never" in prompt.lower()


def test_render_system_prompt_with_context():
    ctx = build_context()
    prompt = render_system_prompt(ctx)
    assert ctx.platform in prompt
