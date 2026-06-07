# 国内 AI 助手垂直深耕 — 设计文档

> 目标：让项目从"通用竞品分析"切换到"国内 AI 助手垂直深耕"，schema 重构 + demo 剧本重新设计
> 目标读者：维护者 + 答辩评委（演示"垂直深耕的工程化 AI 工作流"）
> 关联 spec：[2026-06-07-parse-flexible-dimensions-design.md](./2026-06-07-parse-flexible-dimensions-design.md)（已 commit，本 spec 是其"垂直 demo 层"）

## 为什么

项目当前定位是"通用竞品分析系统"，`DEFAULT_SCHEMA`（`mvp_defaults.py:28`）只有 3 个通用维度（`功能对比` / `用户体验` / `定价策略`），demo 也是 3 维度的飞书/钉钉/企微。这套配置在字节赛题"AI 工程化 + 垂直场景落地"评分项下有 2 个明显短板：

1. **Schema 通用 → 控制力弱** — 通用 schema 对任何赛道都是"50 分及格线"，Agent 输出不稳、质检规则难以硬编码、溯源覆盖率低
2. **数据源撞硬约束** — `collector.py:75-76` 把 `zone="cn"` + `language="zh-CN"` 硬编码，**无法抓海外数据**（ProductHunt/Discord/X/Reddit 全部撞死）。即使想切"AI Agent 出海"赛道，技术上不可行

**答辩场景的核心叙事点应是"AI 助手垂直深耕"**：
- 字节自家业务（豆包）作为主角——评委看着亲切
- 数据源现成（微信公众号/知乎/36氪/雪球，AnySearch CN zone 完美支持）
- Schema 从 3 维度扩到 **7 维度**——直接体现"控制力"，每个维度都能写硬编码质检规则
- 切换 schema 改为 **1 行 config**——演示"系统可迁移到任意垂直赛道"

`parse-end 放宽 spec` 解锁了"任意 dimension"，本 spec 在此基础上把"垂直 demo 层"做厚。

## 做什么

3 块改动：

1. **多文件 Schema 系统** — 拆 `mvp_defaults.py` 为多文件 JSON，config.yaml 加 `active_schema_id` 字段，运行时按需加载
2. **AI 助手 7 维度 Schema** — 新建 `schemas/ai_assistant.json`，覆盖核心玩法/AI 模型/Agent 能力/商业模式/用户社区/内容生态/安全合规
3. **Demo 剧本重写** — 5 竞品（豆包/通义/Kimi/文小言/秘塔）× 3 维度（核心玩法/AI 模型/Agent 能力）= 15 节点主 demo，剩 4 维度作"现场追问"备用

### 不做什么（YAGNI / 推迟到未来 spec）

- ❌ 跨赛道 demo 演示（飞书/钉钉/企微 + 协同办公维度）—— 留到未来 spec；本 spec 先把 AI 助手做透
- ❌ 海外数据源改造（zone 改 global / ProductHunt fetcher）—— 字节相关性国内赛道更高，不必要
- ❌ 改 Collector / Analyst / Writer / Reviewer prompt 主体 —— schema 重构后，agent 自然吃新维度，无需改 prompt
- ❌ 改 frontend —— 报告渲染本就不强耦合 schema 字段
- ❌ 加 8-10 维度 —— 7 个是"深耕"和"控制力"的甜蜜点
- ❌ 实时数据采集（每天重跑）—— demo 一次性跑通即可
- ❌ 多 schema 运行时热切换 —— config.yaml 改后重启服务，YAGNI

## 怎么做

### 决策 1：Schema 拆为多文件 JSON + config.yaml 选 active

**为什么**：当前 `mvp_defaults.py` 是单文件 Python 字典，**换 schema = 改 Python 代码**。这与"垂直 demo 层"的核心理念冲突——切赛道应该**0 代码改动**。

**新结构**：

```yaml
# backend/app/config.yaml (新增)
active_schema_id: "ai-assistant"  # 可选: "general" | "ai-assistant" | "collab-office"

# schemas/ 目录
backend/app/schemas/
├── general.json          # 通用竞品分析（3 维度，原 DEFAULT_SCHEMA 迁过来）
├── ai_assistant.json     # 新增：国内 AI 助手（7 维度）
└── collab_office.json    # 未来 spec 用，本 spec 只占位空文件
```

