import pytest
from pydantic import ValidationError
from app.models.dag import (
    DAGNode, DAGEdge, FeedbackEdge, DAGBlueprint,
    TaskDAG, TraceabilityConfig,
)


def test_dag_node_creation():
    node = DAGNode(
        id="collect_001",
        agent="Collector",
        action="web_search",
        params={"target": "竞品A", "dimension": "核心玩法"},
        depends_on=[],
    )
    assert node.id == "collect_001"
    assert node.agent == "Collector"
    assert node.depends_on == []


def test_dag_edge_creation():
    edge = DAGEdge(from_node="collect_001", to_node="analyze_001")
    assert edge.from_node == "collect_001"
    assert edge.to_node == "analyze_001"


def test_feedback_edge_with_defaults():
    edge = FeedbackEdge(
        from_node="review_001",
        to_node="write_001",
        condition="review_001.status == 'rejected'",
    )
    assert edge.max_rounds == 3
    assert edge.escalation == "auto_approve"


def test_dag_blueprint_validation():
    blueprint = DAGBlueprint(
        nodes=[
            DAGNode(id="a", agent="Collector", action="search", params={}, depends_on=[]),
            DAGNode(id="b", agent="Analyst", action="analyze", params={}, depends_on=["a"]),
        ],
        edges=[DAGEdge(from_node="a", to_node="b")],
        feedback_edges=[],
    )
    assert len(blueprint.nodes) == 2


def test_task_dag_creation():
    dag = TaskDAG(
        task_id="test-001",
        competitors=["竞品A", "竞品B"],
        dimensions=["核心玩法"],
        dag=DAGBlueprint(
            nodes=[
                DAGNode(id="a", agent="Collector", action="search", params={}, depends_on=[]),
            ],
            edges=[],
            feedback_edges=[],
        ),
        traceability=TraceabilityConfig(
            level="full",
            include_reasoning=True,
        ),
    )
    assert dag.task_id == "test-001"
    assert len(dag.competitors) == 2


def test_dag_node_empty_id_rejected():
    with pytest.raises(ValidationError):
        DAGNode(id="", agent="Collector", action="search")


def test_dag_edge_from_alias():
    edge = DAGEdge(**{"from": "a", "to": "b"})
    assert edge.from_node == "a"
    assert edge.to_node == "b"


def test_blueprint_rejects_dangling_depends_on():
    with pytest.raises(ValidationError, match="depends_on.*not in nodes"):
        DAGBlueprint(
            nodes=[DAGNode(id="a", agent="C", action="x", depends_on=["MISSING"])],
            edges=[],
        )


def test_blueprint_rejects_dangling_edge():
    with pytest.raises(ValidationError, match="node not found"):
        DAGBlueprint(
            nodes=[DAGNode(id="a", agent="C", action="x")],
            edges=[DAGEdge(from_node="a", to_node="MISSING")],
        )


def test_invalid_escalation_rejected():
    with pytest.raises(ValidationError):
        FeedbackEdge(
            from_node="a", to_node="b",
            condition="x", escalation="typo_value",
        )
