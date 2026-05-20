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


class DAGConfig(BaseModel):
    max_feedback_rounds: int = 3
    node_timeout_seconds: int = 300
    max_retries: int = 3


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class AppConfig(BaseModel):
    server: ServerConfig
    llm: LLMConfig
    dag: DAGConfig


def load_config(config_path: str | None = None) -> AppConfig:
    if config_path is None:
        config_path = str(Path(__file__).parent.parent / "config.yaml")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # 替换环境变量
    def resolve_env(obj):
        if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_key = obj[2:-1]
            return os.environ.get(env_key, "")
        elif isinstance(obj, dict):
            return {k: resolve_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_env(item) for item in obj]
        return obj

    resolved = resolve_env(raw)
    return AppConfig(**resolved)
