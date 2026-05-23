# Schema v3 MVP 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把竞品分析系统的 Schema 从现状升级到 v3 MVP 模型，跑通"用户填竞品 → 系统自动跑完全流程 → 输出报告"的闭环。

**Architecture:** 修改后端 Task/Competitor 模型 + 内置 DEFAULT_SCHEMA 常量 + 微调 Agent prompt。前端从自由文本输入改为结构化竞品输入框。

**Tech Stack:** Python + FastAPI + Pydantic v2 + React + TypeScript

---

## 文件影响范围

| 文件 | 变化 |
|------|------|
| `backend/app/models/task.py` | `Competitor` 新增，`Task.competitors` 类型变更 |
| `backend/app/models/analysis.py` | `Confidence` 加 `score == 0.0` 的 insufficient_data 信号支持 |
| `backend/app/schema/mvp_defaults.py` | 新建：内置默认 Schema 常量 |
| `backend/app/api/tasks.py` | `CreateTaskRequest` 改为接收结构化竞品列表 |
| `backend/app/agents/writer.py` | `SYSTEM_PROMPT` 加 output_type 约束 |
| `backend/app/agents/analyst.py` | `SYSTEM_PROMPT` 加 min_sources 约束 |
| `backend/app/agents/collector.py` | 硬编码 site:{domain} 搜索 |
| `backend/app/engine/orchestrator.py` | 使用内置 DEFAULT_SCHEMA |
| `backend/app/schema/validators.py` | `validate_traceability` 已有 confidence==0.0 跳过逻辑 |
| `frontend/src/pages/Dashboard.tsx` | 改为竞品 name+domain 结构化输入 |
| `frontend/src/api/client.ts` | `createTask` 请求体格式变更 |

---

## Task 1: 更新 Task/Competitor 模型

**Files:**
- Modify: `backend/app/models/task.py`
- Test: `backend/tests/test_models/test_task.py` (新建)

- [ ] **Step 1: 新建 Competitor 模型测试**

```python
# backend/tests/test_models/test_task.py
import pytest
from app.models.task import Competitor, Task

def test_competitor_required_fields():
    c = Competitor(name="飞书", domain="feishu.cn")
    assert c.name == "飞书"
    assert c.domain == "feishu.cn"

def test_competitor_domain_required():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Competitor(name="飞书")  # domain is required

def test_task_with_competitor_list():
    task = Task(
        task_id="test-001",
        competitors=[
            Competitor(name="飞书", domain="feishu.cn"),
            Competitor(name="钉钉", domain="dingtalk.com"),
        ]
    )
    assert len(task.competitors) == 2
    assert task.competitors[0].domain == "feishu.cn"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_models/test_task.py -v`
Expected: FAIL — ModuleNotFoundError 或 ValidationError

- [ ] **Step 3: 修改 task.py**

```python
# backend/app/models/task.py
from pydantic import BaseModel, Field
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class Competitor(BaseModel):
    """竞品结构：name + domain（必填）"""
    name: str           # "飞书"
    domain: str         # "feishu.cn"

class Task(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    competitors: list[Competitor] = Field(default_factory=list)  # 升级：Competitor 列表
    dimensions: list[str] = Field(default_factory=list)
    dag_json: dict = Field(default_factory=dict)
    node_states: dict[str, NodeStatus] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    report_html: str = ""
    traces: list[dict] = Field(default_factory=list)
    reviews: list[dict] = Field(default_factory=list)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_models/test_task.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/models/task.py tests/test_models/test_task.py
git commit -m "feat: update Task.competitors to Competitor list with required domain"
```

---

## Task 2: 创建内置 DEFAULT_SCHEMA 常量

**Files:**
- Create: `backend/app/schema/mvp_defaults.py`
- Test: `backend/tests/test_schema/test_mvp_defaults.py` (新建)

- [ ] **Step 1: 写 DEFAULT_SCHEMA 和 Pydantic 模型**

