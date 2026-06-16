import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.agents.base import AgentResult


@pytest.fixture
def app():
    return create_app()


def test_build_dag_no_cross_competitor_edges():
    """竞品之间不应有依赖边，确保并发执行。"""
    from app.api.tasks import _build_dag, CompetitorInput

    comps = [
        CompetitorInput(name="飞书", website="feishu.cn"),
        CompetitorInput(name="钉钉", website="dingtalk.com"),
        CompetitorInput(name="企微", website="work.weixin.qq.com"),
    ]
    dims = ["Agent 能力", "商业模式"]
    dag = _build_dag(comps, dims)

    cross = [e for e in dag.edges if e.from_node.split("_")[1] != e.to_node.split("_")[1]]
    assert cross == [], f"发现跨竞品边: {cross}"

    for comp in comps:
        for dim in dims:
            c, a, w = f"c_{comp.name}_{dim}", f"a_{comp.name}_{dim}", f"w_{comp.name}_{dim}"
            assert {"from_node": c, "to_node": a} in [
                {"from_node": e.from_node, "to_node": e.to_node} for e in dag.edges
            ]
            assert {"from_node": a, "to_node": w} in [
                {"from_node": e.from_node, "to_node": e.to_node} for e in dag.edges
            ]


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
async def test_create_task_with_dimensions(app):
    """测试传递 dimensions 参数"""
    with patch("app.api.tasks.orchestrator") as mock_orch:
        mock_orch.execute_mvp = AsyncMock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/", json={
                "competitors": [
                    {"name": "飞书", "domain": "feishu.cn"}
                ],
                "dimensions": ["Agent 能力", "商业模式"]
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "Agent 能力" in data["dimensions"]
            assert "商业模式" in data["dimensions"]


@pytest.mark.asyncio
async def test_create_task_with_invalid_dimensions(app):
    """测试维度校验 - 无效维度返回 422"""
    with patch("app.api.tasks.orchestrator") as mock_orch:
        mock_orch.execute_mvp = AsyncMock()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/", json={
                "competitors": [
                    {"name": "飞书", "domain": "feishu.cn"}
                ],
                "dimensions": ["无效维度", "另一个无效维度"]
            })
            assert resp.status_code == 422
            data = resp.json()
            assert data["detail"]["error_type"] == "dim_not_in_schema"
            assert "无效维度" in data["detail"]["invalid_dims"]
            assert "allowed" in data["detail"]


@pytest.mark.asyncio
async def test_get_dimensions(app):
    """测试获取维度列表端点"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/tasks/dimensions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # 验证返回的维度在白名单内
        from app.constants import ALLOWED_DIMENSIONS
        for dim in data:
            assert dim in ALLOWED_DIMENSIONS


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