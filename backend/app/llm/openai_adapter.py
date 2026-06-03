import time
from typing import AsyncIterator
from app.llm.base import LLMAdapter, Message, LLMResponse


class OpenAIAdapter(LLMAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o", timeout: float = 60.0):
        import openai
        self.client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.model = model

    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        chat_messages = [{"role": m.role, "content": m.content} for m in messages]
        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=self.model, messages=chat_messages, max_tokens=kwargs.get("max_tokens", 4096),
        )
        elapsed = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            content=response.choices[0].message.content, model=self.model,
            tokens_used=response.usage.total_tokens, latency_ms=elapsed,
        )

    async def stream_chat(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        chat_messages = [{"role": m.role, "content": m.content} for m in messages]
        stream = await self.client.chat.completions.create(
            model=self.model, messages=chat_messages,
            max_tokens=kwargs.get("max_tokens", 4096), stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
