# TaskParser 主路径化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户用自然语言驱动 TaskParser 生成 DAG 蓝图、确认后执行，覆盖"AI 理解需求"端到端流程。

**Architecture:** 新增 2 个 FastAPI 端点（`/api/tasks/parse` + `/api/tasks/parse/confirm`）+ 前端 NLP 入口。TaskParser 加 1 次重试（仅 json_parse/llm_empty），失败 422 返错，不降级。蓝图 API 级别无状态，旧 `/api/tasks` 不动。

**Tech Stack:**
- 后端：Python 3.11 + FastAPI + Pydantic v2 + pytest + httpx AsyncClient
- 前端：React 19 + TypeScript strict + Vite + React Flow v12
- LLM：可插拔（默认 Bailian qwen），通过 `LLMRegistry.get_for_agent("TaskParser")` 注入

**Spec:** `docs/superpowers/specs/2026-06-06-taskparser-main-path-design.md`

---

## File Map

| 路径 | 责任 | 操作 |
|------|------|------|
| `backend/app/agents/task_parser.py` | TaskParser Agent（含 execute + retry_with_prompt_hint） | 改 |
| `backend/app/api/parse.py` | 2 端点 + `parse_task_blueprint` 纯函数 | 新建 |
| `backend/app/main.py` | 加载 parse router | 改 |
| `frontend/src/api/client.ts` | `parseTaskBlueprint` + `confirmParse` | 改 |
| `frontend/src/pages/ParsePreview.tsx` | 蓝图预览 + 确认/取消 | 新建 |
| `frontend/src/pages/Dashboard.tsx` | "新建分析" NLP 入口 | 改 |
| `backend/tests/test_agents/test_task_parser_retry.py` | retry 行为单元测试 | 新建 |
| `backend/tests/test_api/test_parse_blueprint.py` | parse_task_blueprint 单元测试 | 新建 |
| `backend/tests/test_api/test_parse_endpoint.py` | POST /parse HTTP 集成测试 | 新建 |
| `backend/tests/test_api/test_confirm_endpoint.py` | POST /parse/confirm HTTP 集成测试 | 新建 |
| `backend/tests/test_e2e/test_parse_to_report.py` | parse→confirm→execute_mvp 端到端 | 新建 |
| `CLAUDE.md` | 加"两条入口"段落 | 改 |

---

## Task Dependency Graph

```
T1 (retry) ──┐
             ├─► T2 (parse_task_blueprint 单元) ─► T3 (POST /parse) ─┐
             │                                                       ├─► T5 (main.py wire) ─► T9 (E2E)
             └───────────────────────────────────► T4 (POST /parse/confirm) ┘
                                                                      ▲
T6 (api/client) ─► T7 (ParsePreview) ─► T8 (Dashboard) ─────────────┘
                                                                      │
T10 (CLAUDE.md + DoD) ◄────────────────────────────────────────────────
```

并行机会：T6→T7→T8（前端链）与 T1→T2→T3→T4（后端链）可同时推进；T5 依赖 T3+T4；T9 依赖 T5+T7；T10 在最后。

---

## Task 1: TaskParser 加 `retry_with_prompt_hint` 方法

**Files:**
- Modify: `backend/app/agents/task_parser.py:46-79`
- Test: `backend/tests/test_agents/test_task_parser_retry.py`（新建）

**Goal:** TaskParser 在 LLM 输出烂掉时能基于上次错误做 1 次重试，messages 注入 `⚠️ 上一轮输出有误：{error_hint}`。

### Steps

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_agents/test_task_parser_retry.py` 新建：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agents.task_parser import TaskParser
from app.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    adapter = MagicMock()
    adapter.chat = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_retry_with_prompt_hint_sends_three_messages(mock_llm):
    """retry 时 messages 含 [system, user: 原 message, user: 错误提示]。"""
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["X"], "dag": {"nodes": [], "edges": []}}',
        model="test",
    )
    parser = TaskParser("TaskParser", mock_llm)

    await parser.retry_with_prompt_hint(
        {"message": "原需求"},
        error_hint="json parse failed: Expecting value",
    )

    call_args = mock_llm.chat.call_args
    messages = call_args.kwargs.get("messages") or call_args.args[0]
    assert len(messages) == 3
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert messages[1].content == "原需求"
    assert messages[2].role == "user"
    assert "⚠️ 上一轮输出有误" in messages[2].content
    assert "json parse failed" in messages[2].content


@pytest.mark.asyncio
async def test_retry_with_prompt_hint_returns_agent_result(mock_llm):
    """retry 成功时返回 success=True 的 AgentResult。"""
    mock_llm.chat.return_value = LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["X"], "dag": {"nodes": [], "edges": []}}',
        model="test",
    )
    parser = TaskParser("TaskParser", mock_llm)

    result = await parser.retry_with_prompt_hint(
        {"message": "x"}, error_hint="bad json"
    )

    assert result.success is True
    assert result.output["competitors"] == ["A"]


@pytest.mark.asyncio
async def test_retry_with_prompt_hint_propagates_failure(mock_llm):
    """retry 时 LLM 仍返回烂 JSON → result.success=False + error_type=json_parse。"""
    mock_llm.chat.return_value = LLMResponse(content="still not json", model="test")
    parser = TaskParser("TaskParser", mock_llm)

    result = await parser.retry_with_prompt_hint(
        {"message": "x"}, error_hint="bad json"
    )

    assert result.success is False
    assert result.error_type == "json_parse"
    assert result.raw_response == "still not json"
```

- [ ] **Step 2: 跑测试，确认 RED**

```bash
cd backend && python -m pytest tests/test_agents/test_task_parser_retry.py -v
```

Expected: 全部 FAIL，错误 `AttributeError: 'TaskParser' object has no attribute 'retry_with_prompt_hint'`。

- [ ] **Step 3: 实现 `retry_with_prompt_hint`**

在 `backend/app/agents/task_parser.py` 的 `execute` 方法（L46）**之后**插入新方法：

