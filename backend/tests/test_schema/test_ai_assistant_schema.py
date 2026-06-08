"""国内 AI 助手 7 维度 schema 完整测试。

验证:
1. ai_assistant.json 文件存在
2. 加载后满足 Pydantic SchemaDefinition
3. 7 个维度都在
4. 每个维度都有 fields 和 quality_rules(非空)
5. 关键 quality_rules 文案正确
"""
from app.constants import AI_ASSISTANT_SCHEMA_PATH
from app.schema.mvp_defaults import get_active_schema


def test_ai_assistant_json_exists():
    """ai_assistant.json 文件存在。"""
    assert AI_ASSISTANT_SCHEMA_PATH.exists(), f"Missing {AI_ASSISTANT_SCHEMA_PATH}"


def test_ai_assistant_json_validates():
    """加载 schema 成功(无 Pydantic 错误)。"""
    schema = get_active_schema()
    assert schema.schema_id == "ai-assistant"
    assert len(schema.groups) == 3  # 产品能力 / 商业与生态 / 合规与监管


def test_seven_dimensions_present():
    """7 个维度都在 schema 内。"""
    schema = get_active_schema()
    all_dim_names = {d.name for g in schema.groups for d in g.dimensions}
    expected = {
        "核心玩法",
        "AI 模型能力",
        "Agent 能力",
        "商业模式",
        "用户社区",
        "内容生态",
        "安全合规",
    }
    assert all_dim_names == expected, f"Missing: {expected - all_dim_names}"


def test_each_dimension_has_fields_and_quality_rules():
    """每个维度都有 ≥1 个 fields 和 ≥1 条 quality_rules。"""
    schema = get_active_schema()
    for group in schema.groups:
        for dim in group.dimensions:
            assert len(dim.fields) >= 1, f"Dim '{dim.name}' has no fields"
            assert len(dim.quality_rules) >= 1, f"Dim '{dim.name}' has no quality_rules"


def test_ai_model_dimension_context_window_rule():
    """AI 模型能力 维度的 context_window 质检规则必须含 '8000'。"""
    schema = get_active_schema()
    ai_model_dim = next(
        d for g in schema.groups for d in g.dimensions if d.name == "AI 模型能力"
    )
    rules_text = " ".join(ai_model_dim.quality_rules)
    assert "8000" in rules_text, f"context_window rule missing 8000: {ai_model_dim.quality_rules}"


def test_agent_dimension_tool_calling_required():
    """Agent 能力 维度的 tool_calling 字段是必填 boolean。"""
    schema = get_active_schema()
    agent_dim = next(
        d for g in schema.groups for d in g.dimensions if d.name == "Agent 能力"
    )
    tool_field = next(f for f in agent_dim.fields if f["name"] == "tool_calling")
    assert tool_field["type"] == "boolean"
    assert tool_field.get("required") is True


def test_compliance_dimension_regulatory_required():
    """安全合规 维度的 regulatory_compliance 字段必填。"""
    schema = get_active_schema()
    compliance_dim = next(
        d for g in schema.groups for d in g.dimensions if d.name == "安全合规"
    )
    reg_field = next(f for f in compliance_dim.fields if f["name"] == "regulatory_compliance")
    assert reg_field.get("required") is True


def test_output_types_mix():
    """schema 包含混合 output_type(paragraph + table),覆盖 Writer format_hint 设计。"""
    schema = get_active_schema()
    types = {d.output_type for g in schema.groups for d in g.dimensions}
    assert "table" in types
    assert "paragraph" in types
