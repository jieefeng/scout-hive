import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agents.task_parser import TaskParser
from app.agents.base import AgentResult
from app.llm.base import LLMResponse
from app.api.parse import parse_task_blueprint, RETRYABLE_ERRORS


VALID_DAG = {
    "nodes": [
        {"id": "c1", "agent": "Collector", "action": "collect",
         "params": {"target": "A", "dimension": "推荐算法"}, "depends_on": []}
    ],
    "edges": [],
    "feedback_edges": [],
}


def _parser_with_llm(chat_mock):
    adapter = MagicMock()
    adapter.chat = AsyncMock(side_effect=chat_mock)
    return TaskParser("TaskParser", adapter)


def _schema():
    return {
        "groups": [
            {"dimensions": [{"name": "推荐算法"}, {"name": "商业化"}]}
        ]
    }


@pytest.mark.asyncio
async def test_parse_success_first_try():
    """LLM 一次返回合法 JSON → success=True。"""
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["推荐算法"], "dag": ' + str(VALID_DAG).replace("'", '"') + ', "summary": "OK"}',
        model="test",
    )))

    result = await parse_task_blueprint("分析 A 的推荐算法", parser, _schema())

    assert result["success"] is True
    assert result["competitors"] == ["A"]
    assert result["dimensions"] == ["推荐算法"]
    assert result["summary"] == "OK"
    assert "blueprint" in result


@pytest.mark.asyncio
async def test_parse_retries_on_json_parse():
    """第 1 轮 json_parse → 重试 1 次 → 成功。"""
    side_effects = [
        LLMResponse(content="not json", model="test"),
        LLMResponse(
            content='{"competitors": ["A"], "dimensions": ["推荐算法"], "dag": ' + str(VALID_DAG).replace("'", '"') + '}',
            model="test",
        ),
    ]
    parser = _parser_with_llm(AsyncMock(side_effect=side_effects))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is True
    assert parser.llm.chat.call_count == 2


@pytest.mark.asyncio
async def test_parse_does_not_retry_on_dim_not_in_schema():
    """第 1 轮返回合法 JSON 但维度不在 schema → 不重试。"""
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["不存在的维度"], "dag": ' + str(VALID_DAG).replace("'", '"') + '}',
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "dim_not_in_schema"
    assert parser.llm.chat.call_count == 1  # 关键：没重试


@pytest.mark.asyncio
async def test_parse_fails_after_retry_exhausted():
    """第 1 轮 + 第 2 轮都 json_parse → 返 json_parse 错误。"""
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content="bad", model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "json_parse"
    assert parser.llm.chat.call_count == 2


@pytest.mark.asyncio
async def test_parse_empty_competitors():
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content='{"competitors": [], "dimensions": ["推荐算法"], "dag": ' + str(VALID_DAG).replace("'", '"') + '}',
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "empty_competitors"


@pytest.mark.asyncio
async def test_parse_too_many_competitors():
    over_limit = ",".join([f'"c{i}"' for i in range(11)])
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content=f'{{"competitors": [{over_limit}], "dimensions": ["推荐算法"], "dag": {str(VALID_DAG).replace(chr(39), chr(34))}}}',
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "too_many_competitors"


@pytest.mark.asyncio
async def test_parse_topology_error():
    """DAG 引用不存在的节点 → 422 topology_error。"""
    bad_dag = {"nodes": [{"id": "a", "agent": "Collector", "action": "x", "params": {}, "depends_on": ["nonexistent"]}], "edges": []}
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["推荐算法"], "dag": ' + str(bad_dag).replace("'", '"') + '}',
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "topology_error"


def test_retryable_errors_set():
    """RETRYABLE_ERRORS 仅含 json_parse 和 llm_empty。"""
    assert RETRYABLE_ERRORS == {"json_parse", "llm_empty"}
