# 删除溯源浏览器置信度 UI 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 TraceBrowser 和 AgentDetail 中的置信度展示 UI，保留后端数据模型不变。

**Architecture:** 纯前端 UI 移除 — 删除 TraceBrowser.tsx 中的置信度进度条卡片和 AgentDetail.tsx 中的 ConfidenceRing 组件及其调用。

**Tech Stack:** React 19 + TypeScript (strict), 前端组件

---

## 文件清单

| 文件 | 职责 |
|------|------|
| `frontend/src/components/TraceBrowser.tsx` | 移除置信度卡片（第 296-318 行） |
| `frontend/src/components/AgentDetail.tsx` | 移除 ConfidenceRing 组件（第 36-70 行）及其调用（第 301 行变量、第 352 行 JSX） |

---

## Task 1: TraceBrowser — 移除置信度卡片

**Files:**
- Modify: `frontend/src/components/TraceBrowser.tsx:296-318`

- [ ] **Step 1: 确认当前文件内容**

读取 `frontend/src/components/TraceBrowser.tsx` 第 290-340 行，确认置信度卡片的起止位置。

- [ ] **Step 2: 删除置信度卡片**

删除第 296-318 行的置信度卡片区块（包含 `置信度` 标题的 flex 卡片）。

- [ ] **Step 3: 验证编译**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: 无错误（仅有已存在的类型检查警告可忽略）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TraceBrowser.tsx
git commit -m "fix: remove confidence card from TraceBrowser"
```

---

## Task 2: AgentDetail — 移除 ConfidenceRing 组件

**Files:**
- Modify: `frontend/src/components/AgentDetail.tsx:36-70` (ConfidenceRing 组件定义)
- Modify: `frontend/src/components/AgentDetail.tsx:301` (confidence 变量)
- Modify: `frontend/src/components/AgentDetail.tsx:352` (ConfidenceRing 调用)

- [ ] **Step 1: 确认当前文件内容**

读取 `frontend/src/components/AgentDetail.tsx` 第 30-80 行（ConfidenceRing 组件）和第 295-360 行（使用处）。

- [ ] **Step 2: 删除 ConfidenceRing 组件定义**

删除第 36-70 行的 `ConfidenceRing` 函数组件。

- [ ] **Step 3: 删除 confidence 变量**

删除第 301 行：
```tsx
const confidence = trace.confidence || { score: 0, level: 'unknown' };
```

- [ ] **Step 4: 删除 ConfidenceRing 调用**

删除第 352 行：
```tsx
<ConfidenceRing score={confidence.score} level={confidence.level} accent={theme.accent} />
```

- [ ] **Step 5: 验证编译**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AgentDetail.tsx
git commit -m "fix: remove ConfidenceRing from AgentDetail"
```

---

## 成功标准

- `TraceBrowser` 详情面板中不再显示置信度进度条
- `AgentDetail` 详情中不再显示置信度环形图
- 后端数据模型（`Confidence` 类、`TraceRecord.confidence` 字段）不受影响
- `npx tsc --noEmit` 无编译错误