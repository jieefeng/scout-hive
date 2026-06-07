# PR 1: Parse 端去 Schema 强制化 + 完整 raw_response + 分支 hint 文案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 砍掉 parse 端 `dim_not_in_schema` 校验，让任意 dimension 通过；422 响应返回完整 LLM 原始输出（不再截断）；hint 文案按 error_type 分支。

**Architecture:** 纯改 `backend/app/api/parse.py` 的 `parse_task_blueprint` 函数——删 dim 校验、删截断、加 HINT_BY_ERROR。`mvp_defaults.py` 仍调用（spec 决策 4 明确"保留调用作为 hint 传给下游"，虽然下游不需要 schema 字段，但保留调用避免破坏模块边界）。`RAW_RESPONSE_MAX_LEN` 常量保留不删（其他地方可能用）。

**Tech Stack:** Python 3.11 + pytest + FastAPI + Pydantic v2

**Spec 参考:** [../specs/2026-06-07-parse-flexible-dimensions-design.md](../specs/2026-06-07-parse-flexible-dimensions-design.md) 决策 1 + 决策 2 + 决策 5

---

## File Structure

| 路径 | 操作 | 职责 |
|---|---|---|
| `backend/app/api/parse.py` | 修改 | 删 dim 校验、删截断、加 HINT_BY_ERROR 字典 |
| `backend/tests/test_api/test_parse_blueprint.py` | 修改 | `test_parse_does_not_retry_on_dim_not_in_schema` → `test_parse_accepts_arbitrary_dim`；加新测试 |
| `backend/tests/test_api/test_parse_endpoint.py` | 修改 | 加 hint 文案分支测试（如果该文件存在并测试 422 响应） |

不新增文件。所有改动局限在 parse.py + 2 个测试文件。

---

## Task 1: 改写 test_parse_does_not_retry_on_dim_not_in_schema → test_parse_accepts_arbitrary_dim

**Files:**
- Modify: `backend/tests/test_api/test_parse_blueprint.py:68-80`

**Why first:** 红绿循环第一步。先把"任意 dimension 通过"测试写出来，当前实现必 fail，验证 red。

- [ ] **Step 1: 替换测试函数**

打开 `backend/tests/test_api/test_parse_blueprint.py`，找到第 68-80 行的 `test_parse_does_not_retry_on_dim_not_in_schema` 函数。**完整替换**为：

```python
@pytest.mark.asyncio
async def test_parse_accepts_arbitrary_dim():
    """任意 dimension（含 schema 没收录的）都应通过 parse 校验。"""
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content='{"competitors": ["A"], "dimensions": ["协同能力"], "dag": ' + str(VALID_DAG).replace("'", '"') + ', "summary": "OK"}',
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is True
    assert result["dimensions"] == ["协同能力"]
    assert parser.llm.chat.call_count == 1  # 一次成功，无需重试
```

- [ ] **Step 2: 运行测试，验证它 FAIL（红）**

```bash
cd backend && python -m pytest tests/test_api/test_parse_blueprint.py::test_parse_accepts_arbitrary_dim -v
```

预期: **FAIL** with `assert result["success"] is True` 失败，因为当前实现会返回 `success=False` + `error_type="dim_not_in_schema"`。

- [ ] **Step 3: 提交 red 测试**

```bash
git add backend/tests/test_api/test_parse_blueprint.py
git commit -m "test(parse): add red test for arbitrary dimension acceptance"
```

---

## Task 2: 删 parse.py 的 dim 校验代码

**Files:**
- Modify: `backend/app/api/parse.py:83-92`

- [ ] **Step 1: 删 `_all_dim_names` 调用的校验块**

打开 `backend/app/api/parse.py`，找到第 83-92 行（"严格短路：dim 必须在 schema 内" 注释开始的 9 行）。**完整删除**这 9 行，函数体从 line 79 紧接到 line 94 的 "竞品数校验"。

删除前 line 79-94：
```python
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
                "raw_response": raw_truncated,
                "error_message": f"维度 '{dim}' 不在 DEFAULT_SCHEMA 内",
            }

    # 竞品数校验
    if not competitors:
```

删除后 line 79-83：
```python
    parsed = result.output
    competitors = parsed.get("competitors", [])
    dimensions = parsed.get("dimensions", [])

    # 竞品数校验
    if not competitors:
```

- [ ] **Step 2: 同时删 `_all_dim_names` 函数定义（line 30-31）**

```python
def _all_dim_names(schema: dict) -> set[str]:
    return {d["name"] for g in schema.get("groups", []) for d in g.get("dimensions", [])}
```

这 2 行**整段删除**（函数已无引用）。

- [ ] **Step 3: 运行 Task 1 的测试，验证它 PASS（绿）**

```bash
cd backend && python -m pytest tests/test_api/test_parse_blueprint.py::test_parse_accepts_arbitrary_dim -v
```

预期: **PASS**。

