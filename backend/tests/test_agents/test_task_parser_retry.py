import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agents.task_parser import TaskParser
from app.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    adapter = MagicMock()
    adapter.chat = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_retry_with_prompt_hint_sends_three_messages(mock_llm):
    """retry 时 messages 含 [system, user: 原 message, user: 错误提示]。"""
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["X"], "dag": {"nodes": [], "edges": []}}',
        model="test",
    )
    parser = TaskParser("TaskParser", mock_llm)

    await parser.retry_with_prompt_hint(
        {"message": "原需求"},
        error_hint="json parse failed: Expecting value",
    )

    call_args = mock_llm.chat.call_args
    messages = call_args.kwargs.get("messages") or call_args.args[0]
    assert len(messages) == 3
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert messages[1].content == "原需求"
    assert messages[2].role == "user"
    assert "⚠️ 上一轮输出有误" in messages[2].content
    assert "json parse failed" in messages[2].content


@pytest.mark.asyncio
async def test_retry_with_prompt_hint_returns_agent_result(mock_llm):
    """retry 成功时返回 success=True 的 AgentResult。"""
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["X"], "dag": {"nodes": [], "edges": []}}',
        model="test",
    )
    parser = TaskParser("TaskParser", mock_llm)

    result = await parser.retry_with_prompt_hint(
        {"message": "x"}, error_hint="bad json"
    )

    assert result.success is True
    assert result.output["competitors"] == ["A"]


@pytest.mark.asyncio
async def test_retry_with_prompt_hint_propagates_failure(mock_llm):
    """retry 时 LLM 仍返回烂 JSON → result.success=False + error_type=json_parse。"""
    mock_llm.chat.return_value = LLMResponse(content="still not json", model="test")
    parser = TaskParser("TaskParser", mock_llm)

    result = await parser.retry_with_prompt_hint(
        {"message": "x"}, error_hint="bad json"
    )

    assert result.success is False
    assert result.error_type == "json_parse"
    assert result.raw_response == "still not json"