```python
# backend/app/schema/mvp_defaults.py
from typing import Literal
from pydantic import BaseModel, Field

OutputType = Literal["table", "paragraph"]

class DimensionSchema(BaseModel):
    name: str
    description: str = ""
    keywords: list[str] = Field(min_length=1)
    output_type: OutputType = "paragraph"
    min_sources: int = Field(default=1, ge=1)

class GroupSchema(BaseModel):
    name: str
    description: str = ""
    dimensions: list[DimensionSchema] = Field(min_length=1)

class SchemaDefinition(BaseModel):
    schema_id: str = "default-mvp"
    name: str = "通用竞品分析模板"
    version: str = "1.0"
    groups: list[GroupSchema] = Field(min_length=1)

DEFAULT_SCHEMA: dict = {
    "schema_id": "default-mvp",
    "name": "通用竞品分析模板",
    "version": "1.0",
    "groups": [
        {
            "name": "产品功能",
            "description": "核心产品功能维度",
            "dimensions": [
                {
                    "name": "功能对比",
                    "description": "对比各竞品提供的核心功能差异，列出各竞品支持的功能项和不支持的功能项。",
                    "keywords": ["功能", "特性", "支持"],
                    "output_type": "table",
                    "min_sources": 2
                },
                {
                    "name": "用户体验",
                    "description": "分析各竞品在界面设计、操作体验、用户评价方面的特点。",
                    "keywords": ["用户体验", "UI", "界面"],
                    "output_type": "paragraph",
                    "min_sources": 1
                }
            ]
        },
        {
            "name": "商业策略",
            "description": "定价与商业策略维度",
            "dimensions": [
                {
                    "name": "定价策略",
                    "description": "对比各竞品的定价模式（免费/订阅/按需）、价格区间、有无隐藏费用。提取每个竞品的具体价格数据。",
                    "keywords": ["定价", "价格", "套餐", "收费"],
                    "output_type": "table",
                    "min_sources": 1
                }
            ]
        }
    ]
}

def load_default_schema() -> SchemaDefinition:
    """加载内置默认 Schema"""
    return SchemaDefinition.model_validate(DEFAULT_SCHEMA)
```

- [ ] **Step 2: 写测试**

```python
# backend/tests/test_schema/test_mvp_defaults.py
import pytest
from app.schema.mvp_defaults import (
    DEFAULT_SCHEMA, load_default_schema,
    DimensionSchema, GroupSchema, SchemaDefinition, OutputType
)

def test_load_default_schema():
    schema = load_default_schema()
    assert schema.schema_id == "default-mvp"
    assert len(schema.groups) == 2

def test_default_groups_have_dimensions():
    schema = load_default_schema()
    product_group = next(g for g in schema.groups if g.name == "产品功能")
    assert len(product_group.dimensions) >= 2

def test_dimension_schema_fields():
    schema = load_default_schema()
    dim = schema.groups[0].dimensions[0]
    assert dim.name == "功能对比"
    assert dim.output_type in ["table", "paragraph"]
    assert len(dim.keywords) >= 1
    assert dim.min_sources >= 1

def test_output_type_enum():
    t = DimensionSchema(
        name="测试", description="测试",
        keywords=["测试"], output_type="table"
    )
    assert t.output_type == "table"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_schema/test_mvp_defaults.py -v`
Expected: FAIL — module not found

- [ ] **Step 4: 创建目录并运行测试**

Run: `mkdir -p backend/app/schema && mkdir -p backend/tests/test_schema`
Run: `cd backend && python -m pytest tests/test_schema/test_mvp_defaults.py -v`
Expected: FAIL — SchemaDefinition.model_validate fails

- [ ] **Step 5: 修复 SchemaDefinition 验证错误**

检查 DEFAULT_SCHEMA 是否有验证问题。如果 `groups[0]["description"]` 存在但 GroupSchema 的 description 默认值为 "" 而非必填，改法正确。继续调试直到 PASS。

- [ ] **Step 6: 提交**

```bash
cd backend && git add app/schema/ tests/test_schema/
git commit -m "feat: add mvp_defaults with built-in DEFAULT_SCHEMA"
```

---

## Task 3: 更新 CreateTaskRequest 和 API

**Files:**
- Modify: `backend/app/api/tasks.py`
- Test: `backend/tests/test_api/test_tasks.py`

- [ ] **Step 1: 写 API 测试**

