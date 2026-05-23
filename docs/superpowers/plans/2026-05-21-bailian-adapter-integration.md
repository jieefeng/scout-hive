# 阿里百练平台 LLM 适配器集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 LLM 适配层中新增阿里百练平台（DashScope）支持，通过继承 OpenAIAdapter 实现最小改动集成。

**Architecture:** BailianAdapter 继承 OpenAIAdapter，复用 OpenAI SDK 的 chat/stream_chat 实现，仅修改 base_url 指向百练兼容端点。新增 LLMError 统一异常类，BailianAdapter 重写 chat() 捕获百练特有异常。

**Tech Stack:** Python, OpenAI SDK (`openai==1.50.0`), Pytest

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| 修改 | `backend/app/llm/base.py` | 新增 `LLMError` 异常类 |
| 新增 | `backend/app/llm/bailian_adapter.py` | BailianAdapter 实现 |
| 修改 | `backend/app/llm/registry.py` | 新增 `bailian` 类型分支 |
| 修改 | `backend/config.yaml` | 新增 bailian adapter 配置 |
| 新增 | `backend/tests/test_llm/test_bailian_adapter.py` | 单元测试 |
| 修改 | `backend/tests/test_llm/test_registry.py` | 新增 bailian 注册测试 |
| 新增 | `backend/tests/test_llm/test_bailian_e2e.py` | 端到端测试 |

---

### Task 1: 新增 LLMError 异常类

**Files:**
- Modify: `backend/app/llm/base.py`
- Test: `backend/tests/test_llm/test_base.py`

- [ ] **Step 1: 编写 LLMError 测试**

```python
# backend/tests/test_llm/test_base.py 末尾追加

def test_llm_error_creation():
    from app.llm.base import LLMError
    err = LLMError("bailian_auth", "API Key 无效")
    assert err.code == "bailian_auth"
    assert err.message == "API Key 无效"
    assert str(err) == "[bailian_auth] API Key 无效"


def test_llm_error_inheritance():
    from app.llm.base import LLMError
    assert issubclass(LLMError, Exception)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_llm/test_base.py::test_llm_error_creation -v`
Expected: FAIL with `ImportError: cannot import name 'LLMError'`

- [ ] **Step 3: 实现 LLMError**

```python
# backend/app/llm/base.py 末尾追加


class LLMError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_llm/test_base.py -v`
Expected: ALL PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/llm/base.py backend/tests/test_llm/test_base.py
git commit -m "feat: add LLMError exception class to LLM base"
```

---

### Task 2: 实现 BailianAdapter

**Files:**
- Create: `backend/app/llm/bailian_adapter.py`
- Create: `backend/tests/test_llm/test_bailian_adapter.py`

- [ ] **Step 1: 编写单元测试**

```python
# backend/tests/test_llm/test_bailian_adapter.py

import pytest
from app.llm.bailian_adapter import BailianAdapter
from app.llm.openai_adapter import OpenAIAdapter


def test_inheritance():
    assert issubclass(BailianAdapter, OpenAIAdapter)


def test_default_model():
    adapter = BailianAdapter(api_key="dummy_key")
    assert adapter.model == "qwen-plus"


def test_custom_model():
    adapter = BailianAdapter(api_key="dummy_key", model="qwen-max")
    assert adapter.model == "qwen-max"


def test_base_url():
    adapter = BailianAdapter(api_key="dummy_key")
    assert str(adapter.client.base_url) == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_base_url_not_openai():
    adapter = BailianAdapter(api_key="dummy_key")
    assert "openai.com" not in str(adapter.client.base_url)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_llm/test_bailian_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.llm.bailian_adapter'`

- [ ] **Step 3: 实现 BailianAdapter**

```python
# backend/app/llm/bailian_adapter.py

import openai
from app.llm.base import LLMError
from app.llm.openai_adapter import OpenAIAdapter


class BailianAdapter(OpenAIAdapter):
    def __init__(self, api_key: str, model: str = "qwen-plus"):
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model

    async def chat(self, messages, **kwargs):
        try:
            return await super().chat(messages, **kwargs)
        except openai.AuthenticationError:
            raise LLMError("bailian_auth", "DASHSCOPE_API_KEY 无效或未设置")
        except openai.RateLimitError:
            raise LLMError("bailian_rate_limit", "百练平台限流，请稍后重试")
        except openai.APIStatusError as e:
            raise LLMError("bailian_api", f"百练 API 错误: {e.status_code}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_llm/test_bailian_adapter.py -v`
