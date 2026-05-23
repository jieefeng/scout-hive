import sys
sys.path.insert(0, "D:/AAComputerCourse/AACode/zijie/backend")

import asyncio
import os
from app.llm.bailian_adapter import BailianAdapter
from app.llm.base import Message

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

async def test():
    # Use the SAME model as config.yaml
    adapter = BailianAdapter(
        api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
        model="qwen3.6-plus-2026-04-02",
    )
    messages = [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content="分析抖音和快手"),
    ]
    print("Calling Bailian API with TaskParser prompt (model=qwen3.6-plus-2026-04-02)...")
    try:
        resp = await adapter.chat(messages, timeout=60)
        print(f"Success! Response length: {len(resp.content)}")
        print(f"Content repr: {repr(resp.content[:500])}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()

asyncio.run(test())