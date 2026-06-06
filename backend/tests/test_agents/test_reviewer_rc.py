import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.agents.reviewer import Reviewer
from app.llm.base import LLMResponse


def test_reviewer_enforce_rc_true():
    """Reviewer 类属性 enforce_rc 必须为 True。"""
    assert Reviewer.enforce_rc is True


def test_reviewer_prompt_mentions_reasoning_chain():
    """Reviewer.SYSTEM_PROMPT 必须显式提到 reasoning_chain 必填。"""
    assert "reasoning_chain" in Reviewer.SYSTEM_PROMPT


def test_reviewer_execute_retries_when_rc_empty():
    """execute 末尾：若 RC 空，应触发 _enforce_reasoning_chain 重试。"""

    async def main():
        reviewer = Reviewer("Reviewer")
        reviewer.llm = MagicMock()
        # 第一次返 RC 空的合法 JSON，第二次返带 RC 的合法 JSON
        reviewer.llm.chat = AsyncMock(side_effect=[
            LLMResponse(
                content='{"verdict": "approved", "checks": [], "feedback_to": "Writer", "feedback_message": ""}',
                model="qwen", tokens_used=80, latency_ms=400,
            ),
            LLMResponse(
                content='{"verdict": "approved", "checks": [], "feedback_to": "Writer", "feedback_message": "", "reasoning_chain": [{"step": 1, "thought": "..."}]}',
                model="qwen", tokens_used=100, latency_ms=400,
            ),
        ])
        result = await reviewer.execute({"competitor": "x", "dimension": "y", "report": "html", "analysis": {}})
        # 触发 2 次 chat（execute 内的 1 次 + 重试 1 次）
        assert reviewer.llm.chat.await_count == 2
        # 第二次补了 RC
        assert len(result.reasoning_chain) == 1

    asyncio.run(main())
