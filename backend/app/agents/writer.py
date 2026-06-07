import json

from app.agents.base import AgentBase, AgentResult
from app.llm.base import Message


class Writer(AgentBase):
    enforce_rc = True

    GENERIC_PROMPT = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

[格式选择规则 - LLM 自决]
- 看到 dimension 名包含「对比 / 矩阵 / 定价 / 功能 / 指标 / Agent 能力 / 商业模式 / 内容生态」等量化词 → 优先用 Markdown 表格
- 看到 dimension 名包含「体验 / 口碑 / 感受 / 故事 / 叙事 / 核心玩法 / 用户社区 / 安全合规」等定性词 → 优先用段落叙述
- 拿不准时优先表格（竞品分析 80% 场景需要横向对比）

[强制规则 - 表格 / 段落都要遵守]
1. 报告必须是完整 HTML 片段（不需要 <html> 和 <head>）
2. 每条结论附溯源浮窗（data-finding-id 属性）
3. 引用来源用 sources 中的真实 URL
4. 表格模式：第一列是维度名，其余列是竞品；所有竞品必须使用完全相同的行维度，没有数据的单元格填"无"
5. 段落模式：结构为 [竞品名]：[分析结论]
6. 使用 input_data.dimension 字段值作为报告标题，禁止改名

[来源引用规则 - 严格遵守]
- 输入数据中的 "sources" 数组包含真实 URL，格式为 [{"source_id": "...", "url": "https://...", "snippet": "..."}]
- 引用来源时必须使用 sources 中的真实 URL，格式为 (来源: <真实URL>)
- **绝对禁止**编造 ref.link、example.com 等虚假 URL
- 如果 sources 中没有可用 URL，则不附带链接，不要编造

关键规则（新增）：
- 你必须输出 `reasoning_chain: [{step, thought, source_ref?}]` 至少 1 条
- 这是答辩展示用，缺漏会重试

输出 JSON 格式：
{"report_html": "<div class='report'>...</div>", "summary": "报告摘要", "reasoning_chain": [{"step": <int>, "thought": "<解释>", "source_ref": "<source_id>"}]}"""

    FORMAT_HINT_TABLE_SUFFIX = "\n[强制] 本次输出必须是 Markdown 表格，不允许段落。"
    FORMAT_HINT_PARAGRAPH_SUFFIX = "\n[强制] 本次输出必须是段落叙述，不允许表格。"

    async def execute(self, input_data: dict) -> AgentResult:
        # 优先用 format_hint（新机制），fallback 到 output_type（向后兼容）
        format_hint = input_data.get("format_hint")
        if format_hint is None:
            format_hint = input_data.get("output_type", "auto")

        if format_hint == "table":
            system_prompt = self.GENERIC_PROMPT + self.FORMAT_HINT_TABLE_SUFFIX
        elif format_hint == "paragraph":
            system_prompt = self.GENERIC_PROMPT + self.FORMAT_HINT_PARAGRAPH_SUFFIX
        else:  # auto
            system_prompt = self.GENERIC_PROMPT

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
        result = AgentResult(
            success=True, output=parsed, llm_response=llm_response,
            sources=collector_sources,
            reasoning_chain=parsed.get("reasoning_chain", []) if isinstance(parsed, dict) else [],
        )
        result = await self._enforce_reasoning_chain(input_data, result)
        return result