**加载机制**：

```python
# backend/app/schema/loader.py (新文件)
def load_active_schema() -> SchemaDefinition:
    config = load_config()
    schema_id = config.active_schema_id or "general"
    schema_path = SCHEMA_DIR / f"{schema_id.replace('-', '_')}.json"
    raw = json.loads(schema_path.read_text(encoding="utf-8"))
    return SchemaDefinition.model_validate(raw)
```

`mvp_defaults.py` 保留（向下兼容），`load_default_schema()` 改为**调 loader**：active_schema_id = "general" 时行为不变。

**切换 demo 操作**（未来跨赛道 spec 用）：

```bash
# 切到协同办公赛道
sed -i 's/active_schema_id:.*/active_schema_id: "collab-office"/' config.yaml
# 重启服务
```

### 决策 2：AI 助手 7 维度 Schema 详细设计

> 7 维度的设计原则：每个维度**至少 1 个主源 + 1 个辅源**，确保 Schema 字段有**可硬编码的质检规则**（这是"控制力"的具体体现）。

#### 维度 1: 核心玩法（output_type=paragraph）

| 字段 | 含义 | 数据源 |
|------|------|--------|
| `core_mechanics` | 对话形式（文字/语音/视频）、角色扮演、多模态输入 | 微信公众号产品测评 + 官网产品介绍 |
| `differentiator` | 该竞品区别于其他家的核心亮点 | 同上 |
| `use_case` | 典型应用场景 | 知乎产品体验回答 |

**质检规则**：`core_mechanics` 必须提到 ≥2 种交互方式（文字/语音/图片/视频/文件），否则拒。

#### 维度 2: AI 模型能力（output_type=table）

| 字段 | 含义 | 数据源 |
|------|------|--------|
| `underlying_model` | 自研/接入（豆包/通义/Qwen/Moonshot/文心/秘塔自研） | 36氪技术博客 + 学术论文 |
| `context_window` | 上下文 token 数 | 官方技术文档 |
| `multimodal_capability` | 图/音/视频/文件支持 | 36氪产品测评 |
| `response_speed` | 响应延迟（秒） | 用户实测帖 |

**质检规则**：`context_window` 必须是数字 ≥ 8000，否则标 UNVERIFIED。

#### 维度 3: Agent 能力（output_type=table）

| 字段 | 含义 | 数据源 |
|------|------|--------|
| `tool_calling` | 是否支持工具/插件调用 | 官方智能体市场 |
| `task_execution` | 任务执行能力（写代码/订外卖/查天气） | 知乎技术分析 |
| `api_integration` | 第三方 API 集成 | 官方开放平台文档 |
| `agent_marketplace` | 智能体/插件数量 | 官方市场截图 |

**质检规则**：`tool_calling` 必须是布尔（true/false），不能是"部分支持"这类模糊词。

#### 维度 4: 商业模式（output_type=table）

| 字段 | 含义 | 数据源 |
|------|------|--------|
| `pricing_model` | 免费 / 订阅 / 内购 / 企业 | 官网价格页 |
| `free_tier` | 免费配额（次数/天） | 同上 |
| `paid_tier_price` | 会员价格（元/月） | 同上 |
| `enterprise_offering` | 企业版/B 端方案 | 36氪/雪球商业分析 |

**质检规则**：`paid_tier_price` 必须是数字或"无"。

#### 维度 5: 用户社区（output_type=paragraph）

| 字段 | 含义 | 数据源 |
|------|------|--------|
| `community_size` | 创作者数量 / 智能体数量 / 活跃用户 | 微博话题阅读量 + 小红书笔记数 |
| `ugc_ecosystem` | UGC 分享机制、激励机制 | 知乎产品分析 |
| `user_sentiment` | 整体口碑（正面/负面关键词） | 小红书/微博 |

**质检规则**：`user_sentiment` 至少出现 2 个具体关键词（"回答质量好"、"响应慢"等），不能是"用户评价良好"这类空话。

