import os
from pathlib import Path
import yaml
from pydantic import BaseModel


class LLMAdapterConfig(BaseModel):
    type: str
    model: str
    api_key: str | None = None
    endpoint: str | None = None


class LLMConfig(BaseModel):
    default: str
    adapters: dict[str, LLMAdapterConfig]
    agent_bindings: dict[str, str]

    def model_post_init(self, __context) -> None:
        if self.default not in self.adapters:
            raise ValueError(
                f"Default adapter '{self.default}' not in {list(self.adapters.keys())}"
            )
        for agent, adapter_name in self.agent_bindings.items():
            if adapter_name not in self.adapters:
                raise ValueError(
                    f"Agent '{agent}' is bound to adapter '{adapter_name}', "
                    f"but only {list(self.adapters.keys())} are defined"
                )


class DAGConfig(BaseModel):
    max_feedback_rounds: int = 3
    node_timeout_seconds: int = 300
    max_retries: int = 3


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 5010
    debug: bool = False


class AnySearchConfig(BaseModel):
    api_key: str = ""
    search_timeout: int = 15
    extract_timeout: int = 30
    max_results_per_query: int = 5


class AppConfig(BaseModel):
    server: ServerConfig
    llm: LLMConfig
    dag: DAGConfig
    anysearch: AnySearchConfig = AnySearchConfig()


def load_config(config_path: str | None = None) -> AppConfig:
    if config_path is None:
        config_path = str(Path(__file__).parent.parent / "config.yaml")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # 替换环境变量
    def resolve_env(obj):
        if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_key = obj[2:-1]
            return os.environ.get(env_key)  # None if missing, not empty string
        elif isinstance(obj, dict):
            return {k: resolve_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_env(item) for item in obj]
        return obj

    resolved = resolve_env(raw)
    return AppConfig(**resolved)
