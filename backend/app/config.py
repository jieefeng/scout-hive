import os
from pathlib import Path
import yaml
from pydantic import BaseModel, Field


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


class PricingTier(BaseModel):
    """CNY / 1k tokens 定价。"""
    in_cost: float = Field(alias="in")
    out_cost: float = Field(alias="out")

    model_config = {"populate_by_name": True}


class LLMPricingConfig(BaseModel):
    """LLM 定价表。键为 model 名（含 'default' 兜底）。"""
    pricing: dict[str, PricingTier] = Field(default_factory=dict)

    def cost_cny(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """估算成本（CNY）。未知 model 走 'default'，无 default 走 0。"""
        tier = self.pricing.get(model) or self.pricing.get("default")
        if not tier:
            return 0.0
        return (tokens_in / 1000.0) * tier.in_cost + (tokens_out / 1000.0) * tier.out_cost


class AppConfig(BaseModel):
    server: ServerConfig
    llm: LLMConfig
    dag: DAGConfig
    anysearch: AnySearchConfig = AnySearchConfig()
    llm_pricing: LLMPricingConfig = LLMPricingConfig()

    # 容忍 config.yaml 残留的旧字段(如废弃的 active_schema_id),避免重启即炸
    model_config = {"extra": "ignore"}


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
    # llm_pricing 在 YAML 里是扁平 {model: {in, out}}，需包成 {pricing: ...} 喂给 Pydantic。
    if isinstance(resolved, dict) and "llm_pricing" in resolved and isinstance(resolved["llm_pricing"], dict):
        resolved["llm_pricing"] = {"pricing": resolved["llm_pricing"]}
    return AppConfig(**resolved)
