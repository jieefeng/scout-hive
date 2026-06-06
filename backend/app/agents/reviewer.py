import json
import uuid

from app.agents.base import AgentBase, AgentResult
from app.llm.base import Message
from app.models.review import ReviewCheck, ReviewIssue, ReviewResult


class Reviewer(AgentBase):
    enforce_rc = True

    SYSTEM_PROMPT = """你是一个质检审查员。你的职责是检查报告的格式和溯源完整性，不审查逻辑正确性。

检查维度：
1. JSON 格式：报告 HTML 是否完整
2. 溯源完整性：每条结论是否有 source_ref 和 quote

规则：
- 无来源 → 直接退回

关键规则（新增）：
- 你必须输出 `reasoning_chain: [{step, thought, source_ref?}]` 至少 1 条
- 这是答辩展示用，缺漏会重试

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
        reasoning_chain = [
            {"step": i + 1, "thought": f"检查 {c.get('dimension', '未知')} — {c.get('status', '未知')}"}
            for i, c in enumerate(parsed.get("checks", []))
        ]
        return await self._enforce_reasoning_chain(input_data, AgentResult(
            success=True, output=review.model_dump(), llm_response=llm_response,
            reasoning_chain=reasoning_chain,
        ))
