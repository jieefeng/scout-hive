# 溯源弹窗 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 320px side panel in ReportViewer with a 95vw × 95vh modal for trace/source display.

**Architecture:** Modify `ReportViewer.tsx` — remove the side panel JSX, add a full-screen modal overlay matching the TaskDetail AgentDetail modal pattern. Trigger logic (event delegation on `data-finding-id`) stays unchanged.

**Tech Stack:** React 19, TypeScript, inline styles (no CSS modules)

---

### Task 1: Replace side panel with modal

**Files:**
- Modify: `frontend/src/components/ReportViewer.tsx:59-137`

- [ ] **Step 1: Replace the return JSX**

Replace the entire `<div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>` block (lines 60-136) with the following. The report content stays the same; the side panel is replaced by a modal overlay:

```tsx
return (
  <>
    <div
      ref={containerRef}
      style={{
        flex: 1, overflow: 'auto', padding: '2rem',
        lineHeight: 1.7, color: '#334155', fontSize: '0.92rem',
      }}
      dangerouslySetInnerHTML={{ __html: task.report_html }}
    />

    {/* ── Trace Modal ── */}
    {panelOpen && (
      <>
        {/* Backdrop */}
        <div
          onClick={() => setPanelOpen(false)}
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(15,23,42,0.5)', backdropFilter: 'blur(6px)',
            zIndex: 99, animation: 'reportModalFadeIn 0.2s ease',
          }}
        />
        {/* Modal */}
        <div style={{
          position: 'fixed', top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '95vw', height: '95vh',
          background: '#fff', borderRadius: '18px',
          boxShadow: '0 25px 80px rgba(0,0,0,0.25), 0 0 0 1px rgba(0,0,0,0.05)',
          zIndex: 100, overflow: 'hidden', display: 'flex', flexDirection: 'column',
          animation: 'reportModalSlideIn 0.25s ease',
        }}>
          {/* Header */}
          <div style={{
            padding: '16px 24px', borderBottom: '1px solid #fef3c7',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            position: 'sticky', top: 0,
            background: 'linear-gradient(135deg, #fffbeb, #fef3c7)',
            borderRadius: '18px 18px 0 0', zIndex: 1,
          }}>
            <span style={{ fontSize: '1rem', fontWeight: 700, color: '#92400e' }}>
              溯源引用
              {activeFindingId && (
                <span style={{ fontWeight: 400, fontSize: '0.8rem', marginLeft: '8px', color: '#b45309' }}>
                  ({activeFindingId})
                </span>
              )}
            </span>
            <button
              onClick={() => setPanelOpen(false)}
              style={{
                width: '32px', height: '32px', borderRadius: '8px',
                background: '#fef3c7', border: '1px solid #fde68a', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '1rem', color: '#92400e', lineHeight: 1, transition: 'all 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = '#fde68a'; e.currentTarget.style.color = '#78350f'; }}
              onMouseLeave={e => { e.currentTarget.style.background = '#fef3c7'; e.currentTarget.style.color = '#92400e'; }}
            >
              ✕
            </button>
          </div>

          {/* Content */}
          <div style={{ overflow: 'auto', flex: 1, padding: '2rem' }}>
            {panelSources.length === 0 ? (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                padding: '4rem 2rem', color: '#92400e', gap: '12px',
              }}>
                <span style={{ fontSize: '2.5rem' }}>📭</span>
                <span style={{ fontSize: '0.95rem', fontWeight: 600 }}>暂无来源数据</span>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '16px' }}>
                {panelSources.map((source, i) => (
                  <div key={source.source_id || i} style={{
                    padding: '20px', borderRadius: '12px',
                    background: '#fffbeb', border: '1px solid #fde68a',
                    transition: 'box-shadow 0.15s',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                  }}>
                    <div style={{ marginBottom: '10px' }}>
                      <span style={{
                        fontSize: '0.72rem', fontWeight: 600, color: '#92400e',
                        background: '#fef3c7', padding: '3px 8px', borderRadius: '4px',
                        textTransform: 'uppercase',
                      }}>
                        {source.type}
                      </span>
                    </div>
                    {source.url && (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          fontSize: '0.85rem', color: '#b45309', textDecoration: 'none',
                          display: 'block', marginBottom: '12px', wordBreak: 'break-all',
                        }}
                      >
                        {source.url} ↗
                      </a>
                    )}
                    {source.snippet && (
                      <p style={{
                        margin: 0, fontSize: '0.88rem', color: '#78350f', lineHeight: 1.6,
                        background: '#fef9e7', padding: '12px 14px', borderRadius: '8px',
                        border: '1px solid #fde68a',
                      }}>
                        {source.snippet}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Animation keyframes */}
        <style>{`
          @keyframes reportModalFadeIn { from { opacity: 0 } to { opacity: 1 } }
          @keyframes reportModalSlideIn { from { opacity: 0; transform: translate(-50%, -48%) scale(0.96) } to { opacity: 1; transform: translate(-50%, -50%) scale(1) } }
        `}</style>
      </>
    )}
  </>
);
```

- [ ] **Step 2: Remove the outer flex container wrapper**

The old code wrapped everything in `<div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>`. The new code uses a fragment (`<>`) instead, so the report content div no longer needs `flex: 1`. Verify the `ref={containerRef}` div's style is unchanged (it already has `overflow: 'auto'`).

- [ ] **Step 3: Verify in browser**

Run the frontend dev server and test:
1. Open a task with a completed report
2. Click a `🔍 浮动溯源` button in the report
3. Verify: 95vw × 95vh modal appears with backdrop blur
4. Verify: sources displayed in grid cards with amber styling
5. Verify: click backdrop or ✕ to close

```bash
cd frontend && npm run dev
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ReportViewer.tsx
git commit -m "feat: replace trace side panel with full-screen modal"
```
