import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.task_parser import TaskParser
from app.agents.collector import Collector
from app.agents.analyst import Analyst
from app.agents.writer import Writer
from app.agents.reviewer import Reviewer
from app.agents.base import AgentResult
from app.engine.orchestrator import Orchestrator
from app.engine.state_manager import StateManager
from app.engine.event_bus import EventBus
from app.models.dag import DAGBlueprint
from app.models.task import Competitor
from app.llm.base import LLMResponse


class MockBailianAdapter:
    """Mock that pretends to be BailianAdapter but returns deterministic JSON."""

    def __init__(self, response_content: str):
        self.response_content = response_content
        self.model = "qwen3.6-plus-2026-04-02"
        self.chat_calls = 0

    async def chat(self, messages, **kwargs):
        self.chat_calls += 1
        return LLMResponse(
            content=self.response_content,
            model=self.model,
            tokens_used=100,
            latency_ms=50,
        )

    async def stream_chat(self, messages, **kwargs):
        for chunk in self.response_content.split():
            yield chunk


TASK_PARSER_FIXTURE = MockBailianAdapter(
    '{"competitors": ["抖音", "快手"], "dimensions": ["推荐算法"], "dag": {"nodes": [{"id": "collect_001", "agent": "Collector", "action": "search", "params": {"target": "抖音", "dimension": "推荐算法"}, "depends_on": []}, {"id": "collect_002", "agent": "Collector", "action": "search", "params": {"target": "快手", "dimension": "推荐算法"}, "depends_on": []}, {"id": "analyze_001", "agent": "Analyst", "action": "analyze", "params": {}, "depends_on": ["collect_001", "collect_002"]}, {"id": "write_001", "agent": "Writer", "action": "write", "params": {}, "depends_on": ["analyze_001"]}, {"id": "review_001", "agent": "Reviewer", "action": "review", "params": {}, "depends_on": ["write_001"]}], "edges": [{"from": "collect_001", "to": "analyze_001"}, {"from": "collect_002", "to": "analyze_001"}, {"from": "analyze_001", "to": "write_001"}, {"from": "write_001", "to": "review_001"}], "feedback_edges": [{"from": "review_001", "to": "write_001", "condition": "review_001.status == rejected", "max_rounds": 3, "escalation": "auto_approve"}]}}'
)

COLLECTOR_FIXTURE = MockBailianAdapter(
    '{"search_queries": ["query1"], "target_urls": [], "strategy": "web_search"}'
)

ANALYST_FIXTURE = MockBailianAdapter(
    '{"competitor": "抖音", "dimension": "推荐算法", "findings": [{"finding_id": "f001", "claim": "抖音使用深度学习推荐", "quote": "deep learning recommendation engine", "quote_type": "exact", "source_ref": "src001", "chunk_ref": "c001", "reasoning_chain": [{"step": 1, "thought": "官网描述"}]}], "comparison_matrix": {"dimensions": ["推荐算法"], "competitors": {"抖音": {"推荐算法": {"status": "Y", "detail": "深度学习"}}}}}'
)

WRITER_FIXTURE = MockBailianAdapter(
    '{"report_html": "<div class=\\"report\\"><h1>抖音 vs 快手 竞品分析报告</h1></div>", "summary": "短视频平台推荐算法对比"}'
)

REVIEWER_FIXTURE = MockBailianAdapter(
    '{"verdict": "approved", "checks": [{"dimension": "溯源完整性", "status": "pass", "issues": []}], "feedback_to": "", "feedback_message": ""}'
)


@pytest.mark.asyncio
async def test_task_parser_returns_valid_dag():
    parser = TaskParser("TaskParser", TASK_PARSER_FIXTURE)

    result = await parser.run({"message": "分析抖音和快手的推荐算法差异"})

    assert result.success is True
    output = result.output
    assert "competitors" in output
    assert output["competitors"] == ["抖音", "快手"]
    assert "dimensions" in output
    assert "dag" in output
    dag = output["dag"]
    assert len(dag["nodes"]) == 5
    assert len(dag["edges"]) == 4
    blueprint = DAGBlueprint(**dag)
    assert blueprint.model_dump()


