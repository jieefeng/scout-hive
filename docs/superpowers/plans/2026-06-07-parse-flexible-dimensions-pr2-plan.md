# PR 2: Writer 合并双 prompt + format_hint 机制 + TaskParser 软建议

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合并 `SYSTEM_PROMPT_TABLE` + `SYSTEM_PROMPT_PARAGRAPH` 为单一 `GENERIC_PROMPT`；Writer `execute()` 支持 `format_hint: table | paragraph | auto`（默认 auto，LLM 自决）；向后兼容旧的 `output_type` 参数；TaskParser prompt 末尾加 `format_hint` 软建议。

**Architecture:** 仅改 `backend/app/agents/writer.py` 和 `backend/app/agents/task_parser.py`。Orchestrator/前端零改动（仍传 `output_type`，Writer 内部映射）。

**Tech Stack:** Python 3.11 + pytest

**Spec 参考:** [../specs/2026-06-07-parse-flexible-dimensions-design.md](../specs/2026-06-07-parse-flexible-dimensions-design.md) 决策 3

---

## File Structure

| 路径 | 操作 | 职责 |
|---|---|---|
| `backend/app/agents/writer.py` | 修改 | 删 SYSTEM_PROMPT_TABLE/PARAGRAPH，加 GENERIC_PROMPT/FORMAT_HINT_SUFFIX；execute 支持 format_hint；output_type 向后兼容 |
| `backend/app/agents/task_parser.py` | 修改 | SYSTEM_PROMPT 末尾加 format_hint 软建议 |
| `backend/tests/test_agents/test_writer_format_hint.py` | 新建 | 3 种 format_hint 模式 + 向后兼容 + 优先级测试 |
| `backend/tests/test_agents/test_writer.py` | 修改 | 现有 `test_writer_with_output_type_*` 测试保留（向后兼容证明） |

不删任何文件。

---

## Task 1: 加 test_writer_format_hint_table 测试（red）

**Files:**
- Create: `backend/tests/test_agents/test_writer_format_hint.py`

- [ ] **Step 1: 写测试文件**

新建 `backend/tests/test_agents/test_writer_format_hint.py`：

```python
"""Writer format_hint 机制测试。

验证：
1. format_hint=table 强制表格输出
2. format_hint=paragraph 强制段落输出
3. format_hint=auto LLM 自决（消息中无强制 suffix）
4. format_hint 优先级 > output_type（两者都设时 format_hint 生效）
5. 不传 format_hint 时 fallback 到 output_type（向后兼容）
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.writer import Writer
from app.llm.base import LLMResponse


@pytest.fixture
def mock_llm():
    adapter = MagicMock()
    adapter.chat = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_format_hint_table_forces_table(mock_llm):
    """format_hint=table → LLM 收到的 system prompt 末尾有"强制表格"suffix。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<table><tr><td>对比</td></tr></table>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "format_hint": "table"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "Markdown 表格" in system_content
    assert "本次输出必须是 Markdown 表格" in system_content


@pytest.mark.asyncio
async def test_format_hint_paragraph_forces_paragraph(mock_llm):
    """format_hint=paragraph → system prompt 末尾有"强制段落"suffix。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div><p>段落报告</p></div>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "format_hint": "paragraph"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "段落叙述" in system_content
    assert "本次输出必须是段落叙述" in system_content


@pytest.mark.asyncio
async def test_format_hint_auto_no_suffix(mock_llm):
    """format_hint=auto → system prompt 不带强制 suffix。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div>报告</div>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "format_hint": "auto"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    # auto 模式无强制 suffix
    assert "本次输出必须是" not in system_content


@pytest.mark.asyncio
async def test_format_hint_takes_precedence_over_output_type(mock_llm):
    """format_hint 与 output_type 都设时，format_hint 生效。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<table>...</table>", "summary": "s"}',
        model="test",
    )
    # format_hint=table + output_type=paragraph（互相冲突），format_hint 应赢
    await writer.run({"findings": [], "format_hint": "table", "output_type": "paragraph"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "本次输出必须是 Markdown 表格" in system_content
    assert "本次输出必须是段落叙述" not in system_content


@pytest.mark.asyncio
async def test_output_type_backward_compatible_table(mock_llm):
    """只设 output_type=table（无 format_hint）→ 行为与改造前一致（仍走表格 suffix）。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<table><tr><td>维度</td></tr></table>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "output_type": "table"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "本次输出必须是 Markdown 表格" in system_content


@pytest.mark.asyncio
async def test_output_type_backward_compatible_paragraph(mock_llm):
    """只设 output_type=paragraph（无 format_hint）→ 段落 suffix。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div><p>段落</p></div>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": [], "output_type": "paragraph"})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "本次输出必须是段落叙述" in system_content


@pytest.mark.asyncio
async def test_default_format_hint_auto(mock_llm):
    """完全不传 format_hint 和 output_type → 默认 auto（无 suffix）。"""
    writer = Writer("Writer", mock_llm)
    mock_llm.chat.return_value = LLMResponse(
        content='{"report_html": "<div>报告</div>", "summary": "s"}',
        model="test",
    )
    await writer.run({"findings": []})

    call_args = mock_llm.chat.call_args
    messages = call_args[0][0]
    system_content = messages[0].content
    assert "本次输出必须是" not in system_content
```

