# Parse 端去 Schema 强制化 + 下游通用化 — 设计文档

> ⚠️ **DEPRECATED 2026-06-08**:本 spec 的"parse 端接受任意 dimension"核心改动已被
> [`2026-06-08-vertical-hard-lockdown-design.md`](./2026-06-08-vertical-hard-lockdown-design.md)
> 反向回滚:`parse.py` 重新加 `dim_not_in_schema` 422 校验,白名单 = ai-assistant
> 7 维度。Writer 通用 prompt + format_hint 软建议保留;parse 端的"任意维度"解锁
> 不再适用。本文档保留作历史决策记录;**不要按本文实施新功能**。

> 目标：让自然语言入口真正"自然"
> 目标读者：维护者 + 答辩评委（演示"任意维度也能跑"）

## 为什么

`POST /api/tasks/parse` 是项目对用户的**自然语言入口**——用户期望"用一句话描述分析需求"。但当前实现把 `DEFAULT_SCHEMA` 当成**真理之源**：

```python
# backend/app/api/parse.py:84-92
allowed = _all_dim_names(schema)
for dim in dimensions:
    if dim not in allowed:
        return {"success": False, "error_type": "dim_not_in_schema", ...}
```

`DEFAULT_SCHEMA`（`mvp_defaults.py:28`）目前只收录 3 个维度：`功能对比` / `用户体验` / `定价策略`。用户写"协同能力"、"AI 能力"、"出海能力"——任何 schema 没收录的词——直接 422 拒绝。**自然语言入口被静默退化成了"必须知道 schema 词表的半结构化入口"**，违背设计意图。

更糟的是 422 响应里：

```python
raw_truncated = _raw_content(result)[:RAW_RESPONSE_MAX_LEN]
```

`raw_response` 被截断，**前端拿不到 LLM 实际说了什么**。422 响应的唯一用途是 debug，截断等于让维护者蒙眼排错。

答辩场景下"任意分析角度都能跑"是核心叙事点（飞书/钉钉/企微的对比分析经常落到"协同能力"、"AI 助手"等 schema 没收的维度），固定词表成了演示瓶颈。

## 做什么

3 块改动：

1. **parse 端去掉 schema 强制校验** — 接受任意 dimension，仅保留基础校验（competitors 非空、不超 `MAX_COMPETITORS`）
2. **422 响应返回完整 LLM 原始输出** — 不再截断 `raw_response`
3. **Writer 合并双 prompt 为通用 prompt** — LLM 自主选 table / paragraph；前端可通过 `format_hint` 覆盖

### 不做什么（YAGNI / 已有 / 风险大）

- ❌ 删除 `DEFAULT_SCHEMA` 文件（保留为**可选 hint**，下游拿不到时走默认）
- ❌ 改 Collector prompt（**已 LLM 驱动**：`collector.py:147-161` 把 `dimension` 直入 user message，LLM 自由生成 `search_queries`；fallback `f"{target} {dimension}"` 也已对任意 dimension 鲁棒）
- ❌ 改 Analyst prompt（**已 LLM 通用**：`analyst.py` 拿 `dimension` 作为分析上下文，schema 字段是 `evidence_threshold` 等数值类，有 schema 缺省即 `1`）
- ❌ 改前端（报告渲染本就不强耦合 schema）
- ❌ 动 Reviewer（已通用）
- ❌ 支持 dimension 在节点间动态变更（每个 collect 节点仍绑定一个 dimension）
- ❌ 改 LLM 适配层 / 流式输出 / 缓存
- ❌ 引入维度归一映射层（"协同能力" → "功能对比"）—— 通用化后不需要，LLM 自主分析

## 怎么做

### 决策 1：parse 端校验只留"基础项"，删 schema 强校验

**为什么**：schema 强制是单一耦合点，砍掉它就解开了 parse 端的最大锁链。基础项（competitors 非空、不超 `MAX_COMPETITORS`）保留是因为这些是**结构性约束**（没竞品分析个啥？30 个竞品跑不动），不是**词汇约束**。

