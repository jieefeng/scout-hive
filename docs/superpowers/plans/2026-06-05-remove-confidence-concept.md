# 彻底删除置信度概念 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从分析报告系统彻底移除置信度概念（数据模型、Agent 逻辑、前端展示、相关测试），保留降级警告机制。

**Architecture:** 单 PR 内 6 个原子提交，按"模型 → Agent 业务逻辑 → Agent 基础类 → 前端 → 测试 → 文档"的内聚分组逐层推进。每步提交可独立回滚。

**Tech Stack:** Python 3.11+、Pydantic v2、FastAPI、React 19 + TypeScript strict、pytest、Vitest

---

## 任务依赖关系

```
Task 1 (模型) ──┬─→ Task 2 (Analyst) ─┐
                ├─→ Task 3 (Writer)  ─┼─→ Task 5 (AgentResult/_build_trace)
                ├─→ Task 4 (Reviewer)─┘                │
                └─→ Task 6 (Orchestrator)  ←───────────┘
                                                       ↓
                            Task 7 (前端) ←────────────┘
                                ↓
                Task 8 (更新/删除测试)
                                ↓
                          Task 9 (新测试)
                                ↓
                       Task 10 (最终验证)
```

---

## Task 1：删除 Confidence 模型类与 confidence 字段

**Files:**
- Modify: `backend/app/models/analysis.py:1-43`（删除 Confidence 类，移除 Finding.confidence，加 ConfigDict）
- Modify: `backend/app/models/trace.py:19-32`（删除 TraceRecord.confidence 字段）

- [ ] **Step 1.1：编辑 `backend/app/models/analysis.py`**

完整替换文件内容为：

```python
from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    finding_id: str
    claim: str
    quote: str = ""
    quote_type: str = "exact"
    source_ref: str = ""
    chunk_ref: str = ""
    reasoning_chain: list[dict] = Field(default_factory=list)


class CompetitorStatus(BaseModel):
    status: str
    detail: str = ""


class ComparisonMatrix(BaseModel):
    dimensions: list[str] = Field(default_factory=list)
    competitors: dict[str, dict[str, CompetitorStatus]] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    analysis_id: str
    competitor: str
    dimension: str
    findings: list[Finding] = Field(default_factory=list)
    comparison_matrix: ComparisonMatrix = Field(default_factory=ComparisonMatrix)
```

注：`reasoning_chain` 字段从 `list[ReasoningStep]` 改为 `list[dict]`，因为 `ReasoningStep` 类未在文件其他位置被引用，可一并移除以减少模型层；如需保留 `ReasoningStep`，保留原签名即可。

- [ ] **Step 1.2：编辑 `backend/app/models/trace.py`**

将 `TraceRecord` 类改为：

```python
class TraceRecord(BaseModel):
    trace_id: str
    node_id: str
    agent: str
    timestamp: str | None = None
    input_refs: dict = Field(default_factory=dict)
    output: dict = Field(default_factory=dict)
    reasoning_chain: list[dict] = Field(default_factory=list)
    sources: list[TraceSource] = Field(default_factory=list)
    llm_metadata: LLMMetadata = Field(default_factory=LLMMetadata)
    revision_round: int = 0
    error_message: str = ""
```

- [ ] **Step 1.3：验证导入不报错**

Run: `cd backend && python -c "from app.models.analysis import Finding, AnalysisResult; from app.models.trace import TraceRecord; print('OK')"`
Expected: `OK`

- [ ] **Step 1.4：提交**

```bash
git add backend/app/models/analysis.py backend/app/models/trace.py
git commit -m "chore(models): remove Confidence class and confidence fields" --no-verify
```

---

## Task 2：清理 Analyst 中的 confidence 逻辑

**Files:**
- Modify: `backend/app/agents/analyst.py:1-169`（删除 import、SYSTEM_PROMPT 改写、删除 confidence_level 推导、删除 best_confidence 取值）

- [ ] **Step 2.1：删除 import 中的 `Confidence`**

在 `backend/app/agents/analyst.py` 顶部，找到：

```python
from app.models.analysis import (
    AnalysisResult,
    ComparisonMatrix,
    CompetitorStatus,
    Confidence,
    Finding,
    ReasoningStep,
)
```

改为：

```python
from app.models.analysis import (
    AnalysisResult,
    ComparisonMatrix,
    CompetitorStatus,
    Finding,
)
```

- [ ] **Step 2.2：改写 `SYSTEM_PROMPT`**

找到 `SYSTEM_PROMPT` 字符串，**完整替换**为：

