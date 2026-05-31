import asyncio
import openai
import logging
from app.llm.base import LLMError
from app.llm.openai_adapter import OpenAIAdapter

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1  # seconds


class BailianAdapter(OpenAIAdapter):
    def __init__(self, api_key: str, model: str = "qwen3.6-plus-2026-04-02"):
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model

    async def chat(self, messages, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return await super().chat(messages, **kwargs)
            except openai.AuthenticationError:
                raise LLMError("bailian_auth", "DASHSCOPE_API_KEY 无效或未设置")
            except openai.RateLimitError:
                raise LLMError("bailian_rate_limit", "百练平台限流，请稍后重试")
            except openai.APIStatusError as e:
                raise LLMError("bailian_api", f"百练 API 错误: {e.status_code}")
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                last_exc = e
                delay = _BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"BailianAdapter connection error (attempt {attempt + 1}/{_MAX_RETRIES}): "
                    f"{type(e).__name__}: {e} — retrying in {delay}s"
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"BailianAdapter unexpected error: {type(e).__name__}: {e}")
                raise
        logger.error(f"BailianAdapter exhausted {_MAX_RETRIES} retries")
        raise last_exc  # type: ignore[misc]

    async def stream_chat(self, messages, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                async for chunk in super().stream_chat(messages, **kwargs):
                    yield chunk
                return
            except openai.AuthenticationError:
                raise LLMError("bailian_auth", "DASHSCOPE_API_KEY 无效或未设置")
            except openai.RateLimitError:
                raise LLMError("bailian_rate_limit", "百练平台限流，请稍后重试")
            except openai.APIStatusError as e:
                raise LLMError("bailian_api", f"百练 API 错误: {e.status_code}")
            except (openai.APIConnectionError, openai.APITimeoutError) as e:
                last_exc = e
                delay = _BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"BailianAdapter stream connection error (attempt {attempt + 1}/{_MAX_RETRIES}): "
                    f"{type(e).__name__}: {e} — retrying in {delay}s"
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"BailianAdapter stream error: {type(e).__name__}: {e}")
                raise
        logger.error(f"BailianAdapter stream exhausted {_MAX_RETRIES} retries")
        raise last_exc  # type: ignore[misc]
