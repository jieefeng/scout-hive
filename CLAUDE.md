# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目是什么

多 Agent 协同的**竞品分析系统**，全链路：信息采集 → 结构化分析 → 报告渲染 → 审查反馈。

架构 = "1 大脑 + 1 心脏 + N 手脚"：
- **TaskParser**（大脑）：纯 AI，与用户对话，输出 DAG 蓝图
- **Orchestrator**（心脏）：纯代码调度引擎，按拓扑序执行 DAG，管理反馈循环
- **手脚**：Collector / Analyst / Writer / Reviewer，各司其职

当前 MVP 路径：`POST /api/tasks` 绕过 TaskParser，直接从竞品列表 + 默认 Schema 程序化构建 DAG，顺序执行节点。

## 绝对不能做的事

| 红线 | 原因 |
|------|------|
| AnySearch 用 `/v1/extract` 端点 | 不存在，只用 `/v1/search` |
| 取 AnySearch 结果用 `data.get("results")` | 正确路径是 `data.get("data", {}).get("results", [])` |
| 丢掉无 `quote` + `source_ref` 的 claim | 数据溯源铁律，无引用的 claim 直接丢弃 |
| 把 Cleaner 当 Agent | 它是基础设施中间件，不是 Agent |
| `print` 调试网络/编码问题 | 必须写文件验证 |
| 连续改多处不验证 | 每步修复后立即用独立脚本验证 |
| 直接 push 到 main | 通过 PR 合并 |
| 硬编码端口（后端 ≠ 5010 / 前端 ≠ 5000） | `config.yaml`、`start.bat`、`api/client.ts` 已统一 |

## 核心技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python + FastAPI + Pydantic v2 |
| 前端 | React 19 + TypeScript (strict) + React Flow v12 + Zustand v5 |
| LLM | 可插拔适配层（Claude / 百练 DashScope / OpenAI / Ollama），当前默认百练 qwen3.6-flash-2026-04-16 |
| 实时通信 | WebSocket + EventBus 内存发布订阅 |
| 数据清洗 | trafilatura |
| 持久化 | SQLite（StateManager 单例） |

## 目录结构

```
zijie/
├── backend/
│   ├── app/
│   │   ├── main.py              # 端口在 config.yaml（当前 5010）
│   │   ├── api/                 # REST/WebSocket 路由
│   │   ├── agents/             # TaskParser/Collector/Analyst/Writer/Reviewer
│   │   ├── engine/             # orchestrator/dag_parser/state_manager
│   │   ├── llm/                # base/claude/openai/bailian/local/registry
│   │   ├── models/             # dag/raw_data/analysis/trace/task/review
│   │   ├── cleaner/            # 数据清洗（非 Agent，是基础设施中间件）
│   │   └── config.yaml         # LLM/Server/DAG/AnySearch 配置
│   └── tests/
└── frontend/src/
    ├── pages/                  # Dashboard / TaskDetail
    └── components/             # DagViewer / AgentDetail / TraceBrowser / ...
```

## 启动命令

```bash
cd backend && uvicorn app.main:app --reload    # 默认端口 5010（config.yaml）
cd frontend && npm run dev                      # Vite dev server 端口 5000
```

一键启动：`start.bat`（后端端口 5010，前端端口 5000）

## 测试

```bash
cd backend && python -m pytest                          # 所有测试
cd backend && python -m pytest tests/test_engine/ -v   # 指定目录
cd backend && python -m pytest path/to/test.py::name -v # 指定函数
```

## 关键设计决策

### LLM 适配层
- `LLMAdapter` 抽象基类定义 `chat()` / `stream_chat()`
- `LLMRegistry` 工厂按配置创建适配器，支持按 Agent 绑定不同模型
- 四种实现：`ClaudeAdapter`、`OpenAIAdapter`、`BailianAdapter`（继承 OpenAI，走 DashScope）、`LocalAdapter`（Ollama）

### 数据溯源规则
- 每条 claim 必须带 `quote` + `source_ref`，无 quote 的 claim 直接丢弃
- `quote_type: "paraphrased"` 置信度权重 ×0.7

### 反馈边机制
- `feedback_edges` 与主 `edges` 分离，最大 3 轮循环，达到上限后 `escalation: "auto_approve"`

### Schema 系统
`backend/app/schema/mvp_defaults.py` 定义 `DEFAULT_SCHEMA`，包含分组和维度。每个维度有 keywords、output_type（table/paragraph）、evidence_threshold、tracking_sources。MVP 路径用它驱动 DAG 构建。

## 编码原则

### 1. 编码前思考
不要假设。不要隐藏困惑。呈现权衡。

- 明确说明假设 — 如果不确定，询问而不是猜测
- 呈现多种解释 — 当存在歧义时，不要默默选择
- 适时提出异议 — 如果存在更简单的方法，说出来
- 困惑时停下来 — 指出不清楚的地方并要求澄清

### 2. 简洁优先
用最少的代码解决问题。不要过度推测。

- 不要添加要求之外的功能
- 不要为一次性代码创建抽象
- 不要添加未要求的"灵活性"或"可配置性"
- 不要为不可能发生的场景做错误处理
- 如果 200 行代码可以写成 50 行，重写它

检验标准：资深工程师会觉得这过于复杂吗？如果是，简化。

### 3. 精准修改
只碰必须碰的。只清理自己造成的混乱。

编辑现有代码时：
- 不要"改进"相邻的代码、注释或格式
- 不要重构没坏的东西
- 匹配现有风格，即使你更倾向于不同的写法
- 如果注意到无关的死代码，提一下 —— 不要删除它

