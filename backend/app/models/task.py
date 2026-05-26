from pydantic import BaseModel, Field, AliasChoices
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class Competitor(BaseModel):
    """竞品结构：name + website（必填）"""
    name: str           # "飞书"
    website: str = Field(validation_alias=AliasChoices('website', 'domain'))  # 兼容旧名

    @property
    def domain(self) -> str:
        """向后兼容：domain 作为 website 的别名"""
        return self.website


class Task(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0  # 0.0 - 1.0
    competitors: list[Competitor] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    dag_json: dict = Field(default_factory=dict)
    node_states: dict[str, NodeStatus] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    report_html: str = ""
    traces: list[dict] = Field(default_factory=list)
    reviews: list[dict] = Field(default_factory=list)
    cancelled: bool = False  # 任务是否被用户取消