Expected: ALL PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/llm/bailian_adapter.py backend/tests/test_llm/test_bailian_adapter.py
git commit -m "feat: add BailianAdapter with error handling"
```

---

### Task 3: 注册表集成

**Files:**
- Modify: `backend/app/llm/registry.py`
- Modify: `backend/tests/test_llm/test_registry.py`

- [ ] **Step 1: 编写注册表测试**

```python
# backend/tests/test_llm/test_registry.py 末尾追加

def test_registry_bailian_creation():
    config = LLMConfig(
        default="bailian",
        adapters={"bailian": LLMAdapterConfig(type="bailian", model="qwen-plus", api_key="sk-test")},
        agent_bindings={},
    )
    registry = LLMRegistry(config)
    adapter = registry.get("bailian")
    from app.llm.bailian_adapter import BailianAdapter
    assert isinstance(adapter, BailianAdapter)
    assert adapter.model == "qwen-plus"


def test_registry_bailian_agent_binding():
    config = LLMConfig(
        default="default_adapter",
        adapters={
            "default_adapter": LLMAdapterConfig(type="local", model="llama3"),
            "bailian": LLMAdapterConfig(type="bailian", model="qwen-max", api_key="sk-test"),
        },
        agent_bindings={"Collector": "bailian"},
    )
    registry = LLMRegistry(config)
    adapter = registry.get_for_agent("Collector")
    from app.llm.bailian_adapter import BailianAdapter
    assert isinstance(adapter, BailianAdapter)
    assert adapter.model == "qwen-max"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_llm/test_registry.py::test_registry_bailian_creation -v`
Expected: FAIL with `ValueError: Unknown adapter type: bailian`

- [ ] **Step 3: 修改注册表**

```python
# backend/app/llm/registry.py

from app.llm.base import LLMAdapter
from app.llm.claude_adapter import ClaudeAdapter
from app.llm.openai_adapter import OpenAIAdapter
from app.llm.local_adapter import LocalAdapter
from app.config import LLMConfig


class LLMRegistry:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._adapters: dict[str, LLMAdapter] = {}

    def _create_adapter(self, name: str) -> LLMAdapter:
        cfg = self.config.adapters[name]
        if cfg.type == "claude":
            return ClaudeAdapter(api_key=cfg.api_key or "", model=cfg.model)
        elif cfg.type == "openai":
            return OpenAIAdapter(api_key=cfg.api_key or "", model=cfg.model)
        elif cfg.type == "local":
            return LocalAdapter(endpoint=cfg.endpoint or "http://localhost:11434", model=cfg.model)
        elif cfg.type == "bailian":
            from app.llm.bailian_adapter import BailianAdapter
            return BailianAdapter(api_key=cfg.api_key or "", model=cfg.model)
        else:
            raise ValueError(f"Unknown adapter type: {cfg.type}")

    def get(self, name: str) -> LLMAdapter:
        if name not in self._adapters:
            self._adapters[name] = self._create_adapter(name)
        return self._adapters[name]

    def get_for_agent(self, agent_name: str) -> LLMAdapter:
        adapter_name = self.config.agent_bindings.get(agent_name, self.config.default)
        return self.get(adapter_name)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_llm/test_registry.py -v`
Expected: ALL PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/llm/registry.py backend/tests/test_llm/test_registry.py
git commit -m "feat: register BailianAdapter in LLM registry"
```

---

### Task 4: 配置变更

**Files:**
- Modify: `backend/config.yaml`

- [ ] **Step 1: 添加百练适配器配置**

```yaml
# backend/config.yaml - llm.adapters 部分新增

    bailian:
      type: bailian
      model: qwen-plus
      api_key: ${DASHSCOPE_API_KEY}
```

完整文件：

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: true

llm:
  default: claude
  adapters:
    claude:
      type: claude
      model: claude-sonnet-4-6-20250514
      api_key: ${ANTHROPIC_API_KEY}
    openai:
      type: openai
      model: gpt-4o
      api_key: ${OPENAI_API_KEY}
    local:
      type: local
      endpoint: http://localhost:11434
      model: llama3
    bailian:
      type: bailian
      model: qwen-plus
      api_key: ${DASHSCOPE_API_KEY}
  agent_bindings:
    TaskParser: claude
    Analyst: claude
    Writer: openai
    Reviewer: claude
    Collector: local