- [ ] **Step 4: 运行整个 parse_blueprint 测试文件，验证其他测试还过**

```bash
cd backend && python -m pytest tests/test_api/test_parse_blueprint.py -v
```

预期: 全部 PASS（特别注意 `test_parse_empty_competitors` / `test_parse_too_many_competitors` / `test_parse_topology_error` / `test_parse_fails_after_retry_exhausted` / `test_parse_success_first_try` / `test_parse_retries_on_json_parse` 仍绿）。

- [ ] **Step 5: 提交 green**

```bash
git add backend/app/api/parse.py
git commit -m "feat(parse): remove dim_not_in_schema validation, accept arbitrary dimensions"
```

---

## Task 3: 加 test_full_raw_response 测试（red）

**Files:**
- Modify: `backend/tests/test_api/test_parse_blueprint.py` (在末尾追加)

- [ ] **Step 1: 追加测试**

在 `backend/tests/test_api/test_parse_blueprint.py` 文件末尾追加：

```python
@pytest.mark.asyncio
async def test_full_raw_response_in_failure():
    """422 响应 raw_response 应包含完整 LLM JSON（不截断到 RAW_RESPONSE_MAX_LEN=200）。"""
    long_raw = '{"competitors": [], "long": "' + ("x" * 500) + '"}'
    parser = _parser_with_llm(AsyncMock(return_value=LLMResponse(
        content=long_raw,
        model="test",
    )))

    result = await parse_task_blueprint("x", parser, _schema())

    assert result["success"] is False
    assert result["error_type"] == "empty_competitors"
    # 完整 raw_response 应 > 500 字符（如果被截断到 200 字符就 fail）
    assert len(result["raw_response"]) > 500
```

- [ ] **Step 2: 运行测试，验证它 FAIL（红）**

```bash
cd backend && python -m pytest tests/test_api/test_parse_blueprint.py::test_full_raw_response_in_failure -v
```

预期: **FAIL** with `assert len(result["raw_response"]) > 500` 失败，因为当前实现 `raw_truncated = _raw_content(result)[:RAW_RESPONSE_MAX_LEN]` 截断到 200 字符。

- [ ] **Step 3: 提交 red 测试**

```bash
git add backend/tests/test_api/test_parse_blueprint.py
git commit -m "test(parse): add red test for full raw_response in failure"
```

---

## Task 4: 删 parse.py 的 raw_response 截断

**Files:**
- Modify: `backend/app/api/parse.py:69` 和所有 `raw_truncated` 引用

- [ ] **Step 1: 改 `parse_task_blueprint` 函数体用完整 raw_response**

打开 `backend/app/api/parse.py`，找到第 69 行：

```python
raw_truncated = _raw_content(result)[:RAW_RESPONSE_MAX_LEN]
```

**改为**：

```python
raw_response_full = _raw_content(result)
```

- [ ] **Step 2: 函数体内所有 `raw_truncated` 替换为 `raw_response_full`**

函数体内有 5 处 `raw_truncated` 引用（line 75, 90, 99, 105, 114）。**全部替换**为 `raw_response_full`。

可以用 `replace_all`（Edit 工具），把 `raw_truncated` 替换为 `raw_response_full`。

- [ ] **Step 3: 运行 Task 3 的测试，验证它 PASS（绿）**

```bash
cd backend && python -m pytest tests/test_api/test_parse_blueprint.py::test_full_raw_response_in_failure -v
```

预期: **PASS**。

- [ ] **Step 4: 运行整个 parse_blueprint 测试文件**

```bash
cd backend && python -m pytest tests/test_api/test_parse_blueprint.py -v
```

预期: 全部 PASS。

- [ ] **Step 5: 提交 green**

```bash
git add backend/app/api/parse.py
git commit -m "feat(parse): return full raw_response on failure, no truncation"
```

---

## Task 5: 加 HINT_BY_ERROR 字典 + hint 文案分支测试（red）

**Files:**
- Modify: `backend/app/api/parse.py:147` (HINT_FALLBACK 附近)
- Modify: `backend/tests/test_api/test_parse_endpoint.py` (追加测试)

- [ ] **Step 1: 加 HINT_BY_ERROR 常量**

打开 `backend/app/api/parse.py`，找到第 147 行 `HINT_FALLBACK` 定义。在它**上方**加：

```python
HINT_BY_ERROR: dict[str, str] = {
    "empty_competitors": "请明确列出至少 1 个竞品名",
    "too_many_competitors": f"竞品数超过上限 {MAX_COMPETITORS}，请精简",
    "json_parse": "LLM 输出不是合法 JSON，请稍后重试或换种描述方式",
    "topology_error": "LLM 生成的 DAG 结构有误，请稍后重试",
}
```

注意 `MAX_COMPETITORS` 已经在 line 25 定义过，可直接引用。

- [ ] **Step 2: 改 422 响应用 HINT_BY_ERROR 分支**

