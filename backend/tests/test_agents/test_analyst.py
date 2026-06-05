import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agents.analyst import Analyst
from app.agents.base import AgentResult
from app.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    adapter = MagicMock()
    adapter.chat = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_analyst_returns_findings_with_quotes(mock_llm):
    analyst = Analyst("Analyst", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitor": "douyin", "dimension": "recommendation", "findings": [{"finding_id": "f001", "claim": "uses deep learning", "quote": "deep learning recommendation engine", "quote_type": "exact", "source_ref": "src001", "chunk_ref": "c001", "reasoning_chain": [{"step": 1, "thought": "official website"}]}], "comparison_matrix": {"dimensions": ["recommendation"], "competitors": {"douyin": {"recommendation": {"status": "Y", "detail": "deep learning"}}}}}',
        model="test",
    )

    raw = {"content": "some content about douyin...", "chunks": []}
    result = await analyst.run(raw)

    assert result.success is True
    output = result.output
    assert "findings" in output


@pytest.mark.asyncio
async def test_analyst_filters_findings_without_quote(mock_llm):
    """Findings without quote are discarded."""
    analyst = Analyst("Analyst", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitor": "ks", "dimension": "monetization", "findings": [{"finding_id": "f001", "claim": "ks revenue grew", "quote": "", "quote_type": "exact", "source_ref": "", "reasoning_chain": []}], "comparison_matrix": {"dimensions": [], "competitors": {}}}',
        model="test",
    )

    result = await analyst.run({"content": "some content"})

    assert result.success is True
    assert len(result.output["findings"]) == 0


@pytest.mark.asyncio
async def test_analyst_invalid_json(mock_llm):
    analyst = Analyst("Analyst", mock_llm)
    mock_llm.chat.return_value = LLMResponse(content="{ not valid json", model="test")

    result = await analyst.run({"content": "x"})

    assert result.success is False
    assert result.error_type == "json_parse"


@pytest.mark.asyncio
async def test_analyst_extracts_reasoning_chain(mock_llm):
    analyst = Analyst("Analyst", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitor": "bilibili", "dimension": "user_growth", "findings": [{"finding_id": "f001", "claim": "MAU over 200M", "quote": "200 million monthly active users", "quote_type": "exact", "source_ref": "src001", "chunk_ref": "c001", "reasoning_chain": [{"step": 1, "thought": "financial report shows"}]}], "comparison_matrix": {"dimensions": [], "competitors": {}}}',
        model="test",
    )

    result = await analyst.run({"content": "bilibili financial report"})

    assert result.success is True
    assert len(result.reasoning_chain) >= 1


@pytest.mark.asyncio
async def test_analyst_reads_min_sources_from_input(mock_llm):
    """min_sources is read from input_data."""
    analyst = Analyst("Analyst", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitor": "x", "dimension": "y", "findings": [{"finding_id": "f001", "claim": "test", "quote": "test quote", "quote_type": "exact", "source_ref": "s001", "chunk_ref": "c001", "reasoning_chain": []}], "comparison_matrix": {"dimensions": [], "competitors": {}}}',
        model="test",
    )

    result = await analyst.run({"content": "data", "min_sources": 3})
    assert result.success is True


@pytest.mark.asyncio
async def test_analyst_min_sources_default_is_one(mock_llm):
    """min_sources defaults to 1 when not provided."""
    analyst = Analyst("Analyst", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitor": "x", "dimension": "y", "findings": [{"finding_id": "f001", "claim": "test", "quote": "test quote", "quote_type": "exact", "source_ref": "s001", "chunk_ref": "c001", "reasoning_chain": []}], "comparison_matrix": {"dimensions": [], "competitors": {}}}',
        model="test",
    )

    result = await analyst.run({"content": "data"})
    assert result.success is True


@pytest.mark.asyncio
async def test_analyst_prompt_contains_min_sources_rules(mock_llm):
    """SYSTEM_PROMPT contains min_sources degradation rules."""
    analyst = Analyst("Analyst", mock_llm)
    assert "min_sources" in analyst.SYSTEM_PROMPT
    assert "sources >= min_sources" in analyst.SYSTEM_PROMPT
    assert "⚠️" in analyst.SYSTEM_PROMPT
    assert "data_insufficient" in analyst.SYSTEM_PROMPT
    assert "confidence" not in analyst.SYSTEM_PROMPT  # 置信度已彻底删除


@pytest.mark.asyncio
async def test_analyst_downgrade_hint_without_confidence(mock_llm):
    """Analyst 的 downgrade_hint 含 ⚠️ 提示但不再提 confidence.level。"""
    analyst = Analyst("Analyst", mock_llm)
    captured = {}

    async def capture(messages, **kwargs):
        captured["user"] = messages[-1].content
        return LLMResponse(
            content='{"competitor": "x", "dimension": "y", "findings": [], "comparison_matrix": {}}',
            model="test",
        )

    mock_llm.chat.side_effect = capture

    # source_count=0 触发 insufficient 分支
    await analyst.run({"content": "data", "sources": []})

    assert "⚠️" in captured["user"]
    assert "confidence.level" not in captured["user"]
    assert "confidence.score" not in captured["user"]