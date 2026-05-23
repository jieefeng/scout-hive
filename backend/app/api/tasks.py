import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.engine.state_manager import StateManager
from app.engine.orchestrator import Orchestrator
from app.engine.event_bus import EventBus
from app.models.dag import DAGBlueprint
from app.models.task import TaskStatus
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
    domain: str


class CreateTaskRequest(BaseModel):
    competitors: list[CompetitorInput]


class TaskResponse(BaseModel):
    task_id: str
    status: str
    competitors: list[CompetitorInput]
    dimensions: list[str]
    node_states: dict
    dag_json: dict = {}
    created_at: str
    updated_at: str
    report_html: str = ""
    traces: list = Field(default_factory=list)
    reviews: list = Field(default_factory=list)


@router.post("/", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    task_id = str(uuid.uuid4())
    competitors = [c.model_dump() for c in req.competitors]

    # Load built-in DEFAULT_SCHEMA
    schema = load_default_schema()
    dimensions = []
    for group in schema.groups:
        for dim in group.dimensions:
            dimensions.append(dim.name)

    # Build simple DAG: Collector → Analyst → Writer per (competitor, dimension)
    nodes = []
    edges = []
    prev_end = None
    for comp in competitors:
        for dim in dimensions:
            c_id = f"c_{comp['name']}_{dim}"
            a_id = f"a_{comp['name']}_{dim}"
            w_id = f"w_{comp['name']}_{dim}"
            nodes.append({"id": c_id, "agent": "Collector", "action": "collect", "params": {"target": comp["name"], "domain": comp["domain"], "dimension": dim}})
            nodes.append({"id": a_id, "agent": "Analyst", "action": "analyze", "params": {"competitor": comp["name"], "dimension": dim}})
            nodes.append({"id": w_id, "agent": "Writer", "action": "write", "params": {"competitor": comp["name"], "dimension": dim}})
            edges.append({"from": c_id, "to": a_id})
            edges.append({"from": a_id, "to": w_id})
            if prev_end:
                edges.append({"from": prev_end, "to": c_id})
            prev_end = w_id

    dag_blueprint = DAGBlueprint(nodes=nodes, edges=edges)
    task = state_manager.create_task(task_id, competitors, dimensions, dag_blueprint.model_dump())
    assert state_manager.get_task(task_id) is not None, "Task was not stored in state_manager"

    async def run_dag():
        try:
            # TODO: Task 4 implements execute_mvp
            raise NotImplementedError("TODO: Task 4 implements execute_mvp")
        except Exception:
            state_manager.update_task_status(task_id, TaskStatus.FAILED)

    asyncio.create_task(run_dag())
    return TaskResponse(**task.model_dump())


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    task = state_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**task.model_dump())


@router.get("/", response_model=list[TaskResponse])
async def list_tasks():
    tasks = state_manager.list_tasks()
    return [TaskResponse(**t.model_dump()) for t in tasks]