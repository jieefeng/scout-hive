import pytest

from app.engine.dag_parser import DAGParser, TopologicalError
from app.models.dag import DAGNode, DAGEdge, FeedbackEdge, DAGBlueprint


def _make_blueprint(nodes, edges, feedback_edges=None):
    return DAGBlueprint(
        nodes=[
            DAGNode(id=n[0], agent=n[1], action=n[2], params={}, depends_on=n[3])
            for n in nodes
        ],
        edges=[DAGEdge(from_node=e[0], to_node=e[1]) for e in edges],
        feedback_edges=[
            FeedbackEdge(from_node=f[0], to_node=f[1], condition=f[2])
            for f in (feedback_edges or [])
        ],
    )


def test_topological_sort_linear():
    bp = _make_blueprint(
        nodes=[
            ("a", "Collector", "search", []),
            ("b", "Analyst", "analyze", ["a"]),
            ("c", "Writer", "write", ["b"]),
        ],
        edges=[("a", "b"), ("b", "c")],
    )
    parser = DAGParser(bp)
    order = parser.topological_sort()
    assert order == ["a", "b", "c"]


def test_topological_sort_parallel():
    bp = _make_blueprint(
        nodes=[
            ("a", "Collector", "search_a", []),
            ("b", "Collector", "search_b", []),
            ("c", "Analyst", "analyze", ["a", "b"]),
        ],
        edges=[("a", "c"), ("b", "c")],
    )
    parser = DAGParser(bp)
    order = parser.topological_sort()
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("c")


def test_get_ready_nodes():
    bp = _make_blueprint(
        nodes=[
            ("a", "Collector", "search", []),
            ("b", "Analyst", "analyze", ["a"]),
        ],
        edges=[("a", "b")],
    )
    parser = DAGParser(bp)
    ready = parser.get_ready_nodes(completed=set())
    assert ready == ["a"]
    ready = parser.get_ready_nodes(completed={"a"})
    assert ready == ["b"]


def test_feedback_edges():
    bp = _make_blueprint(
        nodes=[
            ("w", "Writer", "write", []),
            ("r", "Reviewer", "review", ["w"]),
        ],
        edges=[("w", "r")],
        feedback_edges=[("r", "w", "r.status == 'rejected'")],
    )
    parser = DAGParser(bp)
    assert len(parser.feedback_edges) == 1
    assert parser.feedback_edges[0].from_node == "r"
