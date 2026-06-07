"""Writer format_hint 机制测试。

验证：
1. format_hint=table 强制表格输出
2. format_hint=paragraph 强制段落输出
3. format_hint=auto LLM 自决（消息中无强制 suffix）
4. format_hint 优先级 > output_type（两者都设时 format_hint 生效）
5. 不传 format_hint 时 fallback 到 output_type（向后兼容）
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.writer import Writer
from app.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    adapter = MagicMock()
    adapter.chat = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_format_hint_table_forces_table(mock_llm):
    """format_hint=table → LLM 收到的 system prompt 末尾有"强制表格"suffix。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<table><tr><td>对比</td></tr></table>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "format_hint": "table"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "Markdown 表格" in system_content
    assert "本次输出必须是 Markdown 表格" in system_content


@pytest.mark.asyncio
async def test_format_hint_paragraph_forces_paragraph(mock_llm):
    """format_hint=paragraph → system prompt 末尾有"强制段落"suffix。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div><p>段落报告</p></div>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "format_hint": "paragraph"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "段落叙述" in system_content
    assert "本次输出必须是段落叙述" in system_content


@pytest.mark.asyncio
async def test_format_hint_auto_no_suffix(mock_llm):
    """format_hint=auto → system prompt 不带强制 suffix。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div>报告</div>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "format_hint": "auto"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    # auto 模式无强制 suffix
    assert "本次输出必须是" not in system_content


@pytest.mark.asyncio
async def test_format_hint_takes_precedence_over_output_type(mock_llm):
    """format_hint 与 output_type 都设时，format_hint 生效。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<table>...</table>", "summary": "s"}',
        model="test",
    )
    # format_hint=table + output_type=paragraph（互相冲突），format_hint 应赢
    await writer.run({"findings": [], "format_hint": "table", "output_type": "paragraph"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "本次输出必须是 Markdown 表格" in system_content
    assert "本次输出必须是段落叙述" not in system_content


@pytest.mark.asyncio
async def test_output_type_backward_compatible_table(mock_llm):
    """只设 output_type=table（无 format_hint）→ 行为与改造前一致（仍走表格 suffix）。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<table><tr><td>维度</td></tr></table>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "output_type": "table"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "本次输出必须是 Markdown 表格" in system_content


@pytest.mark.asyncio
async def test_output_type_backward_compatible_paragraph(mock_llm):
    """只设 output_type=paragraph（无 format_hint）→ 段落 suffix。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div><p>段落</p></div>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "output_type": "paragraph"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "本次输出必须是段落叙述" in system_content


@pytest.mark.asyncio
async def test_default_format_hint_auto(mock_llm):
    """完全不传 format_hint 和 output_type → 默认 auto（无 suffix）。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div>报告</div>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": []})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "本次输出必须是" not in system_content
