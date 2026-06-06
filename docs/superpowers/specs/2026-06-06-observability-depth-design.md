# 可观测性深度补完 — 设计文档

> 方向 B：增强补完（带历史 + 叙事丰满）
> 目标档位：答辩展示级
> 目标读者：评委 + 答辩小组 + 后续维护者

## 为什么

课题对可观测性的诉求：「**系统的可观测性**」+「**每一个 Agent 的决策过程与中间产物都完全透明**」+「**每条分析结论均有据可查**」（`docs/architecture.md` § 1）。

当前实现（架构文档 § 6.5 / § 7）已具备的：

- ✅ 节点级 `TraceRecord`（含 input/output/reasoning_chain/sources/llm_metadata）
- ✅ WebSocket 实时事件 + `EventBus` 内存发布订阅
- ✅ `TraceBrowser` / `AgentDetail` 前端组件
- ✅ `scripts/demo_e2e.py` 真实 LLM 跑通

但答辩场景下让评委「一次看到全貌」仍有 2 个差距：

1. **没有任务级聚合视图** — 评委要看"花了多少钱/谁最慢"得自己点开 5-10 个节点
2. **`reasoning_chain` 靠 LLM 自觉** — 架构文档明写"由 Agent 自填（不强制）"，3 个有决策的 Agent 跑下来 `[]` 概率不低，违反"完全透明"诉求

补完这 2 块 = 让可观测性从"工具齐全"升级为"叙事清晰"。

## 做什么

3 块工件，按依赖顺序：

1. **ReasoningChain 强约束** — Analyst / Writer / Reviewer 3 个 Agent prompt 强化 + 后置校验重试（**Collector / TaskParser 豁免**）
2. **后端 metrics 聚合** — `GET /api/tasks/:id/metrics` 1 个聚合端点（实时靠 WS 触发重拉，5 秒节流）
3. **任务级持久化** — `trace_metrics` 表 + `TaskMetricsSnapshot` 模型
4. **前端 TaskOverviewTab** — 3 MetricCard（Cost / Performance / Quality），PerformanceCard 慢节点 top 3 改为横向条形

### 不做什么（YAGNI / 撞 spec 7 红线 / 用户复审决定）

- ❌ OTel / Prometheus / 监控告警（spec 7 § 7 明确不做监控）
- ❌ 改 SQLite → Postgres（够用）
- ❌ 改前端架构（继续 Zustand + 内联 style）
- ❌ metrics 实时推流（实时靠 WS 触发"重拉 /metrics"，5 秒节流）
- ❌ **节点级 GanttChart**（评委注意力在 cost/quality，节点时间分布用 PerformanceCard 横向条形替代）
- ❌ **跨任务对比 / DiffCard**（YAGNI，答辩场景"跑 1 次讲透"是主线）
- ❌ 跨 provider 对比、metrics 历史趋势图、阈值告警
- ❌ ReasoningChain **内容质量**评估（只校验非空）
- ❌ 答辩 Demo 录屏材料（spec 5 不做）

## 怎么做

### 决策 1：实时靠"重拉"而非"推流"

**为什么**：后端只发节点级事件，前端 WS 收到 `node_completed` 后**重拉一次** `/metrics`。避免新增 `metrics_updated` 事件类型、避免双路实现的不一致风险。代价是网络往返 N 次（N=节点数），task 规模 10-30 节点可接受；用 5 秒节流防抖。

**权衡**：推流版（后端增量累加 metrics 事件）更省带宽，但实现成本高、对 spec 6.3"事件类型少而稳"有冲击。

### 决策 2：定价表放 config.yaml 而非硬编码

**为什么**：答辩前可能现场调；不同 model 定价差异大（qwen-flash vs claude-opus 差 ~20x）。未知 model 走 `default` 不崩。

**做法**：

```yaml
# backend/app/config.yaml (新增节点)
llm_pricing:
  "qwen3.6-flash-2026-04-16": {in: 0.0008, out: 0.002}   # CNY / 1k tokens
  "claude-opus-4-8":           {in: 0.015,  out: 0.075}
  "gpt-5.2":                   {in: 0.005,  out: 0.015}
  default:                      {in: 0.001,  out: 0.002}
```

语义：这是**估算**，不是真实账单；UI 标"估算"小角标。

### 决策 3：metrics 独立表 + ALTER TABLE 迁移