当你的改动产生孤儿代码时：
- 删除因你的改动而变得无用的导入/变量/函数
- 不要删除预先存在的死代码，除非被要求

检验标准：每一行修改都应该能直接追溯到用户的请求。

### 4. 目标驱动执行
定义成功标准。循环验证直到达成。

将指令式任务转化为可验证的目标：
- "添加验证" → "为无效输入编写测试，然后让它们通过"
- "修复 bug" → "编写重现 bug 的测试，然后让它通过"
- "重构 X" → "确保重构前后测试都能通过"

对于多步骤任务，说明一个简短的计划：
1. [步骤] → 验证: [检查]
2. [步骤] → 验证: [检查]
3. [步骤] → 验证: [检查]

## 开发规范

### 代码规范
- **后端**: 类型提示全覆盖，async/await 异步模式
- **前端**: TypeScript strict 模式，组件职责单一

### API 设计
- REST API 在 `backend/app/api/`，WebSocket 在 `api/websocket.py`
- 请求/响应模型用 Pydantic

### 状态管理
- `StateManager` 单例，SQLite 持久化（`backend/data/tasks.db`），支持断点续跑
- 管理任务 CRUD、节点状态更新、trace/review 存储、取消和进度计算
- 优雅 schema 迁移（ALTER TABLE + try/except）

### 事件总线
- `EventBus` 内存发布订阅，事件类型：`node_started`、`node_completed`、`node_failed`、`task_completed`、`review_feedback`、`task_stopped`
- WebSocket 广播给所有连接客户端，前端另外 3 秒轮询兜底

### 前端架构
- 路由：`/`（Dashboard）和 `/task/:taskId`（TaskDetail）
- 状态管理：Zustand store（`stores/taskStore.ts`）管理 tasks、currentTask、wsEvents
- API 客户端：`api/client.ts` 硬编码后端地址，REST 和 WebSocket 分开配置
- DAG 可视化：React Flow，节点 ID 格式 `c_{竞品}_{维度}`，颜色映射状态
- 样式：全部内联 style 对象，无 CSS modules

### Git 提交规范

#### Claude Code 提交（英文）

由于 Windows 环境下 bash 包装器对中文字符的兼容性问题，Claude Code 使用英文 commit 信息：

- 格式：`<type>: <description>`
- 类型：feat, fix, docs, refactor, test, chore, perf

#### 人类开发者提交（中文）

人类开发者手动提交时使用中文：

- 格式：`<类型>: <中文描述>`
- 类型：功能、修复、文档、重构、测试、构建、性能

#### Commit 模板配置

项目已配置 `.gitmessage` 模板文件，使用以下命令启用：

```bash
git config commit.template .gitmessage
```

每次提交聚焦单一改动（1 个 feature / 1 个 fix / 1 个 refactor）

## PR 规范

### 核心原则

- **每个 PR 只做一件事**：每个 PR 只实现或修改单一功能
- **鼓励小 PR**：尽可能小、粒度尽可能细的 PR
- **大功能拆分**：大功能应拆分为多个独立 PR 分步提交
- **主分支稳定**：PR 合并后，主分支代码需保持可运行状态

### PR 必需内容

#### 1. 标题格式（中文）
```
<类型>: <一句话说明本 PR 新增/修改了什么>
```
类型：功能、修复、文档、重构、测试、构建、性能

#### 2. 功能描述（中文）
- 说明该功能的作用与使用方式
- 明确用户如何使用该功能

#### 3. 实现思路（中文）
- 简要说明技术选型或核心实现逻辑
- 说明为什么选择这种实现方式

#### 4. 测试方式（中文）
- 如何验证该功能正常运行
- 提供具体的测试步骤或命令

### PR 描述模板

```markdown
## 功能描述
[详细说明该功能的作用与使用方式]

## 实现思路
[简要说明技术选型或核心实现逻辑]

## 测试方式
[如何验证该功能正常运行]

## 变更文件
- [列出主要修改的文件]
```

## 设计文档规范

### 核心原则

设计文档是决策记录，不是代码说明书。

### 结构要求

1. 先讲"为什么"（问题、动机）
2. 再讲"做什么"（目标、范围、不做什么）
3. 再讲"怎么做"（关键设计决策、为什么选这个方案）
4. 最后讲"怎么算成功"（成功标准）

### 禁止

- 不要在设计文档里堆代码实现细节
- 不要逐文件列出"改什么"（那是实现计划的事）
- 不要把设计文档写成技术说明书

### 比重

"为什么"和"做什么"占 70%，"怎么做"占 30%

## 排错指南

### AnySearch API
- 匿名请求（无 API Key）可用 IP 免费配额
- 搜索结果的 `content` 字段已含清洗后正文，SPA 页面直接抓取（trafilatura）无效
- 没有提取端点——页面正文靠搜索结果的 `content` 字段，URL 抓取靠 `trafilatura`

### 常见采集失败
1. API 响应结构判断错误 → 用实际调用验证，不推断
2. 目标页是 SPA → 直接 HTTP 抓取返回 0，用搜索结果的 `content`
3. LLM 生成的中文搜索词在 AnySearch CN zone 有时不返回结果

## 规则撰写原则

每条规则写入 CLAUDE.md 前，问自己：**"如果删掉这条，一个不了解本项目的高级工程师能不能凭常识做对？"**

- **能** → 删掉或泛化为原则性描述
- **不能** → 保留并写具体