**保留的错误码**：
- `empty_competitors` — 竞品列表为空
- `too_many_competitors` — 竞品数 > `MAX_COMPETITORS`（当前 10）
- `json_parse` — LLM 输出不是合法 JSON
- `topology_error` — DAG 引用不存在的节点 / 有环
- `blueprint_tampered` — confirm 端蓝图被改

**删除的错误码**：
- ~~`dim_not_in_schema`~~ — 删

**dimension 校验降级为"软提示"**：`parse_task_blueprint` 不再因 dimension 不在 schema 而失败。dimension 直接进 blueprint 节点 params，Analyst/Writer 拿到啥就分析啥。

### 决策 2：`raw_response` 不再截断

**为什么**：422 的**唯一消费者是 debug 流程**。截断到几 KB 经常让维护者看不到 LLM 实际怎么填的 JSON，找不到解析失败的真因。LLM 一次 parse 的 JSON 通常 1-50KB，HTTP 响应**完全扛得住**。

**做法**：

```python
# backend/app/api/parse.py (改)
return {
    "success": False,
    "error_type": result["error_type"],
    "raw_response": result["raw_response"],  # 完整，不再 [:RAW_RESPONSE_MAX_LEN]
    "error_message": result.get("error_message", ""),
    "hint": HINT_FALLBACK,
}
```

`RAW_RESPONSE_MAX_LEN` 常量**保留不删**（其他地方可能用），只是 parse 端不再用。

### 决策 3：Writer 合并 `SYSTEM_PROMPT_TABLE` + `SYSTEM_PROMPT_PARAGRAPH` 为通用 prompt

**为什么**：当前 Writer 按 `output_type` 二分（`writer.py:7` 两个常量 prompt），是**唯一**与 schema 强耦合的 Agent。合并后 LLM 看 dimension 名就能自决——"定价对比"自然走 table、"用户口碑"自然走 paragraph——更鲁棒（用户改 dimension 名时不用改 schema）。

**新 prompt 设计**：

```text
你是一个报告撰写专家。根据分析结果生成结构化 HTML 竞品分析报告。

[格式选择规则]
- 看到 dimension 名包含「对比 / 矩阵 / 定价 / 功能 / 指标」等量化词 → 优先用 Markdown 表格
- 看到 dimension 名包含「体验 / 口碑 / 感受 / 故事 / 叙事」等定性词 → 优先用段落叙述
- 拿不准时优先表格（竞品分析 80% 场景需要横向对比）

[强制规则]（不管 table/paragraph 都要遵守）
- 报告必须是完整 HTML 片段
- 每条结论附溯源浮窗 (data-finding-id)
- 引用来源用 sources 中的真实 URL
- 使用 input_data.dimension 字段值作报告标题，禁止改名
- 必须输出 reasoning_chain ≥ 1 条
```

**format_hint 覆盖机制**（前端/blueprint 显式控制时）：

```python
# writer.py execute() (改)
format_hint = input_data.get("format_hint", "auto")  # "table" | "paragraph" | "auto"
if format_hint == "table":
    prompt = GENERIC_PROMPT + "\n[强制] 本次输出必须是 Markdown 表格，不允许段落。"
elif format_hint == "paragraph":
    prompt = GENERIC_PROMPT + "\n[强制] 本次输出必须是段落叙述，不允许表格。"
else:  # auto
    prompt = GENERIC_PROMPT  # LLM 自决
```

**`format_hint` 怎么进 blueprint**：parse 端 TaskParser 的 prompt 末尾加"建议在 `write_001.params.format_hint` 字段填 `table` / `paragraph` / `auto`，不强制"。**这是软建议**——LLM 可能不填、可能填错、可能挂错节点。`writer.py execute()` 读不到时走 auto 路径，不报错。前端 UI 可在 confirm 之前可视化改写（**这是另一个 PR 的事**，本 spec 不做）。

**为什么是 `write_001` 节点而不是其他节点**：`writer.py execute()` 是被 Orchestrator 在 Writer 节点上调用，input_data 来自 `node.params`。format_hint 是 Writer 关心的字段，挂其他节点无意义。`write_001` 是 TaskParser prompt 示例中的命名约定，实际 LLM 可能叫 `write_Xxx`——`writer.py` 不依赖名字，只读 params 字段。

