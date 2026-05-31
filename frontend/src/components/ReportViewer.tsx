import { useEffect, useRef, useState } from 'react';
import type { TaskSummary, TraceSource } from '../types';

interface ReportViewerProps {
  task: TaskSummary | null;
  onFindingClick?: (findingId: string, sourceId: string) => void;
}

export default function ReportViewer({ task, onFindingClick }: ReportViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelSources, setPanelSources] = useState<TraceSource[]>([]);
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);

  // Event delegation for data-finding-id clicks in dangerouslySetInnerHTML
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e: MouseEvent) => {
      let target = e.target as HTMLElement | null;
      while (target && target !== el) {
        const findingId = target.dataset.findingId;
        if (findingId) {
          e.preventDefault();
          setActiveFindingId(findingId);
          const allSources: TraceSource[] = [];
          for (const trace of task?.traces ?? []) {
            const agent = trace.agent;
            if ((agent === 'Writer' || agent === 'w') && trace.sources) {
              allSources.push(...trace.sources);
            }
          }
          if (allSources.length > 0) {
            setPanelSources(allSources);
            setPanelOpen(true);
          }
          onFindingClick?.(findingId, '');
          return;
        }
        target = target.parentElement;
      }
    };
    el.addEventListener('click', handler);
    return () => el.removeEventListener('click', handler);
  }, [task?.traces, onFindingClick]);

  if (!task?.report_html) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: '3rem 2rem', color: '#94a3b8', gap: '10px',
      }}>
        <span style={{ fontSize: '2rem' }}>📄</span>
        <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#64748b' }}>报告生成中...</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      <div
        ref={containerRef}
        style={{
          flex: 1, overflow: 'auto', padding: '2rem',
          lineHeight: 1.7, color: '#334155', fontSize: '0.92rem',
        }}
        dangerouslySetInnerHTML={{ __html: task.report_html }}
      />
      {panelOpen && (
        <div style={{
          width: '320px', overflow: 'auto', flexShrink: 0,
          background: '#fffbeb', borderLeft: '1px solid #e2e8f0',
        }}>
          <div style={{
            padding: '12px 16px', borderBottom: '1px solid #fef3c7',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#92400e' }}>
              溯源引用 {activeFindingId && <span style={{ fontWeight: 400, fontSize: '0.75rem' }}>({activeFindingId})</span>}
            </span>
            <button
              onClick={() => setPanelOpen(false)}
              style={{
                width: '26px', height: '26px', borderRadius: '6px',
                background: '#fef3c7', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.8rem', color: '#92400e',
              }}
            >
              ✕
            </button>
          </div>
          {panelSources.length === 0 ? (
            <div style={{ padding: '24px 16px', textAlign: 'center', color: '#92400e', fontSize: '0.82rem' }}>
              暂无来源数据
            </div>
          ) : (
            panelSources.map((source, i) => (
              <div key={source.source_id || i} style={{ padding: '14px 16px', borderBottom: '1px solid #fef3c7' }}>
                <div style={{ marginBottom: '6px' }}>
                  <span style={{
                    fontSize: '0.68rem', fontWeight: 600, color: '#92400e',
                    background: '#fef3c7', padding: '2px 6px', borderRadius: '4px',
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
                      fontSize: '0.78rem', color: '#b45309', textDecoration: 'none',
                      display: 'block', marginBottom: '8px', wordBreak: 'break-all',
                    }}
                  >
                    {source.url} ↗
                  </a>
                )}
                {source.snippet && (
                  <p style={{
                    margin: 0, fontSize: '0.8rem', color: '#78350f', lineHeight: 1.5,
                    background: '#fef9e7', padding: '8px 10px', borderRadius: '6px',
                    border: '1px solid #fde68a',
                  }}>
                    {source.snippet}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}