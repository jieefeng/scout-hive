import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, AliasChoices
from app.engine.state_manager import StateManager
from app.engine.orchestrator import Orchestrator
from app.engine.event_bus import EventBus
from app.models.dag import DAGBlueprint
from app.models.task import TaskStatus, Competitor
from app.schema.mvp_defaults import load_default_schema

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])

state_manager: StateManager = None
orchestrator: Orchestrator = None
event_bus: EventBus = None


def init_router(sm: StateManager, orch: Orchestrator, bus: EventBus):
    global state_manager, orchestrator, event_bus
    state_manager = sm
    orchestrator = orch
    event_bus = bus


class CompetitorInput(BaseModel):
    name: str
    website: str = Field(validation_alias=AliasChoices('website', 'domain'))  # 兼容旧名


class CreateTaskRequest(BaseModel):
    competitors: list[CompetitorInput]


class DebugTaskRequest(BaseModel):
    """调试用快捷请求，所有字段可选，均有默认值。"""
    name: str = "飞书"
    domain: str = "feishu.cn"


class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: float = 0.0  # 0.0 - 1.0
    competitors: list[CompetitorInput]
    dimensions: list[str]
    node_states: dict
    dag_json: dict = {}
    created_at: str
    updated_at: str
    report_html: str = ""
    traces: list = Field(default_factory=list)
    reviews: list = Field(default_factory=list)
    error_message: str = ""


def _build_dag(competitors: list[CompetitorInput], dimensions: list[str]) -> DAGBlueprint:
    """构建 Collector → Analyst → Writer DAG 蓝图。"""
    nodes = []
    edges = []
    prev_comp_end = None
    for comp in competitors:
        comp_writers = []
        for dim in dimensions:
            c_id = f"c_{comp.name}_{dim}"
            a_id = f"a_{comp.name}_{dim}"
            w_id = f"w_{comp.name}_{dim}"
            nodes.append({"id": c_id, "agent": "Collector", "action": "collect", "params": {"target": comp.name, "domain": comp.website, "dimension": dim}})
            nodes.append({"id": a_id, "agent": "Analyst", "action": "analyze", "params": {"competitor": comp.name, "dimension": dim}})
            nodes.append({"id": w_id, "agent": "Writer", "action": "write", "params": {"competitor": comp.name, "dimension": dim}})
            edges.append({"from_node": c_id, "to_node": a_id})
            edges.append({"from_node": a_id, "to_node": w_id})
            comp_writers.append(w_id)
        if prev_comp_end:
            for w_id in prev_comp_end:
                for dim in dimensions:
                    c_id = f"c_{comp.name}_{dim}"
                    edges.append({"from_node": w_id, "to_node": c_id})
        prev_comp_end = comp_writers

    from collections import defaultdict
    dep_map: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        dep_map[edge["to_node"]].append(edge["from_node"])
    for node in nodes:
        node["depends_on"] = dep_map.get(node["id"], [])

    return DAGBlueprint(nodes=nodes, edges=edges)


def _load_dimensions() -> list[str]:
    """从 DEFAULT_SCHEMA 提取所有维度名。"""
    schema = load_default_schema()
    return [dim.name for group in schema.groups for dim in group.dimensions]


async def _create_and_run(competitors: list[CompetitorInput], dimensions: list[str]) -> TaskResponse:
    """创建任务、持久化、启动 DAG 执行，返回 TaskResponse。"""
    task_id = str(uuid.uuid4())
    dag_blueprint = _build_dag(competitors, dimensions)
    task = state_manager.create_task(
        task_id,
        [Competitor(name=c.name, website=c.website) for c in competitors],
        dimensions,
        dag_blueprint.model_dump(),
    )
    assert state_manager.get_task(task_id) is not None, "Task was not stored in state_manager"
    task.progress = state_manager.calculate_progress(task)

    async def run_dag():
        try:
            await orchestrator.execute_mvp(task_id, dag_blueprint, [c.model_dump() for c in competitors])
        except Exception as e:
            logger.exception("Task %s failed: %s", task_id, e)
            state_manager.set_error_message(task_id, str(e))
            state_manager.update_task_status(task_id, TaskStatus.FAILED)

    asyncio.create_task(run_dag())
    return TaskResponse(**task.model_dump())


@router.post("/", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    competitors = [CompetitorInput(name=c.name, website=c.website) for c in req.competitors]
    dimensions = _load_dimensions()
    return await _create_and_run(competitors, dimensions)


@router.post("/debug", response_model=TaskResponse)
async def debug_create_task(req: DebugTaskRequest = DebugTaskRequest()):
    """快捷调试端点：默认创建飞书分析任务，也可自定义。"""
    competitors = [CompetitorInput(name=req.name, website=req.domain)]
    dimensions = _load_dimensions()
    logger.info("Debug task: %s (%s), dimensions=%s", req.name, req.domain, dimensions)
    return await _create_and_run(competitors, dimensions)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    task = state_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.progress = state_manager.calculate_progress(task)
    return TaskResponse(**task.model_dump())


@router.get("/", response_model=list[TaskResponse])
async def list_tasks():
    tasks = state_manager.list_tasks()
    for t in tasks:
        t.progress = state_manager.calculate_progress(t)
    return [TaskResponse(**t.model_dump()) for t in tasks]


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除指定任务。"""
    task = state_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    state_manager.delete_task(task_id)
    return {"ok": True}


@router.post("/{task_id}/stop")
async def stop_task(task_id: str):
    """停止指定任务的执行。"""
    task = state_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Task is not running")
    state_manager.cancel_task(task_id)
    return {"ok": True}