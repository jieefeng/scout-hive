import pytest
from app.agents.base import AgentBase, AgentResult


class DummyAgent(AgentBase):
    async def execute(self, input_data: dict) -> AgentResult:
        return AgentResult(
            success=True, output={"result": "ok"},
            error_type=None, error_message=None,
        )


@pytest.mark.asyncio
async def test_agent_execute():
    agent = DummyAgent(name="TestAgent", llm_adapter=None)
    result = await agent.run({"test": "input"})
    assert result.success is True
    assert result.output == {"result": "ok"}


@pytest.mark.asyncio
async def test_agent_run_with_trace():
    agent = DummyAgent(name="TestAgent", llm_adapter=None)
    result = await agent.run({"test": "input"}, node_id="node_001")
    assert result.success is True
    assert result.trace is not None
    assert result.trace.node_id == "node_001"
    assert result.trace.agent == "TestAgent"
