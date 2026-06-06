import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agents.writer import Writer
from app.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    adapter = MagicMock()
    adapter.chat = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_writer_returns_html_report(mock_llm):
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div class=\\"report\\"><h1>竞品分析报告</h1></div>", "summary": "摘要"}',
        model="test",
    )

    result = await writer.run({"findings": [], "comparison_matrix": {}})

    assert result.success is True
    assert "report_html" in result.output
    assert "<div" in result.output["report_html"]


@pytest.mark.asyncio
async def test_writer_invalid_json(mock_llm):
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(content="{ not json", model="test")

    result = await writer.run({"findings": []})

    assert result.success is False
    assert result.error_type == "json_parse"


@pytest.mark.asyncio
async def test_writer_passes_findings_to_llm(mock_llm):
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div>报告</div>", "summary": "s"}',
        model="test",
    )

    findings = [{"finding_id": "f001", "claim": "Test claim", "quote": "quote"}]
    await writer.run({"findings": findings})

    call_args = mock_llm.chat.call_args
    assert call_args is not None


@pytest.mark.asyncio
async def test_writer_with_output_type_table(mock_llm):
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<table><tr><td>维度</td><td>竞品A</td></tr><tr><td>价格</td><td>低</td></tr></table>", "summary": "表格报告"}',
        model="test",
    )

    result = await writer.run({"output_type": "table", "findings": []})

    assert result.success is True
    assert "table" in result.output["report_html"] or "<table>" in result.output["report_html"]


@pytest.mark.asyncio
async def test_writer_with_output_type_paragraph(mock_llm):
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div class=\\"report\\"><p>竞品A：分析结论</p></div>", "summary": "段落报告"}',
        model="test",
    )

    result = await writer.run({"output_type": "paragraph", "findings": []})

    assert result.success is True


@pytest.mark.asyncio
async def test_writer_has_empty_reasoning_chain(mock_llm):
    """Writer 是格式化节点，不应有推理链。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div>报告</div>", "summary": "摘要"}',
        model="test",
    )

    result = await writer.run({"findings": [], "sources": []})

    assert result.success is True
    assert result.reasoning_chain == []