@pytest.mark.asyncio
async def test_task_parser_handles_markdown_fences():
    class FenceAdapter(MockBailianAdapter):
        async def chat(self, messages, **kwargs):
            return LLMResponse(
                content='```json\n{"competitors": ["A", "B"], "dimensions": ["价格"], "dag": {"nodes": [], "edges": [], "feedback_edges": []}}\n```',
                model="qwen3.6-plus-2026-04-02",
                tokens_used=50,
                latency_ms=20,
            )

    parser = TaskParser("TaskParser", FenceAdapter(""))
    result = await parser.run({"message": "compare A and B"})
    assert result.success is True
    assert result.output["competitors"] == ["A", "B"]


@pytest.mark.asyncio
async def test_task_parser_invalid_json():
    class InvalidAdapter(MockBailianAdapter):
        async def chat(self, messages, **kwargs):
            return LLMResponse(content="{not valid json", model="test", tokens_used=0, latency_ms=0)

    parser = TaskParser("TaskParser", InvalidAdapter(""))
    result = await parser.run({"message": "analyze"})
    assert result.success is False
    assert result.error_type == "json_parse"


@pytest.mark.asyncio
async def test_orchestrator_runs_linear_dag():
    sm = StateManager()
    bus = EventBus()

    parser = TaskParser("TaskParser", TASK_PARSER_FIXTURE)

    collector = Collector("Collector", COLLECTOR_FIXTURE)
    analyst = Analyst("Analyst", ANALYST_FIXTURE)
    writer = Writer("Writer", WRITER_FIXTURE)
    reviewer = Reviewer("Reviewer", REVIEWER_FIXTURE)

    agents = {
        "TaskParser": parser,
        "Collector": collector,
        "Analyst": analyst,
        "Writer": writer,
        "Reviewer": reviewer,
    }
    orch = Orchestrator(sm, bus, agents)

    task_id = "test-dag-run"
    dag_blueprint = DAGBlueprint(
        nodes=[
            {"id": "collect_001", "agent": "Collector", "action": "search", "params": {"target": "抖音", "dimension": "推荐算法"}, "depends_on": []},
            {"id": "analyze_001", "agent": "Analyst", "action": "analyze", "params": {}, "depends_on": ["collect_001"]},
            {"id": "write_001", "agent": "Writer", "action": "write", "params": {}, "depends_on": ["analyze_001"]},
            {"id": "review_001", "agent": "Reviewer", "action": "review", "params": {}, "depends_on": ["write_001"]},
        ],
        edges=[
            {"from": "collect_001", "to": "analyze_001"},
            {"from": "analyze_001", "to": "write_001"},
            {"from": "write_001", "to": "review_001"},
        ],
        feedback_edges=[
            {"from": "review_001", "to": "write_001", "condition": "rejected", "max_rounds": 3, "escalation": "auto_approve"},
        ],
    )

    sm.create_task(task_id, [Competitor(name="抖音", domain="douyin.com"), Competitor(name="快手", domain="kuaishou.com")], ["推荐算法"], dag_blueprint.model_dump())

    await orch.execute_with_feedback(task_id, dag_blueprint)

    task = sm.get_task(task_id)
    assert task.status.value in ("completed", "failed")
    for node in dag_blueprint.nodes:
        assert node.id in task.node_states