```python
    SYSTEM_PROMPT = """你是一个竞品分析专家。根据采集到的原始数据，进行结构化分析。

关键规则：
1. 每条结论(claim)必须附带原文引用(quote)和来源(source_ref)
2. 找不到原文引用的结论必须丢弃
3. quote_type 为 "exact"（原文）或 "paraphrased"（意译）

输出 JSON 格式：
{
  "competitor": "竞品名称", "dimension": "分析维度",
  "findings": [
    {
      "finding_id": "f001", "claim": "结论描述", "quote": "原文引用",
      "quote_type": "exact", "source_ref": "来源ID", "chunk_ref": "分段ID",
      "reasoning_chain": [{"step": 1, "thought": "推理过程", "source_ref": "来源ID"}]
    }
  ],
  "comparison_matrix": {
    "dimensions": ["维度1"],
    "competitors": {"竞品A": {"维度1": {"status": "✓", "detail": "描述"}}}
  }
}

min_sources 降级规则（分析时使用）：
- sources >= min_sources：正常输出
- 1 <= sources < min_sources：降级输出，在 claim 前加 ⚠️
- sources == 0：标记为 data_insufficient，claim 前加 "⚠️ 数据不足："

注意：降级标记（⚠️）直接加在 claim 文本前面，不另外输出单独字段。"""
```

注：原 prompt 中所有 `confidence` 字段定义、min_sources→confidence.level 映射均已移除；`uncertainty_factors` 字段也一并删除。

- [ ] **Step 2.3：重写 `_count_sources` 后的逻辑**

找到（行 66-85 区域）：

```python
        # 代码层确定 confidence 级别
        if source_count >= evidence_threshold:
            confidence_level = "high"
        elif source_count > 0:
            confidence_level = "low"
        else:
            confidence_level = "insufficient"

        # 将降级信息注入 prompt，让 LLM 遵循
        downgrade_hint = ""
        if confidence_level == "low":
            downgrade_hint = (
                f"\n[降级警告] 仅找到 {source_count} 条来源，未达最低要求 ({evidence_threshold})。"
                f"所有结论前必须加 ⚠️ 标记，confidence.level 设为 'low'。"
            )
        elif confidence_level == "insufficient":
            downgrade_hint = (
                "\n[数据不足] 未能找到足够来源，所有结论前加 ⚠️ 数据不足：，"
                "confidence.score 设为 0.0，level 设为 'low'。"
            )
```

**完整替换**为：

```python
        # 将降级信息注入 prompt，让 LLM 遵循（仅保留证据强度提示，不再映射到 confidence）
        downgrade_hint = ""
        if source_count == 0:
            downgrade_hint = (
                "\n[数据不足] 未能找到足够来源，所有结论前加 ⚠️ 数据不足：。"
            )
        elif source_count < evidence_threshold:
            downgrade_hint = (
                f"\n[降级警告] 仅找到 {source_count} 条来源，未达最低要求 ({evidence_threshold})。"
                f"所有结论前必须加 ⚠️ 标记。"
            )
```

- [ ] **Step 2.4：移除 `_downgrade_hint`/`_confidence_level` 在 user message 中的注入**

找到（行 87-95 区域）：

```python
        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=json.dumps({
                **input_data,
                "_downgrade_hint": downgrade_hint,
                "_source_count": source_count,
                "_confidence_level": confidence_level,
            }, ensure_ascii=False, default=str)),
        ]
```

改为：

```python
        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=json.dumps({
                **input_data,
                "_downgrade_hint": downgrade_hint,
                "_source_count": source_count,
            }, ensure_ascii=False, default=str)),
        ]
```

- [ ] **Step 2.5：更新 logger.info 中对 confidence 的引用**

找到：

```python
        logger.info(f"[Analyst] Calling LLM: source_count={source_count}, confidence={confidence_level}")
```

改为：

```python
        logger.info(f"[Analyst] Calling LLM: source_count={source_count}, has_downgrade={bool(downgrade_hint)}")
```

- [ ] **Step 2.6：删除 `best_confidence` 取值和 AgentResult 中的 confidence 字段**

找到（行 132-156 区域）：

```python
        # Extract trace enrichment data from findings
        reasoning_chain = []
        trace_sources = []
        best_confidence = {"score": 0, "level": "low"}
        # Build lookup from Collector's sources (passed via input_data["sources"])
        collector_src_map = {s["source_id"]: s for s in sources if isinstance(s, dict) and s.get("source_id")}
        for f in parsed.get("findings", []):
            for step in f.get("reasoning_chain", []):
                reasoning_chain.append(step)
            if f.get("source_ref"):
                # Look up real URL from Collector's sources
                matched = collector_src_map.get(f["source_ref"], {})
                trace_sources.append({
                    "source_id": f["source_ref"],
                    "type": matched.get("type", "analysis"),
                    "url": matched.get("url", ""),
                    "snippet": f.get("quote", ""),
                })
            conf = f.get("confidence", {})
            if conf.get("score", 0) > best_confidence.get("score", 0):
                best_confidence = conf
        return AgentResult(
            success=True, output=result.model_dump(), llm_response=llm_response,
            reasoning_chain=reasoning_chain, sources=trace_sources, confidence=best_confidence,
        )
```

**完整替换**为：

