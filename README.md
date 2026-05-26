<p align="center">
  <h1 align="center">🐝 Scout Hive</h1>
  <p align="center">
    <strong>AI 驱动的多 Agent 竞品分析协作系统</strong><br>
    <em>AI-driven multi-agent competitive analysis system</em>
  </p>
  <p align="center">
    <a href="#中文">中文</a> · <a href="#english">English</a>
  </p>
</p>

---

## 中文

### 简介

Scout Hive 是一个多 Agent 协作系统，模拟数字调研小组，自动完成从公开信息采集到结构化竞品报告输出的全链路工作。

**核心理念**：1 个大脑 + 1 个心脏 + N 只手脚

- **TaskParser（大脑）**：AI 驱动，与用户对话，输出 DAG 执行蓝图
- **Orchestrator（心脏）**：纯代码调度引擎，按拓扑序执行 DAG，管理反馈循环
- **Collector / Analyst / Writer / Reviewer（手脚）**：AI + 工具，各司其职

### 功能特性

- **智能信息采集**：通过 AnySearch API 搜索公开信息，自动清洗和结构化
- **结构化竞品分析**：基于 Schema 驱动的多维度分析（功能对比、定价、市场定位等）
- **报告自动生成**：AI 撰写带数据溯源的竞品分析报告
- **审查反馈循环**：Reviewer 自动审查报告质量，反馈给 Writer 迭代优化（最多 3 轮）
- **全链路溯源**：每条结论附带 `quote` + `source_ref` + `reasoning_chain`
- **实时可视化**：DAG 执行状态实时展示，WebSocket 推送 + 轮询兜底
- **可插拔 LLM**：支持 Claude / 百练 DashScope / OpenAI / Ollama 本地模型

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python + FastAPI + Pydantic v2 |
| 前端 | React 19 + TypeScript (strict) + React Flow v12 + Zustand v5 |
| LLM | 可插拔适配层（Claude / 百练 / OpenAI / Ollama） |
| 实时通信 | WebSocket + EventBus 内存发布订阅 |
| 数据清洗 | trafilatura |
| 持久化 | SQLite |

### 快速开始

#### 环境要求

- Python 3.10+
- Node.js 18+
- LLM API Key（默认使用百练 DashScope）

#### 安装

```bash
# 克隆仓库
git clone git@github.com:jieefeng/scout-hive.git
cd scout-hive

# 后端依赖
cd backend
pip install -r requirements.txt

# 前端依赖
cd ../frontend
npm install
```

#### 配置

在 `backend/config.yaml` 中配置 LLM：

```yaml
llm:
  default: bailian
  adapters:
    bailian:
      type: bailian
      model: qwen3.6-flash
      api_key: ${DASHSCOPE_API_KEY}  # 设置环境变量
```

设置环境变量：

```bash
# Windows
set DASHSCOPE_API_KEY=your_api_key

# Linux/macOS
export DASHSCOPE_API_KEY=your_api_key
```

#### 启动

```bash
# 一键启动（Windows）
start.bat

# 或分别启动
cd backend && uvicorn app.main:app --reload    # 端口 5010
cd frontend && npm run dev                      # 端口 5000
```

访问 http://localhost:5000 打开前端界面。

### 项目结构

