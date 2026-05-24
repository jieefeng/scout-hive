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
            assert data["competitors"][0]["website"] == "feishu.cn"


@pytest.mark.asyncio
async def test_stop_task_success(app):
    with patch("app.api.tasks.orchestrator") as mock_orch, \
         patch("app.api.tasks.state_manager") as mock_sm:
        mock_orch.execute_mvp = AsyncMock()
        mock_sm.cancel_task = MagicMock(return_value=True)

        # Mock get_task to return a task with RUNNING status for stop endpoint
        def mock_get_task(task_id):
            from app.models.task import TaskStatus
            task = MagicMock()
            task.status = TaskStatus.RUNNING
            return task
        mock_sm.get_task = MagicMock(side_effect=mock_get_task)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 停止任务（用不存在的 task_id 但 mock 返回 RUNNING）
            resp = await client.post("/api/tasks/test-task-id/stop")
            assert resp.status_code == 200
            assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_stop_task_not_found(app):
    with patch("app.api.tasks.orchestrator") as mock_orch, \
         patch("app.api.tasks.state_manager") as mock_sm:
        mock_orch.execute_mvp = AsyncMock()
        mock_sm.get_task = MagicMock(return_value=None)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/nonexistent-id/stop")
            assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stop_task_not_running(app):
    with patch("app.api.tasks.orchestrator") as mock_orch, \
         patch("app.api.tasks.state_manager") as mock_sm:
        mock_orch.execute_mvp = AsyncMock()
        # Mock get_task to return a task with COMPLETED status
        def mock_get_task(task_id):
            from app.models.task import TaskStatus
            task = MagicMock()
            task.status = TaskStatus.COMPLETED
            return task
        mock_sm.get_task = MagicMock(side_effect=mock_get_task)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/test-task-id/stop")
            assert resp.status_code == 400