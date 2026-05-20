import pytest
from unittest.mock import AsyncMock, MagicMock

from app.engine.orchestrator import Orchestrator
from app.engine.state_manager import StateManager
from app.engine.event_bus import EventBus, Event, Event
from app.models.dag import DAGNode, DAGEdge, FeedbackEdge, DAGBlueprint
from app.agents.base import AgentResult
from app.models.task import TaskStatus, NodeStatus


def _make_blueprint():
    return DAGBlueprint(
        nodes=[
            DAGNode(id="collect_001", agent="Collector", action="search", params={"target": "A"}, depends_on=[]),
            DAGNode(id="analyze_001", agent="Analyst", action="analyze", params={}, depends_on=["collect_001"]),
        ],
        edges=[DAGEdge(from_node="collect_001", to_node="analyze_001")],
        feedback_edges=[],
    )


@pytest.mark.asyncio
async def test_orchestrator_runs_linear_dag():
    sm = StateManager()
    bus = EventBus()
    mock_agents = {"Collector": AsyncMock()}
    mock_agents["Collector"].run.return_value = AgentResult(
        success=True, output={"data": "collected"}, json_valid=True,
    )
    orch = Orchestrator(sm, bus, mock_agents)
    task = sm.create_task("t001", ["竞品A"], ["功能对比"], {})
    blueprint = _make_blueprint()

    result = await orch.execute_node("t001", blueprint.nodes[0])
    assert result.success is True
    mock_agents["Collector"].run.assert_called_once()


@pytest.mark.asyncio
async def test_execute_node_publishes_events():
    sm = StateManager()
    bus = EventBus()
    events_received = []

    async def capture(event):
        events_received.append(event)

    bus.subscribe("node_started", capture)
    bus.subscribe("node_completed", capture)

    mock_agent = AsyncMock()
    mock_agent.run.return_value = AgentResult(success=True, output={"x": 1}, json_valid=True)
    mock_agents = {"Collector": mock_agent}

    orch = Orchestrator(sm, bus, mock_agents)
    sm.create_task("t002", [], [], {})
    node = DAGNode(id="n1", agent="Collector", action="a", params={})

    await orch.execute_node("t002", node)

    assert len(events_received) == 2
    assert events_received[0].type == "node_started"
    assert events_received[1].type == "node_completed"
    assert sm.get_task("t002").node_states["n1"] == NodeStatus.COMPLETED


@pytest.mark.asyncio
async def test_execute_node_agent_not_found():
    sm = StateManager()
    bus = EventBus()
    orch = Orchestrator(sm, bus, {})
    sm.create_task("t003", [], [], {})
    node = DAGNode(id="n1", agent="Missing", action="a", params={})

    result = await orch.execute_node("t003", node)
    assert result.success is False
    assert "not found" in result.error_message


@pytest.mark.asyncio
async def test_execute_node_failure():
    sm = StateManager()
    bus = EventBus()
    mock_agent = AsyncMock()
    mock_agent.run.return_value = AgentResult(
        success=False, error_type="unknown", error_message="boom",
    )
    orch = Orchestrator(sm, bus, {"A": mock_agent})
    sm.create_task("t004", [], [], {})
    node = DAGNode(id="n1", agent="A", action="a", params={})

    result = await orch.execute_node("t004", node)
    assert result.success is False
    assert sm.get_task("t004").node_states["n1"] == NodeStatus.FAILED


@pytest.mark.asyncio
async def test_event_bus_history_filter():
    bus = EventBus()
    await bus.publish(Event(type="a", task_id="t1"))
    await bus.publish(Event(type="b", task_id="t2"))
    await bus.publish(Event(type="a", task_id="t1"))

    assert len(bus.get_history()) == 3
    assert len(bus.get_history(task_id="t1")) == 2
    assert len(bus.get_history(task_id="t2")) == 1