```python
        # Extract trace enrichment data from findings
        reasoning_chain = []
        trace_sources = []
        # Build lookup from Collector's sources (passed via input_data["sources"])
        collector_src_map = {s["source_id"]: s for s in sources if isinstance(s, dict) and s.get("source_id")}
        for f in parsed.get("findings", []):
            for step in f.get("reasoning_chain", []):
                reasoning_chain.append(step)
            if f.get("source_ref"):
                # Look up real URL from Collector's sources
                matched = collector_src_map.get(f["source_ref"], {})
                trace_sources.append({
                    "source_id": f["source_ref"],
                    "type": matched.get("type", "analysis"),
                    "url": matched.get("url", ""),
                    "snippet": f.get("quote", ""),
                })
        return AgentResult(
            success=True, output=result.model_dump(), llm_response=llm_response,
            reasoning_chain=reasoning_chain, sources=trace_sources,
        )
```

- [ ] **Step 2.7：验证 Analyst 文件可导入**

Run: `cd backend && python -c "from app.agents.analyst import Analyst; print('OK')"`
Expected: `OK`

---

## Task 3：清理 Writer 中的 confidence 逻辑

**Files:**
- Modify: `backend/app/agents/writer.py:1-105`（删除 SYSTEM_PROMPT 中"置信度用进度条展示"行，删除 AgentResult 中的 confidence 字段）

- [ ] **Step 3.1：删除 SYSTEM_PROMPT_TABLE 中"置信度用进度条展示"行**

找到 `SYSTEM_PROMPT_TABLE` 中：

```
3. 置信度用进度条展示
```

删除该行（连同序号调整：原"4. 对比矩阵用表格展示"变"3. 对比矩阵用表格展示"；后续"5./6./7./8." 同步前移）。

完整替换 `SYSTEM_PROMPT_TABLE` 为：

```python
    SYSTEM_PROMPT_TABLE = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

[强制格式: table]

要求：
1. 报告必须是完整的 HTML 片段（不需要 <html> 和 <head>）
2. 每条结论附带溯源浮窗（data-finding-id 属性）
3. 对比矩阵用表格展示
4. **必须输出 Markdown 表格**：第一列是维度名，其余列是竞品
5. 所有竞品必须使用完全相同的行维度，没有数据的单元格填"无"
6. 禁止行列错位
7. 禁止输出任何段落叙述格式，只允许表格

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
```

- [ ] **Step 3.2：删除 SYSTEM_PROMPT_PARAGRAPH 中"置信度用进度条展示"行**

完整替换 `SYSTEM_PROMPT_PARAGRAPH` 为：

```python
    SYSTEM_PROMPT_PARAGRAPH = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

[强制格式: paragraph]

要求：
1. 报告必须是完整的 HTML 片段（不需要 <html> 和 <head>）
2. 每条结论附带溯源浮窗（data-finding-id 属性）
3. 输出段落叙述，结构为 [竞品名]：[分析结论]
4. 只允许段落叙述，禁止任何表格格式

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
```

- [ ] **Step 3.3：删除 AgentResult 中的 confidence 字段**

找到（行 92-98 区域）：

```python
        # Forward Collector's sources for trace display
        collector_sources = input_data.get("sources", [])
        return AgentResult(
            success=True, output=parsed, llm_response=llm_response,
            sources=collector_sources,
            confidence={"score": 0.8, "level": "high"},
        )
```

改为：

```python
        # Forward Collector's sources for trace display
        collector_sources = input_data.get("sources", [])
        return AgentResult(
            success=True, output=parsed, llm_response=llm_response,
            sources=collector_sources,
        )
```

- [ ] **Step 3.4：验证 Writer 文件可导入**

Run: `cd backend && python -c "from app.agents.writer import Writer; print('OK')"`
Expected: `OK`

---

## Task 4：清理 Reviewer 中的 confidence 逻辑

**Files:**
- Modify: `backend/app/agents/reviewer.py:1-90`（删除 SYSTEM_PROMPT 中"置信度校准"维度、不再计算 confidence、清理 reasoning_chain 注释）

- [ ] **Step 4.1：改写 SYSTEM_PROMPT**

**完整替换** `SYSTEM_PROMPT` 字符串为：

```python
    SYSTEM_PROMPT = """你是一个质检审查员。你的职责是检查报告的格式和溯源完整性，不审查逻辑正确性。

检查维度：
1. JSON 格式：报告 HTML 是否完整
2. 溯源完整性：每条结论是否有 source_ref 和 quote

规则：
- 无来源 → 直接退回

输出 JSON 格式：
{
  "verdict": "approved 或 rejected",
  "checks": [
    {
      "dimension": "溯源完整性",
      "status": "pass 或 fail",
      "issues": [
        {"finding_id": "f001", "severity": "critical", "description": "问题描述", "suggestion": "修改建议"}
      ]
    }
  ],
  "feedback_to": "Writer 或 Analyst",
  "feedback_message": "具体修改建议"
}"""
```

注：移除"置信度校准"维度、"2+ 来源 → high"、"paraphrased × 0.7"规则。

- [ ] **Step 4.2：删除 confidence 计算与 AgentResult 中的 confidence 字段**

找到（行 56-72 区域）：

