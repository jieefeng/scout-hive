import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engine.orchestrator import Orchestrator
from app.engine.state_manager import StateManager
from app.engine.event_bus import EventBus
from app.models.dag import DAGBlueprint, DAGNode, DAGEdge
from app.agents.base import AgentResult
from app.models.task import TaskStatus, Competitor


def _make_mvp_blueprint():
    """Simple DAG: Collector -> Analyst -> Writer for one competitor/dimension."""
    return DAGBlueprint(
        nodes=[
            DAGNode(
                id="collect_001",
                agent="Collector",
                action="search",
                params={"competitor": "竞品A", "dimension": "功能对比", "domain": "产品"},
                depends_on=[],
            ),
            DAGNode(
                id="analyze_001",
                agent="Analyst",
                action="analyze",
                params={"competitor": "竞品A", "dimension": "功能对比"},
                depends_on=["collect_001"],
            ),
            DAGNode(
                id="write_001",
                agent="Writer",
                action="write",
                params={"competitor": "竞品A", "dimension": "功能对比"},
                depends_on=["analyze_001"],
            ),
        ],
        edges=[
            DAGEdge(from_node="collect_001", to_node="analyze_001"),
            DAGEdge(from_node="analyze_001", to_node="write_001"),
        ],
        feedback_edges=[],
    )


@pytest.mark.asyncio
async def test_execute_mvp_loads_default_schema():
    """Verify execute_mvp uses DEFAULT_SCHEMA and builds dim_config map."""
    sm = StateManager()
    bus = EventBus()

    # Mock agents
    mock_collector = AsyncMock()
    mock_collector.execute.return_value = AgentResult(
        success=True,
        output={"raw_data": {"items": [{"title": "功能A", "url": "http://example.com"}]}},
    )

    mock_analyst = AsyncMock()
    mock_analyst.execute.return_value = AgentResult(
        success=True,
        output={"analysis": {"findings": ["功能A支持"]}},
    )

    mock_writer = AsyncMock()
    mock_writer.execute.return_value = AgentResult(
        success=True,
        output={"report_html": "<p>竞品A功能对比报告</p>"},
    )

    mock_agents = {
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
        "Reviewer": AsyncMock(),
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_001"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="产品")], ["功能对比"], {})

    blueprint = _make_mvp_blueprint()
    await orch.execute_mvp(task_id, blueprint, competitors=[{"name": "竞品A", "domain": "产品"}])

    # Verify Collector was called with keywords and evidence_threshold from DEFAULT_SCHEMA
    collector_call = mock_collector.execute.call_args[0][0]
    assert "keywords" in collector_call
    assert collector_call["keywords"] == ["功能", "特性", "支持"]
    assert collector_call["evidence_threshold"] == 2  # from 功能对比 dimension

    # Verify Analyst was called with evidence_threshold
    analyst_call = mock_analyst.execute.call_args[0][0]
    assert analyst_call["evidence_threshold"] == 2

    # Verify Writer was called with output_type
    writer_call = mock_writer.execute.call_args[0][0]
    assert writer_call["output_type"] == "table"

    # Verify task status is COMPLETED
    assert sm.get_task(task_id).status == TaskStatus.COMPLETED

    # Verify report_html was set
    assert sm.get_task(task_id).report_html is not None
    assert "竞品A功能对比报告" in sm.get_task(task_id).report_html


@pytest.mark.asyncio
async def test_execute_mvp_multi_competitor():
    """Verify execute_mvp handles multiple competitors."""
    sm = StateManager()
    bus = EventBus()

    mock_collector = AsyncMock()
    mock_collector.execute.return_value = AgentResult(
        success=True,
        output={"raw_data": {"items": []}},
    )

    mock_analyst = AsyncMock()
    mock_analyst.execute.return_value = AgentResult(
        success=True,
        output={"analysis": {"findings": []}},
    )

    mock_writer = AsyncMock()
    mock_writer.execute.return_value = AgentResult(
        success=True,
        output={"report_html": "<p>Report content</p>"},
    )

    mock_agents = {
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
        "Reviewer": AsyncMock(),
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_002"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="产品"), Competitor(name="竞品B", domain="产品")], ["功能对比"], {})

    # Blueprint with nodes for two competitors
    blueprint = DAGBlueprint(
        nodes=[
            DAGNode(
                id="collect_A",
                agent="Collector",
                action="search",
                params={"competitor": "竞品A", "dimension": "功能对比", "domain": "产品"},
                depends_on=[],
            ),
            DAGNode(
                id="collect_B",
                agent="Collector",
                action="search",
                params={"competitor": "竞品B", "dimension": "功能对比", "domain": "产品"},
                depends_on=[],
            ),
            DAGNode(
                id="analyze_A",
                agent="Analyst",
                action="analyze",
                params={"competitor": "竞品A", "dimension": "功能对比"},
                depends_on=["collect_A"],
            ),
            DAGNode(
                id="analyze_B",
                agent="Analyst",
                action="analyze",
                params={"competitor": "竞品B", "dimension": "功能对比"},
                depends_on=["collect_B"],
            ),
            DAGNode(
                id="write_A",
                agent="Writer",
                action="write",
                params={"competitor": "竞品A", "dimension": "功能对比"},
                depends_on=["analyze_A"],
            ),
            DAGNode(
                id="write_B",
                agent="Writer",
                action="write",
                params={"competitor": "竞品B", "dimension": "功能对比"},
                depends_on=["analyze_B"],
            ),
        ],
        edges=[
            DAGEdge(from_node="collect_A", to_node="analyze_A"),
            DAGEdge(from_node="collect_B", to_node="analyze_B"),
            DAGEdge(from_node="analyze_A", to_node="write_A"),
            DAGEdge(from_node="analyze_B", to_node="write_B"),
        ],
        feedback_edges=[],
    )

    await orch.execute_mvp(task_id, blueprint, competitors=[
        {"name": "竞品A", "domain": "产品"},
        {"name": "竞品B", "domain": "产品"},
    ])

    assert sm.get_task(task_id).status == TaskStatus.COMPLETED
    # Both collectors should have been called
    assert mock_collector.execute.call_count == 2


@pytest.mark.asyncio
async def test_execute_mvp_empty_dag():
    """Verify execute_mvp handles empty DAG gracefully."""
    sm = StateManager()
    bus = EventBus()
    mock_agents = {name: AsyncMock() for name in ["Collector", "Analyst", "Writer", "Reviewer"]}

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_003"
    sm.create_task(task_id, [], [], {})

    blueprint = DAGBlueprint(nodes=[], edges=[], feedback_edges=[])

    await orch.execute_mvp(task_id, blueprint, competitors=[])

    assert sm.get_task(task_id).status == TaskStatus.COMPLETED