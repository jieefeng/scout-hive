# 阿里百练平台 LLM 适配器集成设计

## 1. 概述

### 1.1 背景

当前系统的 LLM 适配层支持 Claude、OpenAI 和本地模型三种适配器。需要新增阿里百练平台（DashScope）支持，使系统能够调用百练平台上的各类模型（Qwen 系列、第三方模型等）。

### 1.2 核心决策

- **实现方式**：继承 `OpenAIAdapter`，复用 OpenAI SDK，仅修改 `base_url`
- **API 端点**：`https://dashscope.aliyuncs.com/compatible-mode/v1`（OpenAI 兼容模式）
- **默认模型**：`qwen-plus`（百练推荐的均衡选择）
- **API Key**：`DASHSCOPE_API_KEY` 环境变量（沿用阿里官方 SDK 标准命名，与 `openai` / `anthropic` 前缀区分清晰）

---

## 2. 架构设计

### 2.1 方案选型

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **方案 1（采用）** | 继承 OpenAIAdapter | 代码量最少，零重复 | 需覆盖方法才能扩展百练特有功能 |
| 方案 2 | 独立实现 | 完全解耦 | 代码重复 |
| 方案 3 | 抽取兼容基类 | DRY，架构优雅 | 需重构现有代码，过度设计 |

### 2.2 类关系

```
LLMAdapter (ABC)
├── ClaudeAdapter
├── OpenAIAdapter
│   └── BailianAdapter ← 新增
└── LocalAdapter
```

---

## 3. 详细设计

### 3.1 BailianAdapter 实现

**文件**：`backend/app/llm/bailian_adapter.py`

```python
import time
from typing import AsyncIterator
from app.llm.openai_adapter import OpenAIAdapter


class BailianAdapter(OpenAIAdapter):
    def __init__(self, api_key: str, model: str = "qwen-plus"):
        import openai
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model
```

- 继承 `OpenAIAdapter`，`chat()` 和 `stream_chat()` 完全复用
- 构造函数仅修改 `base_url` 指向百练兼容端点
- 默认模型设为 `qwen-plus`

### 3.2 异常处理

百练平台的错误码体系与 OpenAI 不完全一致。在 `BailianAdapter` 中重写 `chat()` 方法，捕获百练特有异常并映射到统一的错误类型：

```python
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

> **注意**：百练的限流响应同样返回 HTTP 429，OpenAI SDK 的 `RateLimitError` 可直接捕获。但百练可能有独立的限流策略（如按模型维度限流），需在 E2E 测试中验证。

### 3.3 参数兼容性说明

| 参数 | 兼容性 | 说明 |
|------|--------|------|
| `temperature` | 通用 | 不同模型默认值不同，qwen-plus 默认 0.7，建议根据场景调参 |
| `top_p` | 通用 | 同上 |
| `max_tokens` | 通用 | 百练各模型上限不同，qwen-plus 最大 8192 |
| `stop` | 通用 | 基本兼容，特殊 token 处理可能有差异 |

> 不同模型的"性格"不同，建议算法工程师在切换模型时进行调参测试。

### 3.4 注册表变更

**文件**：`backend/app/llm/registry.py`

在 `_create_adapter` 方法中新增分支：

```python
elif cfg.type == "bailian":
    from app.llm.bailian_adapter import BailianAdapter
    return BailianAdapter(api_key=cfg.api_key or "", model=cfg.model)
```

### 3.5 配置变更

**文件**：`backend/config.yaml`

```yaml
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
    bailian:                    # 新增
      type: bailian
      model: qwen-plus
      api_key: ${DASHSCOPE_API_KEY}
  agent_bindings:
    TaskParser: claude
    Analyst: claude
    Writer: openai
    Reviewer: claude
    Collector: local
    # 可选：将某个 agent 绑定到百练
    # Collector: bailian
```

---

## 4. 测试设计

### 4.1 单元测试

**文件**：`backend/tests/test_llm/test_bailian_adapter.py`

- 验证 `BailianAdapter` 继承自 `OpenAIAdapter`
- 验证 `base_url` 断言：确保指向百练端点，而非 OpenAI 官方地址
- 验证默认模型为 `qwen-plus`

```python
def test_base_url():
    adapter = BailianAdapter(api_key="dummy_key")
    assert str(adapter.client.base_url) == "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

### 4.2 注册表测试

**文件**：`backend/tests/test_llm/test_registry.py`（更新）

- 验证 `type: bailian` 配置能正确创建 `BailianAdapter` 实例
- 验证 agent_binding 到 bailian 适配器正常工作

### 4.3 端到端测试

**文件**：`backend/tests/test_llm/test_bailian_e2e.py`

| 测试用例 | 描述 | 重点 |
|----------|------|------|
| 基础连通性 | 使用 `qwen-plus` 发送简单消息，验证收到正常响应 | 验证 token 计数返回 |
| 流式输出 | 验证 `stream_chat` 能逐块返回内容，前端可正确解析 | **重点验证**：SSE 格式、结束标志 |
| 长文本生成 | 生成 1000+ 字内容，验证流式输出完整性 | 验证超时和部分响应处理 |
| Agent 绑定 | 通过 registry 获取绑定了 bailian 的 agent，验证调用成功 | — |
| 多模型测试 | 测试 qwen-turbo、qwen-max 等模型是否正常工作 | — |

**运行方式**：

```bash
# 需设置环境变量
export DASHSCOPE_API_KEY=sk-xxx

# 运行全部百练测试
pytest backend/tests/test_llm/test_bailian*.py -v

# 仅运行端到端测试
pytest backend/tests/test_llm/test_bailian_e2e.py -v
```

---

## 5. 变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/llm/bailian_adapter.py` | BailianAdapter 实现（含异常处理） |
| 新增 | `backend/tests/test_llm/test_bailian_adapter.py` | 单元测试 |
| 新增 | `backend/tests/test_llm/test_bailian_e2e.py` | 端到端测试 |
| 修改 | `backend/app/llm/base.py` | 新增 `LLMError` 异常类 |
| 修改 | `backend/app/llm/registry.py` | 新增 bailian 类型分支 |
| 修改 | `backend/tests/test_llm/test_registry.py` | 新增 bailian 注册测试 |
| 修改 | `backend/config.yaml` | 新增 bailian adapter 配置 |
| 无变更 | `config.py`, `requirements.txt` | 无需修改 |

---

## 6. 风险与注意事项

| 风险点 | 描述 | 应对建议 |
|--------|------|----------|
| Token 计数差异 | Qwen 模型与 GPT 模型对同一文本的 Token 计算结果不同 | 若系统有基于 Token 的限流/计费逻辑，需引入百练专用 Token 计算器 |
| 流式输出格式 | SSE 数据块结构或结束标志可能有细微差别 | E2E 测试重点验证 `stream_chat`，确保前端正确解析 |
| API 兼容性版本 | 百练兼容模式可能基于 OpenAI 某个历史版本 API 规范 | 当前 `openai==1.50.0` 已验证兼容，升级 SDK 时需回归测试 |
| 模型限流策略 | 百练可能有独立的按模型维度限流 | E2E 测试中验证 429 响应能被正确捕获和处理 |
