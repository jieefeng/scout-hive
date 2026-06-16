import { useState } from 'react';
import type { TraceRecord, ReasoningStep, TraceSource } from '../types';

interface AgentDetailProps {
  trace: TraceRecord | null;
  nodeId?: string | null;
}

/* ── Agent color themes ── */
const AGENT_FULL_NAME: Record<string, string> = {
  c: 'Collector', collector: 'Collector', Collector: 'Collector',
  a: 'Analyst',   analyst: 'Analyst',     Analyst: 'Analyst',
  w: 'Writer',    writer: 'Writer',       Writer: 'Writer',
  r: 'Reviewer',  reviewer: 'Reviewer',   Reviewer: 'Reviewer',
};

function expandAgentName(name: string): string {
  return AGENT_FULL_NAME[name] || name;
}

const AGENT_THEME: Record<string, {
  accent: string; bg: string; icon: string; label: string;
  gradient: string; glow: string; darkBg: string;
}> = {
  Collector: {
    accent: '#3b82f6', bg: '#eff6ff', icon: '🔍', label: '数据采集',
    gradient: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #60a5fa 100%)',
    glow: '0 8px 32px rgba(59,130,246,0.25)',
    darkBg: '#1e3a5f',
  },
  Analyst: {
    accent: '#8b5cf6', bg: '#f5f3ff', icon: '📊', label: '结构分析',
    gradient: 'linear-gradient(135deg, #5b21b6 0%, #8b5cf6 50%, #a78bfa 100%)',
    glow: '0 8px 32px rgba(139,92,246,0.25)',
    darkBg: '#3b1f6e',
  },
  Writer: {
    accent: '#10b981', bg: '#ecfdf5', icon: '✍️', label: '报告写作',
    gradient: 'linear-gradient(135deg, #065f46 0%, #10b981 50%, #34d399 100%)',
    glow: '0 8px 32px rgba(16,185,129,0.25)',
    darkBg: '#1a3d2e',
  },
  Reviewer: {
    accent: '#f59e0b', bg: '#fffbeb', icon: '🔎', label: '质量审查',
    gradient: 'linear-gradient(135deg, #92400e 0%, #f59e0b 50%, #fbbf24 100%)',
    glow: '0 8px 32px rgba(245,158,11,0.25)',
    darkBg: '#4a2c0a',
  },
};

const defaultTheme = {
  accent: '#64748b', bg: '#f8fafc', icon: '⚙️', label: '未知',
  gradient: 'linear-gradient(135deg, #334155 0%, #64748b 50%, #94a3b8 100%)',
  glow: '0 8px 32px rgba(100,116,139,0.2)',
  darkBg: '#1e293b',
};

function getTheme(agent: string) {
  return AGENT_THEME[expandAgentName(agent)] || defaultTheme;
}

/* ── Metric card ── */
function MetricCard({ icon, label, value, accent }: { icon: string; label: string; value: string; accent: string }) {
  return (
    <div style={{
      flex: 1, padding: '16px 20px', borderRadius: '14px',
      background: '#fff', border: '1px solid #e2e8f0',
      display: 'flex', flexDirection: 'column', gap: '10px',
      minWidth: '140px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.02)',
      transition: 'box-shadow 0.2s, transform 0.2s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '1.1rem' }}>{icon}</span>
        <span style={{
          fontSize: '0.72rem', color: '#94a3b8', fontWeight: 600,
          textTransform: 'uppercase', letterSpacing: '0.06em',
        }}>{label}</span>
      </div>
      <span style={{
        fontSize: '1.1rem', fontWeight: 700, color: '#1e293b',
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      }}>{value}</span>
    </div>
  );
}

/* ── Tab bar ── */
type TabKey = 'overview' | 'input' | 'output' | 'reasoning' | 'sources';

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'overview',   label: '概览',   icon: '📋' },
  { key: 'input',      label: '输入',   icon: '📥' },
  { key: 'output',     label: '输出',   icon: '📤' },
  { key: 'reasoning',  label: '推理链', icon: '🧠' },
  { key: 'sources',    label: '数据源', icon: '🔗' },
];

