# AI 驱动的竞品分析 Agent 协作系统 — 设计文档

## 1. 概述

### 1.1 背景

企业产品研发中，传统竞品分析面临流程繁琐重复、信息源分散、极度依赖个人行业认知等痛点。本系统模拟真实数字调研小组，通过多个专职 Agent 的协同，自动完成从公开信息采集到结构化竞品报告输出的全链路工作。

### 1.2 核心目标

- **深度自动化**：从信息采集到报告输出全流程自动化
- **全链路溯源**：每条结论可追溯到原文，附带推理链和置信度
- **完全可观测**：每个 Agent 的决策过程与中间产物透明可见
- **可配置 Schema**：不限定产品领域，用户可自定义竞品知识结构

### 1.3 技术栈

| 层级 | 技术选型 |
|------|----------|
| 后端 | Python + FastAPI |
| 前端 | React + TypeScript |
| DAG 可视化 | React Flow |
| 图表 | ECharts / Recharts |
| 状态管理 | Zustand |
| 实时通信 | WebSocket |
| 数据清洗 | trafilatura |
| LLM | 可插拔适配层（Claude / OpenAI / 本地模型） |

---

## 2. 系统总体架构

### 2.1 四层架构

```
┌─────────────────────────────────────────────────┐
│                   前端展示层                      │
│   Web Dashboard (React) + 在线报告渲染             │
├─────────────────────────────────────────────────┤
│                   API 网关层                      │
│   FastAPI REST/WebSocket + 任务管理               │
├─────────────────────────────────────────────────┤
│               Agent 编排引擎层                    │
│   DAG 调度器 + Agent 运行时 + 状态管理 + 事件总线  │
├─────────────────────────────────────────────────┤
│                 基础设施层                        │
│   LLM 适配层 + 数据采集器 + Cleaner + 存储        │
└─────────────────────────────────────────────────┘
```

### 2.2 核心组件职责

| 组件 | 职责 |
|------|------|
| DAG 调度器 | 解析任务图，按拓扑序调度 Agent，管理依赖和并发 |
| Agent 运行时 | 统一的 Agent 生命周期管理（初始化、执行、暂停、重试） |
| 状态管理器 | 持久化每个 Agent 的输入/输出/中间状态，支持断点续跑 |
| 事件总线 | Agent 间通信和交叉审查的消息通道 |
| 溯源记录器 | 捕获每个决策的推理链、数据来源和置信度 |

---

## 3. Agent 角色定义

### 3.1 架构模式："1 大脑 + 1 心脏 + N 手脚"

```
用户对话
   │
   ▼
┌──────────────────┐
│  TaskParser (AI) │ ← 大脑：需求理解、任务拆解
│  输出 DAG 蓝图    │
└────────┬─────────┘
         │ DAG JSON
         ▼
┌──────────────────┐
│ Orchestrator     │ ← 心脏：纯代码调度引擎
│ (代码驱动)       │
└────────┬─────────┘
         │ 调度指令
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
┌────────┐┌────────┐┌────────┐┌────────┐
│Collector││Analyst ││ Writer ││Reviewer│ ← 手脚：执行专家组
└────────┘└────────┘└────┬───┘└───┬────┘
                         │        │
                         └──反馈──┘
                           (≤3轮)
```

### 3.2 Agent 详情

| Agent | 驱动方式 | 职责 | 输入 | 输出 |
|-------|----------|------|------|------|
| TaskParser | 纯 AI | 与用户对话，理解需求，输出 DAG 蓝图 | 用户自然语言 | DAG JSON |
| Orchestrator | 纯代码 | 按蓝图调度 Agent，管理反馈循环 | DAG JSON | 调度指令 |
| Collector | AI + 工具 | 多源信息采集 | 竞品名称 + 维度 | RawData |
| Analyst | AI | 结构化分析，强制引用 | RawData | AnalysisResult |
| Writer | AI | 渲染 HTML 报告 | AnalysisResult | 报告草稿 |
| Reviewer | AI | 格式 + 溯源校验（不审查逻辑） | 报告草稿 | 审查意见 |

---

## 4. DAG 蓝图 Schema

### 4.1 核心结构

