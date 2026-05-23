import hashlib
import json
import logging
import uuid

import httpx
import trafilatura

from app.agents.base import AgentBase, AgentResult
from app.cleaner.html_cleaner import clean_html
from app.llm.base import Message
from app.models.raw_data import Chunk, RawData, RawDataMetadata

logger = logging.getLogger(__name__)

SEARCH_TIMEOUT = 15


class Collector(AgentBase):
    SYSTEM_PROMPT_TEMPLATE = """你是一个信息采集专家。根据给定的竞品名称、分析维度和域名约束，生成搜索关键词和采集策略。
重要约束：优先在竞品主域名 site:{domain} 中搜索。

输出 JSON 格式：
{{
  "search_queries": ["关键词1", "关键词2"],
  "target_urls": ["https://..."],
  "strategy": "web_search"
}}"""

    SYSTEM_PROMPT_NO_DOMAIN = """你是一个信息采集专家。根据给定的竞品名称和分析维度，生成搜索关键词和采集策略。

输出 JSON 格式：
{
  "search_queries": ["关键词1", "关键词2"],
  "target_urls": ["https://..."],
  "strategy": "web_search"
}"""

    async def _fetch_url(self, url: str) -> str:
        """Fetch a URL and extract main text content using trafilatura."""
        try:
            async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                text = trafilatura.extract(resp.text, include_comments=False, include_tables=True)
                return text or ""
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return ""

    async def _search_ddg(self, query: str) -> list[dict]:
        """Search using DuckDuckGo HTML API and return results with URLs."""
        results = []
        try:
            async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                resp.raise_for_status()
                html = resp.text
                # Extract result links from DuckDuckGo HTML response
                import re
                # DuckDuckGo results have links like <a rel="nofollow" class="result__a" href="...">
                links = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
                snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                for i, url in enumerate(links[:5]):
                    snippet = snippets[i].strip() if i < len(snippets) else ""
                    snippet = re.sub(r'<[^>]+>', '', snippet)  # strip HTML tags
                    results.append({"url": url, "snippet": snippet})
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
        return results

    async def execute(self, input_data: dict) -> AgentResult:
        target = input_data.get("target", "")
        dimension = input_data.get("dimension", "")
        domain = input_data.get("domain", "")
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(domain=domain) if domain else self.SYSTEM_PROMPT_NO_DOMAIN

        domain_hint = f"\n域名约束: site:{domain}" if domain else ""
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=f"竞品: {target}\n分析维度: {dimension}{domain_hint}"),
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

        search_queries = strategy.get("search_queries", [f"{target} {dimension}"])
        target_urls = strategy.get("target_urls", [])

        # Phase 1: Search for relevant URLs via DuckDuckGo
        all_search_results = []
        for query in search_queries[:3]:  # limit to 3 queries
            results = await self._search_ddg(query)
            all_search_results.extend(results)
            # Collect discovered URLs for fetching
            for r in results:
                if r["url"] not in target_urls:
                    target_urls.append(r["url"])

        # Phase 2: Fetch and extract content from top URLs
        collected_texts = []
        sources = []
        for url in target_urls[:5]:  # limit to 5 URLs
            text = await self._fetch_url(url)
            if text:
                collected_texts.append(text)
                sources.append({
                    "source_id": str(uuid.uuid4()),
                    "type": "web",
                    "url": url,
                    "snippet": text[:300],
                })

        # Fallback: if no real content collected, use search snippets
        if not collected_texts and all_search_results:
            for r in all_search_results[:3]:
                collected_texts.append(r.get("snippet", ""))
                sources.append({
                    "source_id": str(uuid.uuid4()),
                    "type": "web",
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", "")[:300],
                })

        raw_content = "\n\n---\n\n".join(collected_texts) if collected_texts else f"未能采集到关于 {target} 的 {dimension} 相关内容。"
        content_hash = hashlib.md5(raw_content.encode()).hexdigest()
        clean_result = clean_html(raw_content)

        raw_data = RawData(
            data_id=str(uuid.uuid4()),
            source_type="web",
            source_url=target_urls[0] if target_urls else f"https://search.example.com?q={target}",
            content=clean_result.text,
            content_hash=content_hash,
            metadata=RawDataMetadata(
                fetched_by=self.name,
                reliability="medium" if collected_texts else "low",
                content_type="search_result",
                status="complete" if collected_texts else "partial",
            ),
            chunks=[
                Chunk(
                    chunk_id=str(uuid.uuid4()),
                    text=clean_result.text,
                    plain_text_snapshot=clean_result.text,
                )
            ],
        )
        confidence_score = 0.7 if collected_texts else 0.3
        return AgentResult(
            success=True, output=raw_data.model_dump(), llm_response=llm_response,
            sources=sources, confidence={"score": confidence_score, "level": "medium" if collected_texts else "low"},
        )
