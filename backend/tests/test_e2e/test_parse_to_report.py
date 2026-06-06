"""端到端：NLP → parse → confirm → execute_mvp → 任务创建。

整个流程都在一个测试内，验证：
1. POST /api/tasks/parse 调 TaskParser → 200 + blueprint
2. POST /api/tasks/parse/confirm 二次校验 blueprint → 200 + task_id
3. 后台 asyncio.create_task 调 execute_mvp
4. StateManager.create_task 被调用且参数正确
"""
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.base import AgentResult
from app.main import create_app
from app.models.task import Competitor, Task, TaskStatus


VALID_BLUEPRINT = {
    "nodes": [
        {"id": f"c_{c}_{d}", "agent": "Collector", "action": "collect",
         "params": {"target": c, "dimension": d, "domain": ""}, "depends_on": []}
        for c in ["A", "B"] for d in ["功能对比"]
    ] + [
        {"id": f"a_{c}_功能对比", "agent": "Analyst", "action": "analyze",
         "params": {"competitor": c, "dimension": "功能对比"}, "depends_on": [f"c_{c}_功能对比"]}
        for c in ["A", "B"]
    ] + [
        {"id": f"w_{c}_功能对比", "agent": "Writer", "action": "write",
         "params": {"competitor": c, "dimension": "功能对比"}, "depends_on": [f"a_{c}_功能对比"]}
        for c in ["A", "B"]
    ],
    "edges": [
        {"from": f"c_{c}_功能对比", "to": f"a_{c}_功能对比"} for c in ["A", "B"]
    ] + [
        {"from": f"a_{c}_功能对比", "to": f"w_{c}_功能对比"} for c in ["A", "B"]
    ],
    "feedback_edges": [],
}


@pytest.mark.asyncio
async def test_e2e_parse_confirm_executes():
    """完整流程：parse 200 → confirm 200 → execute_mvp 被调用 → task 创建。"""
    app = create_app()

    parse_response_content = json.dumps({
        "competitors": ["A", "B"],
        "dimensions": ["功能对比"],
        "dag": VALID_BLUEPRINT,
        "summary": "我打算从功能对比维度对比 A 与 B。",
    })

    with patch("app.api.parse._orch") as mock_orch, \
         patch("app.api.parse._sm") as mock_sm, \
         patch("app.api.parse._bus") as mock_bus:
        mock_orch.execute_mvp = AsyncMock()

        # TaskParser 第一次直接返回成功（避免重试）
        mock_parser = MagicMock()
        mock_parser.run = AsyncMock(return_value=AgentResult(
            success=True,
            output=json.loads(parse_response_content),
            raw_response=parse_response_content,
        ))
        mock_orch.agents = {"TaskParser": mock_parser}

        # mock state_manager.create_task
        def fake_create_task(task_id, comps, dims, dag_json):
            t = Task(
                task_id=task_id,
                status=TaskStatus.PENDING,
                competitors=comps,
                dimensions=dims,
                dag_json=dag_json,
                node_states={},
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
            )
            return t
        mock_sm.create_task = MagicMock(side_effect=fake_create_task)
        mock_sm.calculate_progress = MagicMock(return_value=0.0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. parse
            r1 = await client.post("/api/tasks/parse", json={"message": "分析 A 和 B 的功能对比"})
            assert r1.status_code == 200, r1.text
            parse_data = r1.json()
            assert parse_data["competitors"] == ["A", "B"]
            assert parse_data["dimensions"] == ["功能对比"]

            # 2. confirm（蓝图原样回传，模拟用户没编辑）
            r2 = await client.post(
                "/api/tasks/parse/confirm",
                json={"blueprint": parse_data["blueprint"]},
            )
            assert r2.status_code == 200, r2.text
            task_id = r2.json()["task_id"]
            assert task_id

            # 给 fire-and-forget 的 run_dag 一个 event loop tick
            await asyncio.sleep(0.05)

        # 3. execute_mvp 被调用
        mock_orch.execute_mvp.assert_awaited_once()
        # 4. create_task 被调用
        mock_sm.create_task.assert_called_once()
        call_args = mock_sm.create_task.call_args
        # 第二个位置参数是 competitors 列表
        assert len(call_args.args[1]) == 2