### 决策 4（设计决策，非代码改动）：DEFAULT_SCHEMA 保留为"可选 hint"，parse 端彻底不依赖，Orchestrator 仍加载

> 本节是设计决策说明（**没有新的代码改动**），目的是解释"为什么不删 schema"和"Ochestrator 为什么不动"。

**为什么**：
1. 渐进迁移：现有测试（如 `test_execute_mvp_loads_default_schema`）还依赖 schema 字段
2. keywords / evidence_threshold 对未识别维度仍有用（"协同能力"虽不在 schema，但 schema 里"功能对比"的 keywords 仍可作搜索提示）
3. 完全删除 schema 是大动作，本 spec 聚焦在"解锁 parse 端"

**已发现的现实（**`orchestrator.py:188, 220, 274`**）**：
- `execute_mvp` 已调 `_build_dim_config(schema)` 建维度配置表，然后 `dim_config.get(dim_name, {})` 拿每个节点的配置
- **对未知 dimension 已优雅降级**：返回 `{}`，下游字段各自 default
  - Collector：keywords=[]、evidence_threshold=1、tracking_sources=["web"]（LLM 仍能跑）
  - Analyst：evidence_threshold=1（LLM 仍能跑）
  - Writer：output_type="paragraph"（**这是唯一需要决策 3 干预的字段**）

**具体行为**：
- `parse.py` **完全删掉** `load_default_schema()` 调用（删校验后没有别的用途，留着徒增困惑）
- `Orchestrator.execute_mvp` 主逻辑不动：未知 dimension 走 `{}` 兜底已 work
- Collector / Analyst prompt 不动：已是 LLM 驱动 + 数值字段有 default
- Writer 走决策 3 的 format_hint / auto 路径（**关键改动**）

**DEFAULT_SCHEMA 文件**完全不动。后续若发现"schema 完全没价值"再删（独立 PR）。

### 决策 5（决策 1 的子项）：parse 失败时 hint 文案按 error_type 分支

**当前**（`parse.py:147`）：`"请重写需求使其更具体，或使用 POST /api/tasks 直接提交结构化数据"`

**改为**：

```python
# 按 error_type 分支
HINT_BY_ERROR = {
    "empty_competitors": "请明确列出至少 1 个竞品名",
    "too_many_competitors": f"竞品数超过上限 {MAX_COMPETITORS}，请精简",
    "json_parse": "LLM 输出不是合法 JSON，请稍后重试或换种描述方式",
    "topology_error": "LLM 生成的 DAG 结构有误，请稍后重试",
}
HINT_FALLBACK = "请稍后重试，或使用 POST /api/tasks 直接提交结构化数据"
```

**为什么**：原 hint 暗示"维度必须用 schema 词表"——这正是我们要打破的隐含约束。新 hint 按真实错误原因给指引，避免误导。**这是 PR 1 的一部分**（与决策 1 同 PR）。

## 数据模型

**无新模型**。

现有 `DAGBlueprint` / `ParseResponse` / `AgentResult` 字段足够，dimension 走自由字符串。

## API 设计

**无新端点**。

| 端点 | 变化 |
|------|------|
| `POST /api/tasks/parse` | 422 响应去掉 `dim_not_in_schema`；`raw_response` 不截断；hint 文案按 error_type 分支 |
| `POST /api/tasks/parse/confirm` | 不变（blueprint 仍走 Pydantic 校验，但 dimension 字段是 free str） |
| `POST /api/tasks` | 不变（结构化入口，本来就自由） |

## 改动文件清单

**改动**：
- `backend/app/api/parse.py` — 删 `_all_dim_names` 调用、删 `RAW_RESPONSE_MAX_LEN` 截断、改 hint 文案
- `backend/app/agents/writer.py` — 合并 `SYSTEM_PROMPT_TABLE` / `SYSTEM_PROMPT_PARAGRAPH` 为 `GENERIC_PROMPT`，execute 支持 `format_hint`
- `backend/app/agents/task_parser.py` — `SYSTEM_PROMPT` 末尾加"建议在 blueprint.nodes[].params 里填 `format_hint`"

