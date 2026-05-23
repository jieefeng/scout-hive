# Schema 设计文档 v3 MVP 问题修复方案

> 基于 Agent Team 评审结果，针对 P1 高优先级问题的修复设计

## 1. 修复概述

| 问题 | 优先级 | 涉及层面 | 修复文件 |
|------|--------|----------|----------|
| report_html 未渲染 | P1 | 前端 | TaskDetail.tsx |
| 进度状态不透明 | P1 | 前端+后端 | api/tasks.py, TaskDetail.tsx |
| domain 校验宽松 | P1 | 前端 | Dashboard.tsx |
| 降级策略依赖 prompt | P1 | 后端 | analyst.py, orchestrator.py |

---

## 2. report_html 未渲染

### 现状
- `ReportViewer` 组件存在于 `frontend/src/components/ReportViewer.tsx`
- `TaskDetail.tsx` 没有调用 `ReportViewer`
- 用户完成任务后看不到最终分析报告

### 修复方案
在 `TaskDetail.tsx` 的页面顶部（任务 Header 下方）添加 `<ReportViewer task={currentTask} />`，作为页面主内容区域。

### 布局调整
```
TaskDetail 页面布局（修复后）：
├── Header（任务ID、状态、竞品）
├── ReportViewer（报告主体）← 新增
├── DAG 执行图
├── 溯源浏览器
└── 审查时间轴
```

---

## 3. 进度状态透明化

### 现状
- API 响应中只有 `status: pending/running/completed/failed`
- 用户不知道任务卡在哪一步，预计多长时间完成

### 修复方案

**后端 - TaskResponse 增加 progress 字段：**
```python
class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: float = 0.0  # 0.0 - 1.0
    ...
```

**后端 - 计算 progress 逻辑：**
```python
def calculate_progress(task: Task) -> float:
    total_nodes = len(task.dag_json.get("nodes", []))
    if total_nodes == 0:
        return 0.0
    completed_nodes = sum(
        1 for status in task.node_states.values()
        if status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
    )
    return completed_nodes / total_nodes
```

**前端 - TaskDetail Header 显示进度条：**
```tsx
<div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
  <div style={{
    width: '120px', height: '8px',
    background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden'
  }}>
    <div style={{
      width: `${currentTask.progress * 100}%`,
      height: '100%',
      background: currentTask.status === 'running' ? '#3b82f6' : '#22c55e',
      transition: 'width 0.3s'
    }} />
  </div>
  <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
    {Math.round(currentTask.progress * 100)}%
  </span>
</div>
```

---

## 4. domain 格式校验加强

### 现状
```javascript
// 过于宽松，接受 .ab、example.com. 等无效格式
function isValidDomain(domain: string): boolean {
  return /\.[a-zA-Z]{2,}$/.test(domain.trim());
}
```

### 修复方案
```javascript
function isValidDomain(domain: string): boolean {
  const d = domain.trim();
  // 拒绝空值
  if (!d) return false;
  // 拒绝带协议、路径、端口、查询参数
  if (d.includes('/') || d.includes(':') || d.includes('?')) return false;
  // 拒绝末尾加点
  if (d.endsWith('.')) return false;
  // 基础域名格式：字母数字开头，至少一段顶级域名（2+字符）
  // 允许：feishu.cn, www.feishu.cn, sub.domain.co.uk
  // 拒绝：feishu, .com, example.com., -feishu.cn
  return /^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z]{2,})+$/.test(d);
}
```

**同时优化输入框错误提示：**
- 红色边框 + 下方提示文字
- 提示内容：`请输入有效域名，如 feishu.cn（不含 https://）`

---

## 5. 降级策略代码层校验

### 现状
`analyst.py` 中 `min_sources`（映射到 `evidence_threshold`）的降级逻辑全在 prompt 里：
```
min_sources 降级规则（分析时使用）：
- sources >= min_sources：正常输出，confidence.level = "high"
- 1 <= sources < min_sources：降级输出，confidence.level = "low"...
```

