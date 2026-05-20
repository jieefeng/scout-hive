import pytest

from app.engine.state_manager import StateManager
from app.models.task import TaskStatus, NodeStatus


def test_create_and_get_task():
    sm = StateManager()
    task = sm.create_task(
        task_id="t001",
        competitors=["竞品A"],
        dimensions=["功能对比"],
        dag_json={"nodes": [], "edges": []},
    )
    assert task.task_id == "t001"
    assert task.status == TaskStatus.PENDING
    retrieved = sm.get_task("t001")
    assert retrieved is not None
    assert retrieved.task_id == "t001"


def test_update_node_status():
    sm = StateManager()
    sm.create_task("t001", ["竞品A"], ["功能对比"], {})
    sm.update_node_status("t001", "collect_001", NodeStatus.RUNNING)
    task = sm.get_task("t001")
    assert task.node_states["collect_001"] == NodeStatus.RUNNING


def test_update_task_status():
    sm = StateManager()
    sm.create_task("t001", ["竞品A"], ["功能对比"], {})
    sm.update_task_status("t001", TaskStatus.RUNNING)
    task = sm.get_task("t001")
    assert task.status == TaskStatus.RUNNING


def test_add_trace():
    sm = StateManager()
    sm.create_task("t001", ["竞品A"], ["功能对比"], {})
    sm.add_trace("t001", {"trace_id": "tr001", "agent": "Collector"})
    task = sm.get_task("t001")
    assert len(task.traces) == 1
