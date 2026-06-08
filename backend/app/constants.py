"""硬收窄后的全局常量。

唯一垂直 schema = `schemas/ai_assistant.json`,7 维度白名单在 import 时 cache
成 frozenset,供 parse / tasks / orchestrator / task_parser 4 个消费点共用。

加新维度:改 `ai_assistant.json` → 重启服务即可。
"""
import json
from pathlib import Path

AI_ASSISTANT_SCHEMA_PATH: Path = (
    Path(__file__).parent / "schemas" / "ai_assistant.json"
)


def _load_allowed_dimensions() -> frozenset[str]:
    raw = json.loads(AI_ASSISTANT_SCHEMA_PATH.read_text(encoding="utf-8"))
    dims = [
        dim["name"]
        for group in raw["groups"]
        for dim in group["dimensions"]
    ]
    return frozenset(dims)


# 模块级 cache:import 时 load 一次,之后不再读盘
ALLOWED_DIMENSIONS: frozenset[str] = _load_allowed_dimensions()
