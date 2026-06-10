import json
import time
import uuid
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from app.llm.base import LLMAdapter, LLMResponse, Message
from app.models.trace import LLMMetadata, TraceRecord


class AgentResult(BaseModel):
    success: bool
    output: dict | list = Field(default_factory=dict)
    raw_response: str = ""
    json_valid: bool = True
    error_type: str | None = None  # json_parse | token_limit | network | unknown | None
    error_message: str | None = None
    trace: TraceRecord | None = None
    llm_response: LLMResponse | None = None
    reasoning_chain: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)


# Reasoning chain 缺失时的重试 hint
RC_MISSING_HINT = (
    "⚠️ 上一轮输出缺少 reasoning_chain。请输出至少 1 条结构化步骤："
    '[{"step": <int>, "thought": "<解释你为什么这么判断>", "source_ref"?: "<来源ID>"}]。'
    "reasoning_chain 字段是答辩展示用，缺漏会被记录。"
)


class AgentBase(ABC):
    # 类属性：子类显式 override 启用
    enforce_rc: bool = False

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
            error=result.error_message if not result.success else None,
            reasoning_chain=result.reasoning_chain,
            sources=result.sources,
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

    async def _enforce_reasoning_chain(
        self, input_data: dict, result: AgentResult
    ) -> AgentResult:
        """若 enforce_rc=True 且 reasoning_chain 为空，调 1 次重试补。

        子类在 execute() 末尾调用本方法（带回原始 messages 列表做 hint 上下文）。
        """
        if not (self.enforce_rc and result.success and not result.reasoning_chain):
            return result

        # 用 input_data 转 JSON 字符串作为 user 消息
        messages = self._build_rc_retry_messages(input_data, result)
        try:
            retry_resp = await self.chat(messages)
        except Exception as e:
            # 重试失败：保留原 result，trace 标 [RC retry failed]
            if result.trace:
                result.trace.error_message = (
                    (result.trace.error_message or "") + " [RC retry failed]"
                )
            return result

        # 尝试从 retry_resp 解析 reasoning_chain
        parsed_chain = self._extract_reasoning_chain(retry_resp)
        if parsed_chain:
            result.reasoning_chain = parsed_chain
            result.llm_response = retry_resp
            return result

        # 第二次仍空：接受但在 trace 上加标记
        if result.trace:
            result.trace.error_message = (
                (result.trace.error_message or "") + " [RC missing]"
            )
        return result

    def _build_rc_retry_messages(
        self, input_data: dict, result: AgentResult
    ) -> list[Message]:
        """构造重试消息。子类可 override 自定义（如 Analyst 用 JSON dump）。"""
        return [
            Message(role="user", content=json.dumps(input_data, ensure_ascii=False, default=str)),
            Message(role="user", content=RC_MISSING_HINT),
        ]

    @staticmethod
    def _extract_reasoning_chain(llm_response: LLMResponse) -> list[dict]:
        """从 LLM 响应中尝试解析 reasoning_chain。"""
        content = (llm_response.content or "").strip()
        # Strip markdown code fences
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if len(lines) >= 2 else content.lstrip("`")
        try:
            data = json.loads(content)
        except Exception:
            return []
        chain = data.get("reasoning_chain") or []
        return chain if isinstance(chain, list) else []

    def _build_trace(
        self,
        node_id: str,
        input_data: dict,
        output: dict | list,
        elapsed_ms: int,
        llm_response: LLMResponse | None = None,
        error: str | None = None,
        reasoning_chain: list[dict] | None = None,
        sources: list[dict] | None = None,
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
            llm_metadata=llm_meta,
            error_message=error or "",
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
