from fastapi import APIRouter, HTTPException

from app.engine.state_manager import StateManager
from app.models.metrics import TaskMetricsSnapshot
from app.models.task import NodeStatus

router = APIRouter(prefix="/api/tasks", tags=["metrics"])

# 共享依赖（main.py init_router 注入）
state_manager: StateManager = None


def init_router(sm: StateManager):
    global state_manager
    state_manager = sm


@router.get("/{task_id}/metrics")
def get_task_metrics(task_id: str):
    """返回任务的聚合 metrics 快照。旧任务返 available: false。"""
    task = state_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    rows = state_manager.query_task_metrics(task_id)
    if not rows:
        return {
            "task_id": task_id,
            "available": False,
            "reason": "no metrics recorded",
        }

    # 聚合
    total_elapsed = sum(r["elapsed_ms"] for r in rows)
    total_tokens = sum(r["tokens_total"] for r in rows)
    total_cost = sum(r["cost_cny"] for r in rows)
    llm_call_count = sum(1 for r in rows if r["llm_latency_ms"] > 0)
    # 短期启发式：reasoning_steps=0 视为缺失。可能误报（短答无 chain），
    # 后续可改用 reasoning_chain 长度。
    rc_missing = sum(1 for r in rows if r["reasoning_steps"] == 0 and r["agent"] in {"Analyst", "Writer", "Reviewer"})

    # 慢节点 top-3
    slow = sorted(rows, key=lambda r: r["elapsed_ms"], reverse=True)[:3]
    slow_nodes = [
        {
            "node_id": r["node_id"],
            "agent": r["agent"],
            "elapsed_ms": r["elapsed_ms"],
            "cost_cny": r["cost_cny"],
        }
        for r in slow
    ]

    # 按 agent 聚合
    by_agent: dict = {}
    for r in rows:
        a = r["agent"]
        if a not in by_agent:
            by_agent[a] = {"count": 0, "tokens": 0, "cost_cny": 0.0, "elapsed_ms": 0}
        by_agent[a]["count"] += 1
        by_agent[a]["tokens"] += r["tokens_total"]
        by_agent[a]["cost_cny"] += r["cost_cny"]
        by_agent[a]["elapsed_ms"] += r["elapsed_ms"]

    # node_states 里 completed/failed 计数
    completed_count = sum(1 for s in task.node_states.values() if s == NodeStatus.COMPLETED)
    failed_count = sum(1 for s in task.node_states.values() if s == NodeStatus.FAILED)

    snapshot = TaskMetricsSnapshot(
        task_id=task_id,
        created_at=task.created_at,
        total_elapsed_ms=total_elapsed,
        node_count=len(task.node_states),
        completed_count=completed_count,
        failed_count=failed_count,
        feedback_rounds=0,  # TODO: 从 task.reviews 推算（plan 阶段不深挖）
        total_tokens=total_tokens,
        total_cost_cny=round(total_cost, 4),
        llm_call_count=llm_call_count,
        slow_nodes=slow_nodes,
        agent_breakdown=by_agent,
        quality={
            "feedback_rounds": 0,  # 同上 TODO
            "passed_count": completed_count,  # 简化为 completed 数
        },
        rc_missing_count=rc_missing,
    )
    return {**snapshot.model_dump(), "available": True}