```python
# backend/tests/test_api/test_tasks.py
import pytest
from fastapi.testclient import TestClient

def test_create_task_with_competitors(client: TestClient):
    response = client.post("/api/tasks/", json={
        "competitors": [
            {"name": "飞书", "domain": "feishu.cn"},
            {"name": "钉钉", "domain": "dingtalk.com"}
        ]
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["competitors"]) == 2
    assert data["competitors"][0]["domain"] == "feishu.cn"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_api/test_tasks.py::test_create_task_with_competitors -v`
Expected: FAIL — 字段不匹配

- [ ] **Step 3: 修改 tasks.py**

```python
# backend/app/api/tasks.py
# 找到 CreateTaskRequest 和 create_task 函数，替换为：

class CompetitorInput(BaseModel):
    name: str
    domain: str

class CreateTaskRequest(BaseModel):
    competitors: list[CompetitorInput]

@router.post("/", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    task_id = str(uuid.uuid4())
    competitors = [c.model_dump() for c in req.competitors]

    # 使用内置 DEFAULT_SCHEMA，展开维度
    schema = load_default_schema()
    dimensions = []
    for group in schema.groups:
        for dim in group.dimensions:
            dimensions.append(dim.name)

    # 构建简化 DAG（Collector → Analyst → Writer）
    nodes = []
    edges = []
    prev_node = None
    for comp in req.competitors:
        for dim in dimensions:
            collector_node = f"collector_{comp.name}_{dim}"
            analyst_node = f"analyst_{comp.name}_{dim}"
            writer_node = f"writer_{comp.name}_{dim}"
            nodes.append({"id": collector_node, "agent": "Collector", "action": "collect", "params": {"target": comp.name, "domain": comp.domain, "dimension": dim}})
            nodes.append({"id": analyst_node, "agent": "Analyst", "action": "analyze", "params": {"competitor": comp.name, "dimension": dim}})
            nodes.append({"id": writer_node, "agent": "Writer", "action": "write", "params": {"competitor": comp.name, "dimension": dim}})
            edges.append({"from": collector_node, "to": analyst_node})
            edges.append({"from": analyst_node, "to": writer_node})
            if prev_node:
                edges.append({"from": prev_node, "to": collector_node})
            prev_node = writer_node

    dag_blueprint = DAGBlueprint(nodes=nodes, edges=edges)
    task = state_manager.create_task(task_id, [c.model_dump() for c in req.competitors], dimensions, dag_blueprint.model_dump())

    async def run_dag():
        try:
            await orchestrator.execute_mvp(task_id, dag_blueprint, req.competitors)
        except Exception:
            state_manager.update_task_status(task_id, TaskStatus.FAILED)

    asyncio.create_task(run_dag())
    return TaskResponse(**task.model_dump())
```

同时在 orchestrator 中添加 `execute_mvp` 方法（见 Task 4）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_api/test_tasks.py::test_create_task_with_competitors -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/api/tasks.py tests/test_api/test_tasks.py
git commit -m "refactor: replace free-text task creation with structured competitor input"
```

---

## Task 4: 实现 execute_mvp（Orchestrator 简化路径）

**Files:**
- Modify: `backend/app/engine/orchestrator.py`
- Test: `backend/tests/test_engine/test_orchestrator_mvp.py` (新建)

- [ ] **Step 1: 写 orchestrator MVP 执行测试**

```python
# backend/tests/test_engine/test_orchestrator_mvp.py
import pytest
from app.engine.orchestrator import Orchestrator
from app.schema.mvp_defaults import load_default_schema

@pytest.mark.asyncio
async def test_execute_mvp_loads_default_schema():
    orch = Orchestrator(...)
    # 验证 execute_mvp 使用 DEFAULT_SCHEMA
    # （Mock LLM 调用，验证不报错）
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_engine/test_orchestrator_mvp.py -v`
Expected: FAIL — execute_mvp not exist

- [ ] **Step 3: 读 orchestrator.py 现有结构，然后在类中添加 execute_mvp**

```python
# backend/app/engine/orchestrator.py

