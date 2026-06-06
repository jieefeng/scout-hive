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

const AGENT_THEME: Record<string, { accent: string; bg: string; icon: string; label: string }> = {
  Collector: { accent: '#3b82f6', bg: '#eff6ff', icon: '🔍', label: '数据采集' },
  Analyst:   { accent: '#8b5cf6', bg: '#f5f3ff', icon: '📊', label: '结构分析' },
  Writer:    { accent: '#10b981', bg: '#ecfdf5', icon: '✍️', label: '报告写作' },
  Reviewer:  { accent: '#f59e0b', bg: '#fffbeb', icon: '🔎', label: '质量审查' },
};

const defaultTheme = { accent: '#64748b', bg: '#f8fafc', icon: '⚙️', label: '未知' };

function getTheme(agent: string) {
  return AGENT_THEME[expandAgentName(agent)] || defaultTheme;
}

/* ── Metric card ── */
function MetricCard({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div style={{
      flex: 1, padding: '14px 16px', borderRadius: '12px',
      background: '#fff', border: '1px solid #e2e8f0',
      display: 'flex', flexDirection: 'column', gap: '8px',
      minWidth: '120px',
      boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
      transition: 'box-shadow 0.15s, transform 0.15s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ fontSize: '1rem' }}>{icon}</span>
        <span style={{ fontSize: '0.72rem', color: '#94a3b8', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.03em' }}>{label}</span>
      </div>
      <span style={{ fontSize: '1.05rem', fontWeight: 700, color: '#1e293b' }}>{value}</span>
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
        padding: '2rem', textAlign: 'center', color: '#94a3b8',
        fontSize: '0.85rem', fontStyle: 'italic',
      }}>
        暂无数据
      </div>
    );
  }

  /* Simple syntax coloring */
  const highlighted = json
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"([^"]+)"(?=\s*:)/g, '<span style="color:#7c3aed">"$1"</span>')
    .replace(/: "([^"]*)"/g, ': <span style="color:#059664">"$1"</span>')
    .replace(/: (\d+\.?\d*)/g, ': <span style="color:#d97706">$1</span>')
    .replace(/: (true|false|null)/g, ': <span style="color:#dc2626">$1</span>');

  return (
    <pre
      style={{
        background: '#f8fafc', padding: '1rem 1.25rem', borderRadius: '10px',
        overflow: 'auto', maxHeight: maxHeight || '400px', fontSize: '0.82rem',
        border: '1px solid #e2e8f0', lineHeight: 1.6, margin: 0,
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
      }}
      dangerouslySetInnerHTML={{ __html: highlighted }}
    />
  );
}

