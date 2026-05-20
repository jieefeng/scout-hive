import pytest
from unittest.mock import AsyncMock, patch
import openai
from app.llm.bailian_adapter import BailianAdapter
from app.llm.openai_adapter import OpenAIAdapter
from app.llm.base import LLMError
from app.llm.base import Message


def test_inheritance():
    assert issubclass(BailianAdapter, OpenAIAdapter)


def test_default_model():
    adapter = BailianAdapter(api_key="dummy_key")
    assert adapter.model == "qwen-plus"


def test_custom_model():
    adapter = BailianAdapter(api_key="dummy_key", model="qwen-max")
    assert adapter.model == "qwen-max"


def test_base_url():
    adapter = BailianAdapter(api_key="dummy_key")
    assert str(adapter.client.base_url) == "https://dashscope.aliyuncs.com/compatible-mode/v1/"


def test_base_url_not_openai():
    adapter = BailianAdapter(api_key="dummy_key")
    assert "openai.com" not in str(adapter.client.base_url)


@pytest.mark.asyncio
async def test_chat_auth_error():
    adapter = BailianAdapter(api_key="dummy_key")
    with patch.object(
        OpenAIAdapter, "chat", new_callable=AsyncMock,
        side_effect=openai.AuthenticationError(
            message="invalid api_key",
            response=AsyncMock(status_code=401),
            body=None,
        ),
    ):
        with pytest.raises(LLMError) as exc_info:
            await adapter.chat([Message(role="user", content="test")])
        assert exc_info.value.code == "bailian_auth"


@pytest.mark.asyncio
async def test_chat_rate_limit_error():
    adapter = BailianAdapter(api_key="dummy_key")
    with patch.object(
        OpenAIAdapter, "chat", new_callable=AsyncMock,
        side_effect=openai.RateLimitError(
            message="rate limited",
            response=AsyncMock(status_code=429),
            body=None,
        ),
    ):
        with pytest.raises(LLMError) as exc_info:
            await adapter.chat([Message(role="user", content="test")])
        assert exc_info.value.code == "bailian_rate_limit"


@pytest.mark.asyncio
async def test_stream_chat_auth_error():
    adapter = BailianAdapter(api_key="dummy_key")

    async def _broken_stream(*args, **kwargs):
        raise openai.AuthenticationError(
            message="invalid api_key",
            response=AsyncMock(status_code=401),
            body=None,
        )
        yield  # make it an async generator

    with patch.object(OpenAIAdapter, "stream_chat", side_effect=_broken_stream):
        with pytest.raises(LLMError) as exc_info:
            async for _ in adapter.stream_chat([Message(role="user", content="test")]):
                pass
        assert exc_info.value.code == "bailian_auth"


@pytest.mark.asyncio
async def test_stream_chat_rate_limit_error():
    adapter = BailianAdapter(api_key="dummy_key")

    async def _broken_stream(*args, **kwargs):
        raise openai.RateLimitError(
            message="rate limited",
            response=AsyncMock(status_code=429),
            body=None,
        )
        yield

    with patch.object(OpenAIAdapter, "stream_chat", side_effect=_broken_stream):
        with pytest.raises(LLMError) as exc_info:
            async for _ in adapter.stream_chat([Message(role="user", content="test")]):
                pass
        assert exc_info.value.code == "bailian_rate_limit"