#### 维度 6: 内容生态（output_type=table）

| 字段 | 含义 | 数据源 |
|------|------|--------|
| `plugin_count` | 官方插件/技能数量 | 官方市场 |
| `agent_count` | 智能体数量（用户创建） | 官方市场 |
| `appstore_integrations` | 小程序/移动端集成 | 微信小程序数据 |
| `vertical_coverage` | 覆盖行业数（教育/医疗/法律...） | 36氪行业分析 |

**质检规则**：`plugin_count` 必须是数字。

#### 维度 7: 安全合规（output_type=table）

| 字段 | 含义 | 数据源 |
|------|------|--------|
| `content_moderation` | 内容审核机制（人工/AI/混合） | 网信办通报 + 36氪 |
| `youth_mode` | 青少年模式是否齐全 | 官方公告 |
| `regulatory_compliance` | 监管合规（大模型备案/算法备案） | 网信办备案清单 |
| `data_privacy` | 数据隐私政策 | 隐私政策页面 |

**质检规则**：`regulatory_compliance` 必须列出具体备案号或"已备案"/"未公开"。

### 决策 3：Demo 剧本 = 5 竞品 × 3 维度

**主 demo 配置**：

```yaml
# scripts/demo_ai_assistant.yaml (新增)
task:
  name: "国内 AI 助手横向对比 - 2026 春季"
competitors:
  - name: "豆包"
    domain: "doubao.com"
  - name: "通义千问"
    domain: "tongyi.aliyun.com"
  - name: "Kimi"
    domain: "kimi.moonshot.cn"
  - name: "文小言"
    domain: "yiyan.baidu.com"
  - name: "秘塔 AI 搜索"
    domain: "metaso.cn"
primary_dimensions:
  - "核心玩法"     # 3 维度主 demo
  - "AI 模型能力"
  - "Agent 能力"
backup_dimensions:    # 现场追问备用
  - "商业模式"
  - "用户社区"
  - "内容生态"
  - "安全合规"
```

**节点数估算**：
- 乐观情况（write/review 各 1 节点/维度）：5 竞品 × 3 维度 collect + 5 竞品 × 3 维度 analyze + 3 维度 write + 3 维度 review = **36 节点**
- 实际可能（TaskParser 按 (comp, dim) 全拆 write 节点）：5 竞品 × 3 维度 × 4 节点 = **60 节点**
- 实际范围 **36-60 节点**（取决于 TaskParser LLM 输出形状）

**耗时估算**：每节点 ~15-30 秒（LLM 调用 + 数据采集），**整体 5-15 分钟**。

### 决策 4：Demo 运行入口（CLI 而非前端）

**为什么**：5 竞品 × 3 维度 = 36 节点，前端 launch 流程 + WebSocket 实时展示会过于复杂。**答辩场景下 CLI 启动 + 控制台日志 + 最终 Web 端打开看报告** 更合适。

**新增脚本**：

```python
# scripts/demo_ai_assistant.py
"""
国内 AI 助手 5 竞品 × 3 维度横评 demo

用法:
  python scripts/demo_ai_assistant.py
  python scripts/demo_ai_assistant.py --dimensions "核心玩法,Agent 能力"
"""
```

**展示流程**：
1. CLI 启动，打印 `Task created: <task_id>`
2. 后端按 DAG 跑（与现有 execute_mvp 路径一致）
3. 进度输出：每完成一个节点打印 `[Analyst] 豆包/核心玩法 - 完成 (12.3s)`
4. 跑完后打印 `View report: http://localhost:5000/task/<task_id>`
5. 评委点链接看报告 + TaskOverviewTab

### 决策 5：与"parse-end 放宽 spec"的关系

**底层能力（已 commit）**：[2026-06-07-parse-flexible-dimensions-design.md](./2026-06-07-parse-flexible-dimensions-design.md)
- 砍掉 parse 端 `dim_not_in_schema` 校验
- raw_response 不截断
- Writer 通用 prompt

**本 spec（垂直 demo 层）**：
- 复用底层能力
- 在底层之上叠 schema 多文件 + 7 维度 AI 助手 schema