/* ── JSON syntax-highlighted block ── */
function JsonBlock({ data, maxHeight }: { data: unknown; maxHeight?: string }) {
  const json = JSON.stringify(data, null, 2);
  if (!json || json === 'null' || json === '{}') {
    return (
      <div style={{
        padding: '3rem 2rem', textAlign: 'center', color: '#94a3b8',
        fontSize: '0.88rem', fontStyle: 'italic',
        background: '#f8fafc', borderRadius: '14px', border: '1px dashed #d1d5db',
      }}>
        暂无数据
      </div>
    );
  }

  const highlighted = json
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"([^"]+)"(?=\s*:)/g, '<span style="color:#7c3aed;font-weight:500">"$1"</span>')
    .replace(/: "([^"]*)"/g, ': <span style="color:#059664">"$1"</span>')
    .replace(/: (\d+\.?\d*)/g, ': <span style="color:#d97706;font-weight:500">$1</span>')
    .replace(/: (true|false|null)/g, ': <span style="color:#dc2626;font-weight:500">$1</span>');

  return (
    <pre
      style={{
        background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)',
        padding: '1.25rem 1.5rem', borderRadius: '14px',
        overflow: 'auto', maxHeight: maxHeight || '400px', fontSize: '0.82rem',
        border: '1px solid #e2e8f0', lineHeight: 1.7, margin: 0,
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
        boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.04)',
        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
      }}
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  );
}