```
scout-hive/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── api/                 # REST/WebSocket 路由
│   │   ├── agents/             # 5 个 Agent 实现
│   │   ├── engine/             # Orchestrator / StateManager / DAGParser
│   │   ├── llm/                # LLM 适配层
│   │   ├── models/             # 数据模型
│   │   ├── cleaner/            # 数据清洗中间件
│   │   └── config.yaml         # 配置文件
│   └── tests/                  # 测试用例
└── frontend/
    └── src/
        ├── pages/              # Dashboard / TaskDetail
        └── components/         # DagViewer / AgentDetail / ...
```

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/tasks` | 创建竞品分析任务 |
| `GET` | `/api/tasks` | 获取所有任务 |
| `GET` | `/api/tasks/{id}` | 获取任务详情 |
| `POST` | `/api/tasks/{id}/stop` | 停止任务 |
| `WS` | `/ws` | WebSocket 实时事件 |

### 测试

```bash
cd backend
python -m pytest                    # 全部测试
python -m pytest tests/test_engine/ -v  # 指定目录
```

---

## English

### Introduction

Scout Hive is a multi-agent collaboration system that simulates a digital research team, automating the full pipeline from public intelligence gathering to structured competitive analysis reports.

**Core concept**: 1 Brain + 1 Heart + N Hands

- **TaskParser (Brain)**: AI-driven, converses with users and outputs DAG execution blueprints
- **Orchestrator (Heart)**: Pure code scheduling engine, executes DAGs in topological order, manages feedback loops
- **Collector / Analyst / Writer / Reviewer (Hands)**: AI + tools, each with dedicated responsibilities

### Features

- **Smart Intelligence Gathering**: Search public information via AnySearch API with automatic cleaning and structuring
- **Structured Competitive Analysis**: Schema-driven multi-dimensional analysis (feature comparison, pricing, market positioning, etc.)
- **Automated Report Generation**: AI writes competitive analysis reports with data provenance
- **Review Feedback Loop**: Reviewer automatically audits report quality, feeds back to Writer for iterative improvement (up to 3 rounds)
- **Full-chain Provenance**: Every claim includes `quote` + `source_ref` + `reasoning_chain`
- **Real-time Visualization**: Live DAG execution status with WebSocket push + polling fallback
- **Pluggable LLM**: Supports Claude / DashScope / OpenAI / Ollama local models

### Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python + FastAPI + Pydantic v2 |
| Frontend | React 19 + TypeScript (strict) + React Flow v12 + Zustand v5 |
| LLM | Pluggable adapter layer (Claude / DashScope / OpenAI / Ollama) |
| Real-time | WebSocket + EventBus in-memory pub/sub |
| Data Cleaning | trafilatura |
| Persistence | SQLite |

### Quick Start

#### Prerequisites

- Python 3.10+
- Node.js 18+
- LLM API Key (defaults to DashScope)

#### Installation

```bash
# Clone the repo
git clone git@github.com:jieefeng/scout-hive.git
cd scout-hive

# Backend dependencies
cd backend
pip install -r requirements.txt

# Frontend dependencies
cd ../frontend
npm install
```

#### Configuration

Configure LLM in `backend/config.yaml`:

```yaml
llm:
  default: bailian
  adapters:
    bailian:
      type: bailian
      model: qwen3.6-flash
      api_key: ${DASHSCOPE_API_KEY}  # Set as env var
```

Set environment variables:

```bash
# Windows
set DASHSCOPE_API_KEY=your_api_key

# Linux/macOS
export DASHSCOPE_API_KEY=your_api_key
```

#### Run

```bash
# One-click start (Windows)
start.bat

# Or start separately
cd backend && uvicorn app.main:app --reload    # Port 5010
cd frontend && npm run dev                      # Port 5000
```

Visit http://localhost:5000 to open the frontend.

### Project Structure

```
scout-hive/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── api/                 # REST/WebSocket routes
│   │   ├── agents/             # 5 agent implementations
│   │   ├── engine/             # Orchestrator / StateManager / DAGParser
│   │   ├── llm/                # LLM adapter layer
│   │   ├── models/             # Data models
│   │   ├── cleaner/            # Data cleaning middleware
│   │   └── config.yaml         # Configuration
│   └── tests/                  # Test cases
└── frontend/
    └── src/
        ├── pages/              # Dashboard / TaskDetail
        └── components/         # DagViewer / AgentDetail / ...
```

### API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/tasks` | Create a competitive analysis task |
| `GET` | `/api/tasks` | List all tasks |
| `GET` | `/api/tasks/{id}` | Get task details |
| `POST` | `/api/tasks/{id}/stop` | Stop a task |
| `WS` | `/ws` | WebSocket real-time events |

### Testing

```bash
cd backend
python -m pytest                         # All tests
python -m pytest tests/test_engine/ -v   # Specific directory
```

---

<p align="center">
  Made with 🐝 by <a href="https://github.com/jieefeng">jieefeng</a>
</p>
