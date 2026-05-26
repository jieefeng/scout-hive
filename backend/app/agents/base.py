import time
import uuid
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from app.llm.base import LLMAdapter, LLMResponse, Message
from app.models.trace import LLMMetadata, TraceRecord


class AgentResult(BaseModel):
    success: bool
    output: dict = Field(default_factory=dict)
    raw_response: str = ""
    json_valid: bool = True
    error_type: str | None = None  # json_parse | token_limit | network | unknown | None
    error_message: str | None = None
    trace: TraceRecord | None = None
    llm_response: LLMResponse | None = None
    reasoning_chain: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    confidence: dict = Field(default_factory=dict)


class AgentBase(ABC):
    def __init__(self, name: str, llm_adapter: LLMAdapter | None = None):
        self.name = name
        self.llm = llm_adapter

    async def run(self, input_data: dict, node_id: str = "") -> AgentResult:
        start = time.monotonic()
        try:
            result = await self.execute(input_data)
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            error_type = self._classify_error(e)
            return AgentResult(
                success=False,
                error_type=error_type,
                error_message=str(e),
                trace=self._build_trace(
                    node_id, input_data, {}, elapsed, error=str(e)
                ),
            )

        elapsed = int((time.monotonic() - start) * 1000)
        result.trace = self._build_trace(
            node_id,
            input_data,
            result.output,
            elapsed,
            llm_response=result.llm_response,
            reasoning_chain=result.reasoning_chain,
            sources=result.sources,
            confidence=result.confidence,
        )
        return result

    @abstractmethod
    async def execute(self, input_data: dict) -> AgentResult: ...

    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        if not self.llm:
            raise RuntimeError(f"Agent {self.name} has no LLM adapter")
        return await self.llm.chat(messages, **kwargs)

    async def stream_chat(self, messages: list[Message], **kwargs):
        if not self.llm:
            raise RuntimeError(f"Agent {self.name} has no LLM adapter")
        async for chunk in self.llm.stream_chat(messages, **kwargs):
            yield chunk

    def _build_trace(
        self,
        node_id: str,
        input_data: dict,
        output: dict,
        elapsed_ms: int,
        llm_response: LLMResponse | None = None,
        error: str | None = None,
        reasoning_chain: list[dict] | None = None,
        sources: list[dict] | None = None,
        confidence: dict | None = None,
    ) -> TraceRecord:
        llm_meta = LLMMetadata()
        if llm_response:
            llm_meta = LLMMetadata(
                model=llm_response.model,
                tokens_used=llm_response.tokens_used,
                latency_ms=llm_response.latency_ms,
            )
        return TraceRecord(
            trace_id=str(uuid.uuid4()),
            node_id=node_id,
            agent=self.name,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            input_refs=input_data,
            output=output,
            reasoning_chain=reasoning_chain or [],
            sources=sources or [],
            confidence=confidence or {},
            llm_metadata=llm_meta,
        )

    @staticmethod
    def _classify_error(e: Exception) -> str:
        error_str = str(e).lower()
        if "json" in error_str or "parse" in error_str or "decode" in error_str:
            return "json_parse"
        elif "token" in error_str or "context" in error_str or "limit" in error_str:
            return "token_limit"
        elif "network" in error_str or "connection" in error_str or "timeout" in error_str:
            return "network"
        return "unknown"
