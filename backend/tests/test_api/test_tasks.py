import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.agents.base import AgentResult


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_create_task_with_competitors(app):
    with patch("app.api.tasks.orchestrator") as mock_orch:
        mock_orch.execute_mvp = AsyncMock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/", json={
                "competitors": [
                    {"name": "飞书", "domain": "feishu.cn"},
                    {"name": "钉钉", "domain": "dingtalk.com"}
                ]
            })
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["competitors"]) == 2
            assert data["competitors"][0]["name"] == "飞书"
            assert data["competitors"][0]["domain"] == "feishu.cn"


@pytest.mark.asyncio
async def test_create_task_with_empty_competitors(app):
    with patch("app.api.tasks.orchestrator") as mock_orch:
        mock_orch.execute_mvp = AsyncMock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/", json={
                "competitors": []
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["competitors"] == []
            assert data["status"] == "pending"