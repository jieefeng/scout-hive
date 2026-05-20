from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import AsyncIterator


class Message(BaseModel):
    role: str  # system | user | assistant
    content: str


class LLMResponse(BaseModel):
    content: str
    model: str = ""
    tokens_used: int = 0
    latency_ms: int = 0


class LLMAdapter(ABC):
    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        ...

    @abstractmethod
    async def stream_chat(self, messages: list[Message], **kwargs) -> AsyncIterator[str]:
        ...