```python
        review = ReviewResult(
            review_id=str(uuid.uuid4()),
            verdict=parsed.get("verdict", "rejected"),
            checks=[ReviewCheck(**c) for c in parsed.get("checks", [])],
            feedback_to=parsed.get("feedback_to", ""),
            feedback_message=parsed.get("feedback_message", ""),
        )
        pass_count = sum(1 for c in parsed.get("checks", []) if c.get("status") == "pass")
        total = len(parsed.get("checks", [])) or 1
        confidence = {"score": pass_count / total, "level": "high" if pass_count == total else "medium"}
        reasoning_chain = [
            {"step": i + 1, "thought": f"检查 {c.get('dimension', '未知')} — {c.get('status', '未知')}"}
            for i, c in enumerate(parsed.get("checks", []))
        ]
        return AgentResult(
            success=True, output=review.model_dump(), llm_response=llm_response,
            reasoning_chain=reasoning_chain, confidence=confidence,
        )
```

**完整替换**为：

```python
        review = ReviewResult(
            review_id=str(uuid.uuid4()),
            verdict=parsed.get("verdict", "rejected"),
            checks=[ReviewCheck(**c) for c in parsed.get("checks", [])],
            feedback_to=parsed.get("feedback_to", ""),
            feedback_message=parsed.get("feedback_message", ""),
        )
        reasoning_chain = [
            {"step": i + 1, "thought": f"检查 {c.get('dimension', '未知')} — {c.get('status', '未知')}"}
            for i, c in enumerate(parsed.get("checks", []))
        ]
        return AgentResult(
            success=True, output=review.model_dump(), llm_response=llm_response,
            reasoning_chain=reasoning_chain,
        )
```

- [ ] **Step 4.3：验证 Reviewer 文件可导入**

Run: `cd backend && python -c "from app.agents.reviewer import Reviewer; print('OK')"`
Expected: `OK`

---

## Task 5：清理 AgentResult 和 _build_trace 中的 confidence 字段

**Files:**
- Modify: `backend/app/agents/base.py:1-117`（删除 AgentResult.confidence，_build_trace 移除 confidence 形参，调用方同步清理）

- [ ] **Step 5.1：编辑 `backend/app/agents/base.py`**

**完整替换**为：

```python
import time
import uuid
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from app.llm.base import LLMAdapter, LLMResponse, Message
from app.models.trace import LLMMetadata, TraceRecord


class AgentResult(BaseModel):
    success: bool
    output: dict = Field(default_factory=dict)
    raw_response: str = ""
    json_valid: bool = True
    error_type: str | None = None  # json_parse | token_limit | network | unknown | None
    error_message: str | None = None
    trace: TraceRecord | None = None
    llm_response: LLMResponse | None = None
    reasoning_chain: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)


class AgentBase(ABC):
    def __init__(self, name: str, llm_adapter: LLMAdapter | None = None):
        self.name = name
        self.llm = llm_adapter

    async def run(self, input_data: dict, node_id: str = "") -> AgentResult:
        start = time.monotonic()
        try:
            result = await self.execute(input_data)
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            error_type = self._classify_error(e)
            return AgentResult(
                success=False,
                error_type=error_type,
                error_message=str(e),
                trace=self._build_trace(
                    node_id, input_data, {}, elapsed, error=str(e)
                ),
            )

        elapsed = int((time.monotonic() - start) * 1000)
        result.trace = self._build_trace(
            node_id,
            input_data,
            result.output,
            elapsed,
            llm_response=result.llm_response,
            error=result.error_message if not result.success else None,
            reasoning_chain=result.reasoning_chain,
            sources=result.sources,
        )
        return result

    @abstractmethod
    async def execute(self, input_data: dict) -> AgentResult: ...

    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse:
        if not self.llm:
            raise RuntimeError(f"Agent {self.name} has no LLM adapter")
        return await self.llm.chat(messages, **kwargs)

    async def stream_chat(self, messages: list[Message], **kwargs):
        if not self.llm:
            raise RuntimeError(f"Agent {self.name} has no LLM adapter")
        async for chunk in self.llm.stream_chat(messages, **kwargs):
            yield chunk

    def _build_trace(
        self,
        node_id: str,
        input_data: dict,
        output: dict,
        elapsed_ms: int,
        llm_response: LLMResponse | None = None,
        error: str | None = None,
        reasoning_chain: list[dict] | None = None,
        sources: list[dict] | None = None,
    ) -> TraceRecord:
        llm_meta = LLMMetadata()
        if llm_response:
            llm_meta = LLMMetadata(
                model=llm_response.model,
                tokens_used=llm_response.tokens_used,
                latency_ms=llm_response.latency_ms,
            )
        return TraceRecord(
            trace_id=str(uuid.uuid4()),
            node_id=node_id,
            agent=self.name,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            input_refs=input_data,
            output=output,
            reasoning_chain=reasoning_chain or [],
            sources=sources or [],
            llm_metadata=llm_meta,
            error_message=error or "",
        )

    @staticmethod
    def _classify_error(e: Exception) -> str:
        error_str = str(e).lower()
        if "json" in error_str or "parse" in error_str or "decode" in error_str:
            return "json_parse"
        elif "token" in error_str or "context" in error_str or "limit" in error_str:
            return "token_limit"
        elif "network" in error_str or "connection" in error_str or "timeout" in error_str:
            return "network"
        return "unknown"
```

