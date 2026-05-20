import pytest
from app.models.dag import (
    DAGNode, DAGEdge, FeedbackEdge, DAGBlueprint,
    TaskDAG, TraceabilityConfig,
)


def test_dag_node_creation():
    node = DAGNode(
        id="collect_001",
        agent="Collector",
        action="web_search",
        params={"target": "竞品A", "dimension": "功能对比"},
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
        dimensions=["功能对比"],
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
            include_confidence=True,
        ),
    )
    assert dag.task_id == "test-001"
    assert len(dag.competitors) == 2
