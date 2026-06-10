from pydantic import BaseModel, Field


class TraceSource(BaseModel):
    source_id: str
    type: str  # web | api | document
    url: str = ""
    title: str = ""       # 网页标题
    snippet: str = ""
    fetched_at: str | None = None


class LLMMetadata(BaseModel):
    model: str = ""
    tokens_used: int = 0
    latency_ms: int = 0


class TraceRecord(BaseModel):
    trace_id: str
    node_id: str
    agent: str
    timestamp: str | None = None
    input_refs: dict = Field(default_factory=dict)
    output: dict | list = Field(default_factory=dict)
    reasoning_chain: list[dict] = Field(default_factory=list)
    sources: list[TraceSource] = Field(default_factory=list)
    llm_metadata: LLMMetadata = Field(default_factory=LLMMetadata)
    revision_round: int = 0  # 反馈迭代轮次，0=初始，1+=反馈循环
    error_message: str = ""  # 节点级错误信息（失败时填充）