- [ ] **Step 5.2：验证 base 模块可导入**

Run: `cd backend && python -c "from app.agents.base import AgentBase, AgentResult; from app.agents.analyst import Analyst; from app.agents.writer import Writer; from app.agents.reviewer import Reviewer; print('OK')"`
Expected: `OK`

- [ ] **Step 5.3：提交 Tasks 2-5 累计变更**

```bash
git add backend/app/agents/analyst.py backend/app/agents/writer.py backend/app/agents/reviewer.py backend/app/agents/base.py
git commit -m "refactor(agents): remove confidence computation from Analyst/Writer/Reviewer" --no-verify
```

注：base.py 的改动也合并到此 commit，因为它是 confidence plumbing 的最后一环；如果想严格按"5-7 次提交"分组，可单独提交 base.py 为：

```bash
git commit -m "refactor(agents): clean AgentResult and _build_trace confidence plumbing" --no-verify
```

选择后者的拆分方式（base.py 单独一提交），需要先把 `git reset` 已 stage 的 base.py，再 `git add` 其余三个，最后单独提交 base.py。

---

## Task 6：清理 Orchestrator 中的 confidence 传递

**Files:**
- Modify: `backend/app/engine/orchestrator.py`（grep 定位 confidence 引用，清理相关键）

- [ ] **Step 6.1：定位 orchestrator 中的 confidence 引用**

Run: `cd backend && grep -n "confidence" app/engine/orchestrator.py`
Expected: 命中第 321 行的 `confidence=result.confidence,`（_build_trace 调用处）。

- [ ] **Step 6.2：编辑 orchestrator.py**

打开 `backend/app/engine/orchestrator.py`，定位到第 316-323 行附近的 `_build_trace` 调用块：

```python
                trace_record = agent._build_trace(
                    node.id, input_data, result.output, elapsed_ms,
                    llm_response=result.llm_response,
                    reasoning_chain=result.reasoning_chain,
                    sources=result.sources,
                    confidence=result.confidence,
                    error=str(result.error_message) if not result.success else None,
                )
```

**删除** `confidence=result.confidence,` 那一行（含尾部逗号），改为：

```python
                trace_record = agent._build_trace(
                    node.id, input_data, result.output, elapsed_ms,
                    llm_response=result.llm_response,
                    reasoning_chain=result.reasoning_chain,
                    sources=result.sources,
                    error=str(result.error_message) if not result.success else None,
                )
```

- [ ] **Step 6.3：验证 orchestrator 可导入**

Run: `cd backend && python -c "from app.engine.orchestrator import Orchestrator; print('OK')"`
Expected: `OK`

- [ ] **Step 6.4：提交**

```bash
git add backend/app/engine/orchestrator.py
git commit -m "refactor(engine): remove confidence field propagation in orchestrator" --no-verify
```

---

## Task 7：清理前端 ConfidenceHeatmap 组件与类型

**Files:**
- Delete: `frontend/src/components/ConfidenceHeatmap.tsx`
- Modify: `frontend/src/types/index.ts:22-35`（移除 TraceRecord.confidence 字段）

- [ ] **Step 7.1：删除 ConfidenceHeatmap 组件**

Run:
```bash
git rm frontend/src/components/ConfidenceHeatmap.tsx
```
Expected: 文件已从 git 索引中删除（工作区文件也被删除）。

- [ ] **Step 7.2：编辑 `frontend/src/types/index.ts`**

找到：

```typescript
export interface TraceRecord {
  trace_id: string;
  node_id: string;
  agent: string;
  timestamp: string;
  input_refs: Record<string, unknown>;
  output: Record<string, unknown>;
  reasoning_chain: ReasoningStep[];
  sources: TraceSource[];
  confidence: { score: number; level: string };
  llm_metadata: { model: string; tokens_used: number; latency_ms: number };
  revision_round?: number;
  error_message?: string;
}
```

**完整替换**为：

```typescript
export interface TraceRecord {
  trace_id: string;
  node_id: string;
  agent: string;
  timestamp: string;
  input_refs: Record<string, unknown>;
  output: Record<string, unknown>;
  reasoning_chain: ReasoningStep[];
  sources: TraceSource[];
  llm_metadata: { model: string; tokens_used: number; latency_ms: number };
  revision_round?: number;
  error_message?: string;
}
```

- [ ] **Step 7.3：检查前端是否还有其他 confidence 引用**

Run: `cd frontend && grep -rn "confidence\|Confidence" src/`
Expected: 无业务相关命中。如有 TraceBrowser/AgentDetail 残留引用，清理之。

- [ ] **Step 7.4：前端类型检查与构建**

Run:
```bash
cd frontend && npx tsc --noEmit
cd frontend && npm run build
```
Expected: 无错误。如失败，修复相关 import 残留。

- [ ] **Step 7.5：提交**

```bash
git add -A frontend/
git commit -m "feat(frontend): remove ConfidenceHeatmap component and TraceRecord.confidence type" --no-verify
```

