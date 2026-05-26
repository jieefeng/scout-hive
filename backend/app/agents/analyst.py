import json
import uuid

from app.agents.base import AgentBase, AgentResult
from app.llm.base import Message
from app.models.analysis import (
    AnalysisResult,
    ComparisonMatrix,
    CompetitorStatus,
    Confidence,
    Finding,
    ReasoningStep,
)


class Analyst(AgentBase):
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
      "reasoning_chain": [{"step": 1, "thought": "推理过程", "source_ref": "来源ID"}],
      "confidence": {"score": 0.9, "level": "high", "uncertainty_factors": []}
    }
  ],
  "comparison_matrix": {
    "dimensions": ["维度1"],
    "competitors": {"竞品A": {"维度1": {"status": "✓", "detail": "描述"}}}
  }
}

min_sources 降级规则（分析时使用）：
- sources >= min_sources：正常输出，confidence.level = "high"
- 1 <= sources < min_sources：降级输出，confidence.level = "low"，在 claim 前加 ⚠️，在 uncertainty_factors 中记录"仅找到 N 条来源，未达最低要求 (min_sources)"
- sources == 0：标记为 data_insufficient，claim 前加 "⚠️ 数据不足："，confidence.score = 0.0, level = "low"

注意：降级标记（⚠️）直接加在 claim 文本前面，不另外输出单独字段。"""

    async def execute(self, input_data: dict) -> AgentResult:
        evidence_threshold = input_data.get("evidence_threshold", 1)
        raw_data = input_data.get("raw_data", {})
        sources = input_data.get("sources", [])

        # 代码层计算 source 数量
        source_count = self._count_sources(raw_data, sources)

        # 代码层确定 confidence 级别
        if source_count >= evidence_threshold:
            confidence_level = "high"
        elif source_count > 0:
            confidence_level = "low"
        else:
            confidence_level = "insufficient"

        # 将降级信息注入 prompt，让 LLM 遵循
        downgrade_hint = ""
        if confidence_level == "low":
            downgrade_hint = (
                f"\n[降级警告] 仅找到 {source_count} 条来源，未达最低要求 ({evidence_threshold})。"
                f"所有结论前必须加 ⚠️ 标记，confidence.level 设为 'low'。"
            )
        elif confidence_level == "insufficient":
            downgrade_hint = (
                "\n[数据不足] 未能找到足够来源，所有结论前加 ⚠️ 数据不足：，"
                "confidence.score 设为 0.0，level 设为 'low'。"
            )

        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=json.dumps({
                **input_data,
                "_downgrade_hint": downgrade_hint,
                "_source_count": source_count,
                "_confidence_level": confidence_level,
            }, ensure_ascii=False, default=str)),
        ]
        llm_response = await self.chat(messages)
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
        sources = []
        best_confidence = {"score": 0, "level": "low"}
        for f in parsed.get("findings", []):
            for step in f.get("reasoning_chain", []):
                reasoning_chain.append(step)
            if f.get("source_ref"):
                sources.append({
                    "source_id": f["source_ref"],
                    "type": "analysis",
                    "url": "",
                    "snippet": f.get("quote", ""),
                })
            conf = f.get("confidence", {})
            if conf.get("score", 0) > best_confidence.get("score", 0):
                best_confidence = conf
        return AgentResult(
            success=True, output=result.model_dump(), llm_response=llm_response,
            reasoning_chain=reasoning_chain, sources=sources, confidence=best_confidence,
        )

    def _count_sources(self, raw_data: dict, sources: list | None = None) -> int:
        """计算独立来源的数量。优先用 orchestrator 传入的 sources，否则从 raw_data 推断。"""
        # 优先：orchestrator 从 Collector 的 AgentResult.sources 传入
        if sources and isinstance(sources, list):
            return len(sources)
        # 兜底：raw_data 中有实际内容（source_url 非空且 content 非空）视为 1 条来源
        if raw_data and isinstance(raw_data, dict):
            source_url = raw_data.get("source_url", "")
            content = raw_data.get("content", "")
            if source_url and content and "未能采集到" not in content:
                return 1
        return 0