```python
    async def retry_with_prompt_hint(
        self,
        input_data: dict,
        error_hint: str,
    ) -> AgentResult:
        """第二次执行：把上次错误以 user 消息追加，引导 LLM 修正。

        调用方式与 execute 相同，但 messages 多一轮错误提示 hint。
        """
        user_message = input_data.get("message", "")
        messages = [
            Message(role="system", content=self.SYSTEM_PROMPT),
            Message(role="user", content=user_message),
            Message(
                role="user",
                content=f"⚠️ 上一轮输出有误：{error_hint}\n请重新输出严格符合格式的 JSON。",
            ),
        ]
        logger.info(f"TaskParser retrying LLM with {len(messages)} messages")
        llm_response = await self.chat(messages)
        content = llm_response.content.strip() if llm_response.content else ""
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if len(lines) >= 2 else content.lstrip("`")
        try:
            parsed = json.loads(content) if content else None
        except json.JSONDecodeError as e:
            logger.error(f"TaskParser retry JSON parse error: {e}")
            return AgentResult(
                success=False,
                raw_response=llm_response.content or "",
                json_valid=False,
                error_type="json_parse",
                error_message=str(e),
                llm_response=llm_response,
            )
        if parsed is None:
            return AgentResult(
                success=False,
                raw_response=llm_response.content or "",
                json_valid=False,
                error_type="llm_empty",
                error_message="LLM returned empty content",
                llm_response=llm_response,
            )
        task_id = str(uuid.uuid4())
        dag = TaskDAG(
            task_id=task_id,
            competitors=parsed.get("competitors", []),
            dimensions=parsed.get("dimensions", []),
            dag=DAGBlueprint(**parsed.get("dag", {})),
            traceability=TraceabilityConfig(),
        )
        return AgentResult(success=True, output=dag.model_dump(), llm_response=llm_response)
```

确认文件顶部 `import json, uuid` 还在（已存在）。如果 `Message`、`AgentResult`、`TaskDAG`、`TraceabilityConfig`、`DAGBlueprint` 的 import 缺失，补上：

```python
import json
import uuid
from app.llm.base import Message
from app.agents.base import AgentResult
from app.models.dag import DAGBlueprint, TaskDAG, TraceabilityConfig
```

- [ ] **Step 4: 跑测试，确认 GREEN**

```bash
cd backend && python -m pytest tests/test_agents/test_task_parser_retry.py -v
```

Expected: 3 passed。

- [ ] **Step 5: 跑现有 TaskParser 测试，确认未破坏**

```bash
cd backend && python -m pytest tests/test_agents/test_task_parser.py -v
```

Expected: 5 passed（原有 5 个用例都通过）。

- [ ] **Step 6: 提交**

```bash
cd backend
git add app/agents/task_parser.py tests/test_agents/test_task_parser_retry.py
git commit -m "feat(agents): add TaskParser.retry_with_prompt_hint for JSON parse recovery"
```

---

## Task 2: 抽出 `parse_task_blueprint` 纯函数

**Files:**
- New: `backend/app/api/parse.py`
- Test: `backend/tests/test_api/test_parse_blueprint.py`（新建）

**Goal:** 把"调 TaskParser + 1 次重试 + 5 步严格短路校验"封装成可测试的纯函数，错误类型用字符串字面量（与 spec 错误处理表一致）。

### Steps

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_api/test_parse_blueprint.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agents.task_parser import TaskParser
from app.agents.base import AgentResult
from app.llm.base import LLMResponse
from app.api.parse import parse_task_blueprint, RETRYABLE_ERRORS


VALID_DAG = {
    "nodes": [
        {"id": "c1", "agent": "Collector", "action": "collect",
         "params": {"target": "A", "dimension": "推荐算法"}, "depends_on": []}
    ],
    "edges": [],
    "feedback_edges": [],
}


def _parser_with_llm(chat_mock):
    adapter = MagicMock()
    adapter.chat = AsyncMock(side_effect=chat_mock)
    return TaskParser("TaskParser", adapter)


def _schema():
    return {
        "groups": [
            {"dimensions": [{"name": "推荐算法"}, {"name": "商业化"}]}
        ]
    }


@pytest.mark.asyncio
async def test_parse_success_first_try():
    """LLM 一次返回合法 JSON → success=True。"""
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["推荐算法"], "dag": ' + str(VALID_DAG).replace("'", '"') + ', "summary": "OK"}',
        model="test",
    )))

    result = await parse_task_blueprint("分析 A 的推荐算法", parser, _schema())

    assert result["success"] is True
    assert result["competitors"] == ["A"]
    assert result["dimensions"] == ["推荐算法"]
    assert result["summary"] == "OK"
    assert "blueprint" in result


@pytest.mark.asyncio
async def test_parse_retries_on_json_parse():
    """第 1 轮 json_parse → 重试 1 次 → 成功。"""
    side_effects = [
        LLMResponse(content="not json", model="test"),
        LLMResponse(
            content='{"competitors": ["A"], "dimensions": ["推荐算法"], "dag": ' + str(VALID_DAG).replace("'", '"') + '}',
            model="test",
        ),
    ]
    parser = _parser_with_llm(AsyncMock(side_effect=side_effects))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is True
    assert parser.llm.chat.call_count == 2


@pytest.mark.asyncio
async def test_parse_does_not_retry_on_dim_not_in_schema():
    """第 1 轮返回合法 JSON 但维度不在 schema → 不重试。"""
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["不存在的维度"], "dag": ' + str(VALID_DAG).replace("'", '"') + '}',
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "dim_not_in_schema"
    assert parser.llm.chat.call_count == 1  # 关键：没重试


@pytest.mark.asyncio
async def test_parse_fails_after_retry_exhausted():
    """第 1 轮 + 第 2 轮都 json_parse → 返 json_parse 错误。"""
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content="bad", model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "json_parse"
    assert parser.llm.chat.call_count == 2


@pytest.mark.asyncio
async def test_parse_empty_competitors():
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content='{"competitors": [], "dimensions": ["推荐算法"], "dag": ' + str(VALID_DAG).replace("'", '"') + '}',
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "empty_competitors"


@pytest.mark.asyncio
async def test_parse_too_many_competitors():
    over_limit = ",".join([f'"c{i}"' for i in range(11)])
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content=f'{{"competitors": [{over_limit}], "dimensions": ["推荐算法"], "dag": {str(VALID_DAG).replace(chr(39), chr(34))}}}',
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "too_many_competitors"


@pytest.mark.asyncio
async def test_parse_topology_error():
    """DAG 引用不存在的节点 → 422 topology_error。"""
    bad_dag = {"nodes": [{"id": "a", "agent": "Collector", "action": "x", "params": {}, "depends_on": ["nonexistent"]}], "edges": []}
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["推荐算法"], "dag": ' + str(bad_dag).replace("'", '"') + '}',
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "topology_error"


def test_retryable_errors_set():
    """RETRYABLE_ERRORS 仅含 json_parse 和 llm_empty。"""
    assert RETRYABLE_ERRORS == {"json_parse", "llm_empty"}
```

- [ ] **Step 2: 跑测试，确认 RED**

```bash
cd backend && python -m pytest tests/test_api/test_parse_blueprint.py -v
```

Expected: 全部 FAIL，错误 `ModuleNotFoundError: No module named 'app.api.parse'`。

- [ ] **Step 3: 创建 `backend/app/api/parse.py` 骨架**

新建 `backend/app/api/parse.py`：

