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
}