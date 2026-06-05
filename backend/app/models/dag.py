from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DAGNode(BaseModel):
    id: str = Field(min_length=1)
    agent: str
    action: str
    params: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class DAGEdge(BaseModel):
    from_node: str = Field(alias="from", min_length=1)
    to_node: str = Field(alias="to", min_length=1)

    model_config = {"populate_by_name": True}


class FeedbackEdge(BaseModel):
    from_node: str = Field(alias="from", min_length=1)
    to_node: str = Field(alias="to", min_length=1)
    condition: str
    max_rounds: int = 3
    timeout_per_round: str = "5m"
    escalation: Literal["auto_approve", "halt", "fallback"] = "auto_approve"

    model_config = {"populate_by_name": True}


class DAGBlueprint(BaseModel):
    nodes: list[DAGNode]
    edges: list[DAGEdge]
    feedback_edges: list[FeedbackEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "DAGBlueprint":
        node_ids = {n.id for n in self.nodes}
        for node in self.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    raise ValueError(
                        f"Node '{node.id}' depends_on '{dep}', which is not in nodes"
                    )
        for edge in self.edges:
            if edge.from_node not in node_ids:
                raise ValueError(f"Edge from '{edge.from_node}' — node not found")
            if edge.to_node not in node_ids:
                raise ValueError(f"Edge to '{edge.to_node}' — node not found")
        for fe in self.feedback_edges:
            if fe.from_node not in node_ids:
                raise ValueError(f"FeedbackEdge from '{fe.from_node}' — node not found")
            if fe.to_node not in node_ids:
                raise ValueError(f"FeedbackEdge to '{fe.to_node}' — node not found")
        return self


class TraceabilityConfig(BaseModel):
    level: Literal["full", "summary", "none"] = "full"
    include_reasoning: bool = True


class TaskDAG(BaseModel):
    task_id: str
    competitors: list[str]
    dimensions: list[str]
    dag: DAGBlueprint
    traceability: TraceabilityConfig = Field(default_factory=TraceabilityConfig)