```json
{
  "task_id": "uuid",
  "competitors": ["竞品A", "竞品B"],
  "dimensions": ["功能对比"],
  "dag": {
    "nodes": [
      {
        "id": "collect_001",
        "agent": "Collector",
        "action": "web_search",
        "params": { "target": "竞品A", "dimension": "功能对比" },
        "depends_on": []
      }
    ],
    "edges": [
      { "from": "collect_001", "to": "analyze_001" }
    ],
    "feedback_edges": [
      {
        "from": "review_001",
        "to": "write_001",
        "condition": "review_001.status == 'rejected'",
        "max_rounds": 3,
        "timeout_per_round": "5m",
        "escalation": "auto_approve"
      }
    ]
  },
  "traceability": {
    "level": "full",
    "include_reasoning": true,
    "include_confidence": true
  }
}
```

### 4.2 反馈边机制

| 字段 | 含义 |
|------|------|
| `feedback_edges` | 与主 edges 分离，专门表达回退/循环逻辑 |
| `condition` | 触发回退的条件表达式 |
| `max_rounds` | 最大循环次数，防止死循环 |
| `timeout_per_round` | 单轮超时 |
| `escalation` | 达到上限后的策略：`auto_approve` / `halt` / `fallback` |

---

## 5. 数据采集子系统

### 5.1 采集架构

> **注意：Cleaner 是基础设施层中间件，不是 Agent。** 它在 Collector 和 Analyst 之间自动运行，无需 Orchestrator 调度。使用 trafilatura 进行正文提取和去噪，后续仅做简单的最小长度和编码检测。

```
┌─────────────────────────────────────┐
│           Collector Agent            │
├──────────┬──────────┬───────────────┤
│ Web 采集  │ API 采集  │  文档解析     │
├──────────┴──────────┴───────────────┤
│       trafilatura (正文提取+去噪)    │
├─────────────────────────────────────┤
│         统一数据中间层 (RawData)      │
├─────────────────────────────────────┤
│         去重(content_hash) + 元信息   │
└─────────────────────────────────────┘
```

### 5.2 RawData 模型

```json
{
  "data_id": "uuid",
  "source_type": "web | api | document",
  "source_url": "https://...",
  "content": "原始文本内容",
  "content_hash": "a3f2b8c1...",
  "metadata": {
    "fetched_at": "timestamp",
    "fetched_by": "collector_001",
    "reliability": "high | medium | low",
    "content_type": "pricing_page | press_release | user_review",
    "status": "success | partial | failed",
    "error_message": null
  },
  "chunks": [
    {
      "chunk_id": "uuid",
      "text": "分段文本",
      "embedding": [0.12, 0.34],
      "selector": "body > div.pricing > table > tr:nth-child(2)",
      "plain_text_snapshot": "基础版 ¥99/月..."
    }
  ]
}
```

### 5.3 关键设计点

- **content_hash（指纹去重）**：MD5/SimHash 计算，Orchestrator 采集前查重，跳过已存在的内容
- **selector（引用锚点）**：CSS/XPath 定位网页，页码+段落索引定位文档
- **plain_text_snapshot（纯文本快照）**：selector 定位失败时的兜底方案
- **status + error_message（自保护）**：区分 success/partial/failed，Orchestrator 据此决策

### 5.4 MCP 工具集成

- Web 搜索：通过 MCP 搜索服务获取公开信息
- 第三方 API：通过 MCP 工具调用 SimilarWeb / Crunchbase 等
- 文档解析：本地 PDF/Excel 解析库

---

## 6. Analyst 与 Writer 协作

### 6.1 AnalysisResult 模型

```json
{
  "analysis_id": "uuid",
  "competitor": "竞品A",
  "dimension": "功能对比",
  "findings": [
    {
      "finding_id": "f001",
      "claim": "竞品A 支持多语言，覆盖 12 种语言",
      "quote": "Supporting 12 languages including...",
      "quote_type": "exact | paraphrased",
      "source_ref": "src_003",
      "chunk_ref": "chunk_01",
      "reasoning_chain": [
        { "step": 1, "thought": "官网导航栏显示语言切换器", "source_ref": "src_003" }
      ],
      "confidence": { "score": 0.92, "level": "high", "uncertainty_factors": [] }
    }
  ],
  "comparison_matrix": {
    "dimensions": ["多语言", "API 开放", "SSO"],
    "competitors": {
      "竞品A": { "多语言": { "status": "✓", "detail": "12种语言" }, "API 开放": { "status": "✓", "detail": "RESTful API" }, "SSO": { "status": "✗", "detail": "不支持" } },
      "竞品B": { "多语言": { "status": "✓", "detail": "8种语言" }, "API 开放": { "status": "✗", "detail": "仅内部使用" }, "SSO": { "status": "✓", "detail": "SAML 2.0" } }
    }
  }
}
```

