# PR 2.2: AI 助手 7 维度 Schema 落地

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `ai_assistant.json` schema（7 维度：核心玩法/AI 模型能力/Agent 能力/商业模式/用户社区/内容生态/安全合规），每维度带 fields + quality_rules；config.yaml 切到 ai-assistant；现有调用方零改动（loader 已统一）。

**Architecture:** 仅新增 1 个 JSON 文件 + 1 个测试文件 + 改 1 行 config.yaml。**不动 orchestrator/parse/tasks**——PR 2.1 的 `load_default_schema()` 已 delegate 到 loader，schema 切换自动生效。

**Tech Stack:** Python 3.11 + pytest + Pydantic v2

**Spec 参考:** [../specs/2026-06-07-ai-assistant-vertical-design.md](../specs/2026-06-07-ai-assistant-vertical-design.md) 决策 2 + 决策 5 + 数据模型段

---

## File Structure

| 路径 | 操作 | 职责 |
|---|---|---|
| `backend/app/schemas/ai_assistant.json` | 新建 | 7 维度 AI 助手 schema（核心交付） |
| `backend/app/config.yaml` | 修改 | `active_schema_id: "general"` → `"ai-assistant"` |
| `backend/tests/test_schema/test_ai_assistant_schema.py` | 新建 | 7 维度完整测试 + 字段类型 + 质检规则 |

不删任何文件，不动其他 Python 代码。

---

## Task 1: 创建 ai_assistant.json

**Files:**
- Create: `backend/app/schemas/ai_assistant.json`

- [ ] **Step 1: 创建 JSON 文件**

新建 `backend/app/schemas/ai_assistant.json`，完整内容如下：

