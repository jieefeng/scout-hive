import json

from app.agents.base import AgentBase, AgentResult
from app.llm.base import Message


class Writer(AgentBase):
    SYSTEM_PROMPT_TABLE = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

[强制格式: table]

要求：
1. 报告必须是完整的 HTML 片段（不需要 <html> 和 <head>）
2. 每条结论附带溯源浮窗（data-finding-id 属性）
3. 置信度用进度条展示
4. 对比矩阵用表格展示
5. **必须输出 Markdown 表格**：第一列是维度名，其余列是竞品
6. 所有竞品必须使用完全相同的行维度，没有数据的单元格填"无"
7. 禁止行列错位
8. 每条结论附带 (来源: URL) 引用
9. 禁止输出任何段落叙述格式，只允许表格

输出 JSON 格式：
{"report_html": "<div class='report'>...</div>", "summary": "报告摘要"}"""

    SYSTEM_PROMPT_PARAGRAPH = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

[强制格式: paragraph]

要求：
1. 报告必须是完整的 HTML 片段（不需要 <html> 和 <head>）
2. 每条结论附带溯源浮窗（data-finding-id 属性）
3. 置信度用进度条展示
4. 输出段落叙述，结构为 [竞品名]：[分析结论]
5. 每条结论后附 (来源: URL)
6. 只允许段落叙述，禁止任何表格格式

输出 JSON 格式：
{"report_html": "<div class='report'>...</div>", "summary": "报告摘要"}"""

    async def execute(self, input_data: dict) -> AgentResult:
        output_type = input_data.get("output_type", "paragraph")
        if output_type == "table":
            system_prompt = self.SYSTEM_PROMPT_TABLE
        else:
            system_prompt = self.SYSTEM_PROMPT_PARAGRAPH

        messages = [
            Message(role="system", content=system_prompt),
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
        reasoning_chain = [
            {"step": 1, "thought": "分析采集数据中的关键发现"},
            {"step": 2, "thought": "组织报告结构并生成 HTML"},
        ]
        return AgentResult(
            success=True, output=parsed, llm_response=llm_response,
            reasoning_chain=reasoning_chain, confidence={"score": 0.8, "level": "high"},
        )
