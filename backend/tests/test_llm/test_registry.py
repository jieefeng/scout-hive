import pytest
from app.config import LLMConfig, LLMAdapterConfig
from app.llm.registry import LLMRegistry


def test_registry_creation():
    config = LLMConfig(
        default="test",
        adapters={"test": LLMAdapterConfig(type="local", model="llama3", endpoint="http://localhost:11434")},
        agent_bindings={"Analyst": "test"},
    )
    registry = LLMRegistry(config)
    adapter = registry.get("test")
    assert adapter is not None


def test_registry_agent_binding():
    config = LLMConfig(
        default="default_adapter",
        adapters={
            "default_adapter": LLMAdapterConfig(type="local", model="llama3"),
            "special": LLMAdapterConfig(type="local", model="mistral"),
        },
        agent_bindings={"Analyst": "special"},
    )
    registry = LLMRegistry(config)
    adapter = registry.get_for_agent("Analyst")
    assert adapter.model == "mistral"
    default_adapter = registry.get_for_agent("Writer")
    assert default_adapter.model == "llama3"
