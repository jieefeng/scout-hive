import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.agents.writer import Writer
from app.llm.base import LLMResponse


def test_writer_enforce_rc_true():
    """Writer 类属性 enforce_rc 必须为 True。"""
    assert Writer.enforce_rc is True


def test_writer_table_prompt_mentions_reasoning_chain():
    """Writer.GENERIC_PROMPT 必须显式提到 reasoning_chain 必填（向后兼容旧的 table/paragraph 检查点）。"""
    assert "reasoning_chain" in Writer.GENERIC_PROMPT


def test_writer_paragraph_prompt_mentions_reasoning_chain():
    """Writer.GENERIC_PROMPT 必须显式提到 reasoning_chain 必填（向后兼容旧的 table/paragraph 检查点）。"""
    assert "reasoning_chain" in Writer.GENERIC_PROMPT


def test_writer_execute_retries_when_rc_empty():
    """execute 末尾：若 RC 空，应触发 _enforce_reasoning_chain 重试。"""

    async def main():
        writer = Writer("Writer")
        writer.llm = MagicMock()
        # 第一次返 RC 空的合法 JSON，第二次返带 RC 的合法 JSON
        writer.llm.chat = AsyncMock(side_effect=[
            LLMResponse(
                content='{"report_html": "<div>...</div>"}',
                model="qwen", tokens_used=200, latency_ms=600,
            ),
            LLMResponse(
                content='{"report_html": "<div>...</div>", "reasoning_chain": [{"step": 1, "thought": "..."}]}',
                model="qwen", tokens_used=220, latency_ms=600,
            ),
        ])
        result = await writer.execute({"competitor": "x", "dimension": "y", "analysis": {}})
        # 触发 2 次 chat（execute 内的 1 次 + 重试 1 次）
        assert writer.llm.chat.await_count == 2
        # 第二次补了 RC
        assert len(result.reasoning_chain) == 1

    asyncio.run(main())
