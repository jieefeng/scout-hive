import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import create_app


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
async def test_confirm_endpoint_success(app):
    """成功路径：200 + 拿到 task_id + 触发 execute_mvp。"""
    with patch("app.api.parse._orch") as mock_orch, \
         patch("app.api.parse._sm") as mock_sm, \
         patch("app.api.parse._bus") as mock_bus:
        mock_orch.execute_mvp = AsyncMock()
        mock_sm.create_task = MagicMock()

        from app.models.task import Task
        mock_task = MagicMock(spec=Task)
        mock_task.task_id = "t-123"
        mock_task.status = "pending"
        mock_task.competitors = []
        mock_task.dimensions = ["功能对比"]
        mock_task.node_states = {}
        mock_task.dag_json = {}
        mock_task.created_at = "2026-06-06T00:00:00Z"
        mock_task.updated_at = "2026-06-06T00:00:00Z"
        mock_task.report_html = ""
        mock_task.traces = []
        mock_task.reviews = []
        mock_task.error_message = ""
        mock_task.progress = 0.0
        mock_sm.create_task.return_value = mock_task
        mock_sm.calculate_progress = MagicMock(return_value=0.0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/parse/confirm",
                json={"blueprint": VALID_BLUEPRINT},
            )
            await asyncio.sleep(0)  # 让后台 asyncio.create_task 有机会开始执行

    assert resp.status_code == 200, resp.text
    mock_orch.execute_mvp.assert_awaited_once()
    mock_sm.create_task.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_endpoint_blueprint_tampered(app):
    """蓝图引用不存在节点 → 422 blueprint_tampered。"""
    bad_bp = {
        "nodes": [
            {"id": "a", "agent": "Collector", "action": "x", "params": {},
             "depends_on": ["nonexistent"]}
        ],
        "edges": [],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/tasks/parse/confirm",
            json={"blueprint": bad_bp},
        )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error_type"] == "blueprint_tampered"


@pytest.mark.asyncio
async def test_confirm_endpoint_empty_blueprint(app):
    """空 dict → 422 blueprint_tampered。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/tasks/parse/confirm",
            json={"blueprint": {}},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_type"] in {"blueprint_tampered", "topology_error"}


@pytest.mark.asyncio
async def test_confirm_uses_user_edited_blueprint(app):
    """用户编辑过的 blueprint（多加了节点）应被原样接受。"""
    edited = {
        "nodes": VALID_BLUEPRINT["nodes"] + [
            {"id": "c2", "agent": "Collector", "action": "collect",
             "params": {"target": "B", "dimension": "功能对比"}, "depends_on": []}
        ],
        "edges": [],
        "feedback_edges": [],
    }
    with patch("app.api.parse._orch") as mock_orch, \
         patch("app.api.parse._sm") as mock_sm, \
         patch("app.api.parse._bus") as mock_bus:
        mock_orch.execute_mvp = AsyncMock()
        from app.models.task import Task
        mock_task = MagicMock(spec=Task)
        mock_task.task_id = "t-x"
        mock_task.status = "pending"
        mock_task.competitors = []
        mock_task.dimensions = ["功能对比"]
        mock_task.node_states = {}
        mock_task.dag_json = {}
        mock_task.created_at = "2026-06-06T00:00:00Z"
        mock_task.updated_at = "2026-06-06T00:00:00Z"
        mock_task.report_html = ""
        mock_task.traces = []
        mock_task.reviews = []
        mock_task.error_message = ""
        mock_task.progress = 0.0
        mock_sm.create_task.return_value = mock_task
        mock_sm.calculate_progress = MagicMock(return_value=0.0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/parse/confirm",
                json={"blueprint": edited},
            )
            await asyncio.sleep(0)  # 让后台 asyncio.create_task 有机会开始执行
        assert resp.status_code == 200

        # 验证传入 execute_mvp 的 blueprint 包含 c2
        call_args = mock_orch.execute_mvp.call_args
        passed_blueprint = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["dag"]
        # dag 是 DAGBlueprint Pydantic 模型，nodes 是 list[DAGNode]
        nodes = passed_blueprint.nodes
        node_ids = {n.id for n in nodes}
        assert "c2" in node_ids
