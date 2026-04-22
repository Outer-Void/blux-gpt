from bluxgpt.core.models import MODEL_REGISTRY, MODEL_ALIASES, resolve_model
import pytest


def test_registry_has_all_models():
    assert "gpt-5-mini" in MODEL_REGISTRY
    assert "deepseek-chat" in MODEL_REGISTRY
    assert "deepseek-reasoner" in MODEL_REGISTRY
    assert "claude-haiku-4.5" in MODEL_REGISTRY


def test_registry_does_not_have_old_key():
    assert "deepseek-r2" not in MODEL_REGISTRY


def test_model_spec_fields():
    spec = MODEL_REGISTRY["gpt-5-mini"]
    assert spec.provider == "openai"
    assert spec.key == "gpt-5-mini"
    assert spec.description
    assert spec.api_model_name


def test_deepseek_chat_spec():
    spec = MODEL_REGISTRY["deepseek-chat"]
    assert spec.provider == "deepseek"
    assert spec.key == "deepseek-chat"
    assert spec.description


def test_deepseek_reasoner_spec():
    spec = MODEL_REGISTRY["deepseek-reasoner"]
    assert spec.provider == "deepseek"
    assert spec.key == "deepseek-reasoner"
    assert spec.description


# ---------------------------------------------------------------------------
# API model name lock — registry is the single source of truth for what name
# is sent to each provider. These tests must not be changed without updating
# the provider integration accordingly.
# ---------------------------------------------------------------------------

def test_openai_api_model_name():
    assert MODEL_REGISTRY["gpt-5-mini"].api_model_name == "gpt-5-mini"


def test_deepseek_chat_api_model_name():
    assert MODEL_REGISTRY["deepseek-chat"].api_model_name == "deepseek-chat"


def test_deepseek_reasoner_api_model_name():
    assert MODEL_REGISTRY["deepseek-reasoner"].api_model_name == "deepseek-reasoner"


def test_anthropic_api_model_name():
    # The user-facing lane key and the actual Anthropic API model name differ.
    # The registry holds the authoritative API model name.
    assert MODEL_REGISTRY["claude-haiku-4.5"].api_model_name == "claude-haiku-4-5-20251001"


def test_resolve_canonical_key():
    assert resolve_model("gpt-5-mini") == "gpt-5-mini"
    assert resolve_model("deepseek-chat") == "deepseek-chat"
    assert resolve_model("deepseek-reasoner") == "deepseek-reasoner"
    assert resolve_model("claude-haiku-4.5") == "claude-haiku-4.5"


def test_resolve_aliases():
    assert resolve_model("claude") == "claude-haiku-4.5"
    assert resolve_model("haiku") == "claude-haiku-4.5"
    assert resolve_model("fast") == "claude-haiku-4.5"
    assert resolve_model("deepseek") == "deepseek-chat"
    assert resolve_model("cheap") == "deepseek-chat"
    assert resolve_model("reasoner") == "deepseek-reasoner"
    assert resolve_model("reason") == "deepseek-reasoner"
    assert resolve_model("openai") == "gpt-5-mini"
    assert resolve_model("gpt") == "gpt-5-mini"


def test_resolve_unknown_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        resolve_model("not-a-real-model")


def test_resolve_old_deepseek_key_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        resolve_model("deepseek-r2")


def test_all_aliases_point_to_valid_keys():
    for alias, target in MODEL_ALIASES.items():
        assert target in MODEL_REGISTRY, f"Alias '{alias}' points to unknown key '{target}'"
