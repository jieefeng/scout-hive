from pydantic import BaseModel, Field


class TraceSource(BaseModel):
    source_id: str
    type: str  # web | api | document
    url: str = ""
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
    input_refs: list[str] = Field(default_factory=list)
    output: dict = Field(default_factory=dict)
    reasoning_chain: list[dict] = Field(default_factory=list)
    sources: list[TraceSource] = Field(default_factory=list)
    confidence: dict = Field(default_factory=dict)
    llm_metadata: LLMMetadata = Field(default_factory=LLMMetadata)
