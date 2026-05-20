import json
import uuid

from app.agents.base import AgentBase, AgentResult
from app.llm.base import Message
from app.models.dag import DAGBlueprint, DAGEdge, DAGNode, TaskDAG, TraceabilityConfig


class TaskParser(AgentBase):
    SYSTEM_PROMPT = """你是一个需求分析专家。用户会告诉你想要分析哪些竞品、哪些维度。
你的任务是：
1. 理解用户的分析需求
2. 确定竞品列表和分析维度
3. 输出一个 DAG 任务蓝图（JSON 格式）

输出格式要求（严格 JSON）：
{
  "competitors": ["竞品A", "竞品B"],
  "dimensions": ["功能对比"],
  "dag": {
    "nodes": [
      {"id": "collect_001", "agent": "Collector", "action": "web_search", "params": {"target": "竞品A", "dimension": "功能对比"}, "depends_on": []},
      {"id": "analyze_001", "agent": "Analyst", "action": "feature_analysis", "params": {}, "depends_on": ["collect_001"]},
      {"id": "write_001", "agent": "Writer", "action": "generate_report", "params": {}, "depends_on": ["analyze_001"]},
      {"id": "review_001", "agent": "Reviewer", "action": "quality_check", "params": {}, "depends_on": ["write_001"]}
    ],
    "edges": [
      {"from": "collect_001", "to": "analyze_001"},
      {"from": "analyze_001", "to": "write_001"},
      {"from": "write_001", "to": "review_001"}
    ],
    "feedback_edges": [
      {"from": "review_001", "to": "write_001", "condition": "review_001.status == 'rejected'", "max_rounds": 3, "escalation": "auto_approve"}
    ]
  }
}

注意：
- 每个竞品的每个维度都需要独立的 Collector 节点
- DAG 中不能有环（主 edges）
- 反馈边单独放在 feedback_edges 中"""

    async def execute(self, input_data: dict) -> AgentResult:
        user_message = input_data.get("message", "")
        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=user_message),
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
        task_id = str(uuid.uuid4())
        dag = TaskDAG(
            task_id=task_id,
            competitors=parsed.get("competitors", []),
            dimensions=parsed.get("dimensions", []),
            dag=DAGBlueprint(**parsed.get("dag", {})),
            traceability=TraceabilityConfig(),
        )
        return AgentResult(success=True, output=dag.model_dump(), llm_response=llm_response)
