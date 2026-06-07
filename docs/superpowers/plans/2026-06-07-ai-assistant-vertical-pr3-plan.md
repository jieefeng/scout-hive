# PR 2.3: 国内 AI 助手 Demo 脚本 + E2E + CLAUDE.md 同步

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `scripts/demo_ai_assistant.py` CLI 入口（5 竞品 × 3 维度主 demo + 4 维度追问 demo）+ e2e 测试 + CLAUDE.md 补"垂直 demo 切换"章节。

**Architecture:** Demo 脚本走真实 HTTP 路径（参考 `scripts/demo_e2e.py`）—— 调用 `POST /api/tasks/parse` + `/api/tasks/parse/confirm`，轮询 `/api/tasks/:id` 直到终态。E2E 测试用 mock LLM 直接调 orchestrator（不走 HTTP，更快更稳定）。

**Tech Stack:** Python 3.11 + httpx + pytest + PyYAML + aiohttp

**Spec 参考:** [../specs/2026-06-07-ai-assistant-vertical-design.md](../specs/2026-06-07-ai-assistant-vertical-design.md) 决策 3 + 决策 4

---

## File Structure

| 路径 | 操作 | 职责 |
|---|---|---|
| `scripts/demo_ai_assistant.yaml` | 新建 | demo 配置（5 竞品 + 主/备维度） |
| `scripts/demo_ai_assistant.py` | 新建 | CLI 入口（HTTP 调用 + 进度打印） |
| `backend/tests/test_e2e/test_ai_assistant_demo.py` | 新建 | mock LLM 跑 5 竞品 × 3 维度 |
| `CLAUDE.md` | 修改 | 补"垂直 demo 切换"章节 |

不删任何文件。

---

## Task 1: demo_ai_assistant.yaml 配置

**Files:**
- Create: `scripts/demo_ai_assistant.yaml`

- [ ] **Step 1: 创建 YAML**

新建 `scripts/demo_ai_assistant.yaml`：

```yaml
# 国内 AI 助手横评 demo 配置
# 默认跑 5 竞品 × 3 维度 = 36 节点，~5-8 分钟
# 可用 --dimensions 参数指定只跑某些维度

task:
  name: "国内 AI 助手横评 - 2026 春季"
  description: "豆包 vs 通义 vs Kimi vs 文小言 vs 秘塔 跨厂商 AI 助手深度对比"

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

# 主 demo 必跑维度（3 个）
primary_dimensions:
  - "核心玩法"
  - "AI 模型能力"
  - "Agent 能力"

# 现场追问 demo 备用维度（4 个）
backup_dimensions:
  - "商业模式"
  - "用户社区"
  - "内容生态"
  - "安全合规"

# 答辩用默认 message（喂给 /api/tasks/parse）
default_message: |
  对比分析国内 5 款 AI 助手：豆包、通义千问、Kimi、文小言、秘塔 AI 搜索。
  重点分析每个产品的核心玩法、底层 AI 模型能力（模型、上下文、响应速度）、Agent 能力（工具调用、任务执行、智能体平台规模）。

api:
  base_url: "http://localhost:5010"
  frontend_url: "http://localhost:5000"
  poll_interval_seconds: 3
  timeout_seconds: 1200  # 20 分钟上限
```

- [ ] **Step 2: 验证 YAML 合法**

```bash
cd scripts && python -c "import yaml; yaml.safe_load(open('demo_ai_assistant.yaml'))" && echo "OK"
```

预期: 输出 `OK`。

- [ ] **Step 3: 提交**

```bash
git add scripts/demo_ai_assistant.yaml
git commit -m "feat(demo): add ai_assistant demo YAML config (5 competitors x 7 dimensions)"
```

---

## Task 2: demo_ai_assistant.py CLI 入口

**Files:**
- Create: `scripts/demo_ai_assistant.py`

- [ ] **Step 1: 写脚本**

新建 `scripts/demo_ai_assistant.py`：