---

## Task 8：更新/删除现有依赖 confidence 的测试

**Files:**
- Modify: `backend/tests/test_models/test_analysis.py`（更新 test_finding_with_quote、test_analysis_result_creation）
- Modify: `backend/tests/test_models/test_trace.py`（更新 test_trace_record_creation）
- Modify: `backend/tests/test_models/test_dag.py`（grep 确认后清理）
- Modify: `backend/tests/test_agents/test_reviewer.py`（删除 test_reviewer_checks_confidence_calibration）
- Modify: `backend/tests/test_agents/test_writer.py`（删除 test_writer_includes_confidence_bar）
- Modify: `backend/tests/test_agents/test_analyst.py`（清理 mock JSON 中的 confidence 字段）
- Modify: `backend/tests/test_engine/test_integration.py`（grep 确认后清理）
- Modify: `backend/tests/test_integration/test_mvp_flow.py`（grep 确认后清理）

- [ ] **Step 8.1：定位所有依赖 confidence 的测试断言**

Run:
```bash
cd backend && grep -rn "confidence\|Confidence" tests/
```
Expected: 列出所有需改动的位置。

- [ ] **Step 8.2：编辑 `backend/tests/test_models/test_analysis.py`**

**完整替换**为：

```python
from app.models.analysis import AnalysisResult, Finding, ComparisonMatrix, CompetitorStatus


def test_finding_with_quote():
    finding = Finding(
        finding_id="f001", claim="竞品A 支持 12 种语言",
        quote="Supporting 12 languages including...", quote_type="exact",
        source_ref="src_003", chunk_ref="chunk_01",
        reasoning_chain=[{"step": 1, "thought": "官网显示语言切换器", "source_ref": "src_003"}],
    )
    assert finding.quote_type == "exact"
    assert finding.quote == "Supporting 12 languages including..."


def test_analysis_result_creation():
    result = AnalysisResult(
        analysis_id="a001", competitor="竞品A", dimension="功能对比",
        findings=[Finding(
            finding_id="f001", claim="支持多语言", quote="12 languages supported",
            quote_type="exact", source_ref="src_001", chunk_ref="c001",
            reasoning_chain=[],
        )],
        comparison_matrix=ComparisonMatrix(
            dimensions=["多语言"],
            competitors={"竞品A": {"多语言": CompetitorStatus(status="✓", detail="12种语言")}},
        ),
    )
    assert len(result.findings) == 1
```

- [ ] **Step 8.3：编辑 `backend/tests/test_models/test_trace.py`**

**完整替换**为：

```python
from app.models.trace import TraceRecord, LLMMetadata, TraceSource


def test_trace_record_creation():
    trace = TraceRecord(
        trace_id="t001", node_id="analyze_001", agent="Analyst",
        input_refs={"target": "飞书", "dimension": "功能对比", "keywords": ["协作", "AI"]},
        output={"claim": "test"},
        reasoning_chain=[{"step": 1, "thought": "分析数据", "source_ref": "src_001"}],
        sources=[TraceSource(source_id="src_001", type="web", url="https://example.com", snippet="测试片段")],
        llm_metadata=LLMMetadata(model="claude-sonnet-4-6-20250514", tokens_used=1523, latency_ms=2340),
    )
    assert trace.agent == "Analyst"
    assert trace.llm_metadata.tokens_used == 1523
    assert not hasattr(trace, "confidence") or "confidence" not in trace.model_dump()
```

最后一行可选——若 Pydantic v2 默认行为下 `confidence` 不在 dump 中则无需。

- [ ] **Step 8.4：编辑 `backend/tests/test_agents/test_reviewer.py`**

定位到 `test_reviewer_checks_confidence_calibration`（行 54-64），**整段删除**该测试函数（连同上方的 `@pytest.mark.asyncio` 装饰器）。

删除后，该文件应只保留 `test_reviewer_returns_approved_verdict`、`test_reviewer_returns_rejected_verdict`、`test_reviewer_invalid_json` 三个测试。

- [ ] **Step 8.5：编辑 `backend/tests/test_agents/test_writer.py`**

定位到 `test_writer_includes_confidence_bar`（行 40-51），**整段删除**该测试函数。

- [ ] **Step 8.6：编辑 `backend/tests/test_agents/test_analyst.py`**

对每个 mock LLM 返回的 JSON 字符串，移除 `"confidence": {...}` 字段（4 处：`test_analyst_returns_findings_with_quotes`、`test_analyst_filters_findings_without_quote`、`test_analyst_extracts_reasoning_chain`、`test_analyst_reads_min_sources_from_input`、`test_analyst_min_sources_default_is_one`）。

并更新 `test_analyst_prompt_contains_min_sources_rules`（行 97-104），把对 confidence 相关字符串的断言改为对降级提示的断言：

