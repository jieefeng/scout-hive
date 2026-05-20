from pydantic import BaseModel, Field


class DAGNode(BaseModel):
    id: str
    agent: str
    action: str
    params: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class DAGEdge(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")

    model_config = {"populate_by_name": True}


class FeedbackEdge(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    condition: str
    max_rounds: int = 3
    timeout_per_round: str = "5m"
    escalation: str = "auto_approve"  # auto_approve | halt | fallback

    model_config = {"populate_by_name": True}


class DAGBlueprint(BaseModel):
    nodes: list[DAGNode]
    edges: list[DAGEdge]
    feedback_edges: list[FeedbackEdge] = Field(default_factory=list)


class TraceabilityConfig(BaseModel):
    level: str = "full"
    include_reasoning: bool = True
    include_confidence: bool = True


class TaskDAG(BaseModel):
    task_id: str
    competitors: list[str]
    dimensions: list[str]
    dag: DAGBlueprint
    traceability: TraceabilityConfig = Field(default_factory=TraceabilityConfig)
