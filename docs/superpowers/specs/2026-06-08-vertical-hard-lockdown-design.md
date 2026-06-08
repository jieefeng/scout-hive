# 2026-06-08 AI 助手垂直硬收窄 — 设计文档

> 目标:把项目从"多 schema 共存 + 1 行 config 切换"硬收窄到"单 ai-assistant 路径,通用领域物理上无法输入"
> 目标读者:维护者 + 答辩评委(演示"垂直深耕 = 物理上锁死,不靠默契")
> 关联 spec(已 deprecated):[2026-06-07-ai-assistant-vertical-design.md](./2026-06-07-ai-assistant-vertical-design.md)、[2026-06-07-parse-flexible-dimensions-design.md](./2026-06-07-parse-flexible-dimensions-design.md)

## 为什么

2026-06-07 落地了两份 spec:**spec A**(ai-assistant 垂直深耕)+ **spec B**(parse 端去 schema 强制化)。两份 spec 的设计意图都合理,但**叠加之后**留下 4 个独立通道让"通用领域分析任务"仍可进入系统:

1. `POST /api/tasks/parse`:spec B 砍了 `dim_not_in_schema` → 用户输入"对比飞书钉钉的功能对比"合法通过
2. `active_schema_id: "general"` 1 行 config 切换:spec A 验收要求"回归 general schema 不破"
3. `backend/app/schemas/general.json` 文件物理还在
4. `mvp_defaults.DEFAULT_SCHEMA` + `load_default_schema()` 向后兼容入口物理还在

从产品定位看,**业务侧不再有非 ai-assistant 场景**——demo 剧本是 5 竞品(豆包/通义/Kimi/文小言/秘塔)× 7 维度的 AI 助手赛道。这 4 个通道是技术债:既不被用,又允许"功能对比"等通用维度漏进来后无质检规则可用。

技术债的代价不是"用了它会炸",而是**它存在 → 评委一句话就戳穿"垂直深耕"的故事**:
> "如果只做 ai-assistant,为什么 general.json 还在? 切回去会怎样?"

答案应该是 **"切不回去"** ——这就是硬收窄的目的。

## 做什么

3 个 PR:

1. **后端代码硬收窄**:删 4 个通道里所有死代码 + 加 API 层 422 + LLM 软约束
2. **测试 fixture 字符串收编**:剩余测试中通用维度字符串改为 ai-assistant 维度,测试集语义自洽
3. **文档 + spec 修订**:CLAUDE.md / spec A / spec B 改写,新 spec(本文)记录决策

### 不做什么(YAGNI / 推迟)

- ❌ 改 `ai_assistant.json` 文件名为 `schema.json` —— 零收益,需改 5 处引用
- ❌ inline schema 到 `mvp_defaults.py` —— 失去 Pydantic 校验和外部可编辑性
- ❌ 删 demo 历史产物 `scripts/demo_runs/*` —— 历史脏数据,不影响功能
- ❌ 把 frontend 也"硬收窄"(目前 frontend 不耦合 schema_id,无需改)
- ❌ 加多租户/多 schema 抽象 —— YAGNI

## 怎么做

### 决策 1:双层锁 (API 层硬校验 + LLM 软约束)

为什么两层:
- **仅 LLM 软约束** → LLM 可能哮口,生成"功能对比"漏过去
- **仅 API 层硬校验** → 用户看到 422 误以为系统坏了,体验差
- **双层** → LLM 优先映射到白名单(用户无感),万一 LLM 哮口 API 拦住

实现:
- `app/api/parse.py:parse_task` HTTP 端点在 `parse_task_blueprint` 返回后,加 `dim_not_in_schema` 422 校验:任何 dim 不在 `ALLOWED_DIMENSIONS` 就返 422,响应含 `invalid_dims` + `allowed` 数组
- `app/agents/task_parser.py:TaskParser.SYSTEM_PROMPT` 类初始化时把 7 维度白名单 + 映射规则渲染进 prompt 字符串

注意:service 层 `parse_task_blueprint` 保持不做 dim 校验——职责分离,422 由 HTTP 层负责。`test_parse_blueprint_does_not_validate_dim` 显式断言这个契约。

### 决策 2:删到骨子里

| 文件 | 动作 |
|------|------|
| `backend/app/schema/loader.py` | 删 |
| `backend/app/schemas/general.json` | 删 |
| `backend/app/schemas/collab_office.json` | 删(占位文件,无业务价值) |
| `backend/app/schema/mvp_defaults.py::DEFAULT_SCHEMA` | 删 dict 常量 |
| `backend/app/schema/mvp_defaults.py::load_default_schema()` | 删兼容入口 |
| `backend/app/config.py::AppConfig.active_schema_id` | 删字段 + 加 `extra="ignore"` |
| `backend/config.yaml::active_schema_id` | 删该行及注释 |

`mvp_defaults.py` 重写后只剩 3 个 Pydantic 模型 + 唯一入口 `get_active_schema() -> SchemaDefinition`。

### 决策 3:维度白名单抽 `app/constants.py`

