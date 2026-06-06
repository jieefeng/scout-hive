import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.agents.analyst import Analyst
from app.llm.base import LLMResponse


def test_analyst_enforce_rc_true():
    """Analyst 类属性 enforce_rc 必须为 True。"""
    assert Analyst.enforce_rc is True


def test_analyst_prompt_mentions_reasoning_chain():
    """Analyst.SYSTEM_PROMPT 必须显式提到 reasoning_chain 必填。"""
    assert "reasoning_chain" in Analyst.SYSTEM_PROMPT
    assert "必填" in Analyst.SYSTEM_PROMPT or "必须" in Analyst.SYSTEM_PROMPT


def test_analyst_execute_retries_when_rc_empty():
    """execute 末尾：若 RC 空，应触发 _enforce_reasoning_chain 重试。"""

    async def main():
        analyst = Analyst("Analyst")
        analyst.llm = MagicMock()
        # 第一次返 RC 空的合法 JSON，第二次返带 RC 的合法 JSON
        analyst.llm.chat = AsyncMock(side_effect=[
            LLMResponse(
                content='{"competitor": "x", "dimension": "y", "findings": [], "comparison_matrix": {}}',
                model="qwen", tokens_used=100, latency_ms=500,
            ),
            LLMResponse(
                content='{"competitor": "x", "dimension": "y", "findings": [], "comparison_matrix": {}, "reasoning_chain": [{"step": 1, "thought": "..."}]}',
                model="qwen", tokens_used=120, latency_ms=500,
            ),
        ])
        result = await analyst.execute({"competitor": "x", "dimension": "y", "raw_data": {}})
        # 触发 2 次 chat（execute 内的 1 次 + 重试 1 次）
        assert analyst.llm.chat.await_count == 2
        # 第二次补了 RC
        assert len(result.reasoning_chain) == 1

    asyncio.run(main())
