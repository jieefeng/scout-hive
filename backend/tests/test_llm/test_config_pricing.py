from app.config import AppConfig, LLMPricingConfig, load_config
import tempfile
import os
import yaml


def test_llm_pricing_loaded_from_yaml():
    raw = {
        "server": {"host": "0.0.0.0", "port": 5010},
        "llm": {
            "default": "x",
            "adapters": {"x": {"type": "openai", "model": "gpt-5.2"}},
            "agent_bindings": {},
        },
        "dag": {},
        "anysearch": {},
        "llm_pricing": {
            "gpt-5.2": {"in": 0.005, "out": 0.015},
            "default": {"in": 0.001, "out": 0.002},
        },
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.safe_dump(raw, f)
        path = f.name
    try:
        cfg = load_config(path)
        assert isinstance(cfg.llm_pricing, LLMPricingConfig)
        assert cfg.llm_pricing.pricing["gpt-5.2"].in_cost == 0.005
        assert cfg.llm_pricing.pricing["gpt-5.2"].out_cost == 0.015
        assert cfg.llm_pricing.pricing["default"].in_cost == 0.001
    finally:
        os.unlink(path)


def test_llm_pricing_missing_uses_empty_default():
    raw = {
        "server": {"host": "0.0.0.0", "port": 5010},
        "llm": {
            "default": "x",
            "adapters": {"x": {"type": "openai", "model": "gpt-5.2"}},
            "agent_bindings": {},
        },
        "dag": {},
        "anysearch": {},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.safe_dump(raw, f)
        path = f.name
    try:
        cfg = load_config(path)
        assert cfg.llm_pricing.pricing == {}
    finally:
        os.unlink(path)
