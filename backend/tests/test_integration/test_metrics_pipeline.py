"""测试 state_manager.add_trace 自动写入 trace_metrics 表。

核心契约：调 add_trace(task_id, trace_dict) 时，若 trace 是完整的 TraceRecord dump
（含 trace_id / llm_metadata），state_manager 应当同步把 metrics 落 trace_metrics 表。
非完整 trace（timeout dict、revision dict）不写 metrics —— 这些没 trace_id，强行写会污染。
"""
import json
from pathlib import Path
import pytest

from app.engine.state_manager import StateManager
from app.models.task import Competitor


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """每个测试用独立 SQLite（避免读真实 yaml/真实 db）。"""
    db_path = tmp_path / "tasks.db"
    monkeypatch.setattr(StateManager, "_db_path", db_path)
    StateManager._instance = None
    yield
    StateManager._instance = None


def _make_sm_with_task(task_id: str = "task1") -> StateManager:
    sm = StateManager()
    sm.create_task(
        task_id=task_id,
        competitors=[Competitor(name="飞书", domain="feishu.cn")],
        dimensions=["核心玩法"],
        dag_json={"nodes": [{"id": "n1"}], "edges": []},
    )
    return sm


def test_add_trace_writes_metrics_for_full_trace():
    """完整 TraceRecord dump（带 trace_id + llm_metadata）应自动写 metrics。"""
    sm = _make_sm_with_task("task1")
    trace = {
        "trace_id": "t-001",
        "node_id": "c_飞书_核心玩法",
        "agent": "Analyst",
        "timestamp": "2026-06-06T00:00:00Z",
        "input_refs": {},
        "output": {"claims": []},
        "reasoning_chain": [{"step": 1, "thought": "..."}],
        "sources": [],
        "llm_metadata": {
            "model": "qwen3.7-max-2026-05-17",
            "tokens_used": 1000,
            "latency_ms": 2000,
        },
        "revision_round": 0,
        "error_message": "",
    }

    sm.add_trace("task1", trace)

    rows = sm.query_task_metrics("task1")
    assert len(rows) == 1
    row = rows[0]
    assert row["trace_id"] == "t-001"
    assert row["node_id"] == "c_飞书_核心玩法"
    assert row["agent"] == "Analyst"
    assert row["timestamp"] == "2026-06-06T00:00:00Z"
    # elapsed_ms 暂用 llm_latency_ms 兜底（已知简化：缺真实节点计时）
    assert row["elapsed_ms"] == 2000
    assert row["llm_latency_ms"] == 2000
    # 70/30 token 分配
    assert row["tokens_total"] == 1000
    assert row["tokens_in"] == 700
    assert row["tokens_out"] == 300
    # cost_cny 由 yaml 定价表算出，qwen3.6 默认应 > 0（yaml 里有 default）
    assert row["cost_cny"] >= 0
    # reasoning_chain 长度
    assert row["reasoning_steps"] == 1


def test_add_trace_skips_metrics_for_minimal_dict():
    """非完整 trace（timeout dict：无 trace_id）应跳过 metrics 写入，不抛异常。"""
    sm = _make_sm_with_task("task2")
    timeout_trace = {
        "node_id": "c_飞书_核心玩法",
        "agent": "Collector",
        "elapsed_ms": 180000,
        "error": "节点执行超时 (180秒)",
    }

    sm.add_trace("task2", timeout_trace)  # 不应抛

    # traces JSON 列有这条
    task = sm.get_task("task2")
    assert len(task.traces) == 1
    assert task.traces[0]["agent"] == "Collector"
    # metrics 表没写
    assert sm.query_task_metrics("task2") == []


def test_add_trace_writes_metrics_zero_when_no_llm_metadata():
    """有 trace_id 但缺 llm_metadata 时：写 metrics 行，llm 字段全 0，cost 0。"""
    sm = _make_sm_with_task("task3")
    trace = {
        "trace_id": "t-003",
        "node_id": "n3",
        "agent": "Writer",
        "timestamp": "2026-06-06T00:00:01Z",
        "input_refs": {},
        "output": {},
        "reasoning_chain": [],
        "sources": [],
    }

    sm.add_trace("task3", trace)

    rows = sm.query_task_metrics("task3")
    assert len(rows) == 1
    row = rows[0]
    assert row["trace_id"] == "t-003"
    assert row["agent"] == "Writer"
    assert row["elapsed_ms"] == 0
    assert row["llm_latency_ms"] == 0
    assert row["tokens_total"] == 0
    assert row["cost_cny"] == 0
    assert row["reasoning_steps"] == 0


def test_add_trace_multiple_writes_accumulate():
    """多条完整 trace 累计写入 metrics 行（按 timestamp 升序返回）。"""
    sm = _make_sm_with_task("task4")
    for i in range(3):
        sm.add_trace("task4", {
            "trace_id": f"t-{i:03d}",
            "node_id": f"n{i}",
            "agent": "Analyst",
            "timestamp": f"2026-06-06T00:00:0{i}Z",
            "input_refs": {},
            "output": {},
            "reasoning_chain": [{"step": 1}],
            "sources": [],
            "llm_metadata": {
                "model": "qwen3.7-max-2026-05-17",
                "tokens_used": 100 * (i + 1),
                "latency_ms": 100 * (i + 1),
            },
        })

    rows = sm.query_task_metrics("task4")
    assert len(rows) == 3
    assert [r["trace_id"] for r in rows] == ["t-000", "t-001", "t-002"]
    assert [r["tokens_total"] for r in rows] == [100, 200, 300]
