# 溯源弹窗设计

## 背景

当前 `ReportViewer` 中点击 `🔍 浮动溯源` 按钮后，溯源信息在右侧 320px 窄面板中显示，空间有限，阅读体验差。

## 目标

将溯源信息的展示从右侧窄面板改为 95vw × 95vh 的全屏弹窗，充分利用屏幕空间。

## 方案

直接改造 `ReportViewer.tsx`，把现有窄面板逻辑替换为弹窗。

### 触发机制

保留现有事件委托逻辑：点击带有 `data-finding-id` 属性的元素 → 收集 Writer agent 的 TraceSource → 打开弹窗。

### 弹窗结构

```
[Backdrop: fixed 全屏, rgba(15,23,42,0.5), blur(6px), z-index 99]
[Modal: fixed 居中, 95vw × 95vh, z-index 100, 圆角 18px]
  [Header: sticky, 渐变 amber 背景, 标题 "溯源引用", 关闭按钮]
  [Content: overflow-y auto, padding 2rem]
    [来源卡片 × N]
      [类型 badge]
      [URL 链接]
      [snippet 引用片段]
```

### 样式

- 与 TaskDetail 的 AgentDetail 弹窗风格一致
- amber 色系（`#fffbeb` / `#92400e`）保持溯源主题
- 动画：backdrop 淡入 + 弹窗滑入缩放

### 改动范围

仅修改 `frontend/src/components/ReportViewer.tsx`，不新增文件。
