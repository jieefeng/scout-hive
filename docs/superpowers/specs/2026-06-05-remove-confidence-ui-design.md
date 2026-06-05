# 删除溯源浏览器置信度 UI

## 概述

移除 TraceBrowser 和 AgentDetail 中所有置信度相关的展示 UI。

## 变更范围

### 1. TraceBrowser（frontend/src/components/TraceBrowser.tsx）

删除第 296-318 行的置信度卡片区块：

```tsx
<div style={{
  flex: '1 1 200px', padding: '16px', borderRadius: '12px',
  background: '#fff', border: '1px solid #e2e8f0',
}}>
  <h4 style={{ margin: '0 0 10px', fontSize: '0.82rem', fontWeight: 700, color: '#64748b' }}>置信度</h4>
  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
    ...进度条...
  </div>
</div>
```

### 2. AgentDetail（frontend/src/components/AgentDetail.tsx）

删除 `ConfidenceRing` 组件（第 36-70 行）及其在渲染逻辑中的调用。

## 保留项

- `backend/app/models/analysis.py` — `Confidence` 类保留
- `backend/app/models/trace.py` — `TraceRecord.confidence` 字段保留
- `frontend/src/components/ConfidenceHeatmap.tsx` — 独立热力图组件保留
- `frontend/src/types/index.ts` — `TraceRecord` 类型定义保留

## 成功标准

- TraceBrowser 详情面板中不再显示置信度进度条
- AgentDetail 详情中不再显示置信度环形图
- 后端数据模型和字段不受影响
- 编译无错误

## 影响评估

- 无破坏性变更
- 不影响任何 API 接口
- 不需要数据迁移
- 不需要补充测试（纯 UI 移除）