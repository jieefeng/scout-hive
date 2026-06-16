import json
import logging
import uuid

import httpx

from app.agents.base import AgentBase, AgentResult
from app.llm.base import Message
from app.models.raw_data import RawData

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
            api_code = data.get("code")
            if api_code != 0:
                logger.error(
                    f"AnySearch API error for query '{query}': "
                    f"code={api_code}, message={data.get('message', 'unknown')}"
                )
                return []

            results_list = data.get("data", {}).get("results", [])
            if not results_list:
                logger.warning(
                    f"AnySearch returned no results for query: {query}"
                )
                return []

            for r in results_list:
                results.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "description": r.get("description", ""),
                    "content": r.get("content", ""),
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

        # Phase 1: Search for relevant URLs via AnySearch API
        all_search_results = []
        config = self._get_anysearch_config()
        max_results = config.max_results_per_query or 5

        for query in search_queries[:3]:
            results = await self._search_anysearch(query, max_results=max_results)
            all_search_results.extend(results)

        logger.info(f"[Collector] Search done: {len(all_search_results)} results in {int((_time.monotonic() - start_time) * 1000)}ms")

        # Phase 2: Map search results directly to RawData list
        raw_data_list = []
        sources = []
        for r in all_search_results:
            url = r.get("url", "")
            if not url:
                continue
            raw_data_list.append(RawData(
                source_url=url,
                title=r.get("title", ""),
                description=r.get("description", ""),
                content=r.get("content", ""),
            ).model_dump())
            sources.append({
                "source_id": str(uuid.uuid4()),
                "type": "web",
                "url": url,
                "title": r.get("title", ""),
                "snippet": r.get("description", "")[:300],
            })

        # Fallback: if no results collected
        if not raw_data_list:
            raw_data_list = [RawData(
                source_url=f"https://search.example.com?q={target}",
                title="",
                description="",
                content=f"未能采集到关于 {target} 的 {dimension} 相关内容。",
            ).model_dump()]

        # Build reasoning chain for trace display
        elapsed_s = round(_time.monotonic() - start_time, 1)
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
                           f"映射为 {len(raw_data_list)} 条 RawData\n"
                           f"耗时: {elapsed_s}s",
                "type": "summary",
            },
        ]

        return AgentResult(
            success=True, output=raw_data_list, llm_response=llm_response,
            sources=sources,
            reasoning_chain=reasoning_chain,
        )
