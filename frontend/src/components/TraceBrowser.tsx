import { useState } from 'react';
import type { TraceRecord } from '../types';

interface TraceBrowserProps { traces: TraceRecord[]; }

const AGENT_FULL_NAME: Record<string, string> = {
  c: 'Collector', collector: 'Collector', Collector: 'Collector',
  a: 'Analyst',   analyst: 'Analyst',     Analyst: 'Analyst',
  w: 'Writer',    writer: 'Writer',       Writer: 'Writer',
  r: 'Reviewer',  reviewer: 'Reviewer',   Reviewer: 'Reviewer',
};

function expandAgentName(name: string): string {
  return AGENT_FULL_NAME[name] || name;
}

const AGENT_THEME: Record<string, { color: string; bg: string; icon: string }> = {
  Collector: { color: '#3b82f6', bg: '#eff6ff', icon: '🔍' },
  Analyst:   { color: '#8b5cf6', bg: '#f5f3ff', icon: '📊' },
  Writer:    { color: '#10b981', bg: '#ecfdf5', icon: '✍️' },
  Reviewer:  { color: '#f59e0b', bg: '#fffbeb', icon: '🔎' },
};

export default function TraceBrowser({ traces }: TraceBrowserProps) {
  const [selectedTrace, setSelectedTrace] = useState<TraceRecord | null>(null);
  const [showSourcePanel, setShowSourcePanel] = useState(false);

  if (!traces.length) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: '3rem 2rem', color: '#94a3b8', gap: '10px',
      }}>
        <span style={{ fontSize: '2.5rem' }}>📭</span>
        <span style={{ fontSize: '0.95rem', fontWeight: 600, color: '#64748b' }}>暂无溯源记录</span>
        <span style={{ fontSize: '0.82rem' }}>任务执行后将在此显示推理过程</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100%', minHeight: '400px' }}>
      <div style={{
        width: '260px', minWidth: '220px', overflow: 'auto',
        borderRight: '1px solid #e2e8f0', background: '#fafbfc',
      }}>
        <div style={{
          padding: '12px 16px', borderBottom: '1px solid #e2e8f0',
          fontSize: '0.82rem', fontWeight: 700, color: '#64748b',
          textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>
          溯源记录 ({traces.length})
        </div>
        {traces.map(trace => {
          const agentName = expandAgentName(trace.agent);
          const theme = AGENT_THEME[agentName] || { color: '#64748b', bg: '#f1f5f9', icon: '⚙️' };
          const isActive = selectedTrace?.trace_id === trace.trace_id;
          return (
            <div
              key={trace.trace_id}
              onClick={() => setSelectedTrace(trace)}
              style={{
                padding: '12px 16px', cursor: 'pointer',
                background: isActive ? '#fff' : 'transparent',
                borderLeft: isActive ? `3px solid ${theme.color}` : '3px solid transparent',
                borderBottom: '1px solid #f1f5f9',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = '#f8fafc'; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span style={{
                  width: '24px', height: '24px', borderRadius: '6px',
                  background: theme.bg, display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: '0.75rem', flexShrink: 0,
                }}>
                  {theme.icon}
                </span>
                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#1e293b' }}>
                  {agentName}
                </span>
              </div>
              <div style={{ fontSize: '0.72rem', color: '#64748b', marginLeft: '32px' }}>
                {trace.node_id}
              </div>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8', marginLeft: '32px', marginTop: '2px' }}>
                {trace.timestamp ? new Date(trace.timestamp).toLocaleString('zh-CN') : ''}
              </div>
            </div>
          );
        })}
      </div>

      {selectedTrace ? (
        <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px',
            paddingBottom: '16px', borderBottom: '1px solid #f1f5f9',
          }}>
            {(() => {
              const agentName = expandAgentName(selectedTrace.agent);
              const theme = AGENT_THEME[agentName] || { color: '#64748b', bg: '#f1f5f9', icon: '⚙️' };
              return (
                <>
                  <div style={{
                    width: '40px', height: '40px', borderRadius: '10px',
                    background: theme.bg, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', fontSize: '1.2rem',
                  }}>
                    {theme.icon}
                  </div>
                  <div>
                    <div style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b' }}>{agentName}</div>
                    <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>{selectedTrace.node_id}</div>
                  </div>
                </>
              );
            })()}
          </div>

          <div style={{ marginBottom: '24px' }}>
            <h4 style={{
              margin: '0 0 14px', fontSize: '0.85rem', fontWeight: 700,
              color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px',
            }}>
              <span style={{
                width: '4px', height: '16px', borderRadius: '2px',
                background: 'linear-gradient(180deg, #8b5cf6, #7c3aed)',
              }} />
              推理链
            </h4>
            {selectedTrace.reasoning_chain?.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {selectedTrace.reasoning_chain.map((step, i) => {
                  const theme = AGENT_THEME[expandAgentName(selectedTrace.agent)] || { color: '#64748b' };
                  return (
                    <div key={i} style={{
                      padding: '14px 16px', background: '#f8fafc', borderRadius: '10px',
                      border: '1px solid #e2e8f0', fontSize: '0.85rem', lineHeight: 1.6,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <span style={{
                          width: '22px', height: '22px', borderRadius: '50%',
                          background: theme.color, color: '#fff', fontSize: '0.65rem',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontWeight: 700, flexShrink: 0,
                        }}>
                          {step.step}
                        </span>
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b' }}>步骤 {step.step}</span>
                      </div>
                      <p style={{ margin: 0, color: '#334155' }}>{step.thought}</p>
                      {step.source_ref && (
                        <button
                          onClick={() => setShowSourcePanel(true)}
                          style={{
                            marginTop: '8px', fontSize: '0.75rem', color: theme.color,
                            cursor: 'pointer', background: theme.color + '12', border: 'none',
                            padding: '4px 10px', borderRadius: '6px', fontWeight: 500,
                          }}
                        >
                          📎 查看原文
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{
                padding: '1.5rem', textAlign: 'center', color: '#94a3b8',
                background: '#f8fafc', borderRadius: '10px', border: '1px dashed #e2e8f0',
                fontSize: '0.85rem',
              }}>
                暂无推理记录
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            <div style={{
              flex: '1 1 200px', padding: '16px', borderRadius: '12px',
              background: '#fff', border: '1px solid #e2e8f0',
            }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '0.82rem', fontWeight: 700, color: '#64748b' }}>置信度</h4>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ flex: 1, height: '8px', background: '#f1f5f9', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${(selectedTrace.confidence?.score || 0) * 100}%`,
                    background: selectedTrace.confidence?.level === 'high'
                      ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                      : selectedTrace.confidence?.level === 'medium'
                        ? 'linear-gradient(90deg, #f59e0b, #d97706)'
                        : 'linear-gradient(90deg, #ef4444, #dc2626)',
                    height: '100%', borderRadius: '4px', transition: 'width 0.5s ease',
                  }} />
                </div>
                <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b', minWidth: '40px', textAlign: 'right' }}>
                  {Math.round((selectedTrace.confidence?.score || 0) * 100)}%
                </span>
              </div>
            </div>

            <div style={{
              flex: '1 1 200px', padding: '16px', borderRadius: '12px',
              background: '#fff', border: '1px solid #e2e8f0',
            }}>
              <h4 style={{ margin: '0 0 10px', fontSize: '0.82rem', fontWeight: 700, color: '#64748b' }}>LLM 元信息</h4>
              <div style={{ display: 'flex', gap: '16px', fontSize: '0.82rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ color: '#94a3b8', fontSize: '0.72rem' }}>模型</span>
                  <span style={{ fontWeight: 600, color: '#1e293b' }}>{selectedTrace.llm_metadata?.model || '-'}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ color: '#94a3b8', fontSize: '0.72rem' }}>Token</span>
                  <span style={{ fontWeight: 600, color: '#1e293b' }}>{selectedTrace.llm_metadata?.tokens_used?.toLocaleString() || '-'}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ color: '#94a3b8', fontSize: '0.72rem' }}>耗时</span>
                  <span style={{ fontWeight: 600, color: '#1e293b' }}>{selectedTrace.llm_metadata?.latency_ms ? `${(selectedTrace.llm_metadata.latency_ms / 1000).toFixed(1)}s` : '-'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', color: '#94a3b8', gap: '8px',
        }}>
          <span style={{ fontSize: '2rem' }}>👆</span>
          <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#64748b' }}>选择一条溯源记录</span>
          <span style={{ fontSize: '0.78rem' }}>点击左侧列表查看详情</span>
        </div>
      )}

      {showSourcePanel && selectedTrace && (
        <div style={{
          width: '300px', overflow: 'auto', borderLeft: '1px solid #e2e8f0', background: '#fffbeb',
        }}>
          <div style={{
            padding: '12px 16px', borderBottom: '1px solid #fef3c7',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#92400e' }}>原文引用</span>
            <button
              onClick={() => setShowSourcePanel(false)}
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
          {selectedTrace.sources?.map((source, i) => (
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
                <a href={source.url} target="_blank" rel="noopener noreferrer"
                  style={{
                    fontSize: '0.78rem', color: '#b45309', textDecoration: 'none',
                    display: 'block', marginBottom: '8px', wordBreak: 'break-all',
                  }}>
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
          ))}
        </div>
      )}
    </div>
  );
}
