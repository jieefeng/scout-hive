import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.models.metrics import TraceMetrics
from app.engine.state_manager import StateManager


@pytest.fixture
def app_with_temp_db(monkeypatch):
    """每个 test 用独立 SQLite 文件，避免污染全局单例。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db_path = Path(d) / "tasks.db"
        import app.engine.state_manager as sm_module
        original = sm_module.StateManager._db_path
        sm_module.StateManager._db_path = db_path
        sm_module.StateManager._instance = None
        try:
            app = create_app()
            yield app
        finally:
            sm_module.StateManager._db_path = original
            sm_module.StateManager._instance = None


def test_metrics_endpoint_returns_snapshot(app_with_temp_db):
    """GET /api/tasks/:id/metrics 返回 TaskMetricsSnapshot。"""
    client = TestClient(app_with_temp_db)

    create_resp = client.post("/api/tasks/", json={
        "competitors": [{"name": "Test", "domain": "test.com"}]
    })
    assert create_resp.status_code == 200
    task_id = create_resp.json()["task_id"]

    sm = StateManager()
    for i, (agent, elapsed) in enumerate([("Collector", 1000), ("Analyst", 5000), ("Writer", 3000)]):
        m = TraceMetrics(
            trace_id=f"t{i}",
            task_id=task_id,
            node_id=f"n{i}",
            agent=agent,
            timestamp="2026-06-06T00:00:00Z",
            elapsed_ms=elapsed,
            llm_latency_ms=elapsed - 200,
            tokens_in=100, tokens_out=200, tokens_total=300,
            cost_cny=0.05, reasoning_steps=2,
        )
        sm.save_trace_metrics(m)

    resp = client.get(f"/api/tasks/{task_id}/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["available"] is True
    assert data["total_elapsed_ms"] == 9000  # 1000+5000+3000
    assert data["total_tokens"] == 900  # 3*300
    assert data["node_count"] == 3
    assert len(data["slow_nodes"]) == 3  # top-3
    # 慢节点 top-1 应是 Analyst (5000ms)
    assert data["slow_nodes"][0]["elapsed_ms"] == 5000


def test_metrics_endpoint_old_task_returns_unavailable(app_with_temp_db):
    """旧任务（无 trace_metrics 记录）→ 返 available: false。"""
    client = TestClient(app_with_temp_db)

    create_resp = client.post("/api/tasks/", json={
        "competitors": [{"name": "Test", "domain": "test.com"}]
    })
    assert create_resp.status_code == 200
    task_id = create_resp.json()["task_id"]

    resp = client.get(f"/api/tasks/{task_id}/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["reason"] == "no metrics recorded"