### 问题
依赖 LLM 正确理解并执行降级规则，行为不可靠。

### 修复方案

**analyst.py - 代码层实现降级校验：**

```python
async def execute(self, input_data: dict) -> AgentResult:
    evidence_threshold = input_data.get("evidence_threshold", 1)
    raw_data = input_data.get("raw_data", {})

    # 代码层计算 source 数量
    source_count = self._count_sources(raw_data)

    # 代码层确定 confidence 级别
    if source_count >= evidence_threshold:
        confidence_level = "high"
    elif source_count > 0:
        confidence_level = "low"  # 降级
    else:
        confidence_level = "insufficient"  # 数据不足

    # 将降级信息注入 prompt，让 LLM 遵循
    downgrade_hint = ""
    if confidence_level == "low":
        downgrade_hint = (
            f"\n[降级警告] 仅找到 {source_count} 条来源，未达最低要求 ({evidence_threshold})。"
            f"所有结论前必须加 ⚠️ 标记，confidence.level 设为 'low'。"
        )
    elif confidence_level == "insufficient":
        downgrade_hint = (
            "\n[数据不足] 未能找到足够来源，所有结论前加 ⚠️ 数据不足：，"
            "confidence.score 设为 0.0，level 设为 'low'。"
        )

    # 将降级提示注入 user message
    messages = [
        Message(role="system", content=self.SYSTEM_PROMPT),
        Message(role="user", content=json.dumps({
            **input_data,
            "_downgrade_hint": downgrade_hint,
            "_source_count": source_count,
            "_confidence_level": confidence_level,
        }, ensure_ascii=False, default=str)),
    ]
    # ... 后续处理
```

**同时在 analyst.py 中添加 `_count_sources` 辅助方法：**

```python
def _count_sources(self, raw_data: dict) -> int:
    """计算 raw_data 中独立来源的数量"""
    if not raw_data:
        return 0
    sources = raw_data.get("sources", [])
    if isinstance(sources, list):
        return len(sources)
    # 兼容不同的 raw_data 结构
    chunks = raw_data.get("chunks", [])
    if isinstance(chunks, list):
        # 按 URL 去重
        urls = set(c.get("url", "") for c in chunks if c.get("url"))
        return len(urls)
    return 0
```

---

## 6. 验收标准

| 问题 | 验收条件 |
|------|----------|
| report_html 未渲染 | TaskDetail 页面顶部显示报告内容（当 report_html 非空时） |
| 进度不透明 | TaskDetail Header 显示进度条，运行时百分比持续更新 |
| domain 校验 | 输入 `feishu`、`http://feishu.cn`、`.com` 时输入框变红并显示提示 |
| 降级策略 | 当 source_count < evidence_threshold 时，输出包含 ⚠️ 且 confidence.level = "low" |

---

## 7. 涉及文件清单

| 文件 | 修改内容 |
|------|----------|
| `backend/app/api/tasks.py` | TaskResponse 增加 progress 字段，计算 progress |
| `backend/app/agents/analyst.py` | 代码层实现 evidence_threshold 降级校验 |
| `backend/app/engine/orchestrator.py` | 传递 source_count 给 Analyst |
| `frontend/src/pages/TaskDetail.tsx` | 添加 ReportViewer 组件，显示进度条 |
| `frontend/src/pages/Dashboard.tsx` | 改进 domain 校验正则和错误提示 |
| `frontend/src/types/index.ts` | TaskSummary 增加 progress 字段 |

---

## 8. 测试验证

1. **report_html 渲染**：创建任务，等待完成，在 TaskDetail 页面顶部看到报告
2. **进度条**：运行时观察进度条增长，完成后显示 100%
3. **domain 校验**：尝试提交无效 domain，确认输入框变红
4. **降级策略**：模拟低数据场景，确认 ⚠️ 出现在输出中