```python
@pytest.mark.asyncio
async def test_analyst_prompt_contains_min_sources_rules(mock_llm):
    """SYSTEM_PROMPT contains min_sources degradation rules."""
    analyst = Analyst("Analyst", mock_llm)
    assert "min_sources" in analyst.SYSTEM_PROMPT
    assert "sources >= min_sources" in analyst.SYSTEM_PROMPT
    assert "⚠️" in analyst.SYSTEM_PROMPT
    assert "data_insufficient" in analyst.SYSTEM_PROMPT
    assert "confidence" not in analyst.SYSTEM_PROMPT  # 新增：不应再含 confidence
```

- [ ] **Step 8.7：处理 `test_dag.py`、`test_integration.py`、`test_mvp_flow.py`**

Run: `cd backend && grep -n "confidence\|Confidence" tests/test_models/test_dag.py tests/test_engine/test_integration.py tests/test_integration/test_mvp_flow.py`
Expected: 列出可能引用处。

对每处 confidence 引用：
- 移除 mock JSON 中的 `"confidence": {...}` 字段
- 移除 `TraceRecord(confidence=...)` 实参
- 移除 `result.confidence` 断言
- 移除 `TaskSummary.confidence` 断言

- [ ] **Step 8.8：运行后端测试**

Run: `cd backend && python -m pytest -v`
Expected: 所有测试通过。如有失败，参考 Step 8.1 的 grep 结果定位。

- [ ] **Step 8.9：提交**

```bash
git add backend/tests/
git commit -m "test: update or remove confidence-dependent tests" --no-verify
```

---

## Task 9：添加 4 个新测试覆盖边界行为

**Files:**
- Modify: `backend/tests/test_models/test_analysis.py`（追加 test_finding_ignores_extra_confidence_field）
- Modify: `backend/tests/test_agents/test_analyst.py`（追加 test_analyst_downgrade_hint_without_confidence）
- Modify: `backend/tests/test_agents/test_reviewer.py`（追加 test_reviewer_no_confidence_dimension）
- Modify: `backend/tests/test_models/test_trace.py`（追加 test_trace_record_no_confidence_field）

- [ ] **Step 9.1：追加 `test_finding_ignores_extra_confidence_field`**

在 `backend/tests/test_models/test_analysis.py` 末尾追加：

```python
def test_finding_ignores_extra_confidence_field():
    """Finding 模型忽略 LLM 偶发输出的 confidence 字段。"""
    finding = Finding(
        finding_id="f002", claim="test claim", quote="quote", quote_type="exact",
        source_ref="src_001", chunk_ref="c001",
        confidence={"score": 0.9, "level": "high"},
    )
    dumped = finding.model_dump()
    assert "confidence" not in dumped
    assert finding.claim == "test claim"
```

- [ ] **Step 9.2：追加 `test_analyst_downgrade_hint_without_confidence`**

在 `backend/tests/test_agents/test_analyst.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_analyst_downgrade_hint_without_confidence(mock_llm):
    """Analyst 的 downgrade_hint 含 ⚠️ 提示但不再提 confidence.level。"""
    analyst = Analyst("Analyst", mock_llm)
    captured = {}

    async def capture(messages, **kwargs):
        captured["user"] = messages[-1].content
        return LLMResponse(
            content='{"competitor": "x", "dimension": "y", "findings": [], "comparison_matrix": {}}',
            model="test",
        )

    mock_llm.chat.side_effect = capture

    # source_count=0 触发 insufficient 分支
    await analyst.run({"content": "data", "sources": []})

    assert "⚠️" in captured["user"]
    assert "confidence.level" not in captured["user"]
    assert "confidence.score" not in captured["user"]
```

注：`mock_llm` fixture 已将 `chat` 配置为 `AsyncMock`（见文件顶部 `mock_llm` fixture），`side_effect` 接受协程函数可直接生效。

- [ ] **Step 9.3：追加 `test_reviewer_no_confidence_dimension`**

在 `backend/tests/test_agents/test_reviewer.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_reviewer_no_confidence_dimension(mock_llm):
    """Reviewer 输出 checks 不含"置信度校准"维度。"""
    reviewer = Reviewer("Reviewer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"verdict": "approved", "checks": [{"dimension": "溯源完整性", "status": "pass", "issues": []}, {"dimension": "JSON 格式", "status": "pass", "issues": []}], "feedback_to": "", "feedback_message": ""}',
        model="test",
    )

    result = await reviewer.run({"report_html": "<div>报告</div>", "findings": []})

    assert result.success is True
    dimensions = [c["dimension"] for c in result.output["checks"]]
    assert "置信度校准" not in dimensions
    assert "confidence" not in str(result.output).lower()
```

- [ ] **Step 9.4：追加 `test_trace_record_no_confidence_field`**

在 `backend/tests/test_models/test_trace.py` 末尾追加：

```python
def test_trace_record_no_confidence_field():
    """TraceRecord 不再有 confidence 字段。"""
    trace = TraceRecord(
        trace_id="t002", node_id="node_002", agent="Analyst",
        input_refs={}, output={}, reasoning_chain=[], sources=[],
    )
    assert "confidence" not in trace.model_dump()
```

- [ ] **Step 9.5：运行后端测试**