- [ ] **Step 2: 运行测试，验证 FAIL（红）**

```bash
cd backend && python -m pytest tests/test_agents/test_writer_format_hint.py -v
```

预期: **FAIL**——`test_format_hint_table_forces_table` 等会失败，因为当前实现没有 `format_hint` 参数 / `GENERIC_PROMPT` 常量。

- [ ] **Step 3: 提交 red 测试**

```bash
git add backend/tests/test_agents/test_writer_format_hint.py
git commit -m "test(writer): add red tests for format_hint mechanism"
```

---

## Task 2: 合并 Writer 双 prompt + 加 format_hint 实现（green）

**Files:**
- Modify: `backend/app/agents/writer.py:7-108`

- [ ] **Step 1: 删 SYSTEM_PROMPT_TABLE 和 SYSTEM_PROMPT_PARAGRAPH**

打开 `backend/app/agents/writer.py`，**完整删除** line 10-65 的 `SYSTEM_PROMPT_TABLE` 和 `SYSTEM_PROMPT_PARAGRAPH` 两个常量（连同 docstring/格式规则）。**保留** `class Writer(AgentBase):` 头（line 7-9）和 execute 方法（line 67+）。

- [ ] **Step 2: 加 GENERIC_PROMPT + FORMAT_HINT_SUFFIX**

在 `class Writer(AgentBase): enforce_rc = True` 之后（line 8 后），加：

```python
    GENERIC_PROMPT = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

[格式选择规则 - LLM 自决]
- 看到 dimension 名包含「对比 / 矩阵 / 定价 / 功能 / 指标 / Agent 能力 / 商业模式 / 内容生态」等量化词 → 优先用 Markdown 表格
- 看到 dimension 名包含「体验 / 口碑 / 感受 / 故事 / 叙事 / 核心玩法 / 用户社区 / 安全合规」等定性词 → 优先用段落叙述
- 拿不准时优先表格（竞品分析 80% 场景需要横向对比）

[强制规则 - 表格 / 段落都要遵守]
1. 报告必须是完整 HTML 片段（不需要 <html> 和 <head>）
2. 每条结论附溯源浮窗（data-finding-id 属性）
3. 引用来源用 sources 中的真实 URL
4. 表格模式：第一列是维度名，其余列是竞品；所有竞品必须使用完全相同的行维度，没有数据的单元格填"无"
5. 段落模式：结构为 [竞品名]：[分析结论]
6. 使用 input_data.dimension 字段值作为报告标题，禁止改名

[来源引用规则 - 严格遵守]
- 输入数据中的 "sources" 数组包含真实 URL，格式为 [{"source_id": "...", "url": "https://...", "snippet": "..."}]
- 引用来源时必须使用 sources 中的真实 URL，格式为 (来源: <真实URL>)
- **绝对禁止**编造 ref.link、example.com 等虚假 URL
- 如果 sources 中没有可用 URL，则不附带链接，不要编造

关键规则（新增）：
- 你必须输出 `reasoning_chain: [{step, thought, source_ref?}]` 至少 1 条
- 这是答辩展示用，缺漏会重试

输出 JSON 格式：
{"report_html": "<div class='report'>...</div>", "summary": "报告摘要", "reasoning_chain": [{"step": <int>, "thought": "<解释>", "source_ref": "<source_id>"}]}"""

    FORMAT_HINT_TABLE_SUFFIX = "\n[强制] 本次输出必须是 Markdown 表格，不允许段落。"
    FORMAT_HINT_PARAGRAPH_SUFFIX = "\n[强制] 本次输出必须是段落叙述，不允许表格。"
```

- [ ] **Step 3: 改 execute() 方法支持 format_hint**

找到 line 67-77 的 execute 方法（开头到构造 messages 之前）。**完整替换**为：

```python
    async def execute(self, input_data: dict) -> AgentResult:
        # 优先用 format_hint（新机制），fallback 到 output_type（向后兼容）
        format_hint = input_data.get("format_hint")
        if format_hint is None:
            format_hint = input_data.get("output_type", "auto")

        if format_hint == "table":
            system_prompt = self.GENERIC_PROMPT + self.FORMAT_HINT_TABLE_SUFFIX
        elif format_hint == "paragraph":
            system_prompt = self.GENERIC_PROMPT + self.FORMAT_HINT_PARAGRAPH_SUFFIX
        else:  # auto
            system_prompt = self.GENERIC_PROMPT

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=json.dumps(input_data, ensure_ascii=False, default=str)),
        ]
```

- [ ] **Step 4: 运行 Task 1 的测试，验证 PASS（绿）**

```bash
cd backend && python -m pytest tests/test_agents/test_writer_format_hint.py -v
```

