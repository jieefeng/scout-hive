from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.engine.state_manager import StateManager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

state_manager: StateManager = None


def init_router(sm: StateManager):
    global state_manager
    state_manager = sm


class CreateTaskRequest(BaseModel):
    message: str


class TaskResponse(BaseModel):
    task_id: str
    status: str
    competitors: list[str]
    dimensions: list[str]
    node_states: dict
    created_at: str
    updated_at: str
    report_html: str
    traces: list
    reviews: list


@router.post("/", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    import uuid
    task_id = str(uuid.uuid4())
    task = state_manager.create_task(task_id, [], [], {})
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
