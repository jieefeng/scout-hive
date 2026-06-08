"""ALLOWED_DIMENSIONS 白名单常量测试。

锁定:维度集合从 ai_assistant.json 加载,frozenset 不可变,通用维度被拒。
"""
from app.constants import ALLOWED_DIMENSIONS, AI_ASSISTANT_SCHEMA_PATH


def test_allowed_dimensions_is_frozenset():
    """白名单必须是 frozenset(不可被运行期意外 mutate)。"""
    assert isinstance(ALLOWED_DIMENSIONS, frozenset)


def test_allowed_dimensions_contains_seven_ai_assistant_dims():
    """ai_assistant.json 的 7 个维度必须全部在白名单。"""
    expected = {
        "核心玩法",
        "AI 模型能力",
        "Agent 能力",
        "商业模式",
        "用户社区",
        "内容生态",
        "安全合规",
    }
    assert ALLOWED_DIMENSIONS == expected


def test_general_dimensions_not_in_allowlist():
    """旧通用 schema 的 3 个维度必须不在白名单(硬收窄证据)。"""
    assert "功能对比" not in ALLOWED_DIMENSIONS
    assert "用户体验" not in ALLOWED_DIMENSIONS
    assert "定价策略" not in ALLOWED_DIMENSIONS


def test_ai_assistant_schema_path_exists():
    """常量指向的 ai_assistant.json 文件必须存在。"""
    assert AI_ASSISTANT_SCHEMA_PATH.exists(), (
        f"AI_ASSISTANT_SCHEMA_PATH 文件不存在: {AI_ASSISTANT_SCHEMA_PATH}"
    )
    assert AI_ASSISTANT_SCHEMA_PATH.name == "ai_assistant.json"