预期: 全部 PASS（7 个测试）。

- [ ] **Step 5: 跑现有 writer 测试**

```bash
cd backend && python -m pytest tests/test_agents/test_writer.py -v
```

预期: 全部 PASS（`test_writer_with_output_type_table` / `test_writer_with_output_type_paragraph` 仍绿——证明向后兼容）。

- [ ] **Step 6: 跑所有 agent 测试**

```bash
cd backend && python -m pytest tests/test_agents/ -v
```

预期: 全部 PASS。

- [ ] **Step 7: 提交 green**

```bash
git add backend/app/agents/writer.py
git commit -m "feat(writer): merge dual prompts to GENERIC_PROMPT, add format_hint mechanism"
```

---

## Task 3: TaskParser SYSTEM_PROMPT 加 format_hint 软建议

**Files:**
- Modify: `backend/app/agents/task_parser.py`

- [ ] **Step 1: 找到 SYSTEM_PROMPT 末尾**

打开 `backend/app/agents/task_parser.py`，找到 `SYSTEM_PROMPT` 类变量（line 12 附近，含 `"输出 JSON 格式..."` 段）。

- [ ] **Step 2: 加 format_hint 软建议**

在 `SYSTEM_PROMPT` 末尾的 `"输出 JSON 格式..."` 段后追加：

```text

[format_hint 软建议 - 新增]
- 如果生成的节点含 `Writer` agent（action: "generate_report"），建议在 `params.format_hint` 字段填：
  - "table"（推荐：包含「对比 / 矩阵 / 定价 / 功能 / 指标」等量化词的 dimension）
  - "paragraph"（推荐：包含「体验 / 口碑 / 感受」等定性词的 dimension）
  - "auto"（拿不准时填这个，让 LLM 自决）
- 不强制：Writer 拿不到 format_hint 时走 auto 路径不报错
```

**注意**：这是**软建议**（spec 决策 3 明确）。LLM 可能不填、可能填错、可能挂错节点，Writer 都安全兜底。

- [ ] **Step 3: 跑 TaskParser 现有测试**

```bash
cd backend && python -m pytest tests/test_agents/test_task_parser*.py tests/test_api/test_parse_blueprint.py -v
```

预期: 全部 PASS（SYSTEM_PROMPT 改了不影响现有 JSON 解析逻辑——LLM 仍可输出合法 blueprint）。

- [ ] **Step 4: 提交**

```bash
git add backend/app/agents/task_parser.py
git commit -m "feat(task_parser): add format_hint soft suggestion to SYSTEM_PROMPT"
```

---

## Task 4: 跑全量后端测试 + 验证向后兼容

**Files:** 无（验证步）

- [ ] **Step 1: 跑全量后端测试**

```bash
cd backend && python -m pytest -v
```

预期: 全部 PASS。

- [ ] **Step 2: 跑 e2e 验证旧 demo（飞书/钉钉/企微）仍能跑**

```bash
# 启动后端
cd backend && uvicorn app.main:app --reload --port 5010 &

# 等服务起来后
python scripts/demo_e2e.py --competitors "飞书,钉钉,企微" --no-poll
```

预期: 任务能创建（status 200），节点 RUNNING，结构不变（旧 schema + 旧 output_type 路径仍 work）。

- [ ] **Step 3: 关闭后端**

```bash
# kill 掉 uvicorn 进程
pkill -f "uvicorn app.main:app" || true
```

- [ ] **Step 4: 提交（如有 fix）**

无修改 → 跳过。

---

## Self-Review

### Spec coverage

| Spec 段 | 覆盖任务 |
|---|---|
| 决策 3（Writer 合并双 prompt） | Task 2（GENERIC_PROMPT） |
| 决策 3（format_hint 覆盖机制） | Task 2（FORMAT_HINT_SUFFIX + execute 支持） |
| 决策 3（format_hint 怎么进 blueprint） | Task 3（TaskParser 软建议） |
| 改动文件清单 PR 2 阶段 | Task 1-3 覆盖 |

### Placeholder scan

- [x] 无 TBD / TODO
- [x] 无 "implement later"
- [x] GENERIC_PROMPT 完整可用
- [x] 每个 test code 完整

### Type consistency

- `format_hint: str` 取值 `"table"` / `"paragraph"` / `"auto"` 全局一致
- `FORMAT_HINT_TABLE_SUFFIX` / `FORMAT_HINT_PARAGRAPH_SUFFIX` 字符串前缀 `"\n[强制] "` 一致
- `output_type` 旧参数类型 `str`，仍能映射到 `format_hint`

### 命名一致性

- `GENERIC_PROMPT` 与 `SYSTEM_PROMPT_TABLE/PARAGRAPH` 命名风格一致（UPPER_SNAKE_CASE 类常量）
- `FORMAT_HINT_TABLE_SUFFIX` / `FORMAT_HINT_PARAGRAPH_SUFFIX` 命名对称
- `test_writer_format_hint.py` 文件名与测试主题一致
