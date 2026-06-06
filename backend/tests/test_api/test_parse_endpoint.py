import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.llm.base import LLMResponse


VALID_BLUEPRINT = {
    "nodes": [
        {"id": "c1", "agent": "Collector", "action": "collect",
         "params": {"target": "A", "dimension": "功能对比"}, "depends_on": []}
    ],
    "edges": [],
    "feedback_edges": [],
}


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_parse_endpoint_success(app):
    """成功路径：200 + 含 blueprint/competitors/dimensions/summary。"""
    with patch("app.api.parse._orch") as mock_orch:
        mock_parser = MagicMock()
        mock_parser.run = AsyncMock()
        mock_parser.retry_with_prompt_hint = AsyncMock()
        mock_orch.agents = {"TaskParser": mock_parser}
        from app.agents.base import AgentResult
        mock_parser.run.return_value = AgentResult(
            success=True,
            output={
                "competitors": ["A"],
                "dimensions": ["功能对比"],
                "dag": VALID_BLUEPRINT,
                "summary": "OK",
            },
            raw_response='{"competitors": ["A"], ...}',
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": "分析 A 的功能对比"})

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["competitors"] == ["A"]
    assert data["dimensions"] == ["功能对比"]
    assert data["summary"] == "OK"
    assert "blueprint" in data
    assert data["blueprint"]["nodes"][0]["id"] == "c1"


@pytest.mark.asyncio
async def test_parse_endpoint_empty_message(app):
    """空 message → 422 empty_message，不调 LLM。"""
    with patch("app.api.parse._orch") as mock_orch:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": ""})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error_type"] == "empty_message"


@pytest.mark.asyncio
async def test_parse_endpoint_whitespace_only(app):
    """全空白 → 422 empty_message。"""
    with patch("app.api.parse._orch") as mock_orch:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": "   \n  "})
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_type"] == "empty_message"


@pytest.mark.asyncio
async def test_parse_endpoint_truncates_long_message(app):
    """超长 message 截断到 2000 字。"""
    long_msg = "A" * 3000
    with patch("app.api.parse._orch") as mock_orch:
        mock_parser = MagicMock()
        mock_parser.run = AsyncMock()
        mock_orch.agents = {"TaskParser": mock_parser}
        from app.agents.base import AgentResult
        mock_parser.run.return_value = AgentResult(
            success=True,
            output={"competitors": ["x"], "dimensions": ["功能对比"], "dag": VALID_BLUEPRINT},
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": long_msg})

    assert resp.status_code == 200
    sent_msg = mock_parser.run.call_args.args[0]["message"]
    assert len(sent_msg) == 2000


@pytest.mark.asyncio
async def test_parse_endpoint_returns_422_with_hint_on_json_parse(app):
    """LLM 两轮都 json_parse → 422 + error_type=json_parse + hint。"""
    with patch("app.api.parse._orch") as mock_orch:
        mock_parser = MagicMock()
        mock_parser.run = AsyncMock()
        mock_parser.retry_with_prompt_hint = AsyncMock()
        mock_orch.agents = {"TaskParser": mock_parser}
        from app.agents.base import AgentResult
        fail_result = AgentResult(
            success=False, error_type="json_parse",
            error_message="Expecting value", raw_response="bad json"
        )
        mock_parser.run.return_value = fail_result
        mock_parser.retry_with_prompt_hint.return_value = fail_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": "x"})

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error_type"] == "json_parse"
    assert "raw_response" in detail
    assert "hint" in detail
    assert "POST /api/tasks" in detail["hint"]


@pytest.mark.asyncio
async def test_parse_endpoint_dim_not_in_schema(app):
    """维度不在 DEFAULT_SCHEMA → 422 dim_not_in_schema，不重试。"""
    with patch("app.api.parse._orch") as mock_orch:
        mock_parser = MagicMock()
        mock_parser.run = AsyncMock()
        mock_parser.retry_with_prompt_hint = AsyncMock()
        mock_orch.agents = {"TaskParser": mock_parser}
        from app.agents.base import AgentResult
        mock_parser.run.return_value = AgentResult(
            success=True,
            output={
                "competitors": ["A"],
                "dimensions": ["unknown_dim"],
                "dag": VALID_BLUEPRINT,
            },
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": "x"})

    assert resp.status_code == 422
    assert resp.json()["detail"]["error_type"] == "dim_not_in_schema"
    mock_parser.retry_with_prompt_hint.assert_not_called()  # 关键：没重试