### 6.2 强制引用机制

- 每条 claim 必须附带 `quote` + `source_ref`
- 无 quote 的 claim 直接丢弃，不进报告
- `quote_type: "paraphrased"` 的结论，置信度权重 ×0.7

### 6.3 协作流程

```
Analyst 输出 AnalysisResult (强制带 quote)
        │
        ▼
Writer 渲染为 HTML 报告
        │
        ▼
Reviewer 审查 (只查格式+溯源)
        │
        ├─ 通过 → 完成
        │
        └─ 不通过 → 精准退回
                ├─ 数据问题 → 退回 Analyst
                └─ 表达问题 → 退回 Writer
```

---

## 7. Reviewer 质检机制

### 7.1 审查范围（降级为格式+溯源检查）

| 维度 | 检查内容 | 退回目标 |
|------|----------|----------|
| JSON 格式 | 输出是否符合 Schema | Writer |
| 溯源完整性 | 每条 claim 是否有 source_ref + quote | Writer |
| 置信度校准 | 置信度是否与证据强度匹配 | Analyst |

**不审查逻辑正确性** — Reviewer 没有独立数据源，无法判断逻辑。

### 7.2 置信度校准规则

- 2+ 条独立来源 → 可评 high (≥0.8)
- 仅 1 条来源 → 最高 medium (≤0.7)
- 来源 reliability low → 最高 low (≤0.5)
- paraphrased quote → 权重 ×0.7
- 无来源 → 直接退回

### 7.3 审查输出

```json
{
  "review_id": "uuid",
  "round": 2,
  "verdict": "approved | rejected",
  "checks": [
    {
      "dimension": "溯源完整性",
      "status": "pass | fail",
      "issues": [
        {
          "finding_id": "f003",
          "severity": "critical | warning",
          "description": "第3条结论缺少原文支撑",
          "suggestion": "补充竞品B的API文档引用"
        }
      ]
    }
  ],
  "feedback_to": "Writer | Analyst",
  "feedback_message": "具体修改建议"
}
```

---

## 8. Orchestrator 重试与降级

### 8.1 错误分类处理

```python
async def execute_node(node):
    for attempt in range(3):
        result = await agent.run(node)
        if result.json_valid:
            return result

        if result.error_type == "json_parse":
            node.params["retry_context"] = result.error
            continue
        elif result.error_type == "token_limit":
            return await fallback_to_lighter_model(node)
        elif result.error_type == "network":
            mark_failed(node, fallback="skip")
            return None

    mark_failed(node, fallback="skip")
```

| 错误类型 | 策略 |
|----------|------|
| JSON 格式错误 | 重试（最多 3 次），把错误信息喂回 Agent |
| Token 超限 | 降级到更轻量的模型 |
| 网络错误 | 跳过，不阻塞其他分支 |
| 重试耗尽 | 标记节点失败，执行 fallback |

---

## 9. 可插拔 LLM 适配层

### 9.1 接口抽象

```python
class LLMAdapter(ABC):
    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> Response:
        ...

    @abstractmethod
    async def stream_chat(self, messages: list[Message], **kwargs) -> AsyncIterator[Chunk]:
        ...
```

### 9.2 实现

- `ClaudeAdapter` — 调用 Anthropic API
- `OpenAIAdapter` — 调用 OpenAI API
- `LocalAdapter` — 调用本地模型 (Ollama / vLLM)

### 9.3 配置

```yaml
llm:
  default: claude
  adapters:
    claude:
      type: claude
      model: claude-sonnet-4-6
      api_key: ${ANTHROPIC_API_KEY}
    openai:
      type: openai
      model: gpt-4o
      api_key: ${OPENAI_API_KEY}
    local:
      type: local
      endpoint: http://localhost:11434
      model: llama3

  agent_bindings:
    TaskParser: claude
    Analyst: claude
    Writer: openai
    Reviewer: claude
    Collector: local
```

---

## 10. 溯源与可观测性

### 10.1 Trace Record

每个 Agent 执行时自动产出溯源记录：

