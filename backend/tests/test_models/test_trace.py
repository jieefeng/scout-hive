import pytest
from app.models.trace import TraceRecord, LLMMetadata, TraceSource


def test_trace_record_creation():
    trace = TraceRecord(
        trace_id="t001", node_id="analyze_001", agent="Analyst",
        input_refs={"target": "飞书", "dimension": "功能对比", "keywords": ["协作", "AI"]},
        output={"claim": "test"},
        reasoning_chain=[{"step": 1, "thought": "分析数据", "source_ref": "src_001"}],
        sources=[TraceSource(source_id="src_001", type="web", url="https://example.com", snippet="测试片段")],
        confidence={"score": 0.85, "level": "high"},
        llm_metadata=LLMMetadata(model="claude-sonnet-4-6-20250514", tokens_used=1523, latency_ms=2340),
    )
    assert trace.agent == "Analyst"
    assert trace.llm_metadata.tokens_used == 1523
