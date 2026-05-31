# 维度级并发执行设计

## 背景

当前 `execute_mvp` 通过 `prev_end` 将所有 `(竞品, 维度)` 节点串成一条长链，顺序执行。分析发现各维度之间无任何数据依赖，完全可以并发执行以大幅缩短任务耗时。

## 目标

- 将执行模式从顺序改为维度级并发：同一竞品的不同维度、不同竞品的维度均可并行
- 维度内保持 Collector → Analyst → Writer 顺序（有数据依赖）
- 控制并发上限为 5 路，避免 LLM API 限流
- 单维度失败不影响其他维度继续执行

## 数据依赖分析

每个 `(竞品, 维度)` 对的数据流完全自闭合：

| 阶段 | 输入 | 输出 | 依赖 |
|------|------|------|------|
| Collector | 竞品名 + 维度名 + keywords | raw_data + sources | 无 |
| Analyst | 同对的 raw_data + sources | analysis | 仅依赖同对 Collector |
| Writer | 同对的 analysis | report_html | 仅依赖同对 Analyst |

无跨维度、无跨竞品数据传递。最终报告合并为简单字符串拼接。

## 设计方案

采用 **Semaphore + asyncio.gather** 方案。

### 1. DAG 构建改动

文件：`backend/app/api/tasks.py`

删除 `prev_end` 逻辑（第 79-81 行），让每个 `(竞品, 维度)` 的 C→A→W 子图独立，无跨维度边。

改动前：
```python
prev_end = None
for comp in competitors:
    for dim in dimensions:
        ...
        if prev_end:
            edges.append({"from_node": prev_end, "to_node": c_id})
        prev_end = w_id
```

改动后：
```python
for comp in competitors:
    for dim in dimensions:
        ...
        # 无跨维度边，每个维度的 C→A→W 自闭合
```

### 2. 执行引擎改动

文件：`backend/app/engine/orchestrator.py`

新增 `_run_dimension` 辅助方法，重构 `execute_mvp`。

#### 2.1 `_run_dimension` 协程

```python
async def _run_dimension(
    self,
    task_id: str,
    comp_name: str,
    dim_name: str,
    dim_nodes: list[DAGNode],  # 该维度的 3 个节点，已按 C→A→W 排序
    dim_cfg: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[str, str, dict]:
    """单个 (竞品, 维度) 的执行协程。内部顺序执行，外部并发。"""
    async with semaphore:
        # 必须在获取信号量后检查，避免已取消任务占用并发槽位
        if self.sm.is_task_cancelled(task_id):
            return (comp_name, dim_name, {"skipped": True})

        result_data = {}
        for node in dim_nodes:
            # 执行单节点（复用现有逻辑）
            # 失败时记录状态，break 跳过后续节点
            ...
        return (comp_name, dim_name, result_data)
```

#### 2.2 `execute_mvp` 重构

```python
async def execute_mvp(self, task_id, dag, competitors):
    schema = load_default_schema()
    dim_config = _build_dim_config(schema)
    self.sm.update_task_status(task_id, TaskStatus.RUNNING)

    # 1. 按 (competitor, dimension) 分组
    dim_groups = _group_nodes_by_dimension(dag.nodes)

    # 2. 构建协程列表
    sem = asyncio.Semaphore(5)
    coroutines = [
        self._run_dimension(task_id, comp, dim, nodes, dim_config.get(dim, {}), sem)
        for (comp, dim), nodes in dim_groups.items()
    ]

    # 3. 并发执行
    results_list = await asyncio.gather(*coroutines, return_exceptions=True)

    # 4. 合并结果、生成报告（结构化异常处理，非静默跳过）
    results = {}
    for item in results_list:
        if isinstance(item, Exception):
            logger.error(f"Dimension execution failed: {item}", exc_info=item)
            continue
        comp, dim, data = item
        results[(comp, dim)] = data

    # 5. 拼接报告（逻辑不变）
    ...
```

#### 2.3 辅助函数 `_group_nodes_by_dimension`

```python
def _group_nodes_by_dimension(nodes: list[DAGNode]) -> dict[tuple[str, str], list[DAGNode]]:
    """按 (competitor, dimension) 分组，组内按 agent 类型排序为 C→A→W。"""
    groups: dict[tuple[str, str], list[DAGNode]] = {}
    agent_order = {"Collector": 0, "Analyst": 1, "Writer": 2}
    for node in nodes:
        # 兼容 target/competitor 两种命名
        comp = node.params.get("competitor") or node.params.get("target", "")
        dim = node.params.get("dimension", "")
        if not comp or not dim:
            logger.warning(f"Node {node.id} missing competitor/dimension, skipping")
            continue
        key = (comp, dim)
        groups.setdefault(key, []).append(node)
    for key in groups:
        groups[key].sort(key=lambda n: agent_order.get(n.agent, 99))
        if len(groups[key]) != 3:
            logger.warning(f"Dimension {key} has {len(groups[key])} nodes, expected 3")
    return groups
```

### 3. 失败隔离

- 每个 `_run_dimension` 协程内部 `try/except`
- 失败时将该维度的所有节点标记为 `FAILED`，记录 trace
- `_run_dimension` 内部将节点级异常包装为带 `(comp, dim)` 上下文的异常再抛出，便于 `gather` 捕获时定位具体维度
- `asyncio.gather(return_exceptions=True)` 捕获异常，不中断其他维度
- `execute_mvp` 中对异常记录 `logger.error` 而非静默跳过
- 最终报告跳过失败维度，只拼接成功维度的 `report_html`

### 4. 取消机制

- 取消检查必须在 `async with semaphore:` 内部（获取信号量之后），避免已取消任务占用并发槽位
- 取消后：已启动的维度完成当前节点后停止，未获取信号量的不再启动
- 所有维度停止后，任务状态设为 `STOPPED`

### 5. 进度与事件

- **EventBus**：无改动。事件已按 `node_id` 粒度，前端能处理乱序到达
- **进度计算**：`calculate_progress` 基于 `node_states` 统计，天然支持并发
- **WebSocket**：无改动。3 秒轮询兜底机制不变

## 改动范围

| 文件 | 改动内容 | 改动量 |
|------|---------|--------|
| `backend/app/api/tasks.py` | 删除 `prev_end` 逻辑 | -2 行 |
| `backend/app/engine/orchestrator.py` | 新增 `_run_dimension`、`_group_nodes_by_dimension`，重构 `execute_mvp` | ~60 行 |

不涉及：前端、Agent 层、StateManager、EventBus、Schema

## 预期收益

假设有 3 个竞品 × 3 个维度 = 9 条链，每条链耗时约 30 秒：
- 顺序执行：9 × 30 = 270 秒（4.5 分钟）
- 5 路并发：ceil(9/5) × 30 = 60 秒（1 分钟）
- 提速约 4.5 倍
