import json
import uuid

from app.agents.base import AgentBase, AgentResult
from app.llm.base import Message
from app.models.review import ReviewCheck, ReviewIssue, ReviewResult


class Reviewer(AgentBase):
    SYSTEM_PROMPT = """你是一个质检审查员。你的职责是检查报告的格式和溯源完整性，不审查逻辑正确性。

检查维度：
1. JSON 格式：报告 HTML 是否完整
2. 溯源完整性：每条结论是否有 source_ref 和 quote
3. 置信度校准：置信度是否与证据强度匹配

规则：
- 2+ 条独立来源 → 可评 high (≥0.8)
- 仅 1 条来源 → 最高 medium (≤0.7)
- paraphrased quote → 置信度权重 ×0.7
- 无来源 → 直接退回

输出 JSON 格式：
{
  "verdict": "approved 或 rejected",
  "checks": [
    {
      "dimension": "溯源完整性",
      "status": "pass 或 fail",
      "issues": [
        {"finding_id": "f001", "severity": "critical", "description": "问题描述", "suggestion": "修改建议"}
      ]
    }
  ],
  "feedback_to": "Writer 或 Analyst",
  "feedback_message": "具体修改建议"
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
        review = ReviewResult(
            review_id=str(uuid.uuid4()),
            verdict=parsed.get("verdict", "rejected"),
            checks=[ReviewCheck(**c) for c in parsed.get("checks", [])],
            feedback_to=parsed.get("feedback_to", ""),
            feedback_message=parsed.get("feedback_message", ""),
        )
        return AgentResult(success=True, output=review.model_dump(), llm_response=llm_response)
