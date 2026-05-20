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
4. 置信度根据来源数量和可靠性评估

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
}"""

    async def execute(self, input_data: dict) -> AgentResult:
        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=json.dumps(input_data, ensure_ascii=False, default=str)),
        ]
        llm_response = await self.chat(messages)
        try:
            parsed = json.loads(llm_response.content)
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
        return AgentResult(success=True, output=result.model_dump(), llm_response=llm_response)
