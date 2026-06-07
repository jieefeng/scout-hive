import pytest
from app.schema.mvp_defaults import (
    DEFAULT_SCHEMA, load_default_schema,
    DimensionSchema, GroupSchema, SchemaDefinition
)

def test_load_default_schema():
    schema = load_default_schema()
    # 委托给 loader.load_active_schema()，默认从 config.yaml 读 active_schema_id = "general"
    assert schema.schema_id == "general"
    assert len(schema.groups) >= 1

def test_default_groups_have_dimensions():
    schema = load_default_schema()
    product_group = next(g for g in schema.groups if g.name == "产品功能")
    assert len(product_group.dimensions) >= 2

def test_dimension_schema_fields():
    schema = load_default_schema()
    dim = schema.groups[0].dimensions[0]
    assert dim.name == "功能对比"
    assert dim.output_type in ["table", "paragraph", "battlecard"]
    assert len(dim.keywords) >= 1
    assert dim.evidence_threshold >= 1
    assert dim.tracking_sources == ["web"]

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