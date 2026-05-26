# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 规则撰写原则

每条规则写入 CLAUDE.md 前，问自己：**"如果删掉这条，一个不了解本项目的高级工程师能不能凭常识做对？"**

- **能** → 删掉或泛化为原则性描述
- **不能** → 保留并写具体（如"用 @TransactionalEventListener 不用 Kafka""查数据必须带 OrganizationTag"）

## 项目概述

- **路径**: `D:\AAComputerCourse\AACode\zijie`
- **架构**: "1 大脑 + 1 心脏 + N 手脚" — TaskParser(AI) + Orchestrator(代码) + {Collector, Analyst, Writer, Reviewer}
- **核心功能**: 多 Agent 协同完成竞品分析全链路：信息采集 → 结构化分析 → 报告渲染 → 审查反馈

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python + FastAPI + Pydantic v2 |
| 前端 | React 19 + TypeScript (strict) + React Flow (@xyflow/react) v12 + Zustand v5 |
| LLM | 可插拔适配层（Claude / 百练 DashScope / OpenAI / Ollama 本地） |
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

> **端口规范**: 后端 5010，前端 5000。`config.yaml`、`start.bat`、`api/client.ts` 已统一。

## 测试

```bash
cd backend && python -m pytest                          # 所有测试
cd backend && python -m pytest tests/test_engine/ -v   # 指定目录
cd backend && python -m pytest path/to/test.py::name -v # 指定函数
```

## 关键设计决策

### Agent 驱动方式
- **TaskParser**: 纯 AI，与用户对话，输出 DAG 蓝图
- **Orchestrator**: 纯代码调度引擎，按拓扑序执行 DAG，管理反馈循环
- **Collector/Analyst/Writer/Reviewer**: AI + 工具

### MVP 执行路径（当前 API 使用）
当前 `POST /api/tasks` 绕过 TaskParser，直接从竞品列表 + 默认 Schema 程序化构建 DAG，然后调用 `Orchestrator.execute_mvp()`。MVP 路径顺序执行节点（非并行拓扑），每个节点注入维度配置（keywords、evidence_threshold、output_type）。

### LLM 适配层
- `LLMAdapter` 抽象基类定义 `chat()` / `stream_chat()`
- `LLMRegistry` 工厂按配置创建适配器，支持按 Agent 绑定不同模型
- 四种实现：`ClaudeAdapter`、`OpenAIAdapter`、`BailianAdapter`（继承 OpenAI，走 DashScope）、`LocalAdapter`（Ollama）
- 当前所有 Agent 默认用百练（qwen3.6-flash）

### 数据溯源规则
- 每条 claim 必须带 `quote` + `source_ref`，无 quote 的 claim 直接丢弃
- `quote_type: "paraphrased"` 置信度权重 ×0.7

### 反馈边机制
- `feedback_edges` 与主 `edges` 分离，最大 3 轮循环，达到上限后 `escalation: "auto_approve"`

### Cleaner 定位
- **不是 Agent**，是基础设施层中间件，在 Collector 和 Analyst 之间自动运行

### Schema 系统
`backend/app/schema/mvp_defaults.py` 定义 `DEFAULT_SCHEMA`，包含分组和维度。每个维度有 keywords、output_type（table/paragraph）、evidence_threshold、tracking_sources。MVP 路径用它驱动 DAG 构建。

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

### Git 规范
- 每次提交聚焦单一改动（1 个 feature / 1 个 fix / 1 个 refactor）
- 不直接 push 到 main，通过 PR 合并

## 排错指南

### AnySearch API
- **只用 `/v1/search`**，不存在 `/v1/extract`
- **响应结构**: `{"code": 0, "data": {"results": [...]}}`，取结果时必须用 `data.get("data", {}).get("results", [])`，不是顶层 `data.get("results", [])`
- 匿名请求（无 API Key）可用 IP 免费配额
- 搜索结果的 `content` 字段已含清洗后正文，SPA 页面直接抓取（trafilatura）无效
- 没有提取端点——页面正文靠搜索结果的 `content` 字段，URL 抓取靠 `trafilatura`

### 调试原则
- 网络/编码问题**必须写文件**验证，不用 `print` 到终端
- 每步修复后立即用独立脚本验证，不连续改多处
- 组件边界加日志，401/404 等错误码能快速定位

### 常见采集失败
1. API 响应结构判断错误 → 用实际调用验证，不推断
2. 目标页是 SPA → 直接 HTTP 抓取返回 0，用搜索结果的 `content`
3. LLM 生成的中文搜索词在 AnySearch CN zone 有时不返回结果