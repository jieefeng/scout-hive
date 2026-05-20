import os
import pytest
from app.llm.base import Message, LLMError
from app.llm.bailian_adapter import BailianAdapter
from app.config import LLMConfig, LLMAdapterConfig
from app.llm.registry import LLMRegistry

pytestmark = pytest.mark.skipif(
    not os.environ.get("DASHSCOPE_API_KEY"),
    reason="DASHSCOPE_API_KEY not set",
)


@pytest.fixture
def adapter():
    return BailianAdapter(api_key=os.environ["DASHSCOPE_API_KEY"])


@pytest.mark.asyncio
async def test_basic_chat(adapter):
    messages = [Message(role="user", content="你好，请用一句话介绍自己")]
    response = await adapter.chat(messages)
    assert response.content
    assert len(response.content) > 0
    assert response.model == "qwen-plus"


@pytest.mark.asyncio
async def test_stream_chat(adapter):
    messages = [Message(role="user", content="用三句话描述春天")]
    chunks = []
    async for chunk in adapter.stream_chat(messages):
        chunks.append(chunk)
    assert len(chunks) > 0
    full_text = "".join(chunks)
    assert len(full_text) > 0


@pytest.mark.asyncio
async def test_long_text_generation(adapter):
    messages = [Message(role="user", content="写一篇500字的短文，主题是人工智能的未来")]
    response = await adapter.chat(messages, max_tokens=2048)
    assert len(response.content) > 200


@pytest.mark.asyncio
async def test_system_message(adapter):
    messages = [
        Message(role="system", content="你是一个专业的翻译助手"),
        Message(role="user", content="将以下句子翻译成英文：今天天气很好"),
    ]
    response = await adapter.chat(messages)
    assert response.content


@pytest.mark.asyncio
async def test_registry_integration():
    config = LLMConfig(
        default="bailian",
        adapters={
            "bailian": LLMAdapterConfig(
                type="bailian",
                model="qwen-plus",
                api_key=os.environ["DASHSCOPE_API_KEY"],
            )
        },
        agent_bindings={"Collector": "bailian"},
    )
    registry = LLMRegistry(config)
    adapter = registry.get_for_agent("Collector")
    messages = [Message(role="user", content="你好")]
    response = await adapter.chat(messages)
    assert response.content


@pytest.mark.asyncio
async def test_multiple_models():
    api_key = os.environ["DASHSCOPE_API_KEY"]
    for model in ["qwen-turbo", "qwen-plus"]:
        adapter = BailianAdapter(api_key=api_key, model=model)
        messages = [Message(role="user", content="Hi")]
        response = await adapter.chat(messages, max_tokens=16)
        assert response.content, f"Failed for model: {model}"


@pytest.mark.asyncio
async def test_invalid_api_key():
    adapter = BailianAdapter(api_key="invalid-key")
    messages = [Message(role="user", content="你好")]
    with pytest.raises(LLMError) as exc_info:
        await adapter.chat(messages)
    assert exc_info.value.code == "bailian_auth"