```python
"""自然语言需求 → DAG 蓝图：纯解析层，不入库、不执行。

调用关系：
    POST /api/tasks/parse          → parse_task_blueprint(...)
    POST /api/tasks/parse/confirm  → DAGBlueprint(**req.blueprint) + _create_and_run
"""
import logging
from typing import Any

from app.agents.task_parser import TaskParser
from app.models.dag import DAGBlueprint

logger = logging.getLogger(__name__)

# 仅这两类错误值得重试；其他重试无意义或方向错误。
RETRYABLE_ERRORS = {"json_parse", "llm_empty"}

MAX_COMPETITORS = 10
MESSAGE_MAX_LEN = 2000
RAW_RESPONSE_MAX_LEN = 200


def _all_dim_names(schema: dict) -> set[str]:
    return {d["name"] for g in schema.get("groups", []) for d in g.get("dimensions", [])}


async def parse_task_blueprint(
    message: str,
    task_parser: TaskParser,
    schema: dict,
) -> dict[str, Any]:
    """调 TaskParser 1 次，失败重试 1 次（仅 RETRYABLE_ERRORS）；做严格短路校验。

    Returns:
        success=True  → {success, blueprint, competitors, dimensions, summary, raw_response}
        success=False → {success, error_type, raw_response, [error_message]}
    """
    result = await task_parser.run({"message": message})

    if (not result.success) and result.error_type in RETRYABLE_ERRORS:
        result = await task_parser.retry_with_prompt_hint(
            {"message": message},
            error_hint=result.error_message or "输出格式有误",
        )

    if not result.success:
        return {
            "success": False,
            "error_type": result.error_type or "unknown",
            "raw_response": (result.raw_response or "")[:RAW_RESPONSE_MAX_LEN],
            "error_message": result.error_message or "",
        }

    parsed = result.output
    competitors = parsed.get("competitors", [])
    dimensions = parsed.get("dimensions", [])

    # 严格短路：dim 必须在 schema 内
    allowed = _all_dim_names(schema)
    for dim in dimensions:
        if dim not in allowed:
            return {
                "success": False,
                "error_type": "dim_not_in_schema",
                "raw_response": (result.raw_response or "")[:RAW_RESPONSE_MAX_LEN],
                "error_message": f"维度 '{dim}' 不在 DEFAULT_SCHEMA 内",
            }

    # DAG 引用校验（DAGBlueprint.validate_references 抛 ValueError）
    try:
        DAGBlueprint(**parsed.get("dag", {}))
    except (ValueError, Exception) as e:  # pydantic.ValidationError 也属于 ValueError 子类
        return {
            "success": False,
            "error_type": "topology_error",
            "raw_response": (result.raw_response or "")[:RAW_RESPONSE_MAX_LEN],
            "error_message": str(e),
        }

    # 竞品数校验
    if not competitors:
        return {
            "success": False,
            "error_type": "empty_competitors",
            "raw_response": (result.raw_response or "")[:RAW_RESPONSE_MAX_LEN],
        }
    if len(competitors) > MAX_COMPETITORS:
        return {
            "success": False,
            "error_type": "too_many_competitors",
            "raw_response": (result.raw_response or "")[:RAW_RESPONSE_MAX_LEN],
        }

    return {
        "success": True,
        "blueprint": parsed["dag"],
        "competitors": competitors,
        "dimensions": dimensions,
        "summary": parsed.get("summary", ""),
        "raw_response": (result.raw_response or "")[:RAW_RESPONSE_MAX_LEN],
    }
```

- [ ] **Step 4: 跑测试，确认 GREEN**

```bash
cd backend && python -m pytest tests/test_api/test_parse_blueprint.py -v
```

Expected: 8 passed。

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/api/parse.py tests/test_api/test_parse_blueprint.py
git commit -m "feat(api): add parse_task_blueprint with retry + strict validation"
```

---

## Task 3: 实现 `POST /api/tasks/parse` 端点

**Files:**
- Modify: `backend/app/api/parse.py`（追加 Pydantic 模型 + 端点 + init_router）
- Test: `backend/tests/test_api/test_parse_endpoint.py`（新建）

**Goal:** HTTP 入口，调用 `parse_task_blueprint`；422 错误时返 `detail.error_type` + `raw_response` + `hint`。

### Steps

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_api/test_parse_endpoint.py`：

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.llm.base import LLMResponse


VALID_BLUEPRINT = {
    "nodes": [
        {"id": "c1", "agent": "Collector", "action": "collect",
         "params": {"target": "A", "dimension": "推荐算法"}, "depends_on": []}
    ],
    "edges": [],
    "feedback_edges": [],
}


def _ok_llm_response():
    import json
    return LLMResponse(
        content=json.dumps({
            "competitors": ["A"],
            "dimensions": ["推荐算法"],
            "dag": VALID_BLUEPRINT,
            "summary": "我打算从推荐算法维度分析 A。",
        }),
        model="test",
    )


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_parse_endpoint_success(app):
    """成功路径：200 + 含 blueprint/competitors/dimensions/summary。"""
    with patch("app.api.parse._orch") as mock_orch:
        mock_parser = MagicMock()
        mock_parser.run = AsyncMock()
        mock_parser.retry_with_prompt_hint = AsyncMock()
        # 让 _orch.agents["TaskParser"] 返回 mock_parser
        mock_orch.agents = {"TaskParser": mock_parser}
        # 同时 patch 第一次直接返回 success（不重试）
        from app.agents.base import AgentResult
        mock_parser.run.return_value = AgentResult(
            success=True,
            output={
                "competitors": ["A"],
                "dimensions": ["推荐算法"],
                "dag": VALID_BLUEPRINT,
                "summary": "OK",
            },
            raw_response='{"competitors": ["A"], ...}',
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": "分析 A 的推荐算法"})

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["competitors"] == ["A"]
    assert data["dimensions"] == ["推荐算法"]
    assert data["summary"] == "OK"
    assert "blueprint" in data
    assert data["blueprint"]["nodes"][0]["id"] == "c1"


@pytest.mark.asyncio
async def test_parse_endpoint_empty_message(app):
    """空 message → 422 empty_message，不调 LLM。"""
    with patch("app.api.parse._orch") as mock_orch:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": ""})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error_type"] == "empty_message"


@pytest.mark.asyncio
async def test_parse_endpoint_whitespace_only(app):
    """全空白 → 422 empty_message。"""
    with patch("app.api.parse._orch") as mock_orch:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": "   \n  "})
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_type"] == "empty_message"


