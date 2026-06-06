from pydantic import BaseModel, Field


class TraceMetrics(BaseModel):
    """单次 trace 的指标增量（写入 trace 时同步落库）"""
    trace_id: str                # 关联 TraceRecord.trace_id
    task_id: str                 # 任务级聚合键
    node_id: str                 # DAG 节点 ID
    agent: str                   # Collector / Analyst / Writer / Reviewer
    timestamp: str               # ISO 8601
    elapsed_ms: int              # 节点总耗时（ms），含 LLM + IO
    llm_latency_ms: int = 0      # LLM 调用耗时（ms）
    tokens_in: int = 0           # prompt tokens
    tokens_out: int = 0          # completion tokens
    tokens_total: int = 0        # in + out
    cost_cny: float = 0.0        # 按 llm_pricing 表估算（CNY）
    reasoning_steps: int = 0     # reasoning_chain 长度，0=缺失


class TaskMetricsSnapshot(BaseModel):
    """任务级最终聚合快照"""
    task_id: str
    created_at: str
    total_elapsed_ms: int
    node_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    feedback_rounds: int = 0
    total_tokens: int = 0
    total_cost_cny: float = 0.0
    llm_call_count: int = 0
    slow_nodes: list[dict] = Field(default_factory=list)
    agent_breakdown: dict = Field(default_factory=dict)
    quality: dict = Field(default_factory=dict)
    rc_missing_count: int = 0