找到 parse.py 第 165-174 行的 422 抛出（`raise HTTPException(status_code=422, detail={...})`）。**替换** detail 字典中的 `"hint": HINT_FALLBACK` 为：

```python
            detail={
                "error_type": result["error_type"],
                "raw_response": result.get("raw_response", ""),
                "error_message": result.get("error_message", ""),
                "hint": HINT_BY_ERROR.get(result["error_type"], HINT_FALLBACK),
            },
```

确保缩进 4 空格（与上下对齐）。

- [ ] **Step 3: 追加 hint 分支测试**

打开 `backend/tests/test_api/test_parse_endpoint.py`（如不存在则跳过本步，标记为"待 PR 1.5 补"）。在文件末尾追加：

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import create_app
    return TestClient(create_app())


def test_parse_hint_by_error_type_empty_competitors(client):
    """empty_competitors 错误码 → 特定 hint 文案。"""
    with patch("app.api.parse._orch") as mock_orch:
        mock_parser = MagicMock()
        mock_orch.agents = {"TaskParser": mock_parser}
        # 强制 parse_task_blueprint 返 empty_competitors 错误
        from app.api.parse import parse_task_blueprint
        with patch("app.api.parse.parse_task_blueprint", new=AsyncMock(return_value={
            "success": False,
            "error_type": "empty_competitors",
            "raw_response": "",
            "error_message": "competitors list is empty",
        })):
            resp = client.post("/api/tasks/parse", json={"message": "对比一些竞品"})
            assert resp.status_code == 422
            body = resp.json()["detail"]
            assert body["error_type"] == "empty_competitors"
            assert "请明确列出至少 1 个竞品名" in body["hint"]
```

注意 `AsyncMock` 需要 `from unittest.mock import AsyncMock`。

- [ ] **Step 4: 运行新加的测试，验证它 PASS（绿）**

```bash
cd backend && python -m pytest tests/test_api/test_parse_endpoint.py::test_parse_hint_by_error_type_empty_competitors -v
```

预期: **PASS**（本任务的红绿同时进行，因为 HINT_BY_ERROR 实现与测试一起写）。

- [ ] **Step 5: 运行所有 parse 相关测试**

```bash
cd backend && python -m pytest tests/test_api/ -v
```

预期: 全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/api/parse.py backend/tests/test_api/test_parse_endpoint.py
git commit -m "feat(parse): add HINT_BY_ERROR map for error_type-specific guidance"
```

---

## Task 6: 删 stale 旧测试的 dim_not_in_schema 引用

**Files:**
- Modify: 全仓 grep `dim_not_in_schema`

- [ ] **Step 1: 全仓搜残留**

```bash
cd backend && grep -rn "dim_not_in_schema" --include="*.py" .
```

预期: 0 命中（Task 2 已删，Task 1 已改写测试名）。

- [ ] **Step 2: 全仓搜 "DEFAULT_SCHEMA" 残留**

```bash
cd backend && grep -rn "DEFAULT_SCHEMA\|dim_not_in_schema" --include="*.py" . | grep -v "__pycache__"
```

预期：可能仍有引用（如 spec 决策 4 提到的"Orchestrator 仍加载"）。**这些是 spec 决策 4 明确保留的**，本 PR 不动。

- [ ] **Step 3: 跑所有后端测试**

```bash
cd backend && python -m pytest -v
```

预期：所有测试 PASS（按 spec 1 决策 1，新增 ≥ 4 个测试全绿；现有 parse / orchestrator 测试全绿）。

- [ ] **Step 4: 提交（如有 cleanup）**

如有 Task 6.1 或 6.2 的清理代码（极少，本 PR 应该没有），提交：

```bash
git add -A
git commit -m "chore: clean stale dim_not_in_schema references after parse-end refactor"
```

如果没文件改动，本步跳过。

---

## Self-Review

### Spec coverage

| Spec 段 | 覆盖任务 |
|---|---|
| 决策 1（删 dim 校验） | Task 1 + Task 2 |
| 决策 2（raw_response 不截断） | Task 3 + Task 4 |
| 决策 5（hint 文案按 error_type 分支） | Task 5 |

### Placeholder scan

- [x] 无 TBD / TODO
- [x] 无 "implement later" / "fill in details"
- [x] 每个 code block 完整可用
- [x] 步骤命令带预期输出

### Type consistency

- `result["raw_response"]` 在所有任务里用同一字段名
- `HINT_BY_ERROR` 字典类型 `dict[str, str]` 声明一次
- `error_type` 字符串字面量与 spec 完全一致：`empty_competitors` / `too_many_competitors` / `json_parse` / `topology_error` / `dim_not_in_schema`（最后一个已删）

### 文件一致性

- `parse.py` 修改两处：line 30-31（删函数）、line 69 + 5 处引用 + line 165-174（hint 分支）
- `test_parse_blueprint.py` 修改：line 68-80（改写测试）+ 末尾追加（raw_response 测试）
- `test_parse_endpoint.py` 末尾追加：hint 分支测试