/* ── Reasoning chain ── */
function ReasoningChain({ steps, accent }: { steps: ReasoningStep[]; accent: string }) {
  if (!steps || steps.length === 0) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
        暂无推理记录
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
      {steps.map((step, i) => (
        <div key={i} style={{ display: 'flex', gap: '14px' }}>
          {/* Timeline line */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '24px' }}>
            <div style={{
              width: '24px', height: '24px', borderRadius: '50%',
              background: accent, color: '#fff', fontSize: '0.7rem',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 700, flexShrink: 0,
            }}>
              {step.step}
            </div>
            {i < steps.length - 1 && (
              <div style={{ width: '2px', flex: 1, background: '#e2e8f0', minHeight: '20px' }} />
            )}
          </div>
          {/* Content */}
          <div style={{
            padding: '10px 14px', background: '#fff', border: '1px solid #e2e8f0',
            borderRadius: '10px', marginBottom: '12px', flex: 1,
            fontSize: '0.85rem', lineHeight: 1.6, color: '#334155',
          }}>
            <p style={{ margin: 0 }}>{step.thought}</p>
            {step.source_ref && (
              <span style={{
                display: 'inline-block', marginTop: '6px', fontSize: '0.72rem',
                color: accent, background: accent + '12', padding: '2px 8px',
                borderRadius: '6px', fontWeight: 500,
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
      <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
        暂无数据源
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {sources.map((src, i) => (
        <div key={i} style={{
          padding: '14px 16px', background: '#fff', border: '1px solid #e2e8f0',
          borderRadius: '10px', display: 'flex', flexDirection: 'column', gap: '6px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                fontSize: '0.7rem', fontWeight: 600, color: accent,
                background: accent + '14', padding: '2px 8px', borderRadius: '6px',
                textTransform: 'uppercase',
              }}>
                {src.type}
              </span>
              <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#1e293b' }}>
                {src.source_id}
              </span>
            </div>
            {src.url && (
              <a
                href={src.url} target="_blank" rel="noopener noreferrer"
                style={{
                  fontSize: '0.75rem', color: accent, textDecoration: 'none',
                  display: 'flex', alignItems: 'center', gap: '4px',
                }}
              >
                访问 ↗
              </a>
            )}
          </div>
          {src.snippet && (
            <p style={{
              margin: 0, fontSize: '0.82rem', color: '#64748b', lineHeight: 1.5,
              display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
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
      padding: '4rem 2rem', color: '#94a3b8', gap: '12px',
    }}>
      <span style={{ fontSize: '3rem' }}>{icon}</span>
      <span style={{ fontSize: '1rem', fontWeight: 600, color: '#64748b' }}>{title}</span>
      <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>{desc}</span>
    </div>
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
      <div style={{ padding: '2rem' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '1rem',
        }}>
          <div style={{
            width: '44px', height: '44px', borderRadius: '12px',
            background: '#f1f5f9', display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontSize: '1.5rem',
          }}>
            ⏳
          </div>
          <div>
            <p style={{ margin: 0, fontWeight: 700, fontSize: '1rem', color: '#1e293b' }}>{nodeId}</p>
            <p style={{ margin: 0, fontSize: '0.82rem', color: '#94a3b8' }}>
              等待执行后将显示详情
            </p>
          </div>
        </div>
        <div style={{
          padding: '2rem 1.5rem', background: '#f8fafc', borderRadius: '12px',
          border: '1px dashed #cbd5e1', textAlign: 'center', color: '#94a3b8',
          fontSize: '0.85rem', lineHeight: 1.6,
        }}>
          <span style={{ fontSize: '1.5rem', display: 'block', marginBottom: '8px' }}>📭</span>
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
      {/* ── Hero header ── */}
      <div style={{
        background: `linear-gradient(135deg, ${theme.accent}18, ${theme.accent}08)`,
        padding: '22px 24px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex', alignItems: 'center', gap: '16px',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: '-20px', right: '-20px', width: '100px', height: '100px',
          borderRadius: '50%', background: `${theme.accent}06`,
        }} />
        <div style={{
          width: '52px', height: '52px', borderRadius: '14px',
          background: `linear-gradient(135deg, ${theme.accent}25, ${theme.accent}15)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.5rem', flexShrink: 0,
          boxShadow: `0 4px 12px ${theme.accent}20`,
        }}>
          {theme.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0, position: 'relative', zIndex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{
              fontSize: '0.72rem', fontWeight: 600, color: theme.accent,
              background: theme.accent + '18', padding: '3px 10px', borderRadius: '8px',
            }}>
              {theme.label}
            </span>
            {trace.timestamp && (
              <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                {new Date(trace.timestamp).toLocaleString('zh-CN')}
              </span>
            )}
          </div>
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#1e293b', letterSpacing: '-0.01em' }}>
            {trace.node_id}
          </h3>
        </div>
      </div>

      {/* ── Error banner (failed nodes) ── */}
      {trace.error_message && (
        <div style={{
          margin: '16px 24px 0', padding: '14px 18px', borderRadius: '12px',
          background: '#fef2f2', border: '1px solid #fecaca',
          display: 'flex', alignItems: 'flex-start', gap: '12px',
        }}>
          <span style={{ fontSize: '1.2rem', flexShrink: 0, marginTop: '1px' }}>❌</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#991b1b', marginBottom: '4px' }}>
              执行失败
            </div>
            <div style={{
              fontSize: '0.82rem', color: '#b91c1c', lineHeight: 1.5,
              wordBreak: 'break-word',
            }}>
              {trace.error_message}
            </div>
          </div>
        </div>
      )}

      {/* ── Metrics strip ── */}
      <div style={{
        display: 'flex', gap: '10px', padding: '14px 24px',
        background: 'linear-gradient(180deg, #f8fafc, #f1f5f9)',
        borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap',
      }}>
        <MetricCard icon="🤖" label="模型" value={meta.model || '-'} />
        <MetricCard icon="🪙" label="Token" value={meta.tokens_used ? meta.tokens_used.toLocaleString() : '-'} />
        <MetricCard icon="⏱️" label="耗时" value={meta.latency_ms ? `${(meta.latency_ms / 1000).toFixed(1)}s` : '-'} />
      </div>

      {/* ── Tab bar ── */}
      <div style={{
        display: 'flex', gap: '0', padding: '0 24px',
        borderBottom: '1px solid #e2e8f0', background: '#fff',
      }}>
        {tabsWithCount.map(tab => (
          <button
            key={tab.key}
            onClick={() => !tab.disabled && setActiveTab(tab.key)}
            style={{
              padding: '12px 16px', fontSize: '0.82rem', fontWeight: activeTab === tab.key ? 600 : 500,
              color: tab.disabled ? '#cbd5e1' : activeTab === tab.key ? theme.accent : '#64748b',
              background: activeTab === tab.key ? `${theme.accent}08` : 'none',
              border: 'none', cursor: tab.disabled ? 'not-allowed' : 'pointer',
              borderBottom: activeTab === tab.key ? `2px solid ${theme.accent}` : '2px solid transparent',
              display: 'flex', alignItems: 'center', gap: '6px',
              transition: 'all 0.15s ease',
              position: 'relative',
            }}
          >
            <span style={{ fontSize: '0.9rem' }}>{tab.icon}</span>
            {tab.label}
            {tab.disabled && (
              <span style={{ fontSize: '0.6rem', color: '#cbd5e1', marginLeft: '2px' }}>·</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab content ── */}
      <div style={{ padding: '20px 24px', minHeight: '200px' }}>
        {activeTab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Quick summary of output */}
            <div>
              <h4 style={{ margin: '0 0 10px', fontSize: '0.9rem', color: '#64748b', fontWeight: 600 }}>
                输出结果
              </h4>
              <JsonBlock data={trace.output} maxHeight="260px" />
            </div>
            {/* Quick summary of input */}
            <div>
              <h4 style={{ margin: '0 0 10px', fontSize: '0.9rem', color: '#64748b', fontWeight: 600 }}>
                输入参数
              </h4>
              <JsonBlock data={trace.input_refs} maxHeight="160px" />
            </div>
          </div>
        )}

        {activeTab === 'input' && (
          <div>
            <h4 style={{ margin: '0 0 10px', fontSize: '0.9rem', color: '#64748b', fontWeight: 600 }}>
              输入引用 (input_refs)
            </h4>
            <JsonBlock data={trace.input_refs} />
          </div>
        )}

        {activeTab === 'output' && (
          <div>
            <h4 style={{ margin: '0 0 10px', fontSize: '0.9rem', color: '#64748b', fontWeight: 600 }}>
              输出数据 (output)
            </h4>
            <JsonBlock data={trace.output} />
          </div>
        )}

        {activeTab === 'reasoning' && (
          <div>
            <h4 style={{ margin: '0 0 14px', fontSize: '0.9rem', color: '#64748b', fontWeight: 600 }}>
              推理过程
            </h4>
            <ReasoningChain steps={trace.reasoning_chain || []} accent={theme.accent} />
          </div>
        )}

        {activeTab === 'sources' && (
          <div>
            <h4 style={{ margin: '0 0 14px', fontSize: '0.9rem', color: '#64748b', fontWeight: 600 }}>
              数据来源 ({trace.sources?.length || 0})
            </h4>
            <SourcesList sources={trace.sources || []} accent={theme.accent} />
          </div>
        )}
      </div>
    </div>
  );
}