```json
{
  "schema_id": "ai-assistant",
  "name": "国内 AI 助手横评模板",
  "version": "1.0",
  "groups": [
    {
      "name": "产品能力",
      "description": "AI 助手的核心玩法与底层 AI 能力",
      "dimensions": [
        {
          "name": "核心玩法",
          "description": "对话形式、角色扮演、多模态输入方式。区分该竞品区别于其他家的核心亮点。",
          "keywords": ["聊天", "角色", "语音", "多模态", "对话", "玩法"],
          "output_type": "paragraph",
          "evidence_threshold": 2,
          "tracking_sources": ["web", "social"],
          "fields": [
            {"name": "core_mechanics", "type": "string", "required": true},
            {"name": "differentiator", "type": "string"},
            {"name": "use_case", "type": "string"}
          ],
          "quality_rules": [
            "core_mechanics 必须提到 ≥2 种交互方式（文字/语音/图片/视频/文件），否则拒"
          ]
        },
        {
          "name": "AI 模型能力",
          "description": "底层模型来源、上下文长度、多模态支持、响应速度。这是 2026 年 AI 助手核心差异化点。",
          "keywords": ["模型", "上下文", "token", "多模态", "响应速度", "MoE"],
          "output_type": "table",
          "evidence_threshold": 2,
          "tracking_sources": ["web"],
          "fields": [
            {"name": "underlying_model", "type": "string", "required": true},
            {"name": "context_window", "type": "number", "min": 8000},
            {"name": "multimodal_capability", "type": "list"},
            {"name": "response_speed", "type": "number", "unit": "seconds"}
          ],
          "quality_rules": [
            "context_window 必须是数字 ≥ 8000，否则标 UNVERIFIED",
            "underlying_model 必须给出具体模型名或 '自研'/'接入'"
          ]
        },
        {
          "name": "Agent 能力",
          "description": "任务执行、工具调用、第三方 API 集成、智能体平台规模。",
          "keywords": ["Agent", "任务执行", "工具调用", "API", "智能体", "插件"],
          "output_type": "table",
          "evidence_threshold": 2,
          "tracking_sources": ["web", "social"],
          "fields": [
            {"name": "tool_calling", "type": "boolean", "required": true},
            {"name": "task_execution", "type": "string"},
            {"name": "api_integration", "type": "boolean"},
            {"name": "agent_marketplace", "type": "number", "description": "智能体/插件数量"}
          ],
          "quality_rules": [
            "tool_calling 必须是布尔（true/false），不能是'部分支持'这类模糊词"
          ]
        }
      ]
    },
    {
      "name": "商业与生态",
      "description": "商业模式、用户社区、内容生态",
      "dimensions": [
        {
          "name": "商业模式",
          "description": "订阅模式、免费配额、会员价格、企业版方案。",
          "keywords": ["订阅", "会员", "免费", "配额", "价格", "企业版", "B 端"],
          "output_type": "table",
          "evidence_threshold": 1,
          "tracking_sources": ["web"],
          "fields": [
            {"name": "pricing_model", "type": "string", "required": true},
            {"name": "free_tier", "type": "string"},
            {"name": "paid_tier_price", "type": "number", "unit": "CNY/month"},
            {"name": "enterprise_offering", "type": "string"}
          ],
          "quality_rules": [
            "paid_tier_price 必须是数字或'无'",
            "pricing_model 必须从 ['free', 'subscription', 'freemium', 'enterprise'] 中选"
          ]
        },
        {
          "name": "用户社区",
          "description": "创作者数量、UGC 生态、用户口碑。",
          "keywords": ["创作者", "UGC", "社区", "口碑", "用户评价", "分享"],
          "output_type": "paragraph",
          "evidence_threshold": 1,
          "tracking_sources": ["web", "social"],
          "fields": [
            {"name": "community_size", "type": "string"},
            {"name": "ugc_ecosystem", "type": "string"},
            {"name": "user_sentiment", "type": "string", "required": true}
          ],
          "quality_rules": [
            "user_sentiment 至少出现 2 个具体关键词（如'回答质量好'/'响应慢'），不能是'用户评价良好'这类空话"
          ]
        },
        {
          "name": "内容生态",
          "description": "官方插件数量、智能体数量、小程序集成、行业覆盖。",
          "keywords": ["插件", "智能体", "应用市场", "小程序", "行业", "生态"],
          "output_type": "table",
          "evidence_threshold": 1,
          "tracking_sources": ["web"],
          "fields": [
            {"name": "plugin_count", "type": "number", "required": true},
            {"name": "agent_count", "type": "number"},
            {"name": "appstore_integrations", "type": "string"},
            {"name": "vertical_coverage", "type": "number", "description": "覆盖行业数"}
          ],
          "quality_rules": [
            "plugin_count 必须是数字"
          ]
        }
      ]
    },
    {
      "name": "合规与监管",
      "description": "内容审核、青少年模式、监管合规、数据隐私",
      "dimensions": [
        {
          "name": "安全合规",
          "description": "内容审核机制、青少年模式、大模型备案、算法备案、隐私政策。",
          "keywords": ["审核", "青少年模式", "备案", "监管", "隐私", "合规"],
          "output_type": "table",
          "evidence_threshold": 1,
          "tracking_sources": ["web"],
          "fields": [
            {"name": "content_moderation", "type": "string", "required": true},
            {"name": "youth_mode", "type": "boolean", "required": true},
            {"name": "regulatory_compliance", "type": "string", "required": true},
            {"name": "data_privacy", "type": "string"}
          ],
          "quality_rules": [
            "regulatory_compliance 必须列出具体备案号或'已备案'/'未公开'",
            "youth_mode 必须是布尔"
          ]
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: 验证 JSON 合法**

```bash
cd backend && python -c "import json; json.load(open('app/schemas/ai_assistant.json'))" && echo "OK"
```

预期: 输出 `OK`。如果 JSON 语法错，会抛 `json.JSONDecodeError`，回到 Step 1 修。

- [ ] **Step 3: 提交**

```bash
git add backend/app/schemas/ai_assistant.json
git commit -m "feat(schema): add ai_assistant.json with 7 dimensions (core mechanics, AI model, agent, pricing, community, ecosystem, compliance)"
```

---

## Task 2: 写 7 维度完整测试（red → green）

**Files:**
- Create: `backend/tests/test_schema/test_ai_assistant_schema.py`

- [ ] **Step 1: 写测试文件**

新建 `backend/tests/test_schema/test_ai_assistant_schema.py`：

```python
"""国内 AI 助手 7 维度 schema 完整测试。

验证：
1. JSON 文件本身合法
2. 加载后满足 Pydantic SchemaDefinition
3. 7 个维度都在
4. 每个维度都有 fields 和 quality_rules（非空）
5. 关键 quality_rules 文案正确
"""
import json
from pathlib import Path

