import os
import tempfile
import pytest
from app.engine.state_manager import StateManager


def test_ensure_metrics_table_idempotent():
    """多次调用 _ensure_metrics_table 不应报错。"""
    # ignore_cleanup_errors=True: Windows 平台 SQLite 连接未关时无法 unlink
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        path = os.path.join(d, "tasks.db")
        sm = StateManager(db_path=path)
        # 多次调用应幂等
        sm._ensure_metrics_table()
        sm._ensure_metrics_table()  # 不应抛异常
        # 验证表存在
        row = sm._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trace_metrics'"
        ).fetchone()
        assert row is not None
        # 验证索引存在
        idx = sm._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_tm_task'"
        ).fetchone()
        assert idx is not None


def test_save_and_query_trace_metrics():
    """save_trace_metrics + query_task_metrics 往返一致。"""
    from app.models.metrics import TraceMetrics
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        path = os.path.join(d, "tasks.db")
        sm = StateManager(db_path=path)

        # 插入 3 条
        for i, (agent, elapsed, tokens) in enumerate([
            ("Collector", 1000, 100),
            ("Analyst", 5000, 800),
            ("Writer", 8000, 1200),
        ]):
            m = TraceMetrics(
                trace_id=f"t{i}",
                task_id="task1",
                node_id=f"n{i}",
                agent=agent,
                timestamp="2026-06-06T00:00:00Z",
                elapsed_ms=elapsed,
                llm_latency_ms=elapsed - 500,
                tokens_in=tokens // 2,
                tokens_out=tokens // 2,
                tokens_total=tokens,
                cost_cny=tokens * 0.0001,
                reasoning_steps=2 if agent != "Collector" else 0,
            )
            sm.save_trace_metrics(m)

        # 查询
        rows = sm.query_task_metrics("task1")
        assert len(rows) == 3
        # 按 agent 验证
        by_agent = {r["agent"]: r for r in rows}
        assert by_agent["Collector"]["tokens_total"] == 100
        assert by_agent["Analyst"]["elapsed_ms"] == 5000
        # cost_cny 浮点精度：用 pytest.approx
        assert by_agent["Writer"]["cost_cny"] == pytest.approx(0.12)
        # 跨任务隔离
        empty = sm.query_task_metrics("nonexistent")
        assert empty == []
