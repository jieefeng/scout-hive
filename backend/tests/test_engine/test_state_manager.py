import pytest

from app.engine.state_manager import StateManager
from app.models.task import TaskStatus, NodeStatus, Competitor


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重置数据库"""
    StateManager.reset()
    yield


def test_create_and_get_task():
    sm = StateManager()
    task = sm.create_task(
        task_id="t001",
        competitors=[Competitor(name="竞品A", domain="example.com")],
        dimensions=["核心玩法"],
        dag_json={"nodes": [], "edges": []},
    )
    assert task.task_id == "t001"
    assert task.status == TaskStatus.PENDING
    retrieved = sm.get_task("t001")
    assert retrieved is not None
    assert retrieved.task_id == "t001"
    assert retrieved.competitors[0].name == "竞品A"


def test_update_node_status():
    sm = StateManager()
    sm.create_task("t001", [Competitor(name="竞品A", domain="example.com")], ["核心玩法"], {"nodes": [{"id": "n1"}], "edges": []})
    sm.update_node_status("t001", "n1", NodeStatus.RUNNING)
    task = sm.get_task("t001")
    assert task.node_states["n1"] == NodeStatus.RUNNING


def test_update_task_status():
    sm = StateManager()
    sm.create_task("t001", [Competitor(name="竞品A", domain="example.com")], ["核心玩法"], {"nodes": [], "edges": []})
    sm.update_task_status("t001", TaskStatus.RUNNING)
    task = sm.get_task("t001")
    assert task.status == TaskStatus.RUNNING


def test_add_trace():
    sm = StateManager()
    sm.create_task("t001", [Competitor(name="竞品A", domain="example.com")], ["核心玩法"], {"nodes": [], "edges": []})
    sm.add_trace("t001", {"trace_id": "tr001", "agent": "Collector"})
    task = sm.get_task("t001")
    assert len(task.traces) == 1
    assert task.traces[0]["trace_id"] == "tr001"
    assert task.traces[0]["agent"] == "Collector"


def test_cancel_task():
    sm = StateManager()
    sm.create_task("cancel-t001", [Competitor(name="A", domain="a.com")], [], {"nodes": [], "edges": []})
    assert sm.is_task_cancelled("cancel-t001") is False
    result = sm.cancel_task("cancel-t001")
    assert result is True
    assert sm.is_task_cancelled("cancel-t001") is True


def test_cancel_task_idempotent():
    sm = StateManager()
    sm.create_task("cancel-t002", [Competitor(name="A", domain="a.com")], [], {"nodes": [], "edges": []})
    sm.cancel_task("cancel-t002")
    result = sm.cancel_task("cancel-t002")  # 第二次应返回 False
    assert result is False