from app.schema.loader import load_active_schema, SCHEMA_DIR


def test_ai_assistant_json_exists():
    """ai_assistant.json 文件存在。"""
    path = SCHEMA_DIR / "ai_assistant.json"
    assert path.exists(), f"Missing {path}"


def test_ai_assistant_json_validates():
    """加载 schema 成功（无 Pydantic 错误）。"""
    schema = load_active_schema("ai-assistant")
    assert schema.schema_id == "ai-assistant"
    assert len(schema.groups) == 3  # 产品能力 / 商业与生态 / 合规与监管


def test_seven_dimensions_present():
    """7 个维度都在 schema 内。"""
    schema = load_active_schema("ai-assistant")
    all_dim_names = {d.name for g in schema.groups for d in g.dimensions}
    expected = {
        "核心玩法",
        "AI 模型能力",
        "Agent 能力",
        "商业模式",
        "用户社区",
        "内容生态",
        "安全合规",
    }
    assert all_dim_names == expected, f"Missing: {expected - all_dim_names}"


def test_each_dimension_has_fields_and_quality_rules():
    """每个维度都有 ≥1 个 fields 和 ≥1 条 quality_rules。"""
    schema = load_active_schema("ai-assistant")
    for group in schema.groups:
        for dim in group.dimensions:
            assert len(dim.fields) >= 1, f"Dim '{dim.name}' has no fields"
            assert len(dim.quality_rules) >= 1, f"Dim '{dim.name}' has no quality_rules"


def test_ai_model_dimension_context_window_rule():
    """AI 模型能力 维度的 context_window 质检规则必须含 '8000'。"""
    schema = load_active_schema("ai-assistant")
    ai_model_dim = next(
        d for g in schema.groups for d in g.dimensions if d.name == "AI 模型能力"
    )
    rules_text = " ".join(ai_model_dim.quality_rules)
    assert "8000" in rules_text, f"context_window rule missing 8000: {ai_model_dim.quality_rules}"


def test_agent_dimension_tool_calling_required():
    """Agent 能力 维度的 tool_calling 字段是必填 boolean。"""
    schema = load_active_schema("ai-assistant")
    agent_dim = next(
        d for g in schema.groups for d in g.dimensions if d.name == "Agent 能力"
    )
    tool_field = next(f for f in agent_dim.fields if f["name"] == "tool_calling")
    assert tool_field["type"] == "boolean"
    assert tool_field.get("required") is True


def test_compliance_dimension_regulatory_required():
    """安全合规 维度的 regulatory_compliance 字段必填。"""
    schema = load_active_schema("ai-assistant")
    compliance_dim = next(
        d for g in schema.groups for d in g.dimensions if d.name == "安全合规"
    )
    reg_field = next(f for f in compliance_dim.fields if f["name"] == "regulatory_compliance")
    assert reg_field.get("required") is True


def test_output_types_mix():
    """schema 包含混合 output_type（paragraph + table），覆盖 Writer format_hint 设计。"""
    schema = load_active_schema("ai-assistant")
    types = {d.output_type for g in schema.groups for d in g.dimensions}
    assert "table" in types
    assert "paragraph" in types
