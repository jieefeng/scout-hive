import json
import uuid
import logging

from app.agents.base import AgentBase, AgentResult
from app.constants import ALLOWED_DIMENSIONS
from app.llm.base import Message
from app.models.dag import DAGBlueprint, DAGEdge, DAGNode, TaskDAG, TraceabilityConfig

logger = logging.getLogger(__name__)


_ALLOWED_DIMS_BLOCK = "\n".join(f"  - {d}" for d in sorted(ALLOWED_DIMENSIONS))


class TaskParser(AgentBase):
    SYSTEM_PROMPT = f"""你是一个需求分析专家。用户会告诉你想要分析哪些竞品、哪些维度。
你的任务是：
1. 理解用户的分析需求
2. 确定竞品列表和分析维度
3. 输出一个 DAG 任务蓝图（JSON 格式）

输出格式要求（严格 JSON）：
{{
  "competitors": ["竞品A", "竞品B"],
  "dimensions": ["核心玩法"],
  "dag": {{
    "nodes": [
      {{"id": "collect_001", "agent": "Collector", "action": "web_search", "params": {{"target": "竞品A", "dimension": "核心玩法"}}, "depends_on": []}},
      {{"id": "analyze_001", "agent": "Analyst", "action": "feature_analysis", "params": {{}}, "depends_on": ["collect_001"]}},
      {{"id": "write_001", "agent": "Writer", "action": "generate_report", "params": {{}}, "depends_on": ["analyze_001"]}},
      {{"id": "review_001", "agent": "Reviewer", "action": "quality_check", "params": {{}}, "depends_on": ["write_001"]}}
    ],
    "edges": [
      {{"from": "collect_001", "to": "analyze_001"}},
      {{"from": "analyze_001", "to": "write_001"}},
      {{"from": "write_001", "to": "review_001"}}
    ],
    "feedback_edges": [
      {{"from": "review_001", "to": "write_001", "condition": "review_001.status == 'rejected'", "max_rounds": 3, "escalation": "auto_approve"}}
    ]
  }}
}}

注意：
- 每个竞品的每个维度都需要独立的 Collector 节点
- DAG 中不能有环（主 edges）
- 反馈边单独放在 feedback_edges 中

[硬约束 - 2026-06-08 AI 助手垂直收窄]
- 输出的 dimensions 必须严格在以下 AI 助手 7 项白名单内,不接受任何新维度:
{_ALLOWED_DIMS_BLOCK}
- 若用户消息涉及白名单外的语义维度(如"功能对比"、"协同能力"等通用词),
  请映射到最接近的白名单维度,并在 summary 中说明映射关系,不要新建维度。
- 这是硬约束:超出白名单的 dimensions 会被 API 层 422 拒绝。

[format_hint 软建议]
- 如果生成的节点含 `Writer` agent（action: "generate_report"），建议在 `params.format_hint` 字段填：
  - "table"（推荐：包含「对比 / 矩阵 / 定价 / 功能 / 指标」等量化词的 dimension）
  - "paragraph"（推荐：包含「体验 / 口碑 / 感受」等定性词的 dimension）
  - "auto"（拿不准时填这个，让 LLM 自决）
- 不强制：Writer 拿不到 format_hint 时走 auto 路径不报错"""

    async def execute(self, input_data: dict) -> AgentResult:
        user_message = input_data.get("message", "")
        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=user_message),
        ]
        logger.info(f"TaskParser calling LLM with {len(messages)} messages")
        llm_response = await self.chat(messages)
        logger.info(f"TaskParser LLM response: {repr(llm_response.content[:500]) if llm_response.content else 'EMPTY'}")
        content = llm_response.content.strip()
        # Strip markdown code block fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if len(lines) >= 2 else content.lstrip("`")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"TaskParser JSON parse error: {e}, content={repr(llm_response.content[:200])}")
            return AgentResult(
                success=False,
                raw_response=llm_response.content,
                json_valid=False,
                error_type="json_parse",
                error_message=str(e),
                llm_response=llm_response,
            )
        task_id = str(uuid.uuid4())
        dag = TaskDAG(
            task_id=task_id,
            competitors=parsed.get("competitors", []),
            dimensions=parsed.get("dimensions", []),
            dag=DAGBlueprint(**parsed.get("dag", {})),
            summary=parsed.get("summary", ""),
            traceability=TraceabilityConfig(),
        )
        return AgentResult(success=True, output=dag.model_dump(), llm_response=llm_response)

    async def retry_with_prompt_hint(
        self,
        input_data: dict,
        error_hint: str,
    ) -> AgentResult:
        """第二次执行：把上次错误以 user 消息追加，引导 LLM 修正。

        调用方式与 execute 相同，但 messages 多一轮错误提示 hint。
        """
        user_message = input_data.get("message", "")
        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=user_message),
            Message(
                role="user",
                content=f"⚠️ 上一轮输出有误：{error_hint}\n请重新输出严格符合格式的 JSON。",
            ),
        ]
        logger.info(f"TaskParser retrying LLM with {len(messages)} messages")
        llm_response = await self.chat(messages)
        content = llm_response.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if len(lines) >= 2 else content.lstrip("`")
        if not content:
            return AgentResult(
                success=False,
                raw_response=llm_response.content,
                json_valid=False,
                error_type="llm_empty",
                error_message="LLM returned empty content",
                llm_response=llm_response,
            )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"TaskParser retry JSON parse error: {e}")
            return AgentResult(
                success=False,
                raw_response=llm_response.content,
                json_valid=False,
                error_type="json_parse",
                error_message=str(e),
                llm_response=llm_response,
            )
        task_id = str(uuid.uuid4())
        dag = TaskDAG(
            task_id=task_id,
            competitors=parsed.get("competitors", []),
            dimensions=parsed.get("dimensions", []),
            dag=DAGBlueprint(**parsed.get("dag", {})),
            summary=parsed.get("summary", ""),
            traceability=TraceabilityConfig(),
        )
        return AgentResult(success=True, output=dag.model_dump(), llm_response=llm_response)
