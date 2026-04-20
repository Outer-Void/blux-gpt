from bluxgpt.core.models import MODEL_REGISTRY, MODEL_ALIASES, resolve_model
import pytest


def test_registry_has_all_models():
    assert "gpt-5-mini" in MODEL_REGISTRY
    assert "deepseek-r2" in MODEL_REGISTRY
    assert "claude-haiku-4.5" in MODEL_REGISTRY


def test_model_spec_fields():
    spec = MODEL_REGISTRY["gpt-5-mini"]
    assert spec.provider == "openai"
    assert spec.key == "gpt-5-mini"
    assert spec.description


def test_resolve_canonical_key():
    assert resolve_model("gpt-5-mini") == "gpt-5-mini"
    assert resolve_model("deepseek-r2") == "deepseek-r2"
    assert resolve_model("claude-haiku-4.5") == "claude-haiku-4.5"


def test_resolve_aliases():
    assert resolve_model("claude") == "claude-haiku-4.5"
    assert resolve_model("haiku") == "claude-haiku-4.5"
    assert resolve_model("fast") == "claude-haiku-4.5"
    assert resolve_model("deepseek") == "deepseek-r2"
    assert resolve_model("cheap") == "deepseek-r2"
    assert resolve_model("openai") == "gpt-5-mini"
    assert resolve_model("gpt") == "gpt-5-mini"


def test_resolve_unknown_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        resolve_model("not-a-real-model")


def test_all_aliases_point_to_valid_keys():
    for alias, target in MODEL_ALIASES.items():
        assert target in MODEL_REGISTRY, f"Alias '{alias}' points to unknown key '{target}'"
