from app.schema.mvp_defaults import DimensionSchema


def test_dimension_fields_default_empty_list():
    """默认 fields 为空 list（向后兼容旧 schema）。"""
    dim = DimensionSchema(
        name="测试", description="测试", keywords=["测试"]
    )
    assert dim.fields == []
    assert dim.quality_rules == []


def test_dimension_fields_populated():
    """fields 和 quality_rules 可填充。"""
    dim = DimensionSchema(
        name="AI 模型能力",
        description="底层模型、上下文、响应速度",
        keywords=["模型", "上下文", "token"],
        output_type="table",
        fields=[
            {"name": "underlying_model", "type": "string", "required": True},
            {"name": "context_window", "type": "number", "min": 8000},
        ],
        quality_rules=[
            "context_window 必须是数字 ≥ 8000",
            "underlying_model 必须给出具体模型名",
        ],
    )
    assert len(dim.fields) == 2
    assert dim.fields[0]["name"] == "underlying_model"
    assert "≥ 8000" in dim.quality_rules[0]
