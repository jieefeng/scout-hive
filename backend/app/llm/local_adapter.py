import time
from typing import AsyncIterator
import httpx
from app.llm.base import LLMAdapter, Message, LLMResponse


class LocalAdapter(LLMAdapter):
    def __init__(self, endpoint: str = "http://localhost:11434", model: str = "llama3"):
        self.endpoint = endpoint.rstrip("/")
        self.model = model

    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        chat_messages = [{"role": m.role, "content": m.content} for m in messages]
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self.endpoint}/api/chat",
                json={"model": self.model, "messages": chat_messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
        elapsed = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            content=data["message"]["content"], model=self.model,
            tokens_used=data.get("eval_count", 0), latency_ms=elapsed,
        )

    async def stream_chat(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        chat_messages = [{"role": m.role, "content": m.content} for m in messages]
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST", f"{self.endpoint}/api/chat",
                json={"model": self.model, "messages": chat_messages, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
