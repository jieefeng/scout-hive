from typing import Literal
from pydantic import BaseModel, Field

OutputType = Literal["table", "paragraph", "battlecard"]

class DimensionSchema(BaseModel):
    name: str
    description: str = ""
    keywords: list[str] = Field(min_length=1)
    output_type: OutputType = "paragraph"
    evidence_threshold: int = Field(default=1, ge=1)  # 原 min_sources，已改名
    tracking_sources: list[str] = Field(
        default=["web"],
        description="数据来源：web / social / jobs / reviews / ads"
    )  # 新增可选字段

class GroupSchema(BaseModel):
    name: str
    description: str = ""
    dimensions: list[DimensionSchema] = Field(min_length=1)

class SchemaDefinition(BaseModel):
    schema_id: str = "default-mvp"
    name: str = "通用竞品分析模板"
    version: str = "1.0"
    groups: list[GroupSchema] = Field(min_length=1)

DEFAULT_SCHEMA: dict = {
    "schema_id": "default-mvp",
    "name": "通用竞品分析模板",
    "version": "1.0",
    "groups": [
        {
            "name": "产品功能",
            "description": "核心产品功能维度",
            "dimensions": [
                {
                    "name": "功能对比",
                    "description": "对比各竞品提供的核心功能差异，列出各竞品支持的功能项和不支持的功能项。",
                    "keywords": ["功能", "特性", "支持"],
                    "output_type": "table",
                    "evidence_threshold": 2,
                    "tracking_sources": ["web"]
                },
                {
                    "name": "用户体验",
                    "description": "分析各竞品在界面设计、操作体验、用户评价方面的特点。",
                    "keywords": ["用户体验", "UI", "界面"],
                    "output_type": "paragraph",
                    "evidence_threshold": 1,
                    "tracking_sources": ["web"]
                }
            ]
        },
        {
            "name": "商业策略",
            "description": "定价与商业策略维度",
            "dimensions": [
                {
                    "name": "定价策略",
                    "description": "对比各竞品的定价模式（免费/订阅/按需）、价格区间、有无隐藏费用。提取每个竞品的具体价格数据。",
                    "keywords": ["定价", "价格", "套餐", "收费"],
                    "output_type": "table",
                    "evidence_threshold": 1,
                    "tracking_sources": ["web"]
                }
            ]
        }
    ]
}

def load_default_schema() -> SchemaDefinition:
    """Load the default MVP schema definition.

    Raises:
        ValidationError: If the default schema data is invalid.
    """
    return SchemaDefinition.model_validate(DEFAULT_SCHEMA)