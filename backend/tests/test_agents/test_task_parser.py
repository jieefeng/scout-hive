import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agents.task_parser import TaskParser
from app.agents.base import AgentResult
from app.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    adapter = MagicMock()
    adapter.chat = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_task_parser_returns_valid_dag(mock_llm):
    parser = TaskParser("TaskParser", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitors": ["竞品A", "竞品B"], "dimensions": ["核心玩法"], "dag": {"nodes": [{"id": "c1", "agent": "Collector", "action": "search", "params": {"target": "竞品A"}, "depends_on": []}], "edges": [], "feedback_edges": []}}',
        model="test",
    )

    result = await parser.run({"message": "分析抖音和快手"})

    assert result.success is True
    assert "competitors" in result.output
    assert result.output["competitors"] == ["竞品A", "竞品B"]
    assert result.output["dimensions"] == ["核心玩法"]


@pytest.mark.asyncio
async def test_task_parser_handles_markdown_fences(mock_llm):
    parser = TaskParser("TaskParser", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='```json\n{"competitors": ["A"], "dimensions": ["价格"], "dag": {"nodes": [], "edges": [], "feedback_edges": []}}\n```',
        model="test",
    )

    result = await parser.run({"message": "compare A and B"})

    assert result.success is True
    assert result.output["competitors"] == ["A"]


@pytest.mark.asyncio
async def test_task_parser_invalid_json(mock_llm):
    parser = TaskParser("TaskParser", mock_llm)
    mock_llm.chat.return_value = LLMResponse(content="not json at all {", model="test")

    result = await parser.run({"message": "分析"})

    assert result.success is False
    assert result.error_type == "json_parse"
    assert result.json_valid is False


@pytest.mark.asyncio
async def test_task_parser_multiple_competitors(mock_llm):
    parser = TaskParser("TaskParser", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitors": ["抖音", "快手", "B站"], "dimensions": ["推荐算法", "商业化"], "dag": {"nodes": [], "edges": [], "feedback_edges": []}}',
        model="test",
    )

    result = await parser.run({"message": "分析短视频平台"})

    assert result.success is True
    assert len(result.output["competitors"]) == 3
    assert len(result.output["dimensions"]) == 2


def test_system_prompt_contains_allowed_dimensions():
    """硬收窄软约束:SYSTEM_PROMPT 必须包含 ALLOWED_DIMENSIONS 全部 7 项。

    LLM 看到 prompt 里硬列出的白名单后,生成的 dimensions 应优先收敛到这 7 项。
    """
    from app.constants import ALLOWED_DIMENSIONS

    prompt = TaskParser.SYSTEM_PROMPT
    for dim in ALLOWED_DIMENSIONS:
        assert dim in prompt, f"白名单维度 '{dim}' 缺失于 SYSTEM_PROMPT"