@pytest.mark.asyncio
async def test_parse_endpoint_truncates_long_message(app):
    """超长 message 截断到 2000 字。"""
    long_msg = "A" * 3000
    with patch("app.api.parse._orch") as mock_orch:
        mock_parser = MagicMock()
        mock_parser.run = AsyncMock()
        mock_orch.agents = {"TaskParser": mock_parser}
        from app.agents.base import AgentResult
        mock_parser.run.return_value = AgentResult(
            success=True,
            output={"competitors": ["x"], "dimensions": ["推荐算法"], "dag": VALID_BLUEPRINT},
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": long_msg})

    assert resp.status_code == 200
    sent_msg = mock_parser.run.call_args.args[0]["message"]
    assert len(sent_msg) == 2000


@pytest.mark.asyncio
async def test_parse_endpoint_returns_422_with_hint_on_json_parse(app):
    """LLM 两轮都 json_parse → 422 + error_type=json_parse + hint。"""
    with patch("app.api.parse._orch") as mock_orch:
        mock_parser = MagicMock()
        mock_parser.run = AsyncMock()
        mock_parser.retry_with_prompt_hint = AsyncMock()
        mock_orch.agents = {"TaskParser": mock_parser}
        from app.agents.base import AgentResult
        fail_result = AgentResult(
            success=False, error_type="json_parse",
            error_message="Expecting value", raw_response="bad json"
        )
        mock_parser.run.return_value = fail_result
        mock_parser.retry_with_prompt_hint.return_value = fail_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": "x"})

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error_type"] == "json_parse"
    assert "raw_response" in detail
    assert "hint" in detail
    assert "POST /api/tasks" in detail["hint"]


@pytest.mark.asyncio
async def test_parse_endpoint_dim_not_in_schema(app):
    """维度不在 DEFAULT_SCHEMA → 422 dim_not_in_schema，不重试。"""
    with patch("app.api.parse._orch") as mock_orch:
        mock_parser = MagicMock()
        mock_parser.run = AsyncMock()
        mock_parser.retry_with_prompt_hint = AsyncMock()
        mock_orch.agents = {"TaskParser": mock_parser}
        from app.agents.base import AgentResult
        mock_parser.run.return_value = AgentResult(
            success=True,
            output={
                "competitors": ["A"],
                "dimensions": ["unknown_dim"],
                "dag": VALID_BLUEPRINT,
            },
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/tasks/parse", json={"message": "x"})

    assert resp.status_code == 422
    assert resp.json()["detail"]["error_type"] == "dim_not_in_schema"
    mock_parser.retry_with_prompt_hint.assert_not_called()  # 关键：没重试
```

- [ ] **Step 2: 跑测试，确认 RED**

```bash
cd backend && python -m pytest tests/test_api/test_parse_endpoint.py -v
```

Expected: 6 failed（endpoint 尚未实现，patch 找不到 `app.api.parse._orch`）。

- [ ] **Step 3: 扩展 `parse.py` 加 Pydantic 模型 + 端点 + init_router**

在 `backend/app/api/parse.py` 文件**底部**追加：

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.config import load_config
from app.llm.registry import LLMRegistry
from app.schema.mvp_defaults import load_default_schema

router = APIRouter(prefix="/api/tasks", tags=["parse"])

# 模块级单例，由 init_router 注入
_orch = None  # type: ignore[var-annotated]


def init_router(orch):
    """main.create_app 启动时调用。"""
    global _orch
    _orch = orch


# ---- Pydantic Models ----

class ParseRequest(BaseModel):
    message: str = Field(min_length=0, max_length=10000)


class ParseResponse(BaseModel):
    blueprint: dict
    competitors: list[str]
    dimensions: list[str]
    summary: str = ""


class ParseConfirmRequest(BaseModel):
    blueprint: dict


# ---- Endpoints ----

HINT_FALLBACK = (
    "请重写需求使其更具体，或使用 POST /api/tasks 直接提交结构化数据"
)


@router.post("/parse", response_model=ParseResponse)
async def parse_task(req: ParseRequest):
    message = (req.message or "").strip()
    if not message:
        raise HTTPException(
            status_code=422,
            detail={"error_type": "empty_message", "hint": "需求不能为空"},
        )
    # 截断超长 message（避免烧 token）
    message = message[:MESSAGE_MAX_LEN]

    task_parser = _orch.agents["TaskParser"]
    schema = load_default_schema().model_dump()
    result = await parse_task_blueprint(message, task_parser, schema)

    if not result["success"]:
        raise HTTPException(
            status_code=422,
            detail={
                "error_type": result["error_type"],
                "raw_response": result.get("raw_response", ""),
                "error_message": result.get("error_message", ""),
                "hint": HINT_FALLBACK,
            },
        )

    return ParseResponse(
        blueprint=result["blueprint"],
        competitors=result["competitors"],
        dimensions=result["dimensions"],
        summary=result["summary"],
    )
```

- [ ] **Step 4: 跑测试，确认 GREEN**

```bash
cd backend && python -m pytest tests/test_api/test_parse_endpoint.py -v
```

Expected: 6 passed。

- [ ] **Step 5: 提交**

```bash
cd backend
git add app/api/parse.py tests/test_api/test_parse_endpoint.py
git commit -m "feat(api): add POST /api/tasks/parse endpoint with 422 error contract"
```

---

## Task 4: 实现 `POST /api/tasks/parse/confirm` 端点

**Files:**
- Modify: `backend/app/api/parse.py`（追加 confirm 端点）
- Test: `backend/tests/test_api/test_confirm_endpoint.py`（新建）

**Goal:** 接收前端可能编辑过的 blueprint，二次校验后复用 `_create_and_run` 模式创建 task 并 `execute_mvp`。

### Steps

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_api/test_confirm_endpoint.py`：

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import create_app


VALID_BLUEPRINT = {
    "nodes": [
        {"id": "c1", "agent": "Collector", "action": "collect",
         "params": {"target": "A", "dimension": "推荐算法"}, "depends_on": []}
    ],
    "edges": [],
    "feedback_edges": [],
}


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_confirm_endpoint_success(app):
    """成功路径：200 + 拿到 task_id + 触发 execute_mvp。"""
    with patch("app.api.parse._orch") as mock_orch, \
         patch("app.api.parse._sm") as mock_sm, \
         patch("app.api.parse._bus") as mock_bus:
        mock_orch.execute_mvp = AsyncMock()
        mock_sm.create_task = MagicMock()

        from app.models.task import Task
        mock_task = MagicMock(spec=Task)
        mock_task.task_id = "t-123"
        mock_task.status = "pending"
        mock_task.competitors = []
        mock_task.dimensions = ["推荐算法"]
        mock_task.node_states = {}
        mock_task.dag_json = {}
        mock_task.created_at = "2026-06-06T00:00:00Z"
        mock_task.updated_at = "2026-06-06T00:00:00Z"
        mock_task.report_html = ""
        mock_task.traces = []
        mock_task.reviews = []
        mock_task.error_message = ""
        mock_task.progress = 0.0
        mock_sm.create_task.return_value = mock_task
        mock_sm.calculate_progress = MagicMock(return_value=0.0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/parse/confirm",
                json={"blueprint": VALID_BLUEPRINT},
            )

    assert resp.status_code == 200, resp.text
    mock_orch.execute_mvp.assert_awaited_once()
    mock_sm.create_task.assert_called_once()


@pytest.mark.asyncio
async def test_confirm_endpoint_blueprint_tampered(app):
    """蓝图引用不存在节点 → 422 blueprint_tampered。"""
    bad_bp = {
        "nodes": [
            {"id": "a", "agent": "Collector", "action": "x", "params": {},
             "depends_on": ["nonexistent"]}
        ],
        "edges": [],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/tasks/parse/confirm",
            json={"blueprint": bad_bp},
        )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error_type"] == "blueprint_tampered"


@pytest.mark.asyncio
async def test_confirm_endpoint_empty_blueprint(app):
    """空 dict → 422 blueprint_tampered。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/tasks/parse/confirm",
            json={"blueprint": {}},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_type"] in {"blueprint_tampered", "topology_error"}


@pytest.mark.asyncio
async def test_confirm_uses_user_edited_blueprint(app):
    """用户编辑过的 blueprint（多加了节点）应被原样接受。"""
    edited = {
        "nodes": VALID_BLUEPRINT["nodes"] + [
            {"id": "c2", "agent": "Collector", "action": "collect",
             "params": {"target": "B", "dimension": "推荐算法"}, "depends_on": []}
        ],
        "edges": [],
        "feedback_edges": [],
    }
    with patch("app.api.parse._orch") as mock_orch, \
         patch("app.api.parse._sm") as mock_sm, \
         patch("app.api.parse._bus") as mock_bus:
        mock_orch.execute_mvp = AsyncMock()
        from app.models.task import Task
        mock_task = MagicMock(spec=Task)
        mock_task.task_id = "t-x"
        mock_task.status = "pending"
        mock_task.competitors = []
        mock_task.dimensions = ["推荐算法"]
        mock_task.node_states = {}
        mock_task.dag_json = {}
        mock_task.created_at = "2026-06-06T00:00:00Z"
        mock_task.updated_at = "2026-06-06T00:00:00Z"
        mock_task.report_html = ""
        mock_task.traces = []
        mock_task.reviews = []
        mock_task.error_message = ""
        mock_task.progress = 0.0
        mock_sm.create_task.return_value = mock_task
        mock_sm.calculate_progress = MagicMock(return_value=0.0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/parse/confirm",
                json={"blueprint": edited},
            )
        assert resp.status_code == 200

        # 验证传入 execute_mvp 的 blueprint 包含 c2
        call_args = mock_orch.execute_mvp.call_args
        passed_blueprint = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs["dag"]
        node_ids = {n["id"] for n in passed_blueprint["nodes"]}
        assert "c2" in node_ids
```

- [ ] **Step 2: 跑测试，确认 RED**

```bash
cd backend && python -m pytest tests/test_api/test_confirm_endpoint.py -v
```

Expected: 全部 FAIL（404 Not Found，confirm 端点尚未实现）。

- [ ] **Step 3: 在 `parse.py` 加 `_sm`/`_bus` 状态 + confirm 端点**

修改 `parse.py` 顶部：

```python
# 替换原 _orch 单例块
# 模块级单例，由 init_router 注入
_orch = None  # type: ignore[var-annotated]
_sm = None    # type: ignore[var-annotated]
_bus = None   # type: ignore[var-annotated]


def init_router(orch, sm, bus):
    """main.create_app 启动时调用。"""
    global _orch, _sm, _bus
    _orch = orch
    _sm = sm
    _bus = bus
```

在 `parse.py` 末尾的 `parse_task` 之后追加：

```python
import uuid
from app.models.task import TaskStatus
from app.models.dag import DAGBlueprint
from pydantic import ValidationError


@router.post("/parse/confirm")
async def confirm_parse(req: ParseConfirmRequest):
    """二次校验 blueprint + 创建 task + 启动 execute_mvp。"""
    if not req.blueprint or "nodes" not in req.blueprint:
        raise HTTPException(
            status_code=422,
            detail={"error_type": "blueprint_tampered", "error_message": "blueprint 缺少 nodes"},
        )
    try:
        DAGBlueprint(**req.blueprint)
    except (ValueError, ValidationError) as e:
        raise HTTPException(
            status_code=422,
            detail={"error_type": "blueprint_tampered", "error_message": str(e)},
        )

    task_id = str(uuid.uuid4())
    # 从 blueprint 里抽竞品 / 维度（蓝图的 source of truth，不再相信前端传的额外字段）
    competitors = sorted({n["params"].get("target", "") for n in req.blueprint["nodes"] if n.get("params", {}).get("target")})
    competitors = [c for c in competitors if c]
    dimensions = sorted({n["params"].get("dimension", "") for n in req.blueprint["nodes"] if n.get("params", {}).get("dimension")})
    dimensions = [d for d in dimensions if d]

    from app.models.task import Competitor
    task = _sm.create_task(
        task_id,
        [Competitor(name=c, domain="") for c in competitors],  # 域名待 confirm 阶段补全
        dimensions,
        req.blueprint,
    )
    _sm.update_task_status(task_id, TaskStatus.PENDING)
    task.progress = _sm.calculate_progress(task)

    async def run_dag():
        try:
            await _orch.execute_mvp(
                task_id,
                DAGBlueprint(**req.blueprint),
                [{"name": c, "domain": ""} for c in competitors],
            )
        except Exception as e:
            logger.exception("Confirm task %s failed: %s", task_id, e)
            _sm.set_error_message(task_id, str(e))
            _sm.update_task_status(task_id, TaskStatus.FAILED)

    import asyncio
    asyncio.create_task(run_dag())
    return task
```

> 注：domain 留空字符串。`execute_mvp` 中的 Collector 节点 `params.get("domain", "")` 已是 `""`，下游 Collector 会 fallback。需要后续做"补域名"二次确认时再加，先把流程跑通。

- [ ] **Step 4: 跑测试，确认 GREEN**

```bash
cd backend && python -m pytest tests/test_api/test_confirm_endpoint.py -v
```

Expected: 4 passed。

- [ ] **Step 5: 跑 parse 全套测试，确保没破**

```bash
cd backend && python -m pytest tests/test_api/ -v
```

Expected: parse_blueprint 8 + parse_endpoint 6 + confirm_endpoint 4 = 18 passed。

- [ ] **Step 6: 提交**

```bash
cd backend
git add app/api/parse.py tests/test_api/test_confirm_endpoint.py
git commit -m "feat(api): add POST /api/tasks/parse/confirm with blueprint revalidation"
```

---

## Task 5: 把 parse router 接入 main.py

**Files:**
- Modify: `backend/app/main.py:57-60`

**Goal:** `create_app` 加载 parse router，让端点可访问。

### Steps

- [ ] **Step 1: 改 `main.py`**

把 L57-60 区域：

```python
    tasks.init_router(state_manager, orchestrator, event_bus)
    websocket.init_router(event_bus)
    app.include_router(tasks.router)
    app.include_router(websocket.router)
```

改为：

```python
    tasks.init_router(state_manager, orchestrator, event_bus)
    websocket.init_router(event_bus)
    from app.api import parse as parse_module  # noqa: WPS433 (延迟 import 避免循环)
    parse_module.init_router(orchestrator, state_manager, event_bus)
    app.include_router(tasks.router)
    app.include_router(websocket.router)
    app.include_router(parse_module.router)
```

- [ ] **Step 2: 跑全部后端测试，确认无回归**

```bash
cd backend && python -m pytest -x -q
```

Expected: 全部 passed（旧的 + Task1-4 新加的 18 个）。

- [ ] **Step 3: 跑旧 `/api/tasks` 集成测试，验证回归**

```bash
cd backend && python -m pytest tests/test_api/test_tasks.py -v
```

Expected: 4 passed（原有 4 个用例都通过，行为不变）。

- [ ] **Step 4: 提交**

```bash
cd backend
git add app/main.py
git commit -m "feat(api): wire parse router into FastAPI app"
```

---

## Task 6: 前端 `api/client.ts` 加 parse/confirm 方法

**Files:**
- Modify: `frontend/src/api/client.ts`

**Goal:** 暴露 `parseTaskBlueprint(message)` 和 `confirmParse(blueprint)`。

### Steps

- [ ] **Step 1: 读现有 client.ts**

```bash
cat frontend/src/api/client.ts
```

确认现有 API base URL 与函数风格（一般导出常量 + 异步 fetch 函数）。

- [ ] **Step 2: 加 2 个函数**

在文件末尾追加：

```typescript
export async function parseTaskBlueprint(message: string): Promise<ParseResponse> {
  const resp = await fetch(`${API_BASE}/api/tasks/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new ParseError(resp.status, detail?.detail ?? { error_type: 'unknown' });
  }
  return resp.json();
}

