import time
from typing import AsyncIterator
from app.llm.base import LLMAdapter, Message, LLMResponse


class ClaudeAdapter(LLMAdapter):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6-20250514"):
        import anthropic
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        start = time.monotonic()
        response = await self.client.messages.create(
            model=self.model, max_tokens=kwargs.get("max_tokens", 4096),
            system=system_msg or "", messages=chat_messages,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            content=response.content[0].text, model=self.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            latency_ms=elapsed,
        )

    async def stream_chat(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})
        async with self.client.messages.stream(
            model=self.model, max_tokens=kwargs.get("max_tokens", 4096),
            system=system_msg or "", messages=chat_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