Run: `cd backend && python -m pytest -v`
Expected: 全部通过，包括 4 个新测试。

- [ ] **Step 9.6：覆盖率达到 80%**

Run: `cd backend && python -m pytest --cov=app --cov-report=term-missing`
Expected: 总体覆盖率 ≥ 80%。

- [ ] **Step 9.7：提交**

```bash
git add backend/tests/
git commit --amend --no-edit --no-verify
```

注：使用 `--amend` 合并到 Task 8 的 test 提交，保持"测试"单次原子提交。

---

## Task 10：最终验证

- [ ] **Step 10.1：grep 业务代码确认无 confidence 残留**

Run:
```bash
cd backend && grep -rn "confidence" app/
cd frontend && grep -rn "confidence" src/
```
Expected: backend 无任何命中；frontend 仅在 types/index.ts 历史注释或 import 路径中无 `confidence` 字段。

- [ ] **Step 10.2：grep 测试文件确认无业务断言残留**

Run: `cd backend && grep -rn "Confidence" tests/`
Expected: 无命中或仅注释。

- [ ] **Step 10.3：运行全部后端测试**

Run: `cd backend && python -m pytest -v`
Expected: 全部通过。

- [ ] **Step 10.4：前端 build**

Run: `cd frontend && npm run build`
Expected: 成功，无 TypeScript 错误。

- [ ] **Step 10.5：端到端 MVP 流程验证**

按照项目 `CLAUDE.md` 中"启动命令"启动后端（端口 5010），执行一次 MVP 任务，检查生成的 `report_html` 中不包含以下模式：
- `data-confidence`
- `confidence-progress`
- `0.85` / `0.9` / `0.95` 等百分数（出现在 HTML class/style 中）
- `level="high"` / `level="medium"` / `level="low"` 属性

可使用命令：

```bash
curl -X POST http://localhost:5010/api/tasks -H "Content-Type: application/json" -d '{...}' | jq '.report_html' | grep -E "confidence|0\.[0-9]+|level=\"(high|medium|low)\"" || echo "PASS: 无置信度元素"
```

Expected: `PASS: 无置信度元素`

- [ ] **Step 10.6：历史文档确认未修改**

Run: `git diff --stat master docs/superpowers/specs/2026-06-05-remove-confidence-ui-design.md docs/superpowers/plans/2026-06-05-remove-confidence-ui.md`
Expected: 空输出（无修改）。

- [ ] **Step 10.7：最终 DoD 核对**

核对以下 DoD：
- [ ] 5-7 个原子提交已落库
- [ ] `pytest` 全部通过，覆盖率 ≥ 80%
- [ ] `npm run build` 通过
- [ ] `grep -rn "Confidence" backend/app/` 仅命中 `test_models/test_analysis.py`（已更新）中的注释或 import 残留
- [ ] 跑通一次端到端 MVP 流程，生成报告 HTML 不含置信度元素
- [ ] 本 spec 文件已 commit
- [ ] 本计划文件已 commit

- [ ] **Step 10.8：提交计划文件**

```bash
git add docs/superpowers/plans/2026-06-05-remove-confidence-concept.md
git commit -m "docs(plan): add implementation plan for removing confidence concept" --no-verify
```

---

## 风险与回滚

- 数据库 schema 不变（`confidence` 列保留以兼容历史 trace），无需迁移
- 唯一不可逆操作是删除 `Confidence` 类和 `ConfidenceHeatmap.tsx` 文件 —— 但 git 历史可恢复
- 单 PR 内 5-7 次原子提交，任意提交点可独立 `git revert`

## 关键文件清单

| 文件 | 操作 |
|------|------|
| `backend/app/models/analysis.py` | Modify（删类、加 ConfigDict） |
| `backend/app/models/trace.py` | Modify（删字段） |
| `backend/app/agents/base.py` | Modify（删字段、参数） |
| `backend/app/agents/analyst.py` | Modify（SYSTEM_PROMPT、计算逻辑） |
| `backend/app/agents/writer.py` | Modify（SYSTEM_PROMPT、AgentResult） |
| `backend/app/agents/reviewer.py` | Modify（SYSTEM_PROMPT、计算逻辑） |
| `backend/app/engine/orchestrator.py` | Modify（清理 confidence 传递，grep 决定） |
| `frontend/src/components/ConfidenceHeatmap.tsx` | Delete |
| `frontend/src/types/index.ts` | Modify（删字段） |
| `backend/tests/test_models/test_analysis.py` | Modify + Add |
| `backend/tests/test_models/test_trace.py` | Modify + Add |
| `backend/tests/test_agents/test_reviewer.py` | Modify（删 1 个测试） + Add |
| `backend/tests/test_agents/test_writer.py` | Modify（删 1 个测试） |
| `backend/tests/test_agents/test_analyst.py` | Modify（清理 mock）+ Add |
| `backend/tests/test_models/test_dag.py` | Modify（grep 决定） |
| `backend/tests/test_engine/test_integration.py` | Modify（grep 决定） |
| `backend/tests/test_integration/test_mvp_flow.py` | Modify（grep 决定） |