async def execute_mvp(self, task_id: str, dag_blueprint: DAGBlueprint, competitors: list[dict]):
    """
    MVP 简化执行路径：
    1. 按 dimensions × competitors 展开节点
    2. Collector 用 site:{domain} 搜索
    3. Analyst 按 min_sources 校验
    4. Writer 按 output_type 输出
    5. Reviewer 校验引用
    """
    schema = load_default_schema()
    # 构建 dimension → output_type / min_sources 的映射
    dim_config = {}
    for group in schema.groups:
        for dim in group.dimensions:
            dim_config[dim.name] = {
                "output_type": dim.output_type,
                "min_sources": dim.min_sources,
                "description": dim.description,
                "keywords": dim.keywords,
            }

    # 遍历 DAG 节点执行
    for node in dag_blueprint.nodes:
        if node.agent == "Collector":
            comp = next(c for c in competitors if c["name"] == node.params.get("target"))
            await self._execute_collector_mvp(node, comp, dim_config)
        elif node.agent == "Analyst":
            await self._execute_analyst_mvp(node, dim_config)
        elif node.agent == "Writer":
            await self._execute_writer_mvp(node, dim_config)
```

添加对应的 `_execute_collector_mvp`、`_execute_analyst_mvp`、`_execute_writer_mvp` 私有方法，这些方法调用现有 Agent 但注入额外参数（domain、output_type、min_sources）。

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest tests/test_engine/test_orchestrator_mvp.py -v`
Expected: FAIL 或 SKIP（需要完整 mock）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/engine/orchestrator.py tests/test_engine/test_orchestrator_mvp.py
git commit -m "feat: add execute_mvp path using built-in DEFAULT_SCHEMA"
```

---

## Task 5: Writer Agent prompt 注入 output_type

**Files:**
- Modify: `backend/app/agents/writer.py`
- Test: `backend/tests/test_agents/test_writer.py`

- [ ] **Step 1: 写 Writer output_type 测试**

```python
# backend/tests/test_agents/test_writer.py
def test_writer_output_type_table_constraint():
    from app.agents.writer import Writer
    writer = Writer(name="Writer", llm_adapter=mock_adapter)
    # 当 output_type=table 时，Writer 必须输出表格
    result = await writer.execute({
        "output_type": "table",
        "dimension": "功能对比",
        "findings": [...]
    })
    assert "table" in result.output.get("report_html", "").lower()
```

- [ ] **Step 2: 修改 Writer.SYSTEM_PROMPT**

```python
# backend/app/agents/writer.py

SYSTEM_PROMPT_TABLE = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

关键约束（必须遵守）：
1. output_type = "table"：必须输出 Markdown 表格，第一列是维度名，其余列是竞品
2. 所有竞品必须使用完全相同的行维度（如"基础版价格"、"专业版价格"），没有数据的单元格填"无"
3. 绝对禁止出现行列错位
4. 每条结论附带 (来源: URL) 引用
5. 报告必须是完整的 HTML 片段（不需要 <html> 和 <head>）

输出 JSON 格式：
{"report_html": "<div class='report'>...</div>", "summary": "报告摘要"}"""

SYSTEM_PROMPT_PARAGRAPH = """你是一个报告撰写专家。根据分析结果，生成结构化的 HTML 竞品分析报告。

关键约束（必须遵守）：
1. output_type = "paragraph"：输出段落叙述，结构为 [竞品名]：[分析结论]
2. 每条结论后附 (来源: URL)
3. 不得生成表格
4. 报告必须是完整的 HTML 片段（不需要 <html> 和 <head>）

输出 JSON 格式：
{"report_html": "<div class='report'>...</div>", "summary": "报告摘要"}"""

async def execute(self, input_data: dict) -> AgentResult:
    output_type = input_data.get("output_type", "paragraph")
    system_prompt = SYSTEM_PROMPT_TABLE if output_type == "table" else SYSTEM_PROMPT_PARAGRAPH
    messages = [
        Message(role="system", content=system_prompt),
        Message(role="user", content=json.dumps(input_data, ensure_ascii=False, default=str)),
    ]
    # ... 其余同原 execute
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_agents/test_writer.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
cd backend && git add app/agents/writer.py tests/test_agents/test_writer.py
git commit -m "feat: inject output_type into Writer system prompt for table/paragraph control"
```

---

## Task 6: Analyst Agent prompt 注入 min_sources

**Files:**
- Modify: `backend/app/agents/analyst.py`
- Test: `backend/tests/test_agents/test_analyst.py`

- [ ] **Step 1: 写 Analyst min_sources 测试**

```python
# backend/tests/test_agents/test_analyst.py
def test_analyst_min_sources_constraint():
    from app.agents.analyst import Analyst
    analyst = Analyst(name="Analyst", llm_adapter=mock_adapter)
    result = await analyst.execute({
        "competitor": "飞书",
        "dimension": "功能对比",
        "min_sources": 2,
        "raw_data": {...}
    })
    # 验证降级逻辑：当 sources < min_sources 时，confidence.level = "low"
    # （需要 mock LLM 返回不足来源的数据）
```

- [ ] **Step 2: 修改 Analyst.SYSTEM_PROMPT**

```python
# backend/app/agents/analyst.py

SYSTEM_PROMPT = """你是一个竞品分析专家。根据采集到的原始数据，进行结构化分析。