**新增测试**：
- `backend/tests/test_parse/test_no_dim_validation.py` — parse 接受"协同能力"、"AI 助手"等任意 dimension
- `backend/tests/test_parse/test_full_raw_response.py` — 422 时 raw_response 包含完整 LLM JSON（> 5KB 不被截）
- `backend/tests/test_writer/test_format_hint.py` — Writer 在 `format_hint=table/paragraph/auto` 三种输入下行为正确
- `backend/tests/test_parse/test_hint_by_error.py` — hint 文案按 error_type 分支正确

**不动**：
- `backend/app/schema/mvp_defaults.py`
- `backend/app/agents/{collector,analyst,reviewer}.py`（已是 LLM 驱动 + 数值字段有 default；Collector 兜底 `f"{target} {dimension}"`）
- `backend/app/engine/orchestrator.py`（`dim_config.get(dim_name, {})` 已优雅降级）
- 前端
- `backend/app/agents/base.py`

## 怎么算成功

| 维度 | 验收标准 |
|------|---------|
| **功能 1：parse 接受任意 dimension** | 输入"对比飞书/钉钉/企微的协同能力" → 422 消失，返回合法 blueprint，dimension = "协同能力" |
| **功能 2：raw_response 完整** | 故意构造一次会触发大 LLM 输出的 prompt，422 时 raw_response 包含完整 JSON（手动验证 ≥ 5KB） |
| **功能 3：Writer 通用 prompt** | `format_hint="table"` 强制表格，`"paragraph"` 强制段落，`"auto"` LLM 自决；3 个单测全绿 |
| **回归：旧 3 维度不破** | `功能对比` / `用户体验` / `定价策略` 跑出来的报告与改造前**渲染一致**（快照对比报告 HTML 关键结构） |
| **可观测** | e2e demo（`scripts/demo_e2e.py`）加 1 个 case：飞书/钉钉/企微 × 协同能力 — 任务状态 = COMPLETED、报告 HTML 包含"协同能力"维度名、未触发 `dim_not_in_schema` |
| **测试** | 新增 ≥ 4 个测试全绿；现有 parse / writer / orchestrator 测试全绿 |
| **代码** | 改动文件 ≤ 3 个（parse.py / writer.py / task_parser.py），新增代码 ≤ 300 行 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 自由选 table / paragraph 摇摆 | prompt 给明确规则（"对比/矩阵/定价 → 表格；体验/口碑/感受 → 段落；拿不准 → 表格"）+ 拿不准时优先表格（80% 场景对） |
| dimension 自由度太高导致采集质量方差大 | Collector prompt 已读 keywords，没 keywords 时 LLM 自决搜索词；后续可单独优化（独立 PR） |
| 改 3 处出错 | 拆 2 个 PR：**(1) parse.py 改动**（决策 1+2+5）→ **(2) Writer + TaskParser 改动**（决策 3）。每个 PR 独立测、独立合 |
| 旧 `test_parse_does_not_retry_on_dim_not_in_schema` 失效 | 改写为 `test_parse_accepts_arbitrary_dim`，明确表达"任意 dimension 都通过" |
| `format_hint` 在 blueprint 里没被 LLM 填 | `writer.py execute()` 读不到时走 auto 路径，不报错 |

## 依赖与顺序

```
1. parse.py: 删 schema 校验 + raw_response 不截断 + hint 分支文案     [PR 1]
   ↓
2. PR 1 测试 (test_no_dim_validation + test_full_raw_response
   + test_hint_by_error)                                            [PR 1]
   ↓
3. writer.py: 合并双 prompt + format_hint                            [PR 2]
   ↓
4. task_parser.py SYSTEM_PROMPT: 加 format_hint 建议                 [PR 2]
   ↓
5. PR 2 测试 (test_format_hint)                                      [PR 2]
   ↓
6. e2e 验证：飞书/钉钉/企微 × 协同能力 跑通                          [PR 2]
```

预计实施时间：**1-2 周**（1 人），PR 1 大约 2-3 天，PR 2 大约 4-6 天（含测试 + e2e 验证）。