**两个 spec 互不冲突**：
- 底层 spec 改动文件：`parse.py` / `writer.py` / `task_parser.py`
- 本 spec 改动文件：新增 `schemas/*.json` / `scripts/demo_ai_assistant.py` / `config.yaml`

**实施顺序**：底层 spec PR 1 → 本 spec PR 2。如果评审时间紧，本 spec 可**独立于底层 spec** 跑（因为新 schema 的 7 个维度都受 schema 约束，不依赖 parse 放宽）。

## 数据模型

**无新模型**。

现有 `DAGBlueprint` / `SchemaDefinition` / `DimensionSchema` 字段足够。每个 dimension 多了若干 `fields: list[str]`（用于质检规则校验），这是 `DimensionSchema` 的**新可选字段**：

```python
# backend/app/models/schema.py (新增字段)
class DimensionSchema(BaseModel):
    name: str
    description: str
    keywords: list[str] = []
    output_type: str = "table"  # table | paragraph
    evidence_threshold: int = 1
    tracking_sources: list[str] = ["web"]
    fields: list[dict] = []     # 新增：维度字段定义（含 type + 质检规则）
    quality_rules: list[str] = []  # 新增：LLM 写的质检规则文本
```

**字段示例**：

```json
{
  "name": "AI 模型能力",
  "fields": [
    {"name": "underlying_model", "type": "string", "required": true},
    {"name": "context_window", "type": "number", "min": 8000},
    {"name": "multimodal_capability", "type": "list"},
    {"name": "response_speed", "type": "number"}
  ],
  "quality_rules": [
    "context_window 必须是数字 ≥ 8000",
    "underlying_model 必须给出具体模型名或 '自研'/'接入'"
  ]
}
```

## API 设计

**无新端点**。

| 端点 | 变化 |
|------|------|
| `POST /api/tasks/parse` | 不变（受底层 spec 改动影响） |
| `POST /api/tasks` | 不变 |
| `GET /api/tasks/:id` | 报告内容**可能引用新字段**（`fields`），但展示层不强依赖 |

## 改动文件清单

**新增**：
- `backend/app/schema/loader.py` — `load_active_schema()` 替代 `load_default_schema()`
- `backend/app/schemas/general.json` — 现有 DEFAULT_SCHEMA 迁过来
- `backend/app/schemas/ai_assistant.json` — **核心新增**：7 维度 AI 助手 schema
- `backend/app/schemas/collab_office.json` — 占位空文件（未来 spec 用）
- `backend/app/schemas/__init__.py` — schema 包初始化
- `scripts/demo_ai_assistant.py` — demo 启动入口
- `scripts/demo_ai_assistant.yaml` — demo 配置
- `backend/tests/test_schema/test_multi_schema.py` — 多文件加载测试
- `backend/tests/test_schema/test_ai_assistant_schema.py` — 7 维度字段完整测试
- `backend/tests/test_e2e/test_ai_assistant_demo.py` — e2e（mock LLM）

**改动**：
- `backend/app/models/schema.py` — `DimensionSchema` 加 `fields` / `quality_rules` 字段
- `backend/app/schema/mvp_defaults.py` — 改为 `load_default_schema()` 调 loader，向下兼容
- `backend/app/config.yaml` — 加 `active_schema_id: "ai-assistant"`
- `backend/app/main.py` — 启动时加载 active schema（替代 DEFAULT_SCHEMA）
- `backend/app/api/parse.py` — 用 `load_active_schema()` 替代 `load_default_schema()`
- `backend/app/api/tasks.py` — `_load_dimensions()` 用 active schema
- `backend/app/engine/orchestrator.py` — `execute_mvp` 用 active schema 替代 `load_default_schema()`
- `CLAUDE.md` — 补 "垂直 demo 切换" 章节（讲 schema 切换机制）

**不动**：
- 前端
- `backend/app/agents/{collector,analyst,writer,reviewer}.py`（schema 重构后自然吃新维度）
- `backend/app/cleaner/`、`backend/app/llm/`

## 怎么算成功