/* ── Reasoning chain ── */
function ReasoningChain({ steps, accent }: { steps: ReasoningStep[]; accent: string }) {
  if (!steps || steps.length === 0) {
    return (
      <div style={{
        padding: '3rem 2rem', textAlign: 'center', color: '#94a3b8',
        fontSize: '0.88rem', background: '#f8fafc', borderRadius: '14px',
        border: '1px dashed #d1d5db',
      }}>
        <span style={{ fontSize: '2rem', display: 'block', marginBottom: '8px' }}>🧠</span>
        暂无推理记录
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
      {steps.map((step, i) => (
        <div key={i} style={{ display: 'flex', gap: '16px' }}>
          {/* Timeline */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '28px' }}>
            <div style={{
              width: '28px', height: '28px', borderRadius: '50%',
              background: accent, color: '#fff', fontSize: '0.72rem',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 700, flexShrink: 0,
              boxShadow: `0 2px 8px ${accent}40`,
            }}>
              {step.step}
            </div>
            {i < steps.length - 1 && (
              <div style={{
                width: '2px', flex: 1,
                background: `linear-gradient(180deg, ${accent}30, ${accent}10)`,
                minHeight: '24px',
              }} />
            )}
          </div>
          {/* Content card */}
          <div style={{
            padding: '14px 18px', background: '#fff', border: '1px solid #e2e8f0',
            borderRadius: '12px', marginBottom: '14px', flex: 1,
            fontSize: '0.88rem', lineHeight: 1.7, color: '#334155',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
            transition: 'box-shadow 0.2s',
          }}>
            <p style={{ margin: 0 }}>{step.thought}</p>
            {step.source_ref && (
              <span style={{
                display: 'inline-block', marginTop: '8px', fontSize: '0.72rem',
                color: accent, background: `${accent}12`, padding: '3px 10px',
                borderRadius: '8px', fontWeight: 600,
              }}>
                📎 {step.source_ref}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Sources list ── */
function SourcesList({ sources, accent }: { sources: TraceSource[]; accent: string }) {
  if (!sources || sources.length === 0) {
    return (
      <div style={{
        padding: '3rem 2rem', textAlign: 'center', color: '#94a3b8',
        fontSize: '0.88rem', background: '#f8fafc', borderRadius: '14px',
        border: '1px dashed #d1d5db',
      }}>
        <span style={{ fontSize: '2rem', display: 'block', marginBottom: '8px' }}>🔗</span>
        暂无数据源
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {sources.map((src, i) => (
        <div key={i} style={{
          padding: '16px 20px', background: '#fff', border: '1px solid #e2e8f0',
          borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '8px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          transition: 'box-shadow 0.2s, border-color 0.2s',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{
                fontSize: '0.7rem', fontWeight: 700, color: accent,
                background: `${accent}14`, padding: '3px 10px', borderRadius: '8px',
                textTransform: 'uppercase', letterSpacing: '0.04em',
              }}>
                {src.type}
              </span>
              <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#1e293b' }}>
                {src.source_id}
              </span>
            </div>
            {src.url && (
              <a
                href={src.url} target="_blank" rel="noopener noreferrer"
                style={{
                  fontSize: '0.78rem', color: accent, textDecoration: 'none',
                  display: 'flex', alignItems: 'center', gap: '4px',
                  padding: '4px 10px', borderRadius: '6px',
                  background: `${accent}08`, transition: 'background 0.15s',
                }}
              >
                访问 ↗
              </a>
            )}
          </div>
          {src.snippet && (
            <p style={{
              margin: 0, fontSize: '0.85rem', color: '#64748b', lineHeight: 1.6,
              display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}>
              {src.snippet}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Empty / placeholder states ── */
function EmptyState({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '5rem 2rem', color: '#94a3b8', gap: '14px',
    }}>
      <span style={{ fontSize: '3.5rem' }}>{icon}</span>
      <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#64748b' }}>{title}</span>
      <span style={{ fontSize: '0.9rem', color: '#94a3b8', maxWidth: '300px', textAlign: 'center', lineHeight: 1.6 }}>{desc}</span>
    </div>
  );
}

/* ── Section heading ── */
function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h4 style={{
      margin: '0 0 12px', fontSize: '0.88rem', color: '#475569', fontWeight: 700,
      display: 'flex', alignItems: 'center', gap: '8px',
      letterSpacing: '-0.01em',
    }}>
      {children}
    </h4>
  );
}

/* ── Main component ── */
export default function AgentDetail({ trace, nodeId }: AgentDetailProps) {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');

  if (!nodeId) {
    return <EmptyState icon="👆" title="选择节点" desc="点击 DAG 中的任意节点查看详情" />;
  }

  if (!trace) {
    return (
      <div style={{ padding: '2.5rem' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '1.5rem',
        }}>
          <div style={{
            width: '56px', height: '56px', borderRadius: '16px',
            background: 'linear-gradient(135deg, #f1f5f9, #e2e8f0)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.8rem',
            boxShadow: '0 4px 12px rgba(0,0,0,0.06)',
          }}>
            ⏳
          </div>
          <div>
            <p style={{ margin: 0, fontWeight: 700, fontSize: '1.15rem', color: '#1e293b' }}>{nodeId}</p>
            <p style={{ margin: 0, fontSize: '0.88rem', color: '#94a3b8', marginTop: '4px' }}>
              等待执行后将显示详情
            </p>
          </div>
        </div>
        <div style={{
          padding: '3rem 2rem', background: '#f8fafc', borderRadius: '16px',
          border: '1px dashed #cbd5e1', textAlign: 'center', color: '#94a3b8',
          fontSize: '0.9rem', lineHeight: 1.7,
        }}>
          <span style={{ fontSize: '2rem', display: 'block', marginBottom: '10px' }}>📭</span>
          该节点尚未运行，执行完成后可查看输入、输出、推理链和数据源
        </div>
      </div>
    );
  }

  const theme = getTheme(trace.agent);
  const meta = trace.llm_metadata || { model: '-', tokens_used: 0, latency_ms: 0 };
  const hasReasoning = trace.reasoning_chain && trace.reasoning_chain.length > 0;
  const hasSources = trace.sources && trace.sources.length > 0;

  const tabsWithCount = TABS.map(t => ({
    ...t,
    disabled: (t.key === 'reasoning' && !hasReasoning) || (t.key === 'sources' && !hasSources),
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {/* ── Hero header with gradient ── */}
      <div style={{
        background: theme.gradient,
        padding: '28px 32px',
        display: 'flex', alignItems: 'center', gap: '20px',
        position: 'relative', overflow: 'hidden',
      }}>
        {/* Decorative circles */}
        <div style={{
          position: 'absolute', top: '-30px', right: '-30px', width: '140px', height: '140px',
          borderRadius: '50%', background: 'rgba(255,255,255,0.08)',
        }} />
        <div style={{
          position: 'absolute', bottom: '-50px', left: '20%', width: '180px', height: '180px',
          borderRadius: '50%', background: 'rgba(255,255,255,0.04)',
        }} />
        {/* Grid pattern overlay */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'radial-gradient(rgba(255,255,255,0.08) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
        }} />

        {/* Agent icon */}
        <div style={{
          width: '64px', height: '64px', borderRadius: '18px',
          background: 'rgba(255,255,255,0.18)',
          backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.8rem', flexShrink: 0,
          boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
          border: '1px solid rgba(255,255,255,0.2)',
        }}>
          {theme.icon}
        </div>

        {/* Agent info */}
        <div style={{ flex: 1, minWidth: 0, position: 'relative', zIndex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <span style={{
              fontSize: '0.72rem', fontWeight: 700, color: '#fff',
              background: 'rgba(255,255,255,0.2)', padding: '4px 12px', borderRadius: '8px',
              backdropFilter: 'blur(4px)',
              border: '1px solid rgba(255,255,255,0.15)',
              letterSpacing: '0.04em',
            }}>
              {theme.label}
            </span>
            {trace.timestamp && (
              <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.65)' }}>
                {new Date(trace.timestamp).toLocaleString('zh-CN')}
              </span>
            )}
          </div>
          <h3 style={{
            margin: 0, fontSize: '1.3rem', fontWeight: 700, color: '#fff',
            letterSpacing: '-0.02em',
            textShadow: '0 1px 2px rgba(0,0,0,0.1)',
          }}>
            {trace.node_id}
          </h3>
        </div>
      </div>

      {/* ── Error banner (failed nodes) ── */}
      {trace.error_message && (
        <div style={{
          margin: '20px 28px 0', padding: '16px 20px', borderRadius: '14px',
          background: 'linear-gradient(135deg, #fef2f2, #fee2e2)',
          border: '1px solid #fecaca',
          display: 'flex', alignItems: 'flex-start', gap: '14px',
        }}>
          <span style={{ fontSize: '1.3rem', flexShrink: 0, marginTop: '2px' }}>❌</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#991b1b', marginBottom: '6px' }}>
              执行失败
            </div>
            <div style={{
              fontSize: '0.85rem', color: '#b91c1c', lineHeight: 1.6,
              wordBreak: 'break-word',
            }}>
              {trace.error_message}
            </div>
          </div>
        </div>
      )}

      {/* ── Metrics strip ── */}
      <div style={{
        display: 'flex', gap: '12px', padding: '18px 28px',
        background: 'linear-gradient(180deg, #f8fafc, #f1f5f9)',
        borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap',
      }}>
        <MetricCard icon="🤖" label="模型" value={meta.model || '-'} accent={theme.accent} />
        <MetricCard icon="🪙" label="Token" value={meta.tokens_used ? meta.tokens_used.toLocaleString() : '-'} accent={theme.accent} />
        <MetricCard icon="⏱️" label="耗时" value={meta.latency_ms ? `${(meta.latency_ms / 1000).toFixed(1)}s` : '-'} accent={theme.accent} />
      </div>

      {/* ── Tab bar ── */}
      <div style={{
        display: 'flex', gap: '4px', padding: '6px 28px',
        borderBottom: '1px solid #e2e8f0', background: '#fff',
      }}>
        {tabsWithCount.map(tab => (
          <button
            key={tab.key}
            onClick={() => !tab.disabled && setActiveTab(tab.key)}
            style={{
              padding: '10px 18px', fontSize: '0.85rem',
              fontWeight: activeTab === tab.key ? 700 : 500,
              color: tab.disabled ? '#cbd5e1' : activeTab === tab.key ? theme.accent : '#64748b',
              background: activeTab === tab.key ? `${theme.accent}10` : 'transparent',
              border: 'none', cursor: tab.disabled ? 'not-allowed' : 'pointer',
              borderRadius: '10px',
              display: 'flex', alignItems: 'center', gap: '6px',
              transition: 'all 0.2s ease',
              position: 'relative',
            }}
          >
            <span style={{ fontSize: '0.95rem' }}>{tab.icon}</span>
            {tab.label}
            {tab.disabled && (
              <span style={{ fontSize: '0.55rem', color: '#cbd5e1', marginLeft: '2px' }}>·</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab content ── */}
      <div style={{ padding: '24px 28px', minHeight: '240px' }}>
        {activeTab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <SectionHeading>
                <span style={{
                  width: '4px', height: '16px', borderRadius: '2px',
                  background: theme.accent, display: 'inline-block',
                }} />
                输出结果
              </SectionHeading>
              <JsonBlock data={trace.output} maxHeight="300px" />
            </div>
            <div>
              <SectionHeading>
                <span style={{
                  width: '4px', height: '16px', borderRadius: '2px',
                  background: '#94a3b8', display: 'inline-block',
                }} />
                输入参数
              </SectionHeading>
              <JsonBlock data={trace.input_refs} maxHeight="180px" />
            </div>
          </div>
        )}

        {activeTab === 'input' && (
          <div>
            <SectionHeading>
              <span style={{
                width: '4px', height: '16px', borderRadius: '2px',
                background: theme.accent, display: 'inline-block',
              }} />
              输入引用 (input_refs)
            </SectionHeading>
            <JsonBlock data={trace.input_refs} />
          </div>
        )}

        {activeTab === 'output' && (
          <div>
            <SectionHeading>
              <span style={{
                width: '4px', height: '16px', borderRadius: '2px',
                background: theme.accent, display: 'inline-block',
              }} />
              输出数据 (output)
            </SectionHeading>
            <JsonBlock data={trace.output} />
          </div>
        )}

        {activeTab === 'reasoning' && (
          <div>
            <SectionHeading>
              <span style={{
                width: '4px', height: '16px', borderRadius: '2px',
                background: theme.accent, display: 'inline-block',
              }} />
              推理过程
            </SectionHeading>
            <ReasoningChain steps={trace.reasoning_chain || []} accent={theme.accent} />
          </div>
        )}

        {activeTab === 'sources' && (
          <div>
            <SectionHeading>
              <span style={{
                width: '4px', height: '16px', borderRadius: '2px',
                background: theme.accent, display: 'inline-block',
              }} />
              数据来源 ({trace.sources?.length || 0})
            </SectionHeading>
            <SourcesList sources={trace.sources || []} accent={theme.accent} />
          </div>
        )}
      </div>
    </div>
  );
}
