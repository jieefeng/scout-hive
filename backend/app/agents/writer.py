import json

from app.agents.base import AgentBase, AgentResult
from app.llm.base import Message


class Writer(AgentBase):
    SYSTEM_PROMPT = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

要求：
1. 报告必须是完整的 HTML 片段（不需要 <html> 和 <head>）
2. 每条结论附带溯源浮窗（data-finding-id 属性）
3. 置信度用进度条展示
4. 对比矩阵用表格展示

输出 JSON 格式：
{"report_html": "<div class='report'>...</div>", "summary": "报告摘要"}"""

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
        return AgentResult(success=True, output=parsed, llm_response=llm_response)