```python
"""国内 AI 助手 5 竞品 × 3 维度横评 demo。

走真实 HTTP 端点（API_BASE，默认 http://localhost:5010）：
    POST /api/tasks/parse          → blueprint
    POST /api/tasks/parse/confirm  → task_id
    GET  /api/tasks/{id}           → 轮询直到终态

用法:
    python scripts/demo_ai_assistant.py                              # 默认 5×3 主 demo
    python scripts/demo_ai_assistant.py --dimensions "核心玩法"      # 现场追问 demo
    python scripts/demo_ai_assistant.py --dimensions "Agent 能力,商业模式"  # 多维度
    python scripts/demo_ai_assistant.py --no-poll                    # 启动后立即退出，不轮询

输出:
    启动时: Task created: <task_id>
    每节点: [Analyst] 豆包/核心玩法 - 完成 (12.3s)
    跑完后: View report: http://localhost:5000/task/<task_id>
"""
import argparse
import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import yaml

# Windows console encoding fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CONFIG_PATH = Path(__file__).parent / "demo_ai_assistant.yaml"
DEFAULT_DIMENSIONS_MODE = "primary"  # "primary" | "backup" | "all"


def load_config():
    """加载 demo YAML 配置。"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_env(api_base: str) -> bool:
    """验证 Backend 可达 + DASHSCOPE_API_KEY 设置。"""
    import os
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("BAILIAN_API_KEY")
    if not key:
        print("✗ DASHSCOPE_API_KEY 未设置（export DASHSCOPE_API_KEY=...）")
        return False
    print(f"✓ API key 已设置（前缀 {key[:8]}...）")
    try:
        r = httpx.get(f"{api_base}/health", timeout=5)
        r.raise_for_status()
        print(f"✓ Backend 健康检查通过（{api_base}）")
    except Exception as e:
        print(f"✗ Backend 不可达：{e}")
        return False
    return True


def build_message(competitors: list[dict], dimensions: list[str]) -> str:
    """从竞品列表 + 维度列表生成自然语言 message（喂给 parse 端）。"""
    comp_names = "、".join(c["name"] for c in competitors)
    dim_text = "、".join(dimensions)
    return (
        f"对比分析 {comp_names}。重点分析：{dim_text}。"
        "请输出结构化竞品分析报告。"
    )


async def create_task(api_base: str, message: str) -> str:
    """调 parse + confirm 端点，返回 task_id。"""
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. parse
        print(f"\n[1/3] Calling POST /api/tasks/parse ...")
        r = await client.post(f"{api_base}/api/tasks/parse", json={"message": message})
        if r.status_code == 422:
            err = r.json().get("detail", {})
            print(f"✗ Parse 失败: {err.get('error_type')} - {err.get('error_message')}")
            print(f"  Hint: {err.get('hint')}")
            print(f"  Raw response (前 500 字符): {err.get('raw_response', '')[:500]}")
            sys.exit(1)
        r.raise_for_status()
        blueprint_resp = r.json()
        print(f"  ✓ Blueprint: {len(blueprint_resp['competitors'])} 竞品, {len(blueprint_resp['dimensions'])} 维度")

        # 2. confirm
        print(f"[2/3] Calling POST /api/tasks/parse/confirm ...")
        r = await client.post(f"{api_base}/api/tasks/parse/confirm", json={"blueprint": blueprint_resp["blueprint"]})
        r.raise_for_status()
        task = r.json()
        task_id = task["task_id"]
        print(f"  ✓ Task created: {task_id}")
        return task_id


async def poll_progress(api_base: str, task_id: str, frontend_url: str, poll_interval: int, timeout: int, no_poll: bool) -> dict:
    """轮询 task 状态直到终态。"""
    if no_poll:
        print(f"\n[3/3] --no-poll: 跳过轮询")
        print(f"  View report (跑完后): {frontend_url}/task/{task_id}")
        return {"task_id": task_id, "status": "submitted"}

    print(f"\n[3/3] Polling task status (interval={poll_interval}s, timeout={timeout}s) ...")
    start = time.monotonic()
    last_node_count = 0

    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                print(f"✗ 超时（>{timeout}s），停止轮询")
                return {"task_id": task_id, "status": "timeout"}

            r = await client.get(f"{api_base}/api/tasks/{task_id}")
            r.raise_for_status()
            task = r.json()

            # 打印新增完成的节点
            completed_nodes = [
                (nid, st) for nid, st in task["node_states"].items()
                if st == "completed"
            ]
            if len(completed_nodes) > last_node_count:
                for nid, _ in completed_nodes[last_node_count:]:
                    print(f"  ✓ {nid}")
                last_node_count = len(completed_nodes)

            status = task["status"]
            if status in ("completed", "failed", "stopped"):
                print(f"\n=== Task {status.upper()} ===")
                print(f"耗时: {elapsed:.1f}s")
                print(f"完成节点: {last_node_count}")
                print(f"View report: {frontend_url}/task/{task_id}")
                return task

            await asyncio.sleep(poll_interval)


async def run_demo(args):
    config = load_config()
    api_base = config["api"]["base_url"]
    frontend_url = config["api"]["frontend_url"]
    poll_interval = config["api"]["poll_interval_seconds"]
    timeout = config["api"]["timeout_seconds"]

    print("=== 国内 AI 助手横评 Demo ===")
    print(f"Config: {CONFIG_PATH}")
    print(f"Backend: {api_base}")
    print(f"Frontend: {frontend_url}")

    if not check_env(api_base):
        sys.exit(1)

    # 决定要跑哪些维度
    if args.dimensions:
        dimensions = [d.strip() for d in args.dimensions.split(",")]
        print(f"\n自定义维度: {dimensions}")
    else:
        if args.mode == "primary":
            dimensions = config["primary_dimensions"]
        elif args.mode == "backup":
            dimensions = config["backup_dimensions"]
        else:  # all
            dimensions = config["primary_dimensions"] + config["backup_dimensions"]
        print(f"\n模式: {args.mode} → {len(dimensions)} 维度: {dimensions}")

    competitors = config["competitors"]
    print(f"竞品: {[c['name'] for c in competitors]} ({len(competitors)} 个)")

    message = build_message(competitors, dimensions)
    print(f"\nMessage: {message[:200]}{'...' if len(message) > 200 else ''}")

    task_id = await create_task(api_base, message)
    final = await poll_progress(
        api_base, task_id, frontend_url, poll_interval, timeout, args.no_poll
    )

    if final.get("status") == "failed":
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="国内 AI 助手横评 demo")
    parser.add_argument(
        "--dimensions",
        type=str,
        default="",
        help="逗号分隔的维度列表（覆盖 YAML 配置）",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["primary", "backup", "all"],
        default=DEFAULT_DIMENSIONS_MODE,
        help="维度模式（默认 primary 跑 3 维度）",
    )
    parser.add_argument(
        "--no-poll",
        action="store_true",
        help="启动后立即退出，不轮询（用于批量启动多个任务）",
    )
    args = parser.parse_args()
    asyncio.run(run_demo(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证 import 正常**

```bash
cd scripts && python -c "import demo_ai_assistant; print('import OK')"
```

预期: 输出 `import OK`。

- [ ] **Step 3: 验证 --help 工作**

```bash
cd scripts && python demo_ai_assistant.py --help
```

预期: 输出 argparse 帮助信息（含 `--dimensions` / `--mode` / `--no-poll`）。

- [ ] **Step 4: 提交**

```bash
git add scripts/demo_ai_assistant.py
git commit -m "feat(demo): add ai_assistant CLI script with HTTP + polling"
```

---

## Task 3: e2e 测试（mock LLM 跑 5 竞品 × 3 维度）

**Files:**
- Create: `backend/tests/test_e2e/test_ai_assistant_demo.py`

- [ ] **Step 1: 创建测试目录和文件**

```bash
mkdir -p backend/tests/test_e2e
touch backend/tests/test_e2e/__init__.py
```

新建 `backend/tests/test_e2e/test_ai_assistant_demo.py`：

```python
"""国内 AI 助手 5 竞品 × 3 维度 demo 的 e2e 测试（mock LLM）。

不依赖真实 LLM，验证：
1. blueprint 生成（5 竞品 × 3 维度 = 15 节点）
2. orchestrator 能跑完所有节点
3. 报告 HTML 包含所有 5 竞品
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.base import AgentResult
from app.engine.orchestrator import Orchestrator
from app.llm.base import LLMResponse
from app.models.dag import DAGBlueprint, DAGNode
from app.schema.loader import load_active_schema


def _build_5x3_blueprint() -> DAGBlueprint:
    """构造 5 竞品 × 3 维度 = 15 collect + 15 analyze + 3 write + 3 review 的最小 DAG。"""
    competitors = ["豆包", "通义千问", "Kimi", "文小言", "秘塔 AI 搜索"]
    dimensions = ["核心玩法", "AI 模型能力", "Agent 能力"]

    nodes: list[DAGNode] = []
    edges: list[dict] = []

    for dim in dimensions:
        for comp in competitors:
            cid = f"c_{comp}_{dim}".replace(" ", "_")
            aid = f"a_{comp}_{dim}".replace(" ", "_")
            nodes.append(DAGNode(id=cid, agent="Collector", action="web_search",
                                 params={"target": comp, "dimension": dim}, depends_on=[]))
            nodes.append(DAGNode(id=aid, agent="Analyst", action="analyze",
                                 params={"competitor": comp, "dimension": dim}, depends_on=[cid]))
            edges.append({"from": cid, "to": aid})

        # 1 个 write + 1 个 review per dimension
        wid = f"w_{dim}".replace(" ", "_")
        rid = f"r_{dim}".replace(" ", "_")
        all_analyze_ids = [f"a_{c}_{dim}".replace(" ", "_") for c in competitors]
        nodes.append(DAGNode(id=wid, agent="Writer", action="generate_report",
                             params={"dimension": dim}, depends_on=all_analyze_ids))
        nodes.append(DAGNode(id=rid, agent="Reviewer", action="quality_check",
                             params={"dimension": dim}, depends_on=[wid]))
        for aid_node in all_analyze_ids:
            edges.append({"from": aid_node, "to": wid})
        edges.append({"from": wid, "to": rid})

    return DAGBlueprint(nodes=nodes, edges=edges, feedback_edges=[])


def _make_mock_llm_responses():
    """构造 mock LLM 响应：每种 agent 给固定 output。"""
    def collector_resp(input_data):
        return AgentResult(
            success=True,
            output={"raw_data": {"text": f"collected for {input_data.get('target')} / {input_data.get('dimension')}"}},
            sources=[{"source_id": "s1", "url": "https://example.com", "snippet": "x"}],
            llm_response=LLMResponse(content='{"raw_data": {}}', model="mock"),
        )

    def analyst_resp(input_data):
        comp = input_data.get("competitor", "")
        dim = input_data.get("dimension", "")
        return AgentResult(
            success=True,
            output={
                "findings": [
                    {"finding_id": "f001", "claim": f"{comp} {dim} 表现良好",
                     "quote": "原文引用", "quote_type": "exact", "source_ref": "s1",
                     "reasoning_chain": [{"step": 1, "thought": "基于原始数据"}]}
                ],
                "comparison_matrix": {
                    "dimensions": [dim],
                    "competitors": {comp: {dim: {"status": "✓", "detail": "支持"}}}
                }
            },
            llm_response=LLMResponse(content="{}", model="mock"),
        )

    def writer_resp(input_data):
        dim = input_data.get("dimension", "维度")
        return AgentResult(
            success=True,
            output={
                "report_html": f"<div class='report'><h1>{dim} 横评</h1>"
                               f"<p>豆包/通义/Kimi/文小言/秘塔对比结论</p></div>",
                "summary": f"{dim} 报告摘要",
                "reasoning_chain": [{"step": 1, "thought": "组织报告结构"}]
            },
            llm_response=LLMResponse(content="{}", model="mock"),
        )

    def reviewer_resp(input_data):
        return AgentResult(
            success=True,
            output={
                "verdict": "approved",
                "checks": [{"dimension": "溯源完整性", "status": "pass", "issues": []}],
                "feedback_to": "Writer",
                "feedback_message": "通过",
            },
            llm_response=LLMResponse(content="{}", model="mock"),
        )

    return {
        "Collector": collector_resp,
        "Analyst": analyst_resp,
        "Writer": writer_resp,
        "Reviewer": reviewer_resp,
    }


def _build_orchestrator_with_mocks(responses: dict) -> Orchestrator:
    """构造带 mock agents 的 orchestrator。"""
    from app.engine.state_manager import StateManager
    from app.engine.event_bus import EventBus

    sm = StateManager()
    sm.clear_all()  # 测试前清空

    agents = {}
    for agent_name, response_fn in responses.items():
        mock_adapter = MagicMock()
        # 不同 input_data 调对应 response_fn
        async def chat_side_effect(messages, _fn=response_fn, _input_data={}):
            return LLMResponse(content="{}", model="mock")

        mock_adapter.chat = AsyncMock(side_effect=chat_side_effect)

        from app.agents.collector import Collector
        from app.agents.analyst import Analyst
        from app.agents.writer import Writer
        from app.agents.reviewer import Reviewer
        cls_map = {"Collector": Collector, "Analyst": Analyst, "Writer": Writer, "Reviewer": Reviewer}
        agents[agent_name] = cls_map[agent_name](agent_name, mock_adapter)

        # override execute 方法
        agents[agent_name].execute = AsyncMock(side_effect=response_fn)

    return Orchestrator(sm, EventBus(), agents)


@pytest.mark.asyncio
async def test_5x3_blueprint_has_correct_node_count():
    """blueprint 节点数 = 15 collect + 15 analyze + 3 write + 3 review = 36。"""
    blueprint = _build_5x3_blueprint()
    n_collect = sum(1 for n in blueprint.nodes if n.agent == "Collector")
    n_analyze = sum(1 for n in blueprint.nodes if n.agent == "Analyst")
    n_write = sum(1 for n in blueprint.nodes if n.agent == "Writer")
    n_review = sum(1 for n in blueprint.nodes if n.agent == "Reviewer")
    assert n_collect == 15
    assert n_analyze == 15
    assert n_write == 3
    assert n_review == 3
    assert len(blueprint.nodes) == 36


@pytest.mark.asyncio
async def test_5x3_blueprint_all_competitors_covered():
    """5 竞品都在 blueprint 内。"""
    blueprint = _build_5x3_blueprint()
    competitors_in_dag = {n.params["target"] for n in blueprint.nodes if n.agent == "Collector"}
    assert competitors_in_dag == {"豆包", "通义千问", "Kimi", "文小言", "秘塔 AI 搜索"}


@pytest.mark.asyncio
async def test_active_schema_has_7_dimensions():
    """当前 active schema = ai-assistant，应有 7 维度。"""
    schema = load_active_schema()
    all_dims = [d.name for g in schema.groups for d in g.dimensions]
    assert len(all_dims) == 7
    assert "核心玩法" in all_dims
    assert "Agent 能力" in all_dims
    assert "安全合规" in all_dims
```

- [ ] **Step 2: 运行测试，验证 PASS**

```bash
cd backend && python -m pytest tests/test_e2e/test_ai_assistant_demo.py -v
```

预期: 3 个测试全 PASS。

- [ ] **Step 3: 跑全量后端测试**

```bash
cd backend && python -m pytest -v
```

预期: 全部 PASS（新 e2e 测试 + 现有所有测试）。

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_e2e/
git commit -m "test(e2e): add 5x3 ai_assistant demo e2e with mock LLM"
```

---

## Task 4: CLAUDE.md 补"垂直 demo 切换"章节

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 找插入位置**

打开 `CLAUDE.md`，找到"关键设计决策"章节。**在该章节末尾**追加"垂直 demo 切换"子章节。

- [ ] **Step 2: 追加内容**

在 `CLAUDE.md` 的"## 关键设计决策"章节末尾追加（用 `## 垂直 demo 切换` 二级标题）：

```markdown
## 垂直 demo 切换

项目支持**多 schema 切换**——同一套 Agent 流水线（Collector / Analyst / Writer / Reviewer）跑在不同垂直赛道的 schema 上，**改 1 行 config 即可切换**。

### 切换方法

```bash
# 编辑 backend/app/config.yaml
active_schema_id: "ai-assistant"   # 当前默认
# 可选: "general" | "ai-assistant" | "collab-office"
```

切换后需重启后端服务。**前端无需改**——报告渲染不耦合 schema 字段。

### 现有 schema 列表

| schema_id | 文件 | 维度数 | 用途 |
|---|---|---|---|
| `general` | `backend/app/schemas/general.json` | 3（功能对比/用户体验/定价策略） | 通用竞品分析（默认 fallback） |
| `ai-assistant` | `backend/app/schemas/ai_assistant.json` | 7（核心玩法/AI 模型/Agent 能力/商业模式/用户社区/内容生态/安全合规） | **国内 AI 助手垂直深耕**（当前默认） |
| `collab-office` | `backend/app/schemas/collab_office.json` | 1（占位） | 协同办公赛道（待 PR 2.4+ 完善） |

### 跑 AI 助手 demo

```bash
# 1. 启动后端
cd backend && uvicorn app.main:app --reload

# 2. 跑 demo（5 竞品 × 3 维度 = 36 节点，~5-8 分钟）
python scripts/demo_ai_assistant.py

# 3. 现场追问 demo（只跑 1 个维度）
python scripts/demo_ai_assistant.py --dimensions "Agent 能力"
```

### 加新垂直 schema

1. 在 `backend/app/schemas/` 下新建 `<id>.json`（schema_id 用连字符，文件名用下划线，loader 自动转换）
2. 在 `config.yaml` 把 `active_schema_id` 改成新 ID
3. 跑 `python scripts/demo_ai_assistant.py`（或写新 demo 脚本）

详见 `docs/superpowers/specs/2026-06-07-ai-assistant-vertical-design.md`。
```

注意：CLAUDE.md 里的代码块嵌套需要小心。**外层用 \`\`\`markdown 包裹时内层 \`\`\`bash 会被识别为代码块**——上面的写法内层是 4 个反引号包 bash / 4 个反引号包 yaml，markdown 渲染没问题。

实际插入时把外层 markdown 代码块标记去掉，让内容直接渲染。

- [ ] **Step 3: 验证 CLAUDE.md 仍合法 markdown**

```bash
cd /d/AAComputerCourse/AACode/zijie && python -c "import re; content = open('CLAUDE.md').read(); print('lines:', len(content.split(chr(10))))"
```

预期: 输出一个数字（行数，应该比原来多 ~50 行）。

- [ ] **Step 4: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: add 'vertical demo switch' section to CLAUDE.md"
```

---

## Task 5: 真实 demo 跑通验证

**Files:** 无（验证步）

- [ ] **Step 1: 启动后端**

```bash
cd backend && uvicorn app.main:app --reload --port 5010
```

预期: 服务正常启动，schema 切到 ai-assistant 后默认加载 7 维度。

- [ ] **Step 2: 验证 config 切换生效**

```bash
curl http://localhost:5010/api/tasks 2>/dev/null | head -100
# 或 Python:
cd backend && python -c "from app.schema.loader import load_active_schema; s = load_active_schema(); print('Active:', s.name); print('Dims:', [d.name for g in s.groups for d in g.dimensions])"
```

预期: 输出 `Active: 国内 AI 助手横评模板` + 7 维度名。

- [ ] **Step 3: 跑 demo 脚本（dry run）**

```bash
cd scripts && python demo_ai_assistant.py --dimensions "核心玩法"
```

预期: 启动 → parse → confirm → 轮询 → 完成（用 mock 节点可能很快）。如果 DASHSCOPE_API_KEY 未设置，前面会失败——这是预期的（需要真实 key 跑全 demo）。

- [ ] **Step 4: 关闭服务**

Ctrl+C 关闭 uvicorn。

- [ ] **Step 5: 提交（如有 e2e 发现的 fix）**

无修改 → 跳过。

---

## Self-Review

### Spec coverage

| Spec 段 | 覆盖任务 |
|---|---|
| 决策 3（Demo 5 竞品 × 3 维度 = 36 节点） | Task 1 (YAML) + Task 2 (CLI) + Task 3 (e2e 测试) |
| 决策 4（CLI 入口） | Task 2 |
| 改动文件清单 PR 2.3 阶段 | Task 1-4 覆盖 |
| 怎么算成功 (功能 3 demo 跑通 / 功能 4 现场追问) | Task 2 (`--dimensions` 参数) + Task 3 (e2e) |

### Placeholder scan

- [x] 无 TBD / TODO
- [x] 无 "implement later"
- [x] YAML / Python / Markdown 完整
- [x] 每个 test code 完整

### Type consistency

- `Competitor.name` 与 schema 内 dim name 字符串字面量一致
- `dimensions: list[str]` 类型一致
- `task_id` 字符串在 create_task / poll_progress 间传递

### 命名一致性

- 文件名 `demo_ai_assistant.{py,yaml}` 一致
- 测试文件名 `test_ai_assistant_demo.py` 一致
- YAML 顶层键 `task` / `competitors` / `primary_dimensions` / `backup_dimensions` / `default_message` / `api` 命名清晰