**为什么**：现有 `traces` 是 JSON 列嵌在 `node_states` 里，做 metrics 聚合要全量解析，O(N) 慢。独立表加索引后聚合 O(1)。

**做法**：沿用现有 `state_manager.py` 的 `ALTER TABLE` + `try/except` 幂等模式：

```python
# state_manager.py
def _ensure_metrics_table(self):
    try:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trace_metrics (
                trace_id    TEXT PRIMARY KEY,    -- 关联 TraceRecord
                task_id     TEXT NOT NULL,       -- 任务级聚合键
                node_id     TEXT NOT NULL,       -- DAG 节点 ID（如 c_Notion_AI_pricing）
                agent       TEXT NOT NULL,       -- Collector / Analyst / Writer / Reviewer
                timestamp   TEXT NOT NULL,       -- ISO 8601
                elapsed_ms  INTEGER NOT NULL,    -- 节点总耗时（ms），含 LLM + IO
                llm_latency_ms INTEGER NOT NULL, -- LLM 调用耗时（ms），elapsed_ms 的子集
                tokens_in   INTEGER DEFAULT 0,   -- prompt tokens
                tokens_out  INTEGER DEFAULT 0,   -- completion tokens
                tokens_total INTEGER DEFAULT 0,  -- in + out
                cost_cny    REAL DEFAULT 0,      -- 按 llm_pricing 表估算，CNY
                reasoning_steps INTEGER DEFAULT 0, -- reasoning_chain 长度，0=缺失
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tm_task ON trace_metrics(task_id)")
        self.conn.commit()
    except Exception as e:
        logger.warning(f"trace_metrics table init: {e}")
```

旧任务不补 metrics（启动时不重算历史），UI 显示"无 metrics 数据"，不报错。

### 决策 4：ReasoningChain 强约束（3 Agent 强制 + 2 Agent 豁免）

**强约束范围**（必须有 reasoning_chain）：

| Agent | 理由 |
|-------|------|
| Analyst | 真有决策（claim 怎么提、证据怎么引） |
| Writer | 真有决策（叙事结构、引文编排） |
| Reviewer | 真有决策（哪些项打回、引什么证据） |

**豁免范围**（不强求）：

| Agent | 理由 |
|-------|------|
| Collector | 机械行为（query 由 keywords 生成、URL 由 search 返）；强制 RC 反而逼 LLM 编"为什么选这个 query" |
| TaskParser | 结构化任务（自然语言 → DAG blueprint）；RC 价值低 |

**重试策略**（仅对强约束 Agent 生效）：

```python
# backend/app/agents/base.py (新增方法)
async def _enforce_reasoning_chain(self, result: AgentResult, input_data: dict) -> AgentResult:
    if result.success and not result.reasoning_chain:
        retry = await self._retry_with_hint(
            input_data,
            "上一轮输出缺少 reasoning_chain。请输出至少 1 条结构化步骤："
            "[{step: int, thought: str, source_ref?: str}]，每步要解释你为什么这么判断。"
        )
        if retry.success and retry.reasoning_chain:
            return retry
        # 第二次仍空：接受但在 trace 上加标记
        if result.trace:
            result.trace.error_message = (result.trace.error_message or "") + " [RC missing]"
    return result
```

**为什么只重试 1 次**：2 次重试消耗 3x tokens，cost 不可控；1 次重试覆盖大部分情况。

`_retry_with_hint` 复用现有 `task_parser.py:retry_with_prompt_hint` 的模式（独立 LLM 调用、不走 execute 主体）。

### 决策 5：前端 Tab 切分而非页面切换

**为什么**：现有 `TaskDetail` 已经是单页多组件，加 Tab 切分比新开页面更轻、保留上下文。

**做法**：

```
TaskDetail
  [Overview | DAG | Report | Trace]  ← 顶部 Tab 栏
  ┌─────────────────────────────────┐
  │ 当前 Tab 内容                    │
  └─────────────────────────────────┘
```

`Overview` 渲染 3 个 MetricCard + TraceList（与 TraceBrowser 共用）。

### 展示规范（答辩给评委看什么）

**TaskOverviewTab 布局**：

```
┌─ MetricsBar（3 卡横排，sticky 顶部）──────────────────┐
│ [Cost]   [Performance]  [Quality]                    │
└──────────────────────────────────────────────────────┘
┌─ TraceList（与 TraceBrowser 共用）───────────────────┐
│ 节点级 trace 列表，点击展开 ReasoningChain          │
└──────────────────────────────────────────────────────┘
```

