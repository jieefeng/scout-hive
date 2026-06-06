# TaskParser 主路径化设计

## 为什么

课题要求"AI 驱动的竞品分析 Agent 协作系统"应"模拟真实的数字调研小组"——理想流程是：用户提需求 → AI 调研组长（TaskParser）理解需求、规划任务、产出 DAG 蓝图 → 用户确认 → 执行。

当前实现里：

- `TaskParser`（`backend/app/agents/task_parser.py`）已实现完整，LLM 已绑定（`create_app` L49）
- 但 `api/tasks.py:create_task`（L125）走的是 `_build_dag()`（L60）的**硬编码路径**，把 TaskParser 完全跳过
- 答辩时评委问"AI 怎么理解用户需求"，只能演示 TaskParser 单元测试，没法演示端到端流程

要让 TaskParser 从"名义大脑"变成"真大脑"，需要一条新的 API 路径让用户能以自然语言驱动它。

## 做什么

新增 2 个端点，让用户可以：

1. `POST /api/tasks/parse` 提交自然语言需求 → TaskParser 输出 DAG 蓝图
2. `POST /api/tasks/parse/confirm` 确认蓝图（可能在前端编辑过）→ 启动执行

**旧路径** `POST /api/tasks`、`POST /api/tasks/debug` 一行不动，作为结构化输入入口与调试入口保留。

### 设计原则（决策记录）

| 决策 | 选项 | 选定 | 理由 |
|------|------|------|------|
| API 入口策略 | 新增 / 同接口 mode / 替换 | **新增** | 旧路径是测试与调试入口，替换风险大；新接口能独立演进 |
| 请求体格式 | 纯 message / message+hint / 全结构化 | **纯 message** | 课题强调"AI 理解需求"，hint 字段是让步；MVP 不应留逃生口 |
| TaskParser 失败处理 | 静默降级到旧路径 / 返错给用户 | **1 次重试 + 422 返错** | "降级到旧路径"需要 LLM 抽竞品名 + 补域名 + 全维度展开，**不直**（详见 4/5） |
| 维度约束 | 强制 schema 内 / 完全自由 / 允许扩展 | **强制 schema 内** | `execute_mvp` 依赖 `dim_config`（keywords、evidence_threshold）；LLM 自由发挥则配置全空，质量不可控 |
| 蓝图持久化 | 入库 draft / 独立表 / API 级别无状态 | **API 级别无状态** | MVP 用不到"草稿管理 / 蓝图复用"；YAGNI |

### 不做什么

- ❌ 不引入用户系统 / 鉴权
- ❌ 不做蓝图的拖拽式可视化编辑（用户只能改 JSON 文本框）
- ❌ 不做跨 parse 的语义缓存
- ❌ 不做维度的运行时扩充（要扩充就改 `DEFAULT_SCHEMA`）
- ❌ 不改 `TaskStatus` 枚举（不引入 DRAFT）
- ❌ 不改 `StateManager` 表结构（不入蓝图、也不存 parse 阶段的 trace）
- ❌ 不降级到旧路径（详见 4/5 错误处理）
- ❌ parse 阶段 TaskParser 的 1-2 次 LLM 调用 trace 暂不入库——失败时通过 422 `detail.raw_response` 拿最后一次原文，成功时由 confirm 阶段新建 task 的后续 trace 覆盖展示需求

## 怎么做

### 改动 1：`backend/app/agents/task_parser.py`

加一个重试方法，独立于现有 `execute`：

```python
async def retry_with_prompt_hint(
    self,
    input_data: dict,
    error_hint: str,
) -> AgentResult:
    """第二次执行：把上次错误以 user 消息追加，引导 LLM 修正。"""
    user_message = input_data.get("message", "")
    messages = [
        Message(role="system", content=self.SYSTEM_PROMPT),
        Message(role="user", content=user_message),
        Message(role="user", content=f"⚠️ 上一轮输出有误：{error_hint}\n请重新输出严格符合格式的 JSON。"),
    ]
    # ... 与 execute 同结构，区别仅 messages
```

### 改动 2：`backend/app/api/parse.py`（新文件）

抽出 `parse_task_blueprint` 纯函数 + 2 个 FastAPI 端点。

