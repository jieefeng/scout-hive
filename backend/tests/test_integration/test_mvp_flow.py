"""
MVP flow integration tests.

Verifies the complete MVP flow end-to-end with all LLM calls mocked:
- User fills in competitors -> system runs full flow -> outputs report
- execute_mvp correctly loads DEFAULT_SCHEMA and expands dimension x competitor
- Collector, Analyst, Writer are called with correct params (domain, output_type, min_sources)
- No real network requests, all LLM calls are mocked.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engine.orchestrator import Orchestrator
from app.engine.state_manager import StateManager
from app.engine.event_bus import EventBus
from app.models.dag import DAGBlueprint, DAGNode, DAGEdge
from app.agents.base import AgentResult
from app.models.task import TaskStatus, Competitor


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重置数据库"""
    StateManager.reset()
    yield


def _build_mvp_blueprint(competitors: list[dict], dimensions: list[str]) -> DAGBlueprint:
    """Build MVP DAG: Collector -> Analyst -> Writer for each competitor x dimension.

    Args:
        competitors: list of dicts with "name" and "domain" keys
        dimensions: list of dimension names
    """
    nodes = []
    edges = []
    node_id = 0

    for comp in competitors:
        comp_name = comp["name"]
        comp_domain = comp.get("domain", "")
        for dim in dimensions:
            collect_id = f"collect_{node_id}"
            analyze_id = f"analyze_{node_id}"
            write_id = f"write_{node_id}"

            nodes.extend([
                DAGNode(
                    id=collect_id,
                    agent="Collector",
                    action="search",
                    params={"competitor": comp_name, "dimension": dim, "domain": comp_domain},
                    depends_on=[],
                ),
                DAGNode(
                    id=analyze_id,
                    agent="Analyst",
                    action="analyze",
                    params={"competitor": comp_name, "dimension": dim},
                    depends_on=[collect_id],
                ),
                DAGNode(
                    id=write_id,
                    agent="Writer",
                    action="write",
                    params={"competitor": comp_name, "dimension": dim},
                    depends_on=[analyze_id],
                ),
            ])
            edges.extend([
                DAGEdge(from_node=collect_id, to_node=analyze_id),
                DAGEdge(from_node=analyze_id, to_node=write_id),
            ])
            node_id += 1

    return DAGBlueprint(nodes=nodes, edges=edges, feedback_edges=[])