| 维度 | 验收标准 |
|------|---------|
| **功能 1：多文件 Schema 加载** | `config.yaml` 改 `active_schema_id` 后，restart 服务，`load_active_schema()` 返回对应 schema，单测验证 3 种 schema 都能加载 |
| **功能 2：AI 助手 7 维度 Schema 完整** | `ai_assistant.json` 包含 7 维度、每维度 ≥ 2 个字段、每维度 ≥ 1 条质检规则；JSON 校验通过 |
| **功能 3：Demo 剧本跑通** | `python scripts/demo_ai_assistant.py` 跑 5 竞品 × 3 维度，36 节点全部 COMPLETED，报告 HTML 包含所有 5 竞品 × 3 维度 = 15 单元格 |
| **功能 4：现场追问 demo** | CLI 加 `--dimensions` 参数支持只跑指定维度；剩 4 维度（商业模式/用户社区/内容生态/安全合规）单跑也能出报告 |
| **回归：旧 3 维度不破** | `active_schema_id="general"` 时行为与改造前一致（飞书/钉钉/企微 demo 仍能跑） |
| **可观测** | 报告页可看到 5 竞品 × 3 维度的所有 trace + 推理链 + 引用源 |
| **测试** | 新增 ≥ 4 个测试全绿；现有 schema / parse / writer / orchestrator 测试全绿 |
| **代码** | 改动/新增文件 ≤ 20 个，新增代码 ≤ 800 行 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Schema 切到 AI 助手后，5 竞品的 7 维度全跑 **36 节点 ~ 15 分钟**，评委等不及 | 主 demo 只跑 3 维度（**15 collect + 15 analyze + 3 write + 3 review = 36 节点**，5-8 分钟）；4 维度追问 demo 单独跑 |
| 某些维度的 LLM 输出**质检规则不通过**（如 `user_sentiment` 没关键词） | 质检规则是**软约束**（记 trace warning 不阻塞任务），仅写报告时标注"⚠️ 数据不足"；UI 已支持 `data_insufficient` 渲染 |
| 豆包是字节自家，评委可能怀疑"夹带私货" | Schema 字段**对所有竞品一视同仁**（豆包不需要额外维度的额外字段），且每个字段都有可验证的数据源 |
| `fields` / `quality_rules` 字段改动影响现有 schema 文件 | `DimensionSchema` 新字段设 `default=[]`，向下兼容；现有 schema 文件不改 |
| 切 schema 后旧任务数据仍在 DB 里 | `trace_metrics` 表里 schema_id 不存，但 `node_id` 命名约定 `c_{竞品}_{维度}` 仍能识别；UI 无需改 |
| demo 跑超时 | 节点超时 3 分钟（已有 `NODE_TIMEOUT=180`）；LLM 慢就慢，不影响其他节点 |

## 依赖与顺序

```
1. models/schema.py: DimensionSchema 加 fields/quality_rules        [PR 2.1]
   ↓
2. schema/loader.py: load_active_schema() 实现 + mvp_defaults 兼容   [PR 2.1]
   ↓
3. schemas/general.json: 现有 DEFAULT_SCHEMA 迁过来                  [PR 2.1]
   ↓
4. PR 2.1 测试: test_multi_schema + test_general_schema             [PR 2.1]
   ↓
5. config.yaml: active_schema_id 字段 + ai_assistant.json 7 维度    [PR 2.2]
   ↓
6. orchestrator + tasks + parse: 用 load_active_schema              [PR 2.2]
   ↓
7. PR 2.2 测试: test_ai_assistant_schema                            [PR 2.2]
   ↓
8. scripts/demo_ai_assistant.py: CLI 入口 + YAML 配置              [PR 2.3]
   ↓
9. PR 2.3 测试: test_e2e_ai_assistant_demo (mock LLM)               [PR 2.3]
   ↓
10. 真实数据跑 demo: 飞书/钉钉/企微回归 + AI 助手主 demo            [PR 2.3]
   ↓
11. CLAUDE.md: 补"垂直 demo 切换"章节                              [PR 2.3]
```

预计实施时间：**2-3 周**（1 人），PR 2.1 约 3-5 天、PR 2.2 约 1 周（schema 设计 + 验证）、PR 2.3 约 3-5 天（demo 调通）。