@pytest.mark.asyncio
async def test_orchestrator_feedback_loop_approved():
    sm = StateManager()
    bus = EventBus()

    approved_reviewer = REVIEWER_FIXTURE  # approved verdict

    orch = Orchestrator(
        sm, bus,
        {
            "Collector": Collector("Collector", COLLECTOR_FIXTURE),
            "Analyst": Analyst("Analyst", ANALYST_FIXTURE),
            "Writer": Writer("Writer", WRITER_FIXTURE),
            "Reviewer": Reviewer("Reviewer", approved_reviewer),
        },
    )

    dag_blueprint = DAGBlueprint(
        nodes=[
            {"id": "c1", "agent": "Collector", "action": "s", "params": {}, "depends_on": []},
            {"id": "a1", "agent": "Analyst", "action": "a", "params": {}, "depends_on": ["c1"]},
            {"id": "w1", "agent": "Writer", "action": "w", "params": {}, "depends_on": ["a1"]},
            {"id": "r1", "agent": "Reviewer", "action": "r", "params": {}, "depends_on": ["w1"]},
        ],
        edges=[{"from": "c1", "to": "a1"}, {"from": "a1", "to": "w1"}, {"from": "w1", "to": "r1"}],
        feedback_edges=[{"from": "r1", "to": "w1", "condition": "rejected", "max_rounds": 3, "escalation": "auto_approve"}],
    )

    sm.create_task("feedback-test", [], [], dag_blueprint.model_dump())
    await orch.execute_with_feedback("feedback-test", dag_blueprint)

    task = sm.get_task("feedback-test")
    assert task.status.value == "completed"


@pytest.mark.asyncio
async def test_full_task_create_flow():
    from unittest.mock import AsyncMock, MagicMock
    import uuid

    sm = StateManager()
    bus = EventBus()
    task_parser = TaskParser("TaskParser", TASK_PARSER_FIXTURE)

    mock_collector = MagicMock()
    mock_collector.run = AsyncMock(return_value=AgentResult(
        success=True,
        output={"data_id": "test", "content": "content", "chunks": []},
    ))
    mock_analyst = MagicMock()
    mock_analyst.run = AsyncMock(return_value=AgentResult(
        success=True,
        output={"findings": [], "comparison_matrix": {"dimensions": [], "competitors": {}}},
    ))
    mock_writer = MagicMock()
    mock_writer.run = AsyncMock(return_value=AgentResult(
        success=True,
        output={"report_html": "<div>x</div>", "summary": "s"},
    ))
    mock_reviewer = MagicMock()
    mock_reviewer.run = AsyncMock(return_value=AgentResult(
        success=True,
        output={"verdict": "approved", "checks": [], "feedback_to": "", "feedback_message": ""},
    ))

    agents = {
        "TaskParser": task_parser,
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
        "Reviewer": mock_reviewer,
    }
    orch = Orchestrator(sm, bus, agents)

    task_id = str(uuid.uuid4())
    parse_result = await task_parser.run({"message": "分析抖音和快手"})
    assert parse_result.success
    parsed = parse_result.output
    dag_blueprint = DAGBlueprint(**parsed["dag"])

    task = sm.create_task(task_id, [Competitor(name=c, domain="example.com") for c in parsed["competitors"]], parsed["dimensions"], dag_blueprint.model_dump())
    assert task.task_id == task_id
    assert len(task.competitors) >= 2

    await orch.execute_with_feedback(task_id, dag_blueprint)

    final_task = sm.get_task(task_id)
    assert final_task.status.value in ("completed", "failed")
    assert len(final_task.node_states) == len(dag_blueprint.nodes)


@pytest.mark.asyncio
async def test_event_bus_published_on_node_events():
    sm = StateManager()
    bus = EventBus()
    events = []

    async def on_event(e):
        events.append(e.type)

    bus.subscribe("node_started", on_event)
    bus.subscribe("node_completed", on_event)

    orch = Orchestrator(sm, bus, {"Collector": Collector("Collector", COLLECTOR_FIXTURE)})
    sm.create_task("evt-test", [], [], {})
    from app.models.dag import DAGNode
    node = DAGNode(id="n1", agent="Collector", action="search", params={})

    await orch.execute_node("evt-test", node)

    assert "node_started" in events
    assert "node_completed" in events