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
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:  # 10s fallback
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                text = trafilatura.extract(resp.text, include_comments=False, include_tables=True)
                return text or ""
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return ""

    async def _search_anysearch(self, query: str, max_results: int = 5) -> list[dict]:
        """Search using AnySearch REST API and return results with URLs and snippets."""
        results = []
        config = self._get_anysearch_config()
        url = "https://api.anysearch.com/v1/search"

        headers = {"Content-Type": "application/json"}
        # AnySearch 支持匿名请求 (IP 免费配额)，无需 API Key
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        payload = {
            "query": query,
            "max_results": max_results,
            "zone": "cn",
            "language": "zh-CN",
            "content_types": ["web"],
        }

        try:
            timeout = getattr(config, 'search_timeout', 15)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # AnySearch 返回结构: {'code': 0, 'message': 'success', 'data': {'results': [...]}}
            results_list = data.get("data", {}).get("results", [])
            if not results_list:
                logger.warning(
                    f"AnySearch returned no results for query: {query}, "
                    f"response: {data}"
                )
                return []

            for r in results_list:
                results.append({
                    "url": r.get("url", ""),
                    "snippet": r.get("description", ""),
                    "content": r.get("content", ""),
                    "title": r.get("title", ""),
                })

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(
                    f"AnySearch API认证失败 (401). 请检查 anysearch.api_key 配置是否正确."
                    f" 提示: 需要在 config.yaml 或环境变量中配置有效的 AnySearch API Key."
                )
            else:
                logger.warning(f"AnySearch HTTP error for query '{query}': {e}")
        except httpx.HTTPError as e:
            logger.warning(f"AnySearch HTTP error for query '{query}': {e}")
        except Exception as e:
            logger.warning(f"AnySearch search failed for '{query}': {e}")

        return results

    def _get_anysearch_config(self):
        """Get AnySearch configuration from app config."""
        try:
            from app.config import load_config
            return load_config().anysearch
        except Exception:
            from app.config import AnySearchConfig
            return AnySearchConfig(search_timeout=15, extract_timeout=30)

    @staticmethod
    def _extract_domain(website: str) -> str:
        """从域名或完整 URL 中提取纯域名。"""
        w = website.strip()
        if not w:
            return ""
        # 补全协议以便 URL 解析
        if "/" in w and not w.startswith("http"):
            w = "https://" + w
        if "/" in w:
            try:
                from urllib.parse import urlparse
                host = urlparse(w).hostname or ""
                return host.replace("www.", "") if host else ""
            except Exception:
                pass
        # 纯域名，去掉 www. 和端口
        return w.replace("www.", "").split("/")[0].split(":")[0]

    async def execute(self, input_data: dict) -> AgentResult:
        import time as _time
        start_time = _time.monotonic()

        target = input_data.get("target", "")
        dimension = input_data.get("dimension", "")
        website = input_data.get("domain", "")
        domain = self._extract_domain(website)
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(domain=domain) if domain else self.SYSTEM_PROMPT_NO_DOMAIN

        domain_hint = f"\n域名约束: site:{domain}" if domain else ""
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=f"竞品: {target}\n分析维度: {dimension}{domain_hint}"),
        ]
        logger.info(f"[Collector] Starting: target={target}, dimension={dimension}")
        llm_response = await self.chat(messages)
        logger.info(f"[Collector] LLM strategy generated in {int((_time.monotonic() - start_time) * 1000)}ms")

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

        # 如果输入是完整 URL（而非纯域名），直接加入采集目标
        if website and "/" in website:
            url = website if website.startswith("http") else "https://" + website
            if url not in target_urls:
                target_urls.insert(0, url)

        # Phase 1: Search for relevant URLs via AnySearch API
        all_search_results = []
        config = self._get_anysearch_config()
        max_results = config.max_results_per_query or 5

        for query in search_queries[:3]:
            results = await self._search_anysearch(query, max_results=max_results)
            all_search_results.extend(results)
            for r in results:
                if r["url"] not in target_urls:
                    target_urls.append(r["url"])

        logger.info(f"[Collector] Search done: {len(all_search_results)} results, {len(target_urls)} URLs in {int((_time.monotonic() - start_time) * 1000)}ms")

        # Phase 2: Fetch and extract content from top URLs (direct HTTP with trafilatura)
        collected_texts = []
        sources = []
        # Build a map of url -> search_result for fallback
        url_to_search_result = {r["url"]: r for r in all_search_results}

        for url in target_urls[:5]:  # limit to 5 URLs
            # Use content from search result if available
            search_result = url_to_search_result.get(url, {})
            text = search_result.get("content", "")
            if not text:
                # Fallback to direct HTTP fetch
                text = await self._fetch_url(url)
            if text:
                collected_texts.append(text)
                sources.append({
                    "source_id": str(uuid.uuid4()),
                    "type": "web",
                    "url": url,
                    "title": search_result.get("title", ""),
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
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", "")[:300],
                })

        logger.info(f"[Collector] Fetch done: {len(collected_texts)} texts collected in {int((_time.monotonic() - start_time) * 1000)}ms")

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
        # Build reasoning chain for trace display
        elapsed_s = round(_time.monotonic() - start_time, 1)
        attempted_urls = min(len(target_urls), 5)
        success_rate = round(len(collected_texts) / attempted_urls * 100) if attempted_urls else 0
        reasoning_chain = [
            {
                "step": 1,
                "thought": f"搜索策略：使用 {len(search_queries)} 个关键词进行搜索\n" +
                           "\n".join(f"• \"{q}\"" for q in search_queries),
                "type": "strategy",
            },
            {
                "step": 2,
                "thought": f"采集结果：共搜索到 {len(all_search_results)} 条结果，"
                           f"成功采集 {len(collected_texts)} 个网页\n"
                           f"成功率: {success_rate}% | 耗时: {elapsed_s}s",
                "type": "summary",
            },
        ]

        return AgentResult(
            success=True, output=raw_data.model_dump(), llm_response=llm_response,
            sources=sources,
            reasoning_chain=reasoning_chain,
        )
