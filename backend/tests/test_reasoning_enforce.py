import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.agents.base import AgentBase, AgentResult
from app.llm.base import LLMResponse, Message


class DummyAgent(AgentBase):
    """最小 Agent 子类，用于测试 enforce_rc 行为。"""
    enforce_rc = True

    def __init__(self, chain_present: bool = False):
        super().__init__("Dummy")
        # mock LLM
        self.llm = MagicMock()
        self.llm.chat = AsyncMock()
        self._chain_present = chain_present

    async def execute(self, input_data):
        chain = [{"step": 1, "thought": "..."}] if self._chain_present else []
        return await self._enforce_reasoning_chain(
            input_data,
            AgentResult(
                success=True,
                output={"ok": True},
                reasoning_chain=chain,
                llm_response=LLMResponse(content="{}", model="x", tokens_used=10, latency_ms=100),
            ),
        )


class NonEnforceAgent(AgentBase):
    """豁免 Agent，enforce_rc=False。"""
    enforce_rc = False

    def __init__(self):
        super().__init__("NoEnforce")
        self.llm = MagicMock()
        self.llm.chat = AsyncMock()

    async def execute(self, input_data):
        return await self._enforce_reasoning_chain(
            input_data,
            AgentResult(
                success=True,
                output={"ok": True},
                reasoning_chain=[],
                llm_response=LLMResponse(content="{}", model="x", tokens_used=10, latency_ms=100),
            ),
        )


def test_enforce_rc_triggers_retry_when_chain_empty():
    """enforce_rc=True 且 RC 空 → 调一次 chat 重试。"""

    async def main():
        agent = DummyAgent()
        # 重试调用返带 RC 的 JSON
        agent.llm.chat.return_value = LLMResponse(
            content='{"output": {"ok": true}, "reasoning_chain": [{"step": 1, "thought": "..."}]}',
            model="x", tokens_used=20, latency_ms=100,
        )
        result = await agent.execute({"input": "test"})
        # chat 被调 1 次（重试）
        assert agent.llm.chat.await_count == 1
        # 第二次的 RC 被合并
        assert len(result.reasoning_chain) == 1
        assert result.reasoning_chain[0]["step"] == 1

    asyncio.run(main())


def test_enforce_rc_no_retry_when_chain_present():
    """enforce_rc=True 但 RC 非空 → 不重试。"""

    async def main():
        agent = DummyAgent(chain_present=True)
        # 第一次直接返带 RC
        agent.llm.chat.return_value = LLMResponse(
            content='{"output": {"ok": true}, "reasoning_chain": [{"step": 1, "thought": "..."}]}',
            model="x", tokens_used=20, latency_ms=100,
        )
        result = await agent.execute({"input": "test"})
        # 不调（RC 已存在，跳过重试）
        assert agent.llm.chat.await_count == 0
        assert len(result.reasoning_chain) == 1

    asyncio.run(main())


def test_enforce_rc_false_skips_retry():
    """enforce_rc=False → 不重试，RC 保持空。"""

    async def main():
        agent = NonEnforceAgent()
        # 即便有 mock，也不调（enforce_rc=False 直接返回原 result）
        agent.llm.chat.return_value = LLMResponse(
            content='{"output": {"ok": true}, "reasoning_chain": [{"step": 1, "thought": "..."}]}',
            model="x", tokens_used=20, latency_ms=100,
        )
        result = await agent.execute({"input": "test"})
        # 不调（enforce_rc=False 早退）
        assert agent.llm.chat.await_count == 0
        # RC 仍是空（因为 _enforce_reasoning_chain 在 enforce_rc=False 时直接返回原 result）
        assert result.reasoning_chain == []

    asyncio.run(main())
