# Collector Trace 详情页改版设计

## 为什么

当前 TraceBrowser 中，Collector 节点的详情页几乎为空：

- Collector 的 `execute()` 不填充 `reasoning_chain`，导致推理链区域显示"暂无推理记录"
- 采集到的 sources 数据（url、snippet）存在 trace 里，但藏在需要点击"查看原文"才能打开的侧边栏中
- 而且"查看原文"按钮本身依赖 reasoning_chain 中的 `source_ref` 字段，Collector 没有这个字段，所以按钮根本不出现

**结果：** 用户点击 Collector 节点，看到的是一个空壳页面，无法了解 Collector 到底采集了什么。

### 与之前设计的关系

`2026-05-31-trace-reasoning-chain-cleanup.md` 中规定 Collector 的 `reasoning_chain` 为空列表，理由是"机械采集不存在分析性推理"。本设计**修订该决策**：将 `reasoning_chain` 复用为"执行步骤记录"，Collector 的搜索策略和采集统计作为步骤写入。这不是推理链，而是操作日志，但复用同一字段避免模型改动。

## 做什么

让 Collector 节点的 trace 详情页直接展示采集结果：

1. **搜索策略** — 用了哪些关键词
2. **采集结果列表** — 找到了哪些网页（标题 + URL + 摘要）
3. **采集统计** — 搜索到多少条、成功采集多少、成功率、耗时

### 不做什么

- 不改 TraceRecord 模型结构
- 不改 AgentBase._build_trace()

### 微调：TraceSource 加 title 字段

`backend/app/models/trace.py` 的 `TraceSource` 需要加一个可选 `title` 字段，否则 Pydantic v2 会拒绝 sources 中的额外字段：

```python
class TraceSource(BaseModel):
    source_id: str
    type: str
    url: str = ""
    title: str = ""      # 新增：网页标题
    snippet: str = ""
    fetched_at: str | None = None
```

同步更新前端类型 `frontend/src/types/index.ts`：

```typescript
export interface TraceSource {
  source_id: string;
  type: string;
  url: string;
  title?: string;    // 新增：网页标题
  snippet: string;
}
```
- 不改其他 Agent（Analyst/Writer/Reviewer）的展示逻辑
- 不改 sources 侧边栏（其他 Agent 可能用到）

## 怎么做

### 后端：`backend/app/agents/collector.py`

在 `execute()` 方法末尾、`return AgentResult(...)` 之前，构建 `reasoning_chain`：

```python
reasoning_chain = [
    {
        "step": 1,
        "thought": "搜索策略：使用 N 个关键词进行搜索\n• \"关键词1\"\n• \"关键词2\"",
        "type": "strategy",
    },
    {
        "step": 2,
        "thought": "采集结果：共搜索到 X 条结果，成功采集 Y 个网页\n成功率: Z% | 耗时: Ns",
        "type": "summary",
    },
]
```

将 `reasoning_chain` 传入 `AgentResult(reasoning_chain=reasoning_chain, ...)`。

**数据来源：**
- 搜索关键词：`search_queries` 变量（第 163 行）
- 搜索结果数：`len(all_search_results)`
- 成功采集数：`len(collected_texts)`
- 耗时：`_time.monotonic() - start_time`

**sources 补充 title 字段：**

当前 sources 构建（第 201-206 行）只有 `source_id`、`type`、`url`、`snippet`，没有 `title`。需要从 `url_to_search_result` 中取 title 一并存入：

```python
sources.append({
    "source_id": str(uuid.uuid4()),
    "type": "web",
    "url": url,
    "title": search_result.get("title", ""),  # 新增
    "snippet": text[:300],
})
```

同理，fallback 分支（第 209-217 行）也要补 title。

### 前端：`frontend/src/components/TraceBrowser.tsx`

在详情区域增加条件渲染：当 `selectedTrace.agent` 为 Collector 时，使用 Collector 专属布局。

**Collector 专属布局结构：**

```
┌─────────────────────────────┐
│ 🔍 Collector                │
│ c_competitor_维度            │
├─────────────────────────────┤
│ 🔎 搜索策略                 │
│ 关键词: "竞品A 功能对比"    │
│       "竞品A pricing"       │
├─────────────────────────────┤
│ 📎 采集结果 (N)             │
│ ┌─────────────────────────┐ │
│ │ 🌐 网页标题              │ │
│ │ https://example.com/... │ │
│ │ "snippet 摘要文本..."    │ │
│ └─────────────────────────┘ │
│ ...更多来源...              │
├─────────────────────────────┤
│ 📊 采集统计                 │
│ 搜索: 12条 | 采集: 4页     │
│ 成功率: 80% | 耗时: 3.2s   │
├─────────────────────────────┤
│ 置信度 ████████░░ 80%       │
│ LLM 元信息                  │
└─────────────────────────────┘
```

**渲染逻辑：**

1. 检测 `selectedTrace.agent` 是否为 Collector（通过 `expandAgentName` 判断）
2. 如果是 Collector：
   - 从 `reasoning_chain` 中找 `type === "strategy"` 的步骤，渲染搜索策略卡片
   - 渲染 `sources` 列表，每个来源显示域名标签 + title + URL + snippet
   - 从 `reasoning_chain` 中找 `type === "summary"` 的步骤，渲染统计卡片
   - 置信度和 LLM 元信息保持原样
3. 如果不是 Collector：渲染逻辑完全不变

### 数据流

```
Collector.execute()
  ├─ search_queries → reasoning_chain[0] (type=strategy)
  ├─ search results + fetch → sources[] (url, title, snippet, type)
  └─ 统计 → reasoning_chain[1] (type=summary)
       │
       ▼
AgentBase.run() → _build_trace()
       │
       ▼
TraceRecord { reasoning_chain, sources, confidence, llm_metadata }
       │
       ▼
TraceBrowser
  ├─ agent === 'Collector' → CollectorTraceView
  └─ 其他 → 原有推理链渲染（不变）
```

## 怎么算成功

1. 点击 Collector 节点，能看到搜索策略关键词列表
2. 能看到采集到的网页列表（标题 + URL + 摘要）
3. 能看到采集统计（搜索条数、采集页数、成功率、耗时）
4. 点击其他 Agent 节点，展示逻辑不受影响
5. 无 reasoning_chain 的旧 trace 数据不会导致页面报错（graceful fallback）