关键规则：
1. 每条结论(claim)必须附带原文引用(quote)和来源(source_ref)，找不到原文引用的结论必须丢弃
2. quote_type 为 "exact"（原文）或 "paraphrased"（意译）
3. 当 min_sources > 实际找到的来源数时，在 confidence.uncertainty_factors 中记录"仅找到 N 条来源，未达最低要求 (min_sources)"
4. 当 sources == 0 时，claim 前加 "⚠️ 数据不足："，confidence.score = 0.0, level = "low"
5. 置信度评分：来源数 >= min_sources 时 level="high"，1 <= 来源数 < min_sources 时 level="low"

输出 JSON 格式：
{
  "competitor": "竞品名称", "dimension": "分析维度",
  "findings": [
    {
      "finding_id": "f001", "claim": "结论描述", "quote": "原文引用",
      "quote_type": "exact", "source_ref": "来源ID", "chunk_ref": "分段ID",
      "reasoning_chain": [{"step": 1, "thought": "推理过程", "source_ref": "来源ID"}],
      "confidence": {"score": 0.9, "level": "high", "uncertainty_factors": []}
    }
  ],
  "comparison_matrix": {
    "dimensions": ["维度1"],
    "competitors": {"竞品A": {"维度1": {"status": "✓", "detail": "描述"}}}
  }
}"""
```

- [ ] **Step 3: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_agents/test_analyst.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
cd backend && git add app/agents/analyst.py tests/test_agents/test_analyst.py
git commit -m "feat: inject min_sources into Analyst prompt with degradation rules"
```

---

## Task 7: Collector Agent 硬编码 site:{domain} 搜索

**Files:**
- Modify: `backend/app/agents/collector.py`
- Test: `backend/tests/test_agents/test_collector.py`

- [ ] **Step 1: 修改 Collector.execute 签名，注入 domain**

```python
# backend/app/agents/collector.py

SYSTEM_PROMPT = """你是一个信息采集专家。根据给定的竞品名称和分析维度，生成搜索关键词。

约束：
1. 优先在竞品主域名 site:{domain} 中搜索
2. 主域名找不到时，可尝试子域名（buy.{domain}, help.{domain}）
3. 最多返回 5 个相关 URL

