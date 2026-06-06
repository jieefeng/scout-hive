# Collector Trace 详情页改版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 TraceBrowser 中 Collector 节点的详情页展示搜索策略、采集结果列表和采集统计，替代当前的空壳页面。

**Architecture:** 后端 Collector 在 `execute()` 末尾构建 `reasoning_chain`（搜索策略 + 采集统计），sources 补充 `title` 字段。前端 TraceBrowser 检测 agent 类型，Collector 用专属布局渲染。复用现有 `reasoning_chain` 和 `sources` 字段，不改 TraceRecord 模型结构。

**Tech Stack:** Python + Pydantic v2 (backend), React + TypeScript (frontend)

---

### Task 1: TraceSource 模型加 title 字段

**Files:**
- Modify: `backend/app/models/trace.py:4-9`
- Modify: `frontend/src/types/index.ts:43-48`

- [ ] **Step 1: 后端 TraceSource 加 title**

在 `backend/app/models/trace.py` 的 `TraceSource` 类中加 `title: str = ""`：

```python
class TraceSource(BaseModel):
    source_id: str
    type: str  # web | api | document
    url: str = ""
    title: str = ""       # 新增：网页标题
    snippet: str = ""
    fetched_at: str | None = None
```

- [ ] **Step 2: 前端 TraceSource 加 title**

在 `frontend/src/types/index.ts` 的 `TraceSource` 接口中加 `title?: string`：

```typescript
export interface TraceSource {
  source_id: string;
  type: string;
  url: string;
  title?: string;    // 新增：网页标题
  snippet: string;
}
```

- [ ] **Step 3: 验证后端导入正常**

Run: `cd backend && python -c "from app.models.trace import TraceSource; print(TraceSource(title='test'))"`
Expected: `source_id='' type='' url='' title='test' snippet='' fetched_at=None`

- [ ] **Step 4: 验证前端类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无新增类型错误

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/trace.py frontend/src/types/index.ts
git commit -m "feat: add title field to TraceSource model and frontend type"
```

---

### Task 2: Collector 构建 reasoning_chain 和 sources 补充 title

**Files:**
- Modify: `backend/app/agents/collector.py:135-249`
- Modify: `backend/tests/test_agents/test_collector.py`

- [ ] **Step 1: 写失败测试 — reasoning_chain 包含 strategy 和 summary**

在 `backend/tests/test_agents/test_collector.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_collector_produces_reasoning_chain_with_strategy_and_summary(mock_llm):
    """Collector trace should contain search strategy and collection summary."""
    collector = Collector("Collector", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"search_queries": ["douyin features", "douyin AI"], "target_urls": [], "strategy": "web_search"}',
        model="test",
    )

    result = await collector.run({"target": "douyin", "dimension": "features"})

    assert result.success is True
    assert len(result.reasoning_chain) == 2

    strategy_step = result.reasoning_chain[0]
    assert strategy_step["step"] == 1
    assert strategy_step["type"] == "strategy"
    assert "douyin features" in strategy_step["thought"]
    assert "douyin AI" in strategy_step["thought"]

    summary_step = result.reasoning_chain[1]
    assert summary_step["step"] == 2
    assert summary_step["type"] == "summary"
    assert "采集" in summary_step["thought"]
```

- [ ] **Step 2: 写失败测试 — sources 包含 title 字段**

在同一文件追加：

```python
@pytest.mark.asyncio
async def test_collector_sources_include_title(mock_llm):
    """Collector sources should include title from search results."""
    collector = Collector("Collector", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"search_queries": ["feishu"], "target_urls": [], "strategy": "web_search"}',
        model="test",
    )

    with patch("app.agents.collector.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0, "message": "success",
            "data": {"results": [{
                "url": "https://www.feishu.cn/",
                "description": "飞书官网",
                "content": "飞书正文...",
                "title": "飞书官网"
            }]}
        }
        mock_client.post.return_value = mock_response

        result = await collector.run({"target": "feishu", "dimension": "features"})

        assert result.success is True
        assert result.sources
        assert result.sources[0]["title"] == "飞书官网"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_agents/test_collector.py::test_collector_produces_reasoning_chain_with_strategy_and_summary tests/test_agents/test_collector.py::test_collector_sources_include_title -v`
Expected: FAIL（reasoning_chain 为空，sources 无 title）

- [ ] **Step 4: 实现 — Collector.execute() 构建 reasoning_chain**

在 `backend/app/agents/collector.py` 的 `execute()` 方法中，`confidence_score` 赋值之后、`return AgentResult(...)` 之前，插入：

```python
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
```

- [ ] **Step 5: 实现 — sources 补充 title 字段**

在 `collector.py` 的 sources 构建处（第 201-206 行），加 `title`：

```python
                sources.append({
                    "source_id": str(uuid.uuid4()),
                    "type": "web",
                    "url": url,
                    "title": search_result.get("title", ""),
                    "snippet": text[:300],
                })
