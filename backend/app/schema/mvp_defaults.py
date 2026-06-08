"""Schema 数据模型 + 唯一入口 `get_active_schema()`。

历史:本模块原含 `DEFAULT_SCHEMA` dict + `load_default_schema()` + `load_active_schema()`
delegate 链,2026-06-08 硬收窄到单 ai-assistant schema 后全部下线,只留:

1. 3 个 Pydantic 模型(`DimensionSchema` / `GroupSchema` / `SchemaDefinition`)
2. 单一入口 `get_active_schema() -> SchemaDefinition`(读 ai_assistant.json)
"""
import json
from typing import Literal

from pydantic import BaseModel, Field

from app.constants import AI_ASSISTANT_SCHEMA_PATH

OutputType = Literal["table", "paragraph", "battlecard"]


class DimensionSchema(BaseModel):
    name: str
    description: str = ""
    keywords: list[str] = Field(min_length=1)
    output_type: OutputType = "paragraph"
    evidence_threshold: int = Field(default=1, ge=1)
    tracking_sources: list[str] = Field(default=["web"])
    fields: list[dict] = Field(default_factory=list)
    quality_rules: list[str] = Field(default_factory=list)


class GroupSchema(BaseModel):
    name: str
    description: str = ""
    dimensions: list[DimensionSchema] = Field(min_length=1)


class SchemaDefinition(BaseModel):
    schema_id: str = "ai-assistant"
    name: str = "国内 AI 助手横评模板"
    version: str = "1.0"
    groups: list[GroupSchema] = Field(min_length=1)


def get_active_schema() -> SchemaDefinition:
    """加载唯一 schema(ai_assistant.json)并验证。"""
    raw = json.loads(AI_ASSISTANT_SCHEMA_PATH.read_text(encoding="utf-8"))
    return SchemaDefinition.model_validate(raw)