**3 个 MetricCard 字段定义**（答辩时评委第一眼看到）：

| 卡 | 大数字 | 副信息 | 排名区（横向条形） |
|---|--------|--------|-------------------|
| **CostCard** | 估算总成本 `¥X.XX` | 总 tokens / LLM 调用次数 | 成本 top 3 节点（节点名 + 横向条形 + ¥X.XX） |
| **PerformanceCard** | 总耗时 `Xm Ys` | 节点数 / 失败节点数 | 慢节点 top 3（节点名 + 横向条形 + X ms） |
| **QualityCard** | 反馈循环次数 `X` | passed `Y` / RC 缺失 `Z` | （无） |

每张卡右上角小角标"估算"（CostCard）、"含 X 次重试"（QualityCard > 0 时）。

**为什么砍 DAGCard**：节点数/边数/feedback 边数是 blueprint 静态信息，已在 DAG Tab 展示；Overview 重复出现会浪费评委注意力。

**为什么 QualityCard 大数字是"反馈循环次数"而非"通过率"**：X/Y 通过率抽象层级不对（Y 就是节点数），且"一次性通过 = 质量好"是用户视角、"触发反馈循环 = 反复打回重做"是过程视角。后者更能讲故事：0 次 = 一次跑通、N 次 = 质检发挥作用。RC 缺失放在副信息里，作为"过程透明度"信号。

**PerformanceCard 慢节点条形**（替代 GanttChart）：

- 横向 3 行条形，宽度 = `elapsed_ms / max(elapsed_ms) * 100%`
- 行内文字：`{node_id} · {elapsed_ms}ms · {agent}`
- 信息密度等同甘特图，UI 复杂度更低，~50 行代码

**RC 缺失时的 UI 处理**（失败兜底，不阻塞展示）：

- `ReasoningChain` 组件显示"⚠️ 该节点推理链缺失"占位条（不报错）
- QualityCard 副信息"RC 缺失 X 次"标红
- TraceList 该节点左侧加小红点

**字段命名约束**：所有卡片副信息用 1-3 个关键词，不写完整句子（评委第一眼扫读，密度比可读性重要）。例如"15.2k tokens · 12 calls"，不是"本次任务共消耗 15200 个 token，调用 LLM 12 次"。

## 数据模型

`backend/app/models/metrics.py`（新文件）：

```python
from pydantic import BaseModel, Field


class TraceMetrics(BaseModel):
    """单次 trace 的指标增量（写入 trace 时同步落库）"""
    trace_id: str                # 关联 TraceRecord.trace_id
    task_id: str                 # 任务级聚合键
    node_id: str                 # DAG 节点 ID
    agent: str                   # Collector / Analyst / Writer / Reviewer
    timestamp: str               # ISO 8601
    elapsed_ms: int              # 节点总耗时（ms），含 LLM + IO
    llm_latency_ms: int = 0      # LLM 调用耗时（ms）
    tokens_in: int = 0           # prompt tokens
    tokens_out: int = 0          # completion tokens
    tokens_total: int = 0        # in + out
    cost_cny: float = 0.0        # 按 llm_pricing 表估算（CNY）
    reasoning_steps: int = 0     # reasoning_chain 长度，0=缺失


class TaskMetricsSnapshot(BaseModel):
    """任务级最终聚合快照"""
    task_id: str
    created_at: str
    total_elapsed_ms: int                # 所有节点 elapsed_ms 求和
    node_count: int                      # DAG 节点总数
    completed_count: int                 # 成功节点数
    failed_count: int                    # 失败节点数
    feedback_rounds: int = 0             # feedback_edges 触发的总轮数
    total_tokens: int = 0                # 所有 trace tokens_total 求和
    total_cost_cny: float = 0.0          # 所有 trace cost_cny 求和
    llm_call_count: int = 0              # 触发 LLM 调用的节点数
    slow_nodes: list[dict] = Field(default_factory=list)        # top-3 慢节点 [{node_id, agent, elapsed_ms, cost_cny}]
    agent_breakdown: dict = Field(default_factory=dict)          # {agent_name: {count, tokens, cost, elapsed}}
    quality: dict = Field(default_factory=dict)                  # {feedback_rounds, passed_count}
    rc_missing_count: int = 0                                    # reasoning_chain 缺失节点数，答辩 demo 用
```