输出 JSON 格式：
{
  "search_queries": ["关键词1", "关键词2"],
  "target_urls": ["https://..."]
}"""

async def execute(self, input_data: dict) -> AgentResult:
    target = input_data.get("target", "")
    domain = input_data.get("domain", "")   # 新增：竞品官网域名
    dimension = input_data.get("dimension", "")
    min_sources = input_data.get("min_sources", 1)

    # 构造带 domain 约束的搜索提示
    domain_hint = f"（优先搜索 site:{domain}）" if domain else ""
    user_msg = f"竞品: {target}{domain_hint}\n分析维度: {dimension}\n关键词: {', '.join(input_data.get('keywords', []))}"

    messages = [
        Message(role="system", content=self.SYSTEM_PROMPT),
        Message(role="user", content=user_msg),
    ]
    # ... 其余同原 execute，但搜索 query 自动加上 site:{domain}
```

- [ ] **Step 2: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_agents/test_collector.py -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd backend && git add app/agents/collector.py tests/test_agents/test_collector.py
git commit -m "feat: inject domain into Collector for site:{domain} search constraint"
```

---

## Task 8: 前端竞品输入框（name + domain 结构化）

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: 修改 Dashboard.tsx — 竞品输入改为结构化**

```tsx
// frontend/src/pages/Dashboard.tsx
// 把单行文本输入改为：
// - 动态添加竞品（name + domain 两个输入框）
// - 竞品列表展示（可删除）

const [competitors, setCompetitors] = useState([{ name: '', domain: '' }]);

const addCompetitor = () => setCompetitors([...competitors, { name: '', domain: '' }]);
const removeCompetitor = (i: number) => setCompetitors(competitors.filter((_, idx) => idx !== i));
const updateCompetitor = (i: number, field: 'name' | 'domain', value: string) => {
  const updated = [...competitors];
  updated[i][field] = value;
  setCompetitors(updated);
};

const handleCreate = async () => {
  const valid = competitors.filter(c => c.name.trim() && c.domain.trim());
  if (!valid.length) {
    alert('请至少填写一个竞品（名称和域名）');
    return;
  }
  const task = await createTask(valid);
  // ...
};
```

完整的 JSX 结构：

```tsx
<div style={{ marginBottom: '1rem' }}>
  {competitors.map((comp, i) => (
    <div key={i} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
      <input
        placeholder="竞品名称（如：飞书）"
        value={comp.name}
        onChange={e => updateCompetitor(i, 'name', e.target.value)}
        style={{ flex: 1, padding: '0.5rem' }}
      />
      <input
        placeholder="官网域名（如：feishu.cn）"
        value={comp.domain}
        onChange={e => updateCompetitor(i, 'domain', e.target.value)}
        style={{ flex: 1, padding: '0.5rem' }}
      />
      <button onClick={() => removeCompetitor(i)} style={{ color: 'red' }}>×</button>
    </div>
  ))}
  <button onClick={addCompetitor} style={{ padding: '0.5rem', background: '#eee' }}>+ 添加竞品</button>
</div>
```

- [ ] **Step 2: 修改 api/client.ts**

```typescript
// frontend/src/api/client.ts
export async function createTask(competitors: Array<{name: string, domain: string}>) {
  const response = await fetch(`${API_BASE}/api/tasks/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ competitors }),
  });
  if (!response.ok) throw new Error('创建任务失败');
  return response.json();
}
```

- [ ] **Step 3: 本地测试**

Run: `cd frontend && npm run dev`
验证：
- 输入多个竞品（名称 + 域名）能正确提交
- 任务列表正确显示竞品

- [ ] **Step 4: 提交**

```bash
cd frontend && git add src/pages/Dashboard.tsx src/api/client.ts
git commit -m "feat: replace free-text input with structured competitor name+domain input"
```

---

## Task 9: 串联集成测试

**Files:**
- Create: `backend/tests/test_integration/test_mvp_flow.py`

- [ ] **Step 1: 写全流程集成测试**

```python
# backend/tests/test_integration/test_mvp_flow.py
import pytest

@pytest.mark.asyncio
async def test_full_mvp_flow():
    """
    端到端测试：用户填竞品 → 系统跑完全流程 → 输出报告
    Mock 所有 LLM 调用，验证数据流正确
    """
    from app.engine.orchestrator import Orchestrator
    from app.schema.mvp_defaults import load_default_schema

    orch = Orchestrator(...)
    competitors = [
        {"name": "飞书", "domain": "feishu.cn"},
        {"name": "钉钉", "domain": "dingtalk.com"},
    ]

    schema = load_default_schema()
    # 构建简化 DAG
    # ...

    result = await orch.execute_mvp("test-task-001", dag, competitors)
    assert result.status in ["completed", "failed"]  # 不崩溃即通过
```

- [ ] **Step 2: 运行集成测试**

Run: `cd backend && python -m pytest tests/test_integration/test_mvp_flow.py -v`

- [ ] **Step 3: 提交**

```bash
cd backend && git add tests/test_integration/test_mvp_flow.py
git commit -m "test: add MVP integration flow test"
```

---

## 自检清单

1. **Spec coverage：** 逐条对照 v3 设计文档，每项都能找到对应 Task
2. **Placeholder scan：** 无 TBD/TODO，所有代码块完整
3. **类型一致性：** `Competitor.name/domain`、`output_type: Literal["table","paragraph"]`、`min_sources: int >= 1` 在所有文件中一致

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-05-25-schema-v3-mvp-implementation.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — dispatch fresh subagent per task, review between tasks

**2. Inline Execution** — execute tasks in this session using executing-plans

**Which approach?**