```json
{
  "trace_id": "uuid",
  "node_id": "analyze_001",
  "agent": "Analyst",
  "timestamp": "2026-05-21T10:30:00Z",
  "input_refs": ["collect_001.output"],
  "output": { "..." },
  "reasoning_chain": [ "..." ],
  "sources": [ "..." ],
  "confidence": { "score": 0.85, "level": "high" },
  "llm_metadata": {
    "model": "claude-sonnet-4-6",
    "tokens_used": 1523,
    "latency_ms": 2340
  }
}
```

### 10.2 前端可观测性面板

| 视图 | 内容 |
|------|------|
| DAG 执行图 | 实时高亮当前运行节点，状态一目了然 |
| Agent 详情面板 | 点击展开：输入、输出、推理链、耗时、token |
| 溯源浏览器 | 结论 → 推理链 → 原文，逐级下钻，左右分屏联动 |
| 审查历史 Timeline | 垂直时间轴，红/蓝/绿节点展示驳回/重写/通过 |
| 置信度热力图 | 按维度展示置信度分布 |

---

## 11. 前端展示层

### 11.1 页面结构

**任务仪表盘：**
- 任务列表（进行中/已完成/失败）
- 新建分析入口
- 历史任务查看

**任务执行详情页：**
- 左侧：DAG 可视化（React Flow），节点状态实时更新
- 右侧：Agent 详情面板（推理链、置信度、token 消耗）
- 底部：审查历史 Timeline

### 11.2 交互设计

**溯源分屏联动：**
- 点击 `[原文→]` 触发右侧分屏
- 左侧报告，右侧原文自动滚动 + selector 定位高亮
- selector 失败时降级展示 plain_text_snapshot + 关键词标红

**流式输出：**
- WebSocket 推送 Agent 状态变更
- Analyst 推理链逐字流出
- Writer 报告段落实时渲染
- DAG 节点带呼吸动画

### 11.3 技术选型

- React + TypeScript
- React Flow（DAG 可视化）
- ECharts / Recharts（图表）
- Zustand（状态管理）
- WebSocket（实时通信）

---

## 12. 完整数据流

```
用户输入: "分析手机市场竞品"
         │
         ▼
TaskParser (AI 对话) → DAG 蓝图 JSON
         │
         ▼
Orchestrator (代码) 解析 DAG
         │
         ├─ 指纹查重 → 跳过已采集内容
         │
    ┌────┼────┬──────────┐
    ▼    ▼    ▼          ▼
Collector → trafilatura → Cleaner → Analyst (强制引用) → Writer → Reviewer
                                                                        │
                                                              ┌─────────┤
                                                              │         │
                                                           通过 ✅    不通过 ❌
                                                              │         │
                                                              ▼         ▼
                                                         输出报告    精准退回
                                                                    (≤3轮)
```

---

## 13. 项目结构

```
zijie/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── api/                 # REST/WebSocket 路由
│   │   ├── agents/              # Agent 实现
│   │   │   ├── base.py          # Agent 基类
│   │   │   ├── task_parser.py
│   │   │   ├── collector.py
│   │   │   ├── analyst.py
│   │   │   ├── writer.py
│   │   │   └── reviewer.py
│   │   ├── engine/              # DAG 调度引擎
│   │   │   ├── orchestrator.py
│   │   │   ├── dag_parser.py
│   │   │   └── state_manager.py
│   │   ├── llm/                 # LLM 适配层
│   │   │   ├── base.py
│   │   │   ├── claude_adapter.py
│   │   │   ├── openai_adapter.py
│   │   │   └── local_adapter.py
│   │   ├── models/              # 数据模型
│   │   │   ├── dag.py
│   │   │   ├── raw_data.py
│   │   │   ├── analysis.py
│   │   │   └── trace.py
│   │   ├── cleaner/             # 数据清洗
│   │   └── config/              # 配置管理
│   ├── requirements.txt
│   └── config.yaml
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   └── TaskDetail.tsx
│   │   ├── components/
│   │   │   ├── DagViewer.tsx
│   │   │   ├── AgentDetail.tsx
│   │   │   ├── TraceBrowser.tsx
│   │   │   ├── ReviewTimeline.tsx
│   │   │   └── ReportViewer.tsx
│   │   ├── stores/
│   │   └── services/
│   ├── package.json
│   └── tsconfig.json
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-05-21-competitive-analysis-agent-system-design.md
└── .gitignore
```