@pytest.mark.asyncio
async def test_execute_mvp_full_flow_single_competitor():
    """Test complete MVP flow: one competitor, one dimension."""
    sm = StateManager()
    bus = EventBus()

    # Mock agents with proper _build_trace (sync method returning mock TraceRecord)
    mock_collector = MagicMock()
    mock_collector.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={
            "data_id": "test-data-001",
            "source_type": "web",
            "content": "竞品A functionality details...",
            "chunks": [],
        },
    ))
    mock_collector._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_analyst = MagicMock()
    mock_analyst.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={
            "competitor": "竞品A",
            "dimension": "核心玩法",
            "findings": [
                {
                    "finding_id": "f001",
                    "claim": "竞品A支持功能A",
                    "quote": "原文引用",
                    "quote_type": "exact",
                    "source_ref": "src001",
                    "chunk_ref": "chunk001",
                    "reasoning_chain": [],
                }
            ],
            "comparison_matrix": {"dimensions": [], "competitors": {}},
        },
    ))
    mock_analyst._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_writer = MagicMock()
    mock_writer.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"report_html": "<p>竞品A 核心玩法 报告内容</p>", "summary": "测试报告"},
    ))
    mock_writer._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_agents = {
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_flow_001"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="feishu.cn")], ["核心玩法"], {})

    blueprint = _build_mvp_blueprint(competitors=[{"name": "竞品A", "domain": "feishu.cn"}], dimensions=["核心玩法"])
    await orch.execute_mvp(
        task_id,
        blueprint,
        competitors=[{"name": "竞品A", "domain": "feishu.cn"}],
    )

    # Verify task completed
    assert sm.get_task(task_id).status == TaskStatus.COMPLETED

    # Verify report was generated
    assert "竞品A" in sm.get_task(task_id).report_html
    assert "核心玩法" in sm.get_task(task_id).report_html

    # Verify Collector was called with domain and keywords from DEFAULT_SCHEMA
    collector_call = mock_collector.execute.call_args[0][0]
    assert collector_call["target"] == "竞品A"
    assert collector_call["domain"] == "feishu.cn"
    assert collector_call["keywords"] == ["聊天", "角色", "语音", "多模态", "对话", "玩法"]
    assert collector_call["evidence_threshold"] == 2  # 核心玩法 evidence_threshold in DEFAULT_SCHEMA

    # Verify Analyst was called with evidence_threshold
    analyst_call = mock_analyst.execute.call_args[0][0]
    assert analyst_call["competitor"] == "竞品A"
    assert analyst_call["dimension"] == "核心玩法"
    assert analyst_call["evidence_threshold"] == 2

    # Verify Writer was called with output_type and description
    writer_call = mock_writer.execute.call_args[0][0]
    assert writer_call["competitor"] == "竞品A"
    assert writer_call["dimension"] == "核心玩法"
    assert writer_call["output_type"] == "paragraph"
    assert writer_call["description"] != ""


@pytest.mark.asyncio
async def test_execute_mvp_full_flow_multi_competitor_multi_dimension():
    """Test MVP flow with multiple competitors and multiple dimensions."""
    sm = StateManager()
    bus = EventBus()

    def make_collector_response():
        return AgentResult(
            success=True,
            output={"data_id": "test-data", "content": "content", "chunks": []},
        )

    def make_analyst_response(comp: str, dim: str):
        return AgentResult(
            success=True,
            output={
                "competitor": comp,
                "dimension": dim,
                "findings": [],
                "comparison_matrix": {"dimensions": [], "competitors": {}},
            },
        )

    def make_writer_response(comp: str, dim: str):
        return AgentResult(
            success=True,
            output={"report_html": f"<p>{comp} {dim} 报告</p>", "summary": "summary"},
        )

    mock_collector = MagicMock()
    mock_analyst = MagicMock()
    mock_writer = MagicMock()

    def make_collector_response():
        return AgentResult(
            success=True,
            output={"data_id": "test-data", "content": "content", "chunks": []},
        )

    def make_analyst_response(comp: str, dim: str):
        return AgentResult(
            success=True,
            output={
                "competitor": comp,
                "dimension": dim,
                "findings": [],
                "comparison_matrix": {"dimensions": [], "competitors": {}},
            },
        )

    def make_writer_response(comp: str, dim: str):
        return AgentResult(
            success=True,
            output={"report_html": f"<p>{comp} {dim} 报告</p>", "summary": "summary"},
        )

    mock_collector.execute = AsyncMock(side_effect=lambda args: make_collector_response())
    mock_analyst.execute = AsyncMock(side_effect=lambda args: make_analyst_response(args["competitor"], args["dimension"]))
    mock_writer.execute = AsyncMock(side_effect=lambda args: make_writer_response(args["competitor"], args["dimension"]))

    mock_collector._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))
    mock_analyst._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))
    mock_writer._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_agents = {
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_flow_002"
    sm.create_task(
        task_id,
        [
            Competitor(name="竞品A", domain="feishu.cn"),
            Competitor(name="竞品B", domain="lark.cn"),
        ],
        ["功能对比", "用户体验"],
        {},
    )

    blueprint = _build_mvp_blueprint(
        competitors=[{"name": "竞品A", "domain": "feishu.cn"}, {"name": "竞品B", "domain": "lark.cn"}],
        dimensions=["功能对比", "用户体验"],
    )
    await orch.execute_mvp(
        task_id,
        blueprint,
        competitors=[
            {"name": "竞品A", "domain": "feishu.cn"},
            {"name": "竞品B", "domain": "lark.cn"},
        ],
    )

    assert sm.get_task(task_id).status == TaskStatus.COMPLETED

    # Collector should be called 4 times (2 competitors x 2 dimensions)
    assert mock_collector.execute.call_count == 4

    # Analyst should be called 4 times
    assert mock_analyst.execute.call_count == 4

    # Writer should be called 4 times
    assert mock_writer.execute.call_count == 4

    # Verify all report parts are included
    report = sm.get_task(task_id).report_html
    assert "竞品A" in report
    assert "竞品B" in report


@pytest.mark.asyncio
async def test_execute_mvp_loads_default_schema_dim_config():
    """Verify execute_mvp builds correct dim_config from DEFAULT_SCHEMA."""
    sm = StateManager()
    bus = EventBus()

    mock_collector = MagicMock()
    mock_collector.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"data_id": "test", "content": "", "chunks": []},
    ))
    mock_collector._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_analyst = MagicMock()
    mock_analyst.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"competitor": "", "dimension": "", "findings": [], "comparison_matrix": {}},
    ))
    mock_analyst._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_writer = MagicMock()
    mock_writer.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"report_html": "<p>report</p>", "summary": ""},
    ))
    mock_writer._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_agents = {
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_schema_001"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="test.com")], ["核心玩法", "AI 模型能力", "商业模式"], {})

    blueprint = _build_mvp_blueprint(
        competitors=[{"name": "竞品A", "domain": "test.com"}],
        dimensions=["核心玩法", "AI 模型能力", "商业模式"],
    )
    await orch.execute_mvp(
        task_id,
        blueprint,
        competitors=[{"name": "竞品A", "domain": "test.com"}],
    )

    # Verify Collector calls have correct keywords/min_sources per dimension
    calls = mock_collector.execute.call_args_list
    call_params = [c[0][0] for c in calls]

    # 核心玩法: keywords=["聊天", "角色", "语音", "多模态", "对话", "玩法"], min_sources=2, output_type=paragraph
    func_call = next(c for c in call_params if c["dimension"] == "核心玩法")
    assert func_call["keywords"] == ["聊天", "角色", "语音", "多模态", "对话", "玩法"]
    assert func_call["evidence_threshold"] == 2

    # AI 模型能力: keywords=["模型", "上下文", "token", "多模态", "响应速度", "MoE"], evidence_threshold=2, output_type=table
    model_call = next(c for c in call_params if c["dimension"] == "AI 模型能力")
    assert model_call["keywords"] == ["模型", "上下文", "token", "多模态", "响应速度", "MoE"]
    assert model_call["evidence_threshold"] == 2

    # 商业模式: keywords=["订阅", "会员", "免费", "配额", "价格", "企业版", "B 端"], evidence_threshold=1, output_type=table
    price_call = next(c for c in call_params if c["dimension"] == "商业模式")
    assert price_call["keywords"] == ["订阅", "会员", "免费", "配额", "价格", "企业版", "B 端"]
    assert price_call["evidence_threshold"] == 1

    # Verify Writer calls have correct output_type per dimension
    writer_calls = mock_writer.execute.call_args_list
    writer_params = [c[0][0] for c in writer_calls]

    func_write = next(c for c in writer_params if c["dimension"] == "核心玩法")
    assert func_write["output_type"] == "paragraph"

    model_write = next(c for c in writer_params if c["dimension"] == "AI 模型能力")
    assert model_write["output_type"] == "table"

    price_write = next(c for c in writer_params if c["dimension"] == "商业模式")
    assert price_write["output_type"] == "table"


@pytest.mark.asyncio
async def test_execute_mvp_collector_injects_domain():
    """Verify Collector receives domain from competitor."""
    sm = StateManager()
    bus = EventBus()

    mock_collector = MagicMock()
    mock_collector.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"data_id": "test", "content": "", "chunks": []},
    ))
    mock_collector._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_analyst = MagicMock()
    mock_analyst.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"competitor": "", "dimension": "", "findings": [], "comparison_matrix": {}},
    ))
    mock_analyst._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_writer = MagicMock()
    mock_writer.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"report_html": "<p>report</p>", "summary": ""},
    ))
    mock_writer._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_agents = {
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_domain_001"
    sm.create_task(task_id, [Competitor(name="飞书", domain="feishu.cn")], ["核心玩法"], {})

    blueprint = _build_mvp_blueprint(competitors=[{"name": "飞书", "domain": "feishu.cn"}], dimensions=["核心玩法"])
    await orch.execute_mvp(
        task_id,
        blueprint,
        competitors=[{"name": "飞书", "domain": "feishu.cn"}],
    )

    collector_call = mock_collector.execute.call_args[0][0]
    assert collector_call["domain"] == "feishu.cn"


@pytest.mark.asyncio
async def test_execute_mvp_analyst_injects_evidence_threshold():
    """Verify Analyst receives evidence_threshold from dimension config."""
    sm = StateManager()
    bus = EventBus()

    mock_collector = MagicMock()
    mock_collector.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"data_id": "test", "content": "", "chunks": []},
    ))
    mock_collector._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_analyst = MagicMock()
    mock_analyst.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"competitor": "", "dimension": "", "findings": [], "comparison_matrix": {}},
    ))
    mock_analyst._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_writer = MagicMock()
    mock_writer.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"report_html": "<p>report</p>", "summary": ""},
    ))
    mock_writer._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_agents = {
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_evidence_threshold_001"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="test.com")], ["核心玩法"], {})

    blueprint = _build_mvp_blueprint(competitors=[{"name": "竞品A", "domain": "test.com"}], dimensions=["核心玩法"])
    await orch.execute_mvp(
        task_id,
        blueprint,
        competitors=[{"name": "竞品A", "domain": "test.com"}],
    )

    analyst_call = mock_analyst.execute.call_args[0][0]
    assert analyst_call["evidence_threshold"] == 2  # from 核心玩法 in DEFAULT_SCHEMA


@pytest.mark.asyncio
async def test_execute_mvp_writer_injects_output_type():
    """Verify Writer receives output_type from dimension config."""
    sm = StateManager()
    bus = EventBus()

    mock_collector = MagicMock()
    mock_collector.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"data_id": "test", "content": "", "chunks": []},
    ))
    mock_collector._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_analyst = MagicMock()
    mock_analyst.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"competitor": "", "dimension": "", "findings": [], "comparison_matrix": {}},
    ))
    mock_analyst._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_writer = MagicMock()
    mock_writer.execute = AsyncMock(return_value=AgentResult(
        success=True,
        output={"report_html": "<p>report</p>", "summary": ""},
    ))
    mock_writer._build_trace = MagicMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    mock_agents = {
        "Collector": mock_collector,
        "Analyst": mock_analyst,
        "Writer": mock_writer,
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_output_type_001"
    sm.create_task(task_id, [Competitor(name="竞品A", domain="test.com")], ["核心玩法", "AI 模型能力"], {})

    blueprint = _build_mvp_blueprint(
        competitors=[{"name": "竞品A", "domain": "test.com"}],
        dimensions=["核心玩法", "AI 模型能力"],
    )
    await orch.execute_mvp(
        task_id,
        blueprint,
        competitors=[{"name": "竞品A", "domain": "test.com"}],
    )

    writer_calls = mock_writer.execute.call_args_list
    params_by_dim = {c[0][0]["dimension"]: c[0][0] for c in writer_calls}

    assert params_by_dim["核心玩法"]["output_type"] == "paragraph"
    assert params_by_dim["AI 模型能力"]["output_type"] == "table"


@pytest.mark.asyncio
async def test_execute_mvp_empty_competitors():
    """Verify execute_mvp handles empty competitor list gracefully."""
    sm = StateManager()
    bus = EventBus()
    mock_agents = {
        name: AsyncMock() for name in ["Collector", "Analyst", "Writer"]
    }

    orch = Orchestrator(sm, bus, mock_agents)
    task_id = "test_mvp_empty_001"
    sm.create_task(task_id, [], [], {})

    blueprint = DAGBlueprint(nodes=[], edges=[], feedback_edges=[])
    await orch.execute_mvp(task_id, blueprint, competitors=[])

    # Empty competitors → no report → FAILED
    task = sm.get_task(task_id)
    assert task.status == TaskStatus.FAILED
    assert "未生成报告" in task.error_message