dag:
  max_feedback_rounds: 3
  node_timeout_seconds: 300
  max_retries: 3
```

- [ ] **Step 2: 验证配置加载**

```bash
cd backend && python -c "from app.config import load_config; c = load_config(); print('bailian' in c.llm.adapters)"
```
Expected: `True`

- [ ] **Step 3: 提交**

```bash
git add backend/config.yaml
git commit -m "feat: add bailian adapter config to config.yaml"
```

---

### Task 5: 端到端测试

**Files:**
- Create: `backend/tests/test_llm/test_bailian_e2e.py`

> **前提**: 需设置环境变量 `DASHSCOPE_API_KEY`

- [ ] **Step 1: 编写端到端测试**

```python
# backend/tests/test_llm/test_bailian_e2e.py

import os
import pytest
from app.llm.base import Message, LLMError
from app.llm.bailian_adapter import BailianAdapter
from app.config import LLMConfig, LLMAdapterConfig
from app.llm.registry import LLMRegistry

pytestmark = pytest.mark.skipif(
    not os.environ.get("DASHSCOPE_API_KEY"),
    reason="DASHSCOPE_API_KEY not set",
)


@pytest.fixture
def adapter():
    return BailianAdapter(api_key=os.environ["DASHSCOPE_API_KEY"])


@pytest.mark.asyncio
async def test_basic_chat(adapter):
    messages = [Message(role="user", content="你好，请用一句话介绍自己")]
    response = await adapter.chat(messages)
    assert response.content
    assert len(response.content) > 0
    assert response.model == "qwen-plus"


@pytest.mark.asyncio
async def test_stream_chat(adapter):
    messages = [Message(role="user", content="用三句话描述春天")]
    chunks = []
    async for chunk in adapter.stream_chat(messages):
        chunks.append(chunk)
    assert len(chunks) > 0
    full_text = "".join(chunks)
    assert len(full_text) > 0


@pytest.mark.asyncio
async def test_long_text_generation(adapter):
    messages = [Message(role="user", content="写一篇500字的短文，主题是人工智能的未来")]
    response = await adapter.chat(messages, max_tokens=2048)
    assert len(response.content) > 200


@pytest.mark.asyncio
async def test_system_message(adapter):
    messages = [
        Message(role="system", content="你是一个专业的翻译助手"),
        Message(role="user", content="将以下句子翻译成英文：今天天气很好"),
    ]
    response = await adapter.chat(messages)
    assert response.content


@pytest.mark.asyncio
async def test_registry_integration():
    config = LLMConfig(
        default="bailian",
        adapters={
            "bailian": LLMAdapterConfig(
                type="bailian",
                model="qwen-plus",
                api_key=os.environ["DASHSCOPE_API_KEY"],
            )
        },
        agent_bindings={"Collector": "bailian"},
    )
    registry = LLMRegistry(config)
    adapter = registry.get_for_agent("Collector")
    messages = [Message(role="user", content="你好")]
    response = await adapter.chat(messages)
    assert response.content


@pytest.mark.asyncio
async def test_multiple_models():
    api_key = os.environ["DASHSCOPE_API_KEY"]
    for model in ["qwen-turbo", "qwen-plus"]:
        adapter = BailianAdapter(api_key=api_key, model=model)
        messages = [Message(role="user", content="Hi")]
        response = await adapter.chat(messages, max_tokens=16)
        assert response.content, f"Failed for model: {model}"


@pytest.mark.asyncio
async def test_invalid_api_key():
    adapter = BailianAdapter(api_key="invalid-key")
    messages = [Message(role="user", content="你好")]
    with pytest.raises(LLMError) as exc_info:
        await adapter.chat(messages)
    assert exc_info.value.code == "bailian_auth"
```

- [ ] **Step 2: 运行端到端测试**

```bash
export DASHSCOPE_API_KEY=sk-xxx
cd backend && python -m pytest tests/test_llm/test_bailian_e2e.py -v
```
Expected: ALL PASS（需有效 API Key）

- [ ] **Step 3: 提交**

```bash
git add backend/tests/test_llm/test_bailian_e2e.py
git commit -m "test: add BailianAdapter end-to-end tests"
```

---

### Task 6: 全量回归测试

- [ ] **Step 1: 运行全部 LLM 测试**

```bash
cd backend && python -m pytest tests/test_llm/ -v
```
Expected: ALL PASS

- [ ] **Step 2: 运行全部后端测试**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: ALL PASS

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: complete BailianAdapter integration"
```
