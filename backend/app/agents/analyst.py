import json
import logging
import uuid

from app.agents.base import AgentBase, AgentResult
from app.llm.base import Message
from app.models.analysis import (
    AnalysisResult,
    ComparisonMatrix,
    CompetitorStatus,
    Finding,
)

logger = logging.getLogger(__name__)


class Analyst(AgentBase):
    enforce_rc = True

    SYSTEM_PROMPT = """你是一个竞品分析专家。根据采集到的原始数据，进行结构化分析。

关键规则：
1. 每条结论(claim)必须附带原文引用(quote)和来源(source_ref)
2. 找不到原文引用的结论必须丢弃
3. quote_type 为 "exact"（原文）或 "paraphrased"（意译）

输出 JSON 格式：
{
  "competitor": "竞品名称", "dimension": "分析维度",
  "findings": [
    {
      "finding_id": "f001", "claim": "结论描述", "quote": "原文引用",
      "quote_type": "exact", "source_ref": "来源ID", "chunk_ref": "分段ID",
      "reasoning_chain": [{"step": 1, "thought": "推理过程", "source_ref": "来源ID"}]
    }
  ],
  "comparison_matrix": {
    "dimensions": ["维度1"],
    "competitors": {"竞品A": {"维度1": {"status": "✓", "detail": "描述"}}}
  }
}

min_sources 降级规则（分析时使用）：
- sources >= min_sources：正常输出
- 1 <= sources < min_sources：降级输出，在 claim 前加 ⚠️
- sources == 0：标记为 data_insufficient，claim 前加 "⚠️ 数据不足："

注意：降级标记（⚠️）直接加在 claim 文本前面，不另外输出单独字段。

关键规则（新增）：
- 你必须输出 `reasoning_chain: [{step, thought, source_ref?}]` 至少 1 条
- 这是答辩展示用，缺漏会重试"""

    async def execute(self, input_data: dict) -> AgentResult:
        import time as _time
        start_time = _time.monotonic()

        competitor = input_data.get("competitor", "")
        dimension = input_data.get("dimension", "")
        logger.info(f"[Analyst] Starting: competitor={competitor}, dimension={dimension}")

        evidence_threshold = input_data.get("evidence_threshold", 1)
        raw_data = input_data.get("raw_data", {})
        sources = input_data.get("sources", [])

        # 代码层计算 source 数量
        source_count = self._count_sources(raw_data, sources)

        # 将降级信息注入 prompt，让 LLM 遵循
        downgrade_hint = ""
        if source_count == 0:
            downgrade_hint = (
                "\n[数据不足] 未能找到足够来源，所有结论前加 ⚠️ 数据不足：。"
            )
        elif source_count < evidence_threshold:
            downgrade_hint = (
                f"\n[降级警告] 仅找到 {source_count} 条来源，未达最低要求 ({evidence_threshold})。"
                f"所有结论前必须加 ⚠️ 标记。"
            )

        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=json.dumps({
                **input_data,
                "_downgrade_hint": downgrade_hint,
                "_source_count": source_count,
            }, ensure_ascii=False, default=str)),
        ]
        downgrade_label = "insufficient" if source_count == 0 else ("low" if source_count < evidence_threshold else "none")
        logger.info(f"[Analyst] Calling LLM: source_count={source_count}, downgrade={downgrade_label}")
        llm_response = await self.chat(messages)
        logger.info(f"[Analyst] LLM response received in {int((_time.monotonic() - start_time) * 1000)}ms")
        try:
            raw = llm_response.content
            # Strip markdown code fences if present (common LLM output pattern)
            raw = raw.strip()
            if raw.startswith("```"):
                # Remove first ```json or ``` line
                lines = raw.split("\n")
                if lines and lines[0].strip().startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines)
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            return AgentResult(
                success=False,
                raw_response=llm_response.content,
                json_valid=False,
                error_type="json_parse",
                error_message=str(e),
                llm_response=llm_response,
            )
        valid_findings = []
        for f in parsed.get("findings", []):
            if f.get("quote") and f.get("source_ref"):
                valid_findings.append(Finding(**f))
        result = AnalysisResult(
            analysis_id=str(uuid.uuid4()),
            competitor=parsed.get("competitor", ""),
            dimension=parsed.get("dimension", ""),
            findings=valid_findings,
            comparison_matrix=ComparisonMatrix(**parsed.get("comparison_matrix", {})),
        )
        # Extract trace enrichment data from findings
        reasoning_chain = []
        trace_sources = []
        # Build lookup from Collector's sources (passed via input_data["sources"])
        collector_src_map = {s["source_id"]: s for s in sources if isinstance(s, dict) and s.get("source_id")}
        step_counter = 1  # 全局递增步骤编号
        for f in parsed.get("findings", []):
            for step in f.get("reasoning_chain", []):
                # 重新编号，保证全局递增
                step_copy = {**step, "step": step_counter}
                reasoning_chain.append(step_copy)
                step_counter += 1
            if f.get("source_ref"):
                # Look up real URL from Collector's sources
                matched = collector_src_map.get(f["source_ref"], {})
                trace_sources.append({
                    "source_id": f["source_ref"],
                    "type": matched.get("type", "analysis"),
                    "url": matched.get("url", ""),
                    "snippet": f.get("quote", ""),
                })
        agent_result = AgentResult(
            success=True, output=result.model_dump(), llm_response=llm_response,
            reasoning_chain=reasoning_chain, sources=trace_sources,
        )
        # 强制 reasoning_chain：若为空（enforce_rc=True）则触发重试
        return await self._enforce_reasoning_chain(input_data, agent_result)

    def _count_sources(self, raw_data, sources: list | None = None) -> int:
        """计算独立来源的数量。优先用 orchestrator 传入的 sources，否则从 raw_data 推断。"""
        # 优先：orchestrator 从 Collector 的 AgentResult.sources 传入
        if sources and isinstance(sources, list):
            return len(sources)
        # raw_data 现在是 list[dict]，每个 dict 是一个 RawData
        if isinstance(raw_data, list):
            count = 0
            for item in raw_data:
                if isinstance(item, dict):
                    url = item.get("source_url", "")
                    content = item.get("content", "")
                    if url and content:
                        count += 1
            return count
        # 兼容旧格式（单 dict）
        if isinstance(raw_data, dict):
            source_url = raw_data.get("source_url", "")
            content = raw_data.get("content", "")
            if source_url and content and "未能采集到" not in content:
                return 1
        return 0