4 个消费点(parse / tasks / orchestrator / task_parser)+ 5 个测试都引用同一份白名单,不抽必然散落:

```python
# app/constants.py
AI_ASSISTANT_SCHEMA_PATH: Path = Path(__file__).parent / "schemas" / "ai_assistant.json"

def _load_allowed_dimensions() -> frozenset[str]:
    raw = json.loads(AI_ASSISTANT_SCHEMA_PATH.read_text(encoding="utf-8"))
    return frozenset(d["name"] for g in raw["groups"] for d in g["dimensions"])

ALLOWED_DIMENSIONS: frozenset[str] = _load_allowed_dimensions()  # import 时一次性 cache
```

为什么 `frozenset`:不可被运行期意外 mutate;`in` 操作 O(1)。

### 决策 4:`ai_assistant.json` 保留原名,不改 schema.json

锁死后 "ai_assistant" 前缀确实带"领域"语义,理论上可改为更通用的 `schema.json`。但:
- 改名 = 改 5 处 spec/plan/CLAUDE.md 引用
- "ai-assistant 是当前唯一路径,未来若加新 schema 再改名" —— YAGNI
- 文件名的"领域语义"反而是好事:它直白告诉读者"这个项目锁死在 AI 助手赛道"

### 决策 5:旧 spec 标 deprecated,不删

历史决策记录的价值 ≥ 实现细节。spec A/B 顶部加 deprecated 段 + 指向新 spec,正文保留:
- git blame 可追溯
- 新人接手时,看到"为什么硬收窄"的来龙去脉
- 不破坏 plan/docs 之间的相对引用

## 怎么算成功

| 验收项 | 标准 |
|--------|------|
| **4 个生产消费点全走白名单** | `parse.py` / `tasks.py::_load_dimensions` / `orchestrator.py::execute_mvp` / `task_parser.py::SYSTEM_PROMPT` 全部引用 `ALLOWED_DIMENSIONS` 或 `get_active_schema()` |
| **死代码清零** | `grep -rn "load_default_schema\|active_schema_id\|DEFAULT_SCHEMA\|general.json\|collab_office" backend/app/ --include="*.py"` 仅命中注释 / docstring,无实际代码引用 |
| **API 层硬校验** | curl `POST /api/tasks/parse` 输入"对比飞书钉钉的功能对比" → 422 + `error_type=dim_not_in_schema` + `invalid_dims=["功能对比"]` + `allowed` 含 7 项 |
| **LLM 软约束** | `TaskParser.SYSTEM_PROMPT` 字符串包含全部 7 维度名(`test_system_prompt_contains_allowed_dimensions` 单测) |
| **回归** | 后端 pytest 全绿(除 7 个 pre-existing bailian_e2e 失败,与本次无关) |
| **测试语义** | `grep -rn "功能对比" backend/tests/` 仅命中 `test_constants/test_allowed_dimensions.py` 的反向断言 |
| **文档同步** | CLAUDE.md "两条入口" 段说硬锁定;spec A/B 顶部有 deprecated 块;本 spec 存在 |

## 回滚路径

回滚难度:**中(2-3 小时,大部分是 `git revert`)**。

操作:
1. `git revert <PR1 SHA>` 恢复 `loader.py` / `general.json` / `collab_office.json` / `mvp_defaults.DEFAULT_SCHEMA` / `config.active_schema_id` / `parse.py` 的 422 校验删除
2. `git revert <PR2 SHA>` 恢复 fixture 字符串
3. `git revert <PR3 SHA>` 恢复文档
4. (可选)再写一份新 spec 描述"为什么解锁"

**无 breaking change**:用户一直走 ai-assistant 路径,回滚不影响线上用户。

## 影响面

| 层 | 影响 |
|----|------|
| 生产 | 删 3 个 schema 文件,删 1 个 loader.py;改 6 个 .py 文件;新建 1 个 constants.py |
| 测试 | 5 个旧测试删/重写,新加 6 个测试;12 个 fixture 文件字符串收编;210 测试全绿 |
| 文档 | CLAUDE.md 2 段重写;2 份 spec 标 deprecated;1 份新 spec(本文);1 个 demo_e2e.py 删除 |
| 前端 | 无改动(本就不耦合 schema_id) |
| 数据库 | 无 schema 迁移;旧任务的 dimension 字符串仍保留在 SQLite 内,仅文本展示,无校验影响 |
| API 兼容性 | `POST /api/tasks/parse` 对超出白名单的输入返 422 而非 200,**轻微 breaking**;线上用户实际只走 ai-assistant 维度,影响为 0 |

## 实施顺序

```
PR1 (后端代码硬收窄) → PR2 (fixture 收编) → PR3 (文档 + spec)
       ↓                       ↓                    ↓
   pytest 全绿            pytest 全绿          文档 + spec deprecated
```

PR1 必先合,PR2 和 PR3 依赖 PR1 但彼此可并行。若 CI 紧,可 PR1+PR2 合并为单 PR,PR3 单独走。