```

在 fallback 分支（第 209-217 行）同样加 `title`：

```python
                sources.append({
                    "source_id": str(uuid.uuid4()),
                    "type": "web",
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", "")[:300],
                })
```

- [ ] **Step 6: 实现 — AgentResult 传入 reasoning_chain**

修改 `return AgentResult(...)` 加上 `reasoning_chain=reasoning_chain`：

```python
        return AgentResult(
            success=True, output=raw_data.model_dump(), llm_response=llm_response,
            sources=sources, confidence={"score": confidence_score, "level": "medium" if collected_texts else "low"},
            reasoning_chain=reasoning_chain,
        )
```

- [ ] **Step 7: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_agents/test_collector.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/agents/collector.py backend/tests/test_agents/test_collector.py
git commit -m "feat: Collector produces reasoning_chain with search strategy and collection stats"
```

---

### Task 3: TraceBrowser Collector 专属渲染

**Files:**
- Modify: `frontend/src/components/TraceBrowser.tsx:95-226`

- [ ] **Step 1: 提取 Collector 判断辅助函数**

在 `TraceBrowser.tsx` 的 `expandAgentName` 函数之后添加：

```typescript
function isCollectorAgent(agent: string): boolean {
  return expandAgentName(agent) === 'Collector';
}
```

- [ ] **Step 2: 添加搜索策略卡片组件**

在 `isCollectorAgent` 之后添加：

