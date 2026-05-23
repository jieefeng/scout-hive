import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agents.reviewer import Reviewer
from app.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    adapter = MagicMock()
    adapter.chat = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_reviewer_returns_approved_verdict(mock_llm):
    reviewer = Reviewer("Reviewer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"verdict": "approved", "checks": [{"dimension": "溯源完整性", "status": "pass", "issues": []}], "feedback_to": "", "feedback_message": ""}',
        model="test",
    )

    result = await reviewer.run({"report_html": "<div>报告</div>", "findings": []})

    assert result.success is True
    assert result.output["verdict"] == "approved"


@pytest.mark.asyncio
async def test_reviewer_returns_rejected_verdict(mock_llm):
    reviewer = Reviewer("Reviewer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"verdict": "rejected", "checks": [{"dimension": "溯源完整性", "status": "fail", "issues": [{"finding_id": "f001", "severity": "critical", "description": "缺少原文引用", "suggestion": "补充引用"}]}], "feedback_to": "Writer", "feedback_message": "请补充原文引用"}',
        model="test",
    )

    result = await reviewer.run({"report_html": "<div>报告</div>"})

    assert result.success is True
    assert result.output["verdict"] == "rejected"
    assert result.output["feedback_to"] == "Writer"


@pytest.mark.asyncio
async def test_reviewer_invalid_json(mock_llm):
    reviewer = Reviewer("Reviewer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(content="not json {{{", model="test")

    result = await reviewer.run({"report_html": "<div>x</div>"})

    assert result.success is False
    assert result.error_type == "json_parse"


@pytest.mark.asyncio
async def test_reviewer_checks_confidence_calibration(mock_llm):
    reviewer = Reviewer("Reviewer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"verdict": "approved", "checks": [{"dimension": "置信度校准", "status": "pass", "issues": []}, {"dimension": "溯源完整性", "status": "pass", "issues": []}], "feedback_to": "", "feedback_message": ""}',
        model="test",
    )

    result = await reviewer.run({"report_html": "<div>报告</div>", "findings": [{"confidence": {"score": 0.9}}]})

    assert result.success is True
    assert len(result.output["checks"]) == 2