## API 设计

| 端点 | 方法 | 用途 | 返回 |
|------|------|------|------|
| `/api/tasks/:id/metrics` | GET | 任务级聚合（回放主用） | `TaskMetricsSnapshot` |

`?include_old=true` 兼容旧任务（无 metrics 时返 `{available: false, reason: "old task"}`）。

**砍掉的端点**（vs 初版）：
- ❌ `/api/tasks/:id/metrics/compare`（无 ComparePanel）
- ❌ `/api/tasks/:id/traces/timeline`（无 GanttChart）

## 改动文件清单

**新增**：
- `backend/app/models/metrics.py` — `TraceMetrics` / `TaskMetricsSnapshot`
- `backend/app/agents/_reasoning.py` — `_enforce_reasoning_chain` / `_retry_with_hint`（共享工具）
- `backend/app/api/metrics.py` — 1 个 metrics 端点
- `frontend/src/components/TaskOverviewTab.tsx` — 3 MetricCard + TraceList 容器
- `backend/tests/test_metrics.py`（6 测试）
- `backend/tests/test_reasoning_enforce.py`（3 测试）
- `backend/tests/test_metrics_api.py`（2 测试）
- `backend/tests/test_state_manager_alter.py`（2 测试）

**改动**：
- `backend/app/agents/base.py` — 集成 `_enforce_reasoning_chain`（仅强约束 Agent 触发）
- `backend/app/agents/{analyst,writer,reviewer}.py` — prompt 强化（**Collector / TaskParser 不动**）
- `backend/app/engine/state_manager.py` — `trace_metrics` 表 + `save_trace_metrics` / `query_task_metrics`
- `backend/app/main.py` — 注册 metrics router
- `backend/app/config.yaml` — `llm_pricing` 节点
- `frontend/src/api/client.ts` — 1 个新方法
- `frontend/src/stores/taskStore.ts` — `metrics: TaskMetricsSnapshot | null` 字段 + WS 触发重拉（5 秒节流）
- `frontend/src/pages/TaskDetail.tsx` — 顶部 Tab 栏
- `scripts/demo_e2e.py` — 末尾打印 metrics 报告

## 怎么算成功

| 维度 | 验收标准 |
|------|---------|
| **功能 1** | `scripts/demo_e2e.py` 跑 1 个真实竞品，UI 在 Overview Tab 看到 3 MetricCard + 慢节点条形 + ReasoningChain 全部非空 |
| **可观测** | 任何升级后跑过的任务都能从 DB 拉 metrics，不依赖重新跑 |
| **可解释** | 3 强约束 Agent 跑 10 轮真实数据，`reasoning_chain` 缺失 ≤ 1 次（其余 9 次为 1 次重试覆盖） |
| **回退** | 旧任务（升级前跑的）UI 显示"无 metrics 数据"而非报错 |
| **测试** | 新增 ≥ 13 个测试全绿；现有 168 测试全绿 |
| **代码** | 改动文件 ≤ 14 个，新增代码 ≤ 1200 行 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 第二次重试仍填不出 RC | `rc_missing_count` 计数 + UI 角标，不阻塞任务 |
| 定价表不准 | config.yaml 可调，UI 标"估算"语义 |
| ALTER TABLE 失败 | 沿用 try/except 幂等 + 启动检查 |
| 实时拉 metrics 频率过高 | 5 秒节流：同 task 最多 1 次 |
| 旧任务 UI 报错 | `?include_old=true` 兼容路径，UI 显式"无数据"而非崩 |
| Collector / TaskParser 漏改 prompt | `_enforce_reasoning_chain` 在 base.py 上由 Agent 类属性 `enforce_rc: bool` 显式控制，默认 False |

## 依赖与顺序

```
1. 模型定义 (metrics.py)
   ↓
2. state_manager 加表 + ALTER TABLE
   ↓
3. ReasoningChain 工具 (_reasoning.py) + base.py 集成
   ↓
4. 3 Agent (Analyst/Writer/Reviewer) prompt 改写
   ↓
5. /metrics API 端点
   ↓
6. 前端 TaskOverviewTab
   ↓
7. TaskDetail Tab 切换
   ↓
8. demo_e2e.py 集成 metrics 报告
   ↓
9. 测试 + 真实数据验证
```

预计实施时间：**1.5-2.5 周**（2 人）。
