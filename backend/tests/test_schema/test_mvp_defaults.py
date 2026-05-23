import pytest
from app.schema.mvp_defaults import (
    DEFAULT_SCHEMA, load_default_schema,
    DimensionSchema, GroupSchema, SchemaDefinition
)

def test_load_default_schema():
    schema = load_default_schema()
    assert schema.schema_id == "default-mvp"
    assert len(schema.groups) == 2

def test_default_groups_have_dimensions():
    schema = load_default_schema()
    product_group = next(g for g in schema.groups if g.name == "产品功能")
    assert len(product_group.dimensions) >= 2

def test_dimension_schema_fields():
    schema = load_default_schema()
    dim = schema.groups[0].dimensions[0]
    assert dim.name == "功能对比"
    assert dim.output_type in ["table", "paragraph"]
    assert len(dim.keywords) >= 1
    assert dim.min_sources >= 1

def test_output_type_enum():
    t = DimensionSchema(
        name="测试", description="测试",
        keywords=["测试"], output_type="table"
    )
    assert t.output_type == "table"