```python
# parse.py 核心结构（伪代码，最终在 plan 阶段定细节）

async def parse_task_blueprint(
    message: str,
    task_parser: TaskParser,
    schema: dict,
) -> ParseResult:
    """调 TaskParser 1 次，失败重试 1 次；返回结构化结果。"""
    result = await task_parser.execute({"message": message})
    if not result.success and result.error_type in {"json_parse", "llm_empty"}:
        result = await task_parser.retry_with_prompt_hint(
            {"message": message},
            error_hint=result.error_message or "输出格式有误",
        )
    if not result.success:
        return ParseResult(success=False, error_type=result.error_type, raw_response=result.raw_response)
    # 严格短路校验
    parsed = result.output
    for dim in parsed["dimensions"]:
        if dim not in {d.name for g in schema["groups"] for d in g["dimensions"]}:
            return ParseResult(success=False, error_type="dim_not_in_schema", dim=dim)
    DAGBlueprint(**parsed["dag"])  # 触发 validate_references；失败抛 ValueError
    if not parsed["competitors"]:
        return ParseResult(success=False, error_type="empty_competitors")
    if len(parsed["competitors"]) > 10:
        return ParseResult(success=False, error_type="too_many_competitors")
    return ParseResult(success=True, blueprint=parsed["dag"], competitors=parsed["competitors"],
                       dimensions=parsed["dimensions"], summary=parsed.get("summary", ""))


@router.post("/api/tasks/parse")
async def parse_task(req: ParseRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(422, detail={"error_type": "empty_message", "hint": "..."})
    message = req.message[:2000]  # 截断超长
    schema = load_default_schema()
    result = await parse_task_blueprint(message, agents["TaskParser"], schema)
    if not result.success:
        raise HTTPException(422, detail={
            "error_type": result.error_type,
            "raw_response": result.raw_response[:200],
            "hint": "请重写需求使其更具体，或使用 POST /api/tasks 直接提交结构化数据",
        })
    return ParseResponse(blueprint=result.blueprint, competitors=result.competitors,
                         dimensions=result.dimensions, summary=result.summary)


@router.post("/api/tasks/parse/confirm")
async def confirm_parse(req: ParseConfirmRequest):
    try:
        blueprint = DAGBlueprint(**req.blueprint)
    except (ValueError, ValidationError) as e:
        raise HTTPException(422, detail={"error_type": "blueprint_tampered", "error": str(e)})
    # 复用 _create_and_run 的 task 创建逻辑，传 blueprint 代替 _build_dag()
    ...
```

### 改动 3：`backend/app/main.py`

`create_app` 加 1 行：`app.include_router(parse.router)`。

`agents["TaskParser"]` 已在 L49 注册，无需改动。

### 改动 4：前端 3 处

| 文件 | 变化 |
|------|------|
| `frontend/src/api/client.ts` | +`parseTaskBlueprint(message)`、`confirmParse(blueprint)` |
| `frontend/src/pages/Dashboard.tsx` | +"新建分析"按钮：弹窗选 "自然语言" / "结构化" |
| `frontend/src/pages/ParsePreview.tsx`（新文件） | 渲染 blueprint（节点列表、边、feedback_edges）、competitor/dimension 列表、LLM 生成的 summary、"确认执行" / "修改蓝图" / "取消" |

不写大段视觉设计，组件职责单一即可。

## 错误处理（只对两类重试）

| 错误类型 | 重试？ | 422 hint |
|---------|--------|---------|
| `llm_unavailable` | ❌ | "AI 服务暂不可用" |
| `llm_empty` | ✅ | "AI 未返回内容" |
| `json_parse` | ✅ | "AI 输出无法解析为 JSON" |
| `dim_not_in_schema` | ❌ | "维度 'XXX' 不在 DEFAULT_SCHEMA 内" |
| `topology_error`（来自 `DAGBlueprint.validate_references`） | ❌ | "DAG 校验失败：..." |
| `empty_competitors` / `too_many_competitors` | ❌ | "竞品数 1-10" |
| `blueprint_tampered`（confirm 阶段） | ❌ | "蓝图校验失败：..." |
| `empty_message`（不调 LLM） | ❌ | "需求不能为空" |

## 怎么算成功（DoD）

- [ ] 后端：`/api/tasks/parse` 与 `/api/tasks/parse/confirm` 实现并通过单元 + 集成测试
- [ ] 后端：旧 `/api/tasks` 与 `/api/tasks/debug` 行为**完全不变**（回归测试通过）
- [ ] 前端：Dashboard 加 NLP 入口；ParsePreview 页能渲染 blueprint + summary + 确认/取消
- [ ] E2E：从 Dashboard 输入自然语言 → 看到预览 → 确认 → TaskDetail 看到完整 DAG 执行
- [ ] 边界覆盖 18 条（详见 plan 阶段）：
  - 1 空 message / 2 全标点 / 3 超长 / 4 多 JSON 对象 / 5 markdown 围栏
  - 6 0 维度 / 7 13 维度 / 8 特殊字符 / 9 重复 confirm / 10 蓝图被改坏
  - 11 空 dict / 12 关闭页面 / 13 节点失败 / 14 retry 时 LLM 挂 / 15 schema 热改
  - 16 并发 parse / 17 前端版本不一致 / 18 测试时 mock LLM
- [ ] 文档：CLAUDE.md 增加一段"两条入口"的说明（不堆设计细节）
- [ ] 答辩演示：能录一段从自然语言输入到报告产出的连续视频

## 文件清单

| 操作 | 路径 |
|------|------|
| 改 | `backend/app/agents/task_parser.py`（+ `retry_with_prompt_hint`） |
| 新建 | `backend/app/api/parse.py`（含 `parse_task_blueprint` + 2 端点） |
| 改 | `backend/app/main.py`（+ 1 行 `include_router`） |
| 改 | `frontend/src/api/client.ts`（+ 2 个 fetch 包装） |
| 改 | `frontend/src/pages/Dashboard.tsx`（+ "新建分析"入口） |
| 新建 | `frontend/src/pages/ParsePreview.tsx`（DAG 预览 + 确认） |
| 新建 | `backend/tests/test_agents/test_task_parser_retry.py` |
| 新建 | `backend/tests/test_api/test_parse_blueprint.py` |
| 新建 | `backend/tests/test_api/test_parse_endpoint.py` |
| 新建 | `backend/tests/test_api/test_confirm_endpoint.py` |
| 新建 | `backend/tests/test_e2e/test_parse_to_report.py` |
| 改 | `CLAUDE.md`（+ 1 段"两条入口"） |
