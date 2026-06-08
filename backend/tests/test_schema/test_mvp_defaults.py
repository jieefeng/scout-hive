"""Pydantic schema 模型 + get_active_schema 测试。

硬收窄后:`load_default_schema` / `DEFAULT_SCHEMA` 已删,只剩 3 个 Pydantic
模型 + 唯一入口 `get_active_schema()`(读 ai_assistant.json)。
"""
import pytest

from app.schema.mvp_defaults import (
    DimensionSchema,
    GroupSchema,
    SchemaDefinition,
    get_active_schema,
)


def test_get_active_schema_loads_ai_assistant():
    """唯一入口必须返回 ai-assistant schema(无 config 切换)。"""
    schema = get_active_schema()
    assert schema.schema_id == "ai-assistant"
    assert len(schema.groups) >= 1


def test_get_active_schema_has_seven_dimensions():
    """ai-assistant 共 7 维度。"""
    schema = get_active_schema()
    all_dims = [d.name for g in schema.groups for d in g.dimensions]
    assert len(all_dims) == 7


def test_get_active_schema_first_group_is_product_ability():
    schema = get_active_schema()
    product_group = next(g for g in schema.groups if g.name == "产品能力")
    assert len(product_group.dimensions) >= 2


def test_dimension_schema_fields_align_with_ai_assistant():
    schema = get_active_schema()
    dim = schema.groups[0].dimensions[0]
    assert dim.name == "核心玩法"
    assert dim.output_type in ["table", "paragraph", "battlecard"]
    assert len(dim.keywords) >= 1
    assert dim.evidence_threshold >= 1
    assert dim.tracking_sources == ["web", "social"]


def test_output_type_enum():
    t = DimensionSchema(
        name="测试", description="测试",
        keywords=["测试"], output_type="table"
    )
    assert t.output_type == "table"


def test_battlecard_output_type():
    t = DimensionSchema(
        name="测试", description="测试",
        keywords=["测试"], output_type="battlecard"
    )
    assert t.output_type == "battlecard"


def test_tracking_sources_default():
    t = DimensionSchema(
        name="测试", description="测试",
        keywords=["测试"]
    )
    assert t.tracking_sources == ["web"]


def test_load_default_schema_removed():
    """废弃入口必须不再可 import(硬收窄证据)。"""
    import app.schema.mvp_defaults as mod
    assert not hasattr(mod, "load_default_schema"), (
        "load_default_schema 应已被删除;旧调用方必须迁移到 get_active_schema()"
    )
    assert not hasattr(mod, "DEFAULT_SCHEMA"), (
        "DEFAULT_SCHEMA dict 应已被删除;唯一真相之源是 ai_assistant.json"
    )