```typescript
function CollectorStrategyCard({ trace }: { trace: TraceRecord }) {
  const strategy = trace.reasoning_chain?.find((s: any) => s.type === 'strategy');
  if (!strategy) return null;
  return (
    <div style={{ marginBottom: '24px' }}>
      <h4 style={{
        margin: '0 0 14px', fontSize: '0.85rem', fontWeight: 700,
        color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px',
      }}>
        <span style={{
          width: '4px', height: '16px', borderRadius: '2px',
          background: 'linear-gradient(180deg, #3b82f6, #2563eb)',
        }} />
        搜索策略
      </h4>
      <div style={{
        padding: '14px 16px', background: '#eff6ff', borderRadius: '10px',
        border: '1px solid #bfdbfe', fontSize: '0.85rem', lineHeight: 1.8,
        color: '#1e40af', whiteSpace: 'pre-wrap',
      }}>
        {strategy.thought}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 添加采集结果列表组件**

在 `CollectorStrategyCard` 之后添加：

```typescript
function CollectorSourcesList({ trace }: { trace: TraceRecord }) {
  if (!trace.sources?.length) return null;
  return (
    <div style={{ marginBottom: '24px' }}>
      <h4 style={{
        margin: '0 0 14px', fontSize: '0.85rem', fontWeight: 700,
        color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px',
      }}>
        <span style={{
          width: '4px', height: '16px', borderRadius: '2px',
          background: 'linear-gradient(180deg, #3b82f6, #2563eb)',
        }} />
        采集结果 ({trace.sources.length})
      </h4>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {trace.sources.map((source, i) => (
          <div key={source.source_id || i} style={{
            padding: '14px 16px', background: '#f8fafc', borderRadius: '10px',
            border: '1px solid #e2e8f0',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span style={{ fontSize: '0.85rem' }}>🌐</span>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#1e293b' }}>
                {source.title || (() => { try { return new URL(source.url || 'https://unknown').hostname; } catch { return '未知来源'; } })()}
              </span>
            </div>
            {source.url && (
              <a href={source.url} target="_blank" rel="noopener noreferrer" style={{
                fontSize: '0.78rem', color: '#3b82f6', textDecoration: 'none',
                display: 'block', marginBottom: '8px', wordBreak: 'break-all',
                marginLeft: '28px',
              }}>
                {source.url} ↗
              </a>
            )}
            {source.snippet && (
              <p style={{
                margin: 0, fontSize: '0.8rem', color: '#475569', lineHeight: 1.5,
                background: '#fff', padding: '8px 10px', borderRadius: '6px',
                border: '1px solid #e2e8f0', marginLeft: '28px',
              }}>
                {source.snippet}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 添加采集统计卡片组件**

在 `CollectorSourcesList` 之后添加：

```typescript
function CollectorSummaryCard({ trace }: { trace: TraceRecord }) {
  const summary = trace.reasoning_chain?.find((s: any) => s.type === 'summary');
  if (!summary) return null;
  return (
    <div style={{ marginBottom: '24px' }}>
      <h4 style={{
        margin: '0 0 14px', fontSize: '0.85rem', fontWeight: 700,
        color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px',
      }}>
        <span style={{
          width: '4px', height: '16px', borderRadius: '2px',
          background: 'linear-gradient(180deg, #3b82f6, #2563eb)',
        }} />
        采集统计
      </h4>
      <div style={{
        padding: '14px 16px', background: '#f0f9ff', borderRadius: '10px',
        border: '1px solid #bae6fd', fontSize: '0.85rem', lineHeight: 1.8,
        color: '#0c4a6e', whiteSpace: 'pre-wrap',
      }}>
        {summary.thought}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 在详情区域添加条件渲染**

在 `TraceBrowser.tsx` 的详情区域（`selectedTrace ?` 分支），在 header 之后、置信度卡片之前，将原有的推理链渲染替换为条件渲染：

```tsx
          {isCollectorAgent(selectedTrace.agent) ? (
            <>
              <CollectorStrategyCard trace={selectedTrace} />
              <CollectorSourcesList trace={selectedTrace} />
              <CollectorSummaryCard trace={selectedTrace} />
            </>
          ) : (
            <div style={{ marginBottom: '24px' }}>
              <h4 style={{
                margin: '0 0 14px', fontSize: '0.85rem', fontWeight: 700,
                color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px',
              }}>
                <span style={{
                  width: '4px', height: '16px', borderRadius: '2px',
                  background: 'linear-gradient(180deg, #8b5cf6, #7c3aed)',
                }} />
                推理链
              </h4>
              {selectedTrace.reasoning_chain?.length ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {selectedTrace.reasoning_chain.map((step, i) => {
                    const theme = AGENT_THEME[expandAgentName(selectedTrace.agent)] || { color: '#64748b' };
                    return (
                      <div key={i} style={{
                        padding: '14px 16px', background: '#f8fafc', borderRadius: '10px',
                        border: '1px solid #e2e8f0', fontSize: '0.85rem', lineHeight: 1.6,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                          <span style={{
                            width: '22px', height: '22px', borderRadius: '50%',
                            background: theme.color, color: '#fff', fontSize: '0.65rem',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontWeight: 700, flexShrink: 0,
                          }}>
                            {step.step}
                          </span>
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b' }}>步骤 {step.step}</span>
                        </div>
                        <p style={{ margin: 0, color: '#334155' }}>{step.thought}</p>
                        {step.source_ref && (
                          <button
                            onClick={() => setShowSourcePanel(true)}
                            style={{
                              marginTop: '8px', fontSize: '0.75rem', color: theme.color,
                              cursor: 'pointer', background: theme.color + '12', border: 'none',
                              padding: '4px 10px', borderRadius: '6px', fontWeight: 500,
                            }}
                          >
                            📎 查看原文
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{
                  padding: '1.5rem', textAlign: 'center', color: '#94a3b8',
                  background: '#f8fafc', borderRadius: '10px', border: '1px dashed #e2e8f0',
                  fontSize: '0.85rem',
                }}>
                  暂无推理记录
                </div>
              )}
            </div>
          )}
```

- [ ] **Step 6: 验证前端构建**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 7: 验证前端构建产物**

Run: `cd frontend && npm run build`
Expected: 构建成功，无错误

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/TraceBrowser.tsx
git commit -m "feat: Collector trace view shows search strategy, sources list, and stats"
```

---

### Task 4: 旧数据兼容性验证

- [ ] **Step 1: 验证旧 Collector trace（无 reasoning_chain）不报错**

旧 trace 数据中 Collector 的 `reasoning_chain` 为空数组，`sources` 无 `title` 字段。前端 graceful fallback：

- `CollectorStrategyCard`：`reasoning_chain?.find` 返回 undefined → 组件返回 null → 不渲染 ✅
- `CollectorSourcesList`：`trace.sources?.length` 为 0 → 不渲染 ✅（或 sources 有数据但无 title → 显示 URL hostname）
- `CollectorSummaryCard`：同 strategy ✅

手动检查：在浏览器中打开一个已有任务的 Collector 节点，确认不报错。

- [ ] **Step 2: 如果有 fallback 问题，修复并 commit**

```bash
git add frontend/src/components/TraceBrowser.tsx
git commit -m "fix: graceful fallback for legacy Collector traces without title/reasoning_chain"
```

---

### Task 5: 端到端验证

- [ ] **Step 1: 运行全部后端测试**

Run: `cd backend && python -m pytest -v`
Expected: ALL PASS，无回归

- [ ] **Step 2: 启动后端 + 前端，创建任务验证**

```bash
cd backend && uvicorn app.main:app --reload &
cd frontend && npm run dev &
```

通过 Dashboard 创建一个新任务，等待 Collector 节点执行完成，点击 Collector 节点查看详情：

- 能看到搜索策略关键词列表
- 能看到采集到的网页列表（标题 + URL + 摘要）
- 能看到采集统计
- 置信度和 LLM 元信息正常显示

- [ ] **Step 3: 验证其他 Agent 节点不受影响**

点击 Analyst / Writer / Reviewer 节点，确认推理链展示逻辑不变。