```

- [ ] **Step 2: 运行测试，验证 PASS（绿）**

```bash
cd backend && python -m pytest tests/test_schema/test_ai_assistant_schema.py -v
```

预期: 全部 PASS（7 维度 JSON 一次写好，应直接满足所有断言）。

- [ ] **Step 3: 跑所有 schema 测试**

```bash
cd backend && python -m pytest tests/test_schema/ -v
```

预期: 全部 PASS（包含 general / multi / dimension_fields / mvp_defaults / ai_assistant）。

- [ ] **Step 4: 提交**

```bash
git add backend/tests/test_schema/test_ai_assistant_schema.py
git commit -m "test(schema): add 7-dimension ai_assistant schema coverage"
```

---

## Task 3: 切 config.yaml 到 ai-assistant + 验证现有功能

**Files:**
- Modify: `backend/app/config.yaml`

- [ ] **Step 1: 改 config.yaml**

打开 `backend/app/config.yaml`，找到 PR 2.1 加的 `active_schema_id: "general"`，**改为**：

```yaml
active_schema_id: "ai-assistant"
```

- [ ] **Step 2: 跑全量 schema 测试**

```bash
cd backend && python -m pytest tests/test_schema/ -v
```

预期: 全部 PASS（loader 自动加载 ai_assistant.json）。

- [ ] **Step 3: 跑 orchestrator / parse / tasks 测试**

```bash
cd backend && python -m pytest tests/test_engine/ tests/test_api/ -v
```

预期: 全部 PASS。**这些测试不依赖具体维度名**，但要确保 load_default_schema 仍能 work（loader 自动切到 ai-assistant，dim 集合变了——orchestrator 不强依赖 dim_name 所以应该没问题）。

- [ ] **Step 4: 跑全量后端测试**

```bash
cd backend && python -m pytest -v
```

预期: 全部 PASS。

- [ ] **Step 5: 手动验证（可选）**

```bash
cd backend && python -c "from app.schema.loader import load_active_schema; s = load_active_schema(); print('Schema:', s.name); print('Dims:', [d.name for g in s.groups for d in g.dimensions])"
```

预期: 输出
```
Schema: 国内 AI 助手横评模板
Dims: ['核心玩法', 'AI 模型能力', 'Agent 能力', '商业模式', '用户社区', '内容生态', '安全合规']
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/config.yaml
git commit -m "feat(schema): switch active_schema_id to ai-assistant"
```

---

## Task 4: 跑 e2e 验证 demo 跑通（dry run）

**Files:** 无（验证步）

- [ ] **Step 1: 启动后端**

```bash
cd backend && uvicorn app.main:app --reload --port 5010
```

预期: 服务正常启动，端口 5010 监听。

- [ ] **Step 2: 启动前端**

```bash
cd frontend && npm run dev
```

预期: Vite dev server 启动，端口 5000 监听。

- [ ] **Step 3: 浏览器访问 http://localhost:5000**

UI 应能正常加载，Dashboard / TaskDetail 页面渲染正常。

- [ ] **Step 4: 用结构化入口（POST /api/tasks）跑 1 个真实任务**

任选 1 个现有竞品 + 1 个新维度（如"豆包 × AI 模型能力"），用结构化入口提交。验证任务能跑通。

**注意**：这一步**不能用 parse 端**（parse 端是 PR 1 任务，与 PR 2.2 解耦）。用现有 `POST /api/tasks` 结构化入口。

如发现 schema 切换后某项不工作，回滚 config.yaml 到 "general"，记录问题，PR 2.2 暂时不改 orchestrator/parse。

- [ ] **Step 5: 关闭服务**

Ctrl+C 关闭 uvicorn 和 vite。

- [ ] **Step 6: 提交（如有 e2e 发现的 fix）**

如有修复：

```bash
git add backend/ frontend/
git commit -m "fix(e2e): address schema switch to ai-assistant regression"
```

无修复 → 跳过。

---

## Self-Review

### Spec coverage

| Spec 段 | 覆盖任务 |
|---|---|
| 决策 2（AI 助手 7 维度 Schema 详细设计） | Task 1（JSON 文件）+ Task 2（测试） |
| 决策 5（与 spec 1 关系：零调用方改动） | Task 3（config 切换）+ Task 4（e2e 验证） |
| 数据模型段（fields / quality_rules） | Task 1（每个 dim 填了 fields + quality_rules） |
| 改动文件清单 PR 2.2 阶段 | Task 1-3 覆盖（不改 orchestrator/tasks/parse） |

### Placeholder scan

- [x] 无 TBD / TODO
- [x] 无 "implement later"
- [x] JSON 完整
- [x] 每个 test code 完整

### Type consistency

- `fields: list[dict]` 每条 field dict 有 `name` + `type` 字段
- `type` 字段值统一字符串: `string` / `number` / `boolean` / `list`（与 spec 决策 2 一致）
- `quality_rules: list[str]` 元素是字符串
- `output_type` 字符串值: `paragraph` / `table`（与 mvp_defaults OutputType Literal 一致）

### 命名一致性

- 7 维度名与 spec 决策 2 表格完全一致
- 字段名 snake_case 风格（underlying_model, context_window, tool_calling 等）
- `schema_id: "ai-assistant"` 与文件名 `ai_assistant.json` 一致（loader 用 `.replace("-", "_")` 转换）
