from app.config import AppConfig, LLMPricingConfig, PricingTier, load_config
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


def test_cost_cny_branches():
    """覆盖 cost_cny 三个分支：known model / unknown + default / 未知无 default。"""
    # known model: 1000 tokens in, 1000 tokens out
    pricing = LLMPricingConfig(pricing={
        "gpt-5.2": PricingTier(**{"in": 0.005, "out": 0.015}),
        "default": PricingTier(**{"in": 0.001, "out": 0.002}),
    })
    # 1000 * 0.005/1000 + 1000 * 0.015/1000 = 0.005 + 0.015 = 0.02
    assert pricing.cost_cny("gpt-5.2", 1000, 1000) == 0.02

    # unknown model with default: 500 * 0.001/1000 + 500 * 0.002/1000 = 0.0005 + 0.001 = 0.0015
    assert pricing.cost_cny("claude-opus-4-8", 500, 500) == 0.0015

    # empty config: any model returns 0.0
    empty = LLMPricingConfig()
    assert empty.cost_cny("gpt-5.2", 1000, 1000) == 0.0
    assert empty.cost_cny("unknown-model", 1000, 1000) == 0.0

    # zero tokens: 0.0
    assert pricing.cost_cny("gpt-5.2", 0, 0) == 0.0
