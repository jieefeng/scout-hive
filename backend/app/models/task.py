from pydantic import BaseModel, Field
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Competitor(BaseModel):
    """竞品结构：name + domain（必填）"""
    name: str           # "飞书"
    domain: str         # "feishu.cn"


class Task(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    competitors: list[Competitor] = Field(default_factory=list)  # 升级：Competitor 列表
    dimensions: list[str] = Field(default_factory=list)
    dag_json: dict = Field(default_factory=dict)
    node_states: dict[str, NodeStatus] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    report_html: str = ""
    traces: list[dict] = Field(default_factory=list)
    reviews: list[dict] = Field(default_factory=list)
