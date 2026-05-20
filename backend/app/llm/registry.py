from app.llm.base import LLMAdapter
from app.llm.claude_adapter import ClaudeAdapter
from app.llm.openai_adapter import OpenAIAdapter
from app.llm.local_adapter import LocalAdapter
from app.config import LLMConfig


class LLMRegistry:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._adapters: dict[str, LLMAdapter] = {}

    def _create_adapter(self, name: str) -> LLMAdapter:
        cfg = self.config.adapters[name]
        if cfg.type == "claude":
            return ClaudeAdapter(api_key=cfg.api_key or "", model=cfg.model)
        elif cfg.type == "openai":
            return OpenAIAdapter(api_key=cfg.api_key or "", model=cfg.model)
        elif cfg.type == "local":
            return LocalAdapter(endpoint=cfg.endpoint or "http://localhost:11434", model=cfg.model)
        else:
            raise ValueError(f"Unknown adapter type: {cfg.type}")

    def get(self, name: str) -> LLMAdapter:
        if name not in self._adapters:
            self._adapters[name] = self._create_adapter(name)
        return self._adapters[name]

    def get_for_agent(self, agent_name: str) -> LLMAdapter:
        adapter_name = self.config.agent_bindings.get(agent_name, self.config.default)
        return self.get(adapter_name)
