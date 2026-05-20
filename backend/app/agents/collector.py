import hashlib
import json
import uuid

from app.agents.base import AgentBase, AgentResult
from app.cleaner.html_cleaner import clean_html
from app.llm.base import Message
from app.models.raw_data import Chunk, RawData, RawDataMetadata


class Collector(AgentBase):
    SYSTEM_PROMPT = """你是一个信息采集专家。根据给定的竞品名称和分析维度，生成搜索关键词和采集策略。
输出 JSON 格式：
{
  "search_queries": ["关键词1", "关键词2"],
  "target_urls": ["https://..."],
  "strategy": "web_search"
}"""

    async def execute(self, input_data: dict) -> AgentResult:
        target = input_data.get("target", "")
        dimension = input_data.get("dimension", "")
        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=f"竞品: {target}\n分析维度: {dimension}"),
        ]
        llm_response = await self.chat(messages)
        try:
            strategy = json.loads(llm_response.content)
        except Exception:
            strategy = {
                "search_queries": [f"{target} {dimension}"],
                "target_urls": [],
                "strategy": "web_search",
            }

        raw_content = f"关于 {target} 的 {dimension} 信息。这是一段模拟的采集内容。"
        content_hash = hashlib.md5(raw_content.encode()).hexdigest()
        clean_result = clean_html(raw_content)

        raw_data = RawData(
            data_id=str(uuid.uuid4()),
            source_type="web",
            source_url=f"https://search.example.com?q={target}",
            content=clean_result.text,
            content_hash=content_hash,
            metadata=RawDataMetadata(
                fetched_by=self.name,
                reliability="medium",
                content_type="search_result",
                status=clean_result.status,
            ),
            chunks=[
                Chunk(
                    chunk_id=str(uuid.uuid4()),
                    text=clean_result.text,
                    plain_text_snapshot=clean_result.text,
                )
            ],
        )
        return AgentResult(success=True, output=raw_data.model_dump(), llm_response=llm_response)
