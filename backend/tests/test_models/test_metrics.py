from app.models.metrics import TraceMetrics, TaskMetricsSnapshot


def test_trace_metrics_required_fields():
    m = TraceMetrics(
        trace_id="t1",
        task_id="task1",
        node_id="c_Notion_pricing",
        agent="Collector",
        timestamp="2026-06-06T00:00:00Z",
        elapsed_ms=1234,
    )
    assert m.llm_latency_ms == 0
    assert m.tokens_in == 0
    assert m.tokens_out == 0
    assert m.tokens_total == 0
    assert m.cost_cny == 0.0
    assert m.reasoning_steps == 0


def test_trace_metrics_all_fields():
    m = TraceMetrics(
        trace_id="t1",
        task_id="task1",
        node_id="n1",
        agent="Analyst",
        timestamp="2026-06-06T00:00:00Z",
        elapsed_ms=5000,
        llm_latency_ms=3500,
        tokens_in=200,
        tokens_out=400,
        tokens_total=600,
        cost_cny=0.012,
        reasoning_steps=3,
    )
    assert m.tokens_total == 600
    assert m.cost_cny == 0.012
    assert m.reasoning_steps == 3


def test_task_metrics_snapshot_defaults():
    s = TaskMetricsSnapshot(task_id="task1", created_at="2026-06-06T00:00:00Z", total_elapsed_ms=10000)
    assert s.feedback_rounds == 0
    assert s.total_tokens == 0
    assert s.total_cost_cny == 0.0
    assert s.llm_call_count == 0
    assert s.slow_nodes == []
    assert s.agent_breakdown == {}
    assert s.quality == {}
    assert s.rc_missing_count == 0
    assert s.node_count == 0
    assert s.completed_count == 0
    assert s.failed_count == 0
