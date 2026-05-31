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
8. 禁止输出任何段落叙述格式，只允许表格

[来源引用规则 - 严格遵守]
- 输入数据中的 "sources" 数组包含真实 URL，格式为 [{"source_id": "...", "url": "https://...", "snippet": "..."}]
- 引用来源时必须使用 sources 中的真实 URL，格式为 (来源: <真实URL>)
- **绝对禁止**编造 ref.link、example.com 等虚假 URL
- 如果 sources 中没有可用 URL，则不附带链接，不要编造

[维度名称规则 - 严格遵守]
- 必须使用输入数据中的 "dimension" 字段值作为报告标题/维度列名称
- **绝对禁止**自行发明或改写维度名称

输出 JSON 格式：
{"report_html": "<div class='report'>...</div>", "summary": "报告摘要"}"""

    SYSTEM_PROMPT_PARAGRAPH = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

[强制格式: paragraph]

要求：
1. 报告必须是完整的 HTML 片段（不需要 <html> 和 <head>）
2. 每条结论附带溯源浮窗（data-finding-id 属性）
3. 置信度用进度条展示
4. 输出段落叙述，结构为 [竞品名]：[分析结论]
5. 只允许段落叙述，禁止任何表格格式

[来源引用规则 - 严格遵守]
- 输入数据中的 "sources" 数组包含真实 URL，格式为 [{"source_id": "...", "url": "https://...", "snippet": "..."}]
- 引用来源时必须使用 sources 中的真实 URL，格式为 (来源: <真实URL>)
- **绝对禁止**编造 ref.link、example.com 等虚假 URL
- 如果 sources 中没有可用 URL，则不附带链接，不要编造

[维度名称规则 - 严格遵守]
- 必须使用输入数据中的 "dimension" 字段值作为报告标题
- **绝对禁止**自行发明或改写维度名称

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
            raw = llm_response.content
            # Strip markdown code fences if present (common LLM output pattern)
            raw = raw.strip()
            if raw.startswith("```"):
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
        # Forward Collector's sources for trace display
        collector_sources = input_data.get("sources", [])
        first_source_id = collector_sources[0].get("source_id", "") if collector_sources else ""
        reasoning_chain = [
            {"step": 1, "thought": "分析采集数据中的关键发现", "source_ref": first_source_id},
            {"step": 2, "thought": "组织报告结构并生成 HTML"},
        ]
        return AgentResult(
            success=True, output=parsed, llm_response=llm_response,
            reasoning_chain=reasoning_chain, sources=collector_sources,
            confidence={"score": 0.8, "level": "high"},
        )
