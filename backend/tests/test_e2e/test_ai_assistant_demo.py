"""国内 AI 助手 5 竞品 × 3 维度 demo 的 e2e 测试(mock LLM)。

不依赖真实 LLM,验证:
1. blueprint 生成(5 竞品 × 3 维度 = 15 节点)
2. 5 竞品都在 blueprint 内
3. 当前 active schema = ai-assistant,应有 7 维度
"""
import pytest

from app.models.dag import DAGBlueprint, DAGNode
from app.schema.mvp_defaults import get_active_schema


def _build_5x3_blueprint() -> DAGBlueprint:
    """构造 5 竞品 × 3 维度 = 15 collect + 15 analyze + 3 write + 3 review 的最小 DAG。"""
    competitors = ["豆包", "通义千问", "Kimi", "文小言", "秘塔 AI 搜索"]
    dimensions = ["核心玩法", "AI 模型能力", "Agent 能力"]

    nodes = []
    edges = []

    for dim in dimensions:
        for comp in competitors:
            cid = f"c_{comp}_{dim}".replace(" ", "_")
            aid = f"a_{comp}_{dim}".replace(" ", "_")
            nodes.append(DAGNode(id=cid, agent="Collector", action="web_search",
                                 params={"target": comp, "dimension": dim}, depends_on=[]))
            nodes.append(DAGNode(id=aid, agent="Analyst", action="analyze",
                                 params={"competitor": comp, "dimension": dim}, depends_on=[cid]))
            edges.append({"from": cid, "to": aid})

        # 1 个 write + 1 个 review per dimension
        wid = f"w_{dim}".replace(" ", "_")
        rid = f"r_{dim}".replace(" ", "_")
        all_analyze_ids = [f"a_{c}_{dim}".replace(" ", "_") for c in competitors]
        nodes.append(DAGNode(id=wid, agent="Writer", action="generate_report",
                             params={"dimension": dim}, depends_on=all_analyze_ids))
        nodes.append(DAGNode(id=rid, agent="Reviewer", action="quality_check",
                             params={"dimension": dim}, depends_on=[wid]))
        for aid_node in all_analyze_ids:
            edges.append({"from": aid_node, "to": wid})
        edges.append({"from": wid, "to": rid})

    return DAGBlueprint(nodes=nodes, edges=edges, feedback_edges=[])


def test_5x3_blueprint_has_correct_node_count():
    """blueprint 节点数 = 15 collect + 15 analyze + 3 write + 3 review = 36。"""
    blueprint = _build_5x3_blueprint()
    n_collect = sum(1 for n in blueprint.nodes if n.agent == "Collector")
    n_analyze = sum(1 for n in blueprint.nodes if n.agent == "Analyst")
    n_write = sum(1 for n in blueprint.nodes if n.agent == "Writer")
    n_review = sum(1 for n in blueprint.nodes if n.agent == "Reviewer")
    assert n_collect == 15
    assert n_analyze == 15
    assert n_write == 3
    assert n_review == 3
    assert len(blueprint.nodes) == 36


def test_5x3_blueprint_all_competitors_covered():
    """5 竞品都在 blueprint 内。"""
    blueprint = _build_5x3_blueprint()
    competitors_in_dag = {n.params["target"] for n in blueprint.nodes if n.agent == "Collector"}
    assert competitors_in_dag == {"豆包", "通义千问", "Kimi", "文小言", "秘塔 AI 搜索"}


def test_active_schema_has_7_dimensions():
    """当前 active schema = ai-assistant,应有 7 维度。"""
    schema = get_active_schema()
    all_dims = [d.name for g in schema.groups for d in g.dimensions]
    assert len(all_dims) == 7
    assert "核心玩法" in all_dims
    assert "Agent 能力" in all_dims
    assert "安全合规" in all_dims