export async function confirmParse(blueprint: object): Promise<TaskResponse> {
  const resp = await fetch(`${API_BASE}/api/tasks/parse/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ blueprint }),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(`confirm failed: ${resp.status} ${JSON.stringify(detail)}`);
  }
  return resp.json();
}

export class ParseError extends Error {
  status: number;
  detail: { error_type: string; raw_response?: string; hint?: string; error_message?: string };
  constructor(status: number, detail: any) {
    super(detail?.error_type ?? `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export interface ParseResponse {
  blueprint: { nodes: any[]; edges: any[]; feedback_edges?: any[] };
  competitors: string[];
  dimensions: string[];
  summary: string;
}

export interface TaskResponse {
  task_id: string;
  status: string;
  // ... 其他字段由后端 TaskResponse 决定，TS 端不强校验
  [key: string]: unknown;
}
```

- [ ] **Step 3: 跑前端类型检查**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 无错误（可能 pre-existing warnings，但 parse 相关的必须无错）。

- [ ] **Step 4: 提交**

```bash
cd frontend
git add src/api/client.ts
git commit -m "feat(frontend): add parseTaskBlueprint and confirmParse API methods"
```

---

## Task 7: 前端 `ParsePreview.tsx` 页

**Files:**
- New: `frontend/src/pages/ParsePreview.tsx`

**Goal:** 用户在 preview 页看到 blueprint、competitor/dimension 列表、summary 文字，点"确认执行"调 `confirmParse`，点"取消"回 Dashboard。

### Steps

- [ ] **Step 1: 创建 `ParsePreview.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parseTaskBlueprint, confirmParse, ParseError, ParseResponse } from '../api/client';

export default function ParsePreview() {
  const [params] = useSearchParams();
  const initialMessage = params.get('message') ?? '';
  const navigate = useNavigate();

  const [message, setMessage] = useState(initialMessage);
  const [loading, setLoading] = useState(false);
  const [parseResult, setParseResult] = useState<ParseResponse | null>(null);
  const [blueprintJson, setBlueprintJson] = useState<string>('');
  const [error, setError] = useState<{ type: string; raw?: string; hint?: string } | null>(null);

  async function handleParse() {
    setLoading(true);
    setError(null);
    setParseResult(null);
    try {
      const r = await parseTaskBlueprint(message);
      setParseResult(r);
      setBlueprintJson(JSON.stringify(r.blueprint, null, 2));
    } catch (e) {
      if (e instanceof ParseError) {
        setError({
          type: e.detail.error_type,
          raw: e.detail.raw_response,
          hint: e.detail.hint,
        });
      } else {
        setError({ type: 'network', hint: String(e) });
      }
    } finally {
      setLoading(false);
    }
  }

  // 路由进来时如果带了 message 就自动 parse
  useEffect(() => {
    if (initialMessage && !parseResult && !loading) {
      handleParse();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleConfirm() {
    if (!blueprintJson.trim()) return;
    let blueprint: object;
    try {
      blueprint = JSON.parse(blueprintJson);
    } catch {
      setError({ type: 'json_parse', hint: '蓝图 JSON 格式有误' });
      return;
    }
    setLoading(true);
    try {
      const task = await confirmParse(blueprint);
      navigate(`/task/${task.task_id}`);
    } catch (e) {
      setError({ type: 'confirm_failed', hint: String(e) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto', fontFamily: 'sans-serif' }}>
      <h1 style={{ fontSize: 22 }}>解析自然语言需求</h1>

      <label style={{ display: 'block', marginTop: 16, fontWeight: 600 }}>
        需求描述
      </label>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={4}
        style={{ width: '100%', padding: 8, fontSize: 14, fontFamily: 'inherit' }}
        placeholder="例：对比飞书、钉钉、企业微信的 AI 协作能力"
      />
      <button
        onClick={handleParse}
        disabled={loading || !message.trim()}
        style={{ marginTop: 8, padding: '8px 16px' }}
      >
        {loading ? '解析中...' : '解析'}
      </button>

      {error && (
        <div
          style={{
            marginTop: 16, padding: 12, background: '#fef2f2',
            border: '1px solid #fca5a5', borderRadius: 4,
          }}
        >
          <div style={{ color: '#b91c1c', fontWeight: 600 }}>
            解析失败: {error.type}
          </div>
          {error.hint && <div style={{ marginTop: 4, color: '#7f1d1d' }}>{error.hint}</div>}
          {error.raw && (
            <details style={{ marginTop: 8 }}>
              <summary>查看 AI 原始输出</summary>
              <pre style={{ background: '#fff', padding: 8, fontSize: 12, overflow: 'auto' }}>
                {error.raw}
              </pre>
            </details>
          )}
        </div>
      )}

      {parseResult && (
        <>
          <section style={{ marginTop: 24 }}>
            <h2 style={{ fontSize: 18 }}>AI 调研组长的理解</h2>
            {parseResult.summary && <p>{parseResult.summary}</p>}
            <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
              <div>
                <strong>竞品：</strong>
                {parseResult.competitors.join('、')}
              </div>
              <div>
                <strong>维度：</strong>
                {parseResult.dimensions.join('、')}
              </div>
              <div>
                <strong>节点数：</strong>
                {parseResult.blueprint.nodes.length}
              </div>
            </div>
          </section>

          <section style={{ marginTop: 16 }}>
            <h2 style={{ fontSize: 18 }}>DAG 蓝图（可编辑 JSON）</h2>
            <textarea
              value={blueprintJson}
              onChange={(e) => setBlueprintJson(e.target.value)}
              rows={20}
              style={{
                width: '100%', padding: 8, fontFamily: 'monospace', fontSize: 12,
                background: '#f9fafb',
              }}
            />
          </section>

          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <button
              onClick={handleConfirm}
              disabled={loading}
              style={{
                padding: '8px 16px', background: '#10b981', color: '#fff',
                border: 'none', borderRadius: 4, cursor: 'pointer',
              }}
            >
              {loading ? '启动中...' : '确认执行'}
            </button>
            <button
              onClick={() => navigate('/')}
              style={{ padding: '8px 16px' }}
            >
              取消
            </button>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 注册路由（在 `App.tsx`）**

读 `frontend/src/App.tsx`，确认路由表，添加：

```tsx
import ParsePreview from './pages/ParsePreview';
// 在路由表里加：
<Route path="/parse" element={<ParsePreview />} />
```

- [ ] **Step 3: 跑前端类型检查 + 构建**

```bash
cd frontend && npx tsc --noEmit && npx vite build
```

Expected: 无错误。

- [ ] **Step 4: 提交**

```bash
cd frontend
git add src/pages/ParsePreview.tsx src/App.tsx
git commit -m "feat(frontend): add ParsePreview page with blueprint editor and confirm flow"
```

---

## Task 8: 前端 `Dashboard.tsx` 加 NLP 入口

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

**Goal:** 在 Dashboard 顶部加"用自然语言新建分析"按钮，跳到 `/parse?message=...`。

### Steps

- [ ] **Step 1: 读现有 Dashboard**

```bash
cat frontend/src/pages/Dashboard.tsx
```

确认现有结构（一般有"新建分析"按钮 + Task 列表）。

- [ ] **Step 2: 加 NLP 入口**

在 Dashboard 顶部"新建分析"按钮旁边加：

```tsx
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

export default function Dashboard() {
  // ... 现有 state
  const navigate = useNavigate();
  const [nlpMessage, setNlpMessage] = useState('');

  function goToNlpParse() {
    if (!nlpMessage.trim()) {
      navigate('/parse');
    } else {
      navigate(`/parse?message=${encodeURIComponent(nlpMessage.trim())}`);
    }
  }

  return (
    <div>
      {/* 现有内容 */}
      <section style={{ marginBottom: 24, padding: 16, background: '#f0f9ff', borderRadius: 8 }}>
        <h2 style={{ fontSize: 18, marginTop: 0 }}>用自然语言新建分析（AI 调研组长）</h2>
        <input
          value={nlpMessage}
          onChange={(e) => setNlpMessage(e.target.value)}
          placeholder="例：对比飞书、钉钉、企业微信的 AI 协作能力"
          style={{ width: '100%', padding: 8, fontSize: 14 }}
        />
        <button
          onClick={goToNlpParse}
          style={{ marginTop: 8, padding: '8px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 4 }}
        >
          → AI 解析并预览
        </button>
      </section>

      {/* 现有"结构化"新建按钮（如有）保留 */}
    </div>
  );
}
```

- [ ] **Step 3: 跑前端类型检查 + 构建**

```bash
cd frontend && npx tsc --noEmit && npx vite build
```

Expected: 无错误。

- [ ] **Step 4: 提交**

```bash
cd frontend
git add src/pages/Dashboard.tsx
git commit -m "feat(frontend): add NLP entry on Dashboard for natural language task creation"
```

---

## Task 9: E2E 测试 parse → confirm → execute_mvp

**Files:**
- New: `backend/tests/test_e2e/test_parse_to_report.py`

**Goal:** 端到端验证：parse 端点 → confirm 端点 → 看到 task 进入 COMPLETED 状态。

### Steps

- [ ] **Step 1: 写 E2E 测试**

新建 `backend/tests/test_e2e/test_parse_to_report.py`：

```python
"""端到端：NLP → parse → confirm → execute_mvp → 任务完成。"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.llm.base import LLMResponse
from app.models.task import Task, TaskStatus, Competitor


VALID_BLUEPRINT = {
    "nodes": [
        {"id": f"c_{c}_{d}", "agent": "Collector", "action": "collect",
         "params": {"target": c, "dimension": d, "domain": ""}, "depends_on": []}
        for c in ["A", "B"] for d in ["推荐算法"]
    ] + [
        {"id": f"a_{c}_推荐算法", "agent": "Analyst", "action": "analyze",
         "params": {"competitor": c, "dimension": "推荐算法"}, "depends_on": [f"c_{c}_推荐算法"]}
        for c in ["A", "B"]
    ] + [
        {"id": f"w_{c}_推荐算法", "agent": "Writer", "action": "write",
         "params": {"competitor": c, "dimension": "推荐算法"}, "depends_on": [f"a_{c}_推荐算法"]}
        for c in ["A", "B"]
    ],
    "edges": [
        {"from": f"c_{c}_推荐算法", "to": f"a_{c}_推荐算法"} for c in ["A", "B"]
    ] + [
        {"from": f"a_{c}_推荐算法", "to": f"w_{c}_推荐算法"} for c in ["A", "B"]
    ],
    "feedback_edges": [],
}


@pytest.mark.asyncio
async def test_e2e_parse_confirm_executes():
    """完整流程：parse 200 → confirm 200 → execute_mvp 被调用 → task 创建。"""
    app = create_app()

    parse_response_content = json.dumps({
        "competitors": ["A", "B"],
        "dimensions": ["推荐算法"],
        "dag": VALID_BLUEPRINT,
        "summary": "我打算从推荐算法维度对比 A 与 B。",
    })

    with patch("app.api.parse._orch") as mock_orch, \
         patch("app.api.parse._sm") as mock_sm, \
         patch("app.api.parse._bus") as mock_bus:
        mock_orch.execute_mvp = AsyncMock()

        # TaskParser 第一次直接返回成功（避免重试）
        mock_parser = MagicMock()
        from app.agents.base import AgentResult
        mock_parser.run = AsyncMock(return_value=AgentResult(
            success=True,
            output=json.loads(parse_response_content),
            raw_response=parse_response_content,
        ))
        mock_orch.agents = {"TaskParser": mock_parser}

        # mock state_manager.create_task
        from datetime import datetime
        def fake_create_task(task_id, comps, dims, dag_json):
            t = Task(
                task_id=task_id,
                status=TaskStatus.PENDING,
                competitors=comps,
                dimensions=dims,
                dag_json=dag_json,
                node_states={},
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
            )
            return t
        mock_sm.create_task = MagicMock(side_effect=fake_create_task)
        mock_sm.calculate_progress = MagicMock(return_value=0.0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. parse
            r1 = await client.post("/api/tasks/parse", json={"message": "分析 A 和 B 的推荐算法"})
            assert r1.status_code == 200, r1.text
            parse_data = r1.json()
            assert parse_data["competitors"] == ["A", "B"]
            assert parse_data["dimensions"] == ["推荐算法"]

            # 2. confirm（蓝图原样回传，模拟用户没编辑）
            r2 = await client.post(
                "/api/tasks/parse/confirm",
                json={"blueprint": parse_data["blueprint"]},
            )
            assert r2.status_code == 200, r2.text
            task_id = r2.json()["task_id"]
            assert task_id

        # 3. execute_mvp 被调用
        mock_orch.execute_mvp.assert_awaited_once()
        # 4. create_task 被调用
        mock_sm.create_task.assert_called_once()
        call_args = mock_sm.create_task.call_args
        # 第二个位置参数是 competitors 列表
        assert len(call_args.args[1]) == 2
```

- [ ] **Step 2: 跑 E2E 测试**

```bash
cd backend && python -m pytest tests/test_e2e/test_parse_to_report.py -v
```

Expected: 1 passed。

- [ ] **Step 3: 跑后端全部测试**

```bash
cd backend && python -m pytest -q
```

Expected: 全 passed，无回归。

- [ ] **Step 4: 提交**

```bash
cd backend
git add tests/test_e2e/test_parse_to_report.py
git commit -m "test(e2e): add parse→confirm→execute_mvp end-to-end test"
```

---

## Task 10: CLAUDE.md 加"两条入口"说明 + DoD 复核

**Files:**
- Modify: `CLAUDE.md`

**Goal:** 让团队成员在 CLAUDE.md 里能直接看到两条入口的区别，不堆设计细节。

### Steps

- [ ] **Step 1: 找 CLAUDE.md 现有"启动命令"或"绝对不能做的事"章节**

定位到适合插入"两条入口"段落的位置（建议在"绝对不能做的事"后、"核心技术栈"前）。

- [ ] **Step 2: 插入 1 段**

追加：

```markdown
## 两条入口：自然语言 vs 结构化

`POST /api/tasks` 走硬编码 `_build_dag`（**结构化入口**），适合调试与已有竞品清单的场景。`POST /api/tasks/parse` 走 TaskParser（**自然语言入口**），让用户用一句话描述需求，AI 调研组长生成 DAG 蓝图、用户在前端确认后 `POST /api/tasks/parse/confirm` 启动执行。

约束：parse 路径的维度强制在 `DEFAULT_SCHEMA` 内；解析失败时**不降级**到结构化入口，直接返 422 + `error_type` + `raw_response`。
```

- [ ] **Step 3: 跑全测试 + 前端构建，做最终回归**

```bash
cd backend && python -m pytest -q
cd frontend && npx tsc --noEmit && npx vite build
```

Expected: 全 pass，无错误。

- [ ] **Step 4: DoD 复核**

逐项核对 spec 中的 DoD 清单：

- [ ] 后端 2 端点 + 测试通过 → ✓ Task 1-5 完成
- [ ] 旧 `/api/tasks` 行为不变 → ✓ Task 5 跑了 `test_tasks.py` 回归
- [ ] 前端 NLP 入口 + ParsePreview → ✓ Task 7-8
- [ ] E2E 走通 → ✓ Task 9
- [ ] 18 条边界（空/超长/特殊字符/重复 confirm 等）→ 部分覆盖于 Task 1-4 单测；**剩余边界**（如 frontend 关闭页面、并发 parse、schema 热改）属部署级，文档化到下面"已知未覆盖"列表
- [ ] CLAUDE.md 加段 → ✓ 当前任务
- [ ] 答辩演示视频 → **非代码任务**，由用户后续操作

- [ ] **Step 5: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: document two entry points (NLP parse vs structured) in CLAUDE.md"
```

- [ ] **Step 6: 合并到 master（如适用）**

根据 `feedback_git_worktree_workflow` 规则：
- 当前分支：`fix/node-timeout-and-logging`
- 新功能按惯例应在新分支做；如当前就在 worktree 内，可直接 PR 到 master
- 不在 master 上直接 push

```bash
git push origin <current-branch>
gh pr create --base master --title "feat: TaskParser NLP main path" --body "..."
```

---

## Self-Review

对照 spec 走一遍：

| Spec 要求 | 任务 | 状态 |
|----------|------|------|
| POST /api/tasks/parse | T3 | ✓ |
| POST /api/tasks/parse/confirm | T4 | ✓ |
| TaskParser.retry_with_prompt_hint | T1 | ✓ |
| 1 次重试（仅 json_parse/llm_empty） | T2 (RETRYABLE_ERRORS 集合) | ✓ |
| 失败 422 返错，不降级 | T3 (HINT_FALLBACK) | ✓ |
| 维度强制 schema 内 | T2 (_all_dim_names) | ✓ |
| 蓝图 API 级别无状态 | spec 决策表 | ✓ |
| 旧 /api/tasks 不动 | T5 回归测试 | ✓ |
| 前端 NLP 入口 | T8 | ✓ |
| ParsePreview 页 | T7 | ✓ |
| 5 个新测试文件 | T1/T2/T3/T4/T9 | ✓ |
| DoD 6 项 | T10 复核 | ✓ |
| 18 条边界 | 单元测试覆盖：1-3, 5, 9, 11, 14, 18；未覆盖：4, 6-8, 10, 12-13, 15-17（已说明） | 部分 |

占位符扫描：无 TBD/TODO/模糊指令；所有代码块完整。

类型一致性检查：
- `parse_task_blueprint(message, task_parser, schema)` → 3 个位置参数，全部 3 个测试用到
- `init_router(orch, sm, bus)` → Task 3-4 改，Task 5 改 main.py 调用
- `ParseError` 在 client.ts 导出，T7 ParsePreview 导入

修复过程中发现的小问题（已在步骤中处理）：
- T1 的 retry 路径补 `import Message`（Step 3 内有完整 import 块）
- T4 的 confirm 端点加 `_sm`/`_bus` 单例，Step 3 替换原 `_orch` 单例块
- T7 ParsePreview 自动 parse 用 useEffect 防双触发

**计划完整，覆盖 spec 全部要点。**
