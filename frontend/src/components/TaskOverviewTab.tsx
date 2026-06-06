import type { TaskSummary, TraceRecord } from '../types';
import type { TaskMetricsSnapshot, SlowNode } from '../api/client';

interface TaskOverviewTabProps {
  task: TaskSummary;
  metrics: TaskMetricsSnapshot | null;
  onSelectTrace: (trace: TraceRecord, nodeId: string | null) => void;
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.floor(s % 60)}s`;
}

function formatCny(cny: number): string {
  return `¥${cny.toFixed(2)}`;
}

function formatTokens(t: number): string {
  if (t < 1000) return `${t}`;
  return `${(t / 1000).toFixed(1)}k`;
}

interface MetricCardProps {
  title: string;
  bigNumber: string;
  subInfo: string;
  badge?: string;
  badgeColor?: string;
  topList?: Array<{ label: string; barPct: number; right: string }>;
}

function MetricCard({ title, bigNumber, subInfo, badge, badgeColor = '#64748b', topList }: MetricCardProps) {
  return (
    <div style={{
      flex: 1,
      background: '#fff',
      border: '1px solid #e2e8f0',
      borderRadius: '12px',
      padding: '1rem 1.25rem',
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.85rem', color: '#64748b', fontWeight: 500 }}>{title}</span>
        {badge && (
          <span style={{ fontSize: '0.7rem', color: badgeColor, background: badgeColor + '15', padding: '2px 8px', borderRadius: '4px' }}>
            {badge}
          </span>
        )}
      </div>
      <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.25rem' }}>
        {bigNumber}
      </div>
      <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: topList ? '0.75rem' : 0 }}>
        {subInfo}
      </div>
      {topList && topList.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {topList.map((item, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem' }}>
              <span style={{ minWidth: '90px', color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.label}
              </span>
              <div style={{ flex: 1, height: '6px', background: '#f1f5f9', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{ width: `${item.barPct}%`, height: '100%', background: '#3b82f6' }} />
              </div>
              <span style={{ minWidth: '50px', textAlign: 'right', color: '#0f172a', fontWeight: 500 }}>{item.right}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TaskOverviewTab({ task, metrics, onSelectTrace }: TaskOverviewTabProps) {
  // 旧任务 / 无 metrics 数据
  if (!metrics || metrics.available === false) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: '#94a3b8' }}>
        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📊</div>
        <div>无 metrics 数据（任务在升级前跑过）</div>
      </div>
    );
  }

  // CostCard：总成本 + 成本 top 3 节点
  const totalCost = formatCny(metrics.total_cost_cny);
  const costTop3 = [...metrics.slow_nodes]
    .sort((a, b) => b.cost_cny - a.cost_cny)
    .slice(0, 3)
    .map(s => ({
      label: `${s.node_id} · ${s.agent}`,
      barPct: metrics.total_cost_cny > 0 ? (s.cost_cny / metrics.total_cost_cny) * 100 : 0,
      right: formatCny(s.cost_cny),
    }));

  // PerformanceCard：总耗时 + 慢节点 top 3（横向条形）
  const totalElapsed = formatMs(metrics.total_elapsed_ms);
  const maxElapsed = Math.max(...metrics.slow_nodes.map(s => s.elapsed_ms), 1);
  const slowTop3 = metrics.slow_nodes.slice(0, 3).map((s: SlowNode) => ({
    label: `${s.node_id} · ${s.agent}`,
    barPct: (s.elapsed_ms / maxElapsed) * 100,
    right: formatMs(s.elapsed_ms),
  }));

  // QualityCard：反馈循环次数 + passed / RC 缺失
  const feedbackRounds = metrics.quality?.feedback_rounds ?? metrics.feedback_rounds;
  const passedCount = metrics.quality?.passed_count ?? metrics.completed_count;
  const rcMissing = metrics.rc_missing_count;
  const qualitySub = `passed ${passedCount} · RC 缺失 ${rcMissing}`;

  return (
    <div>
      {/* MetricsBar（3 卡） */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
        <MetricCard
          title="💰 成本"
          bigNumber={totalCost}
          subInfo={`${formatTokens(metrics.total_tokens)} tokens · ${metrics.llm_call_count} calls`}
          badge="估算"
          badgeColor="#f59e0b"
          topList={costTop3}
        />
        <MetricCard
          title="⏱️ 性能"
          bigNumber={totalElapsed}
          subInfo={`${metrics.node_count} 节点 · ${metrics.failed_count} 失败`}
          topList={slowTop3}
        />
        <MetricCard
          title="✅ 质量"
          bigNumber={`${feedbackRounds}`}
          subInfo={qualitySub}
          badge={feedbackRounds > 0 ? `含 ${feedbackRounds} 次重试` : undefined}
          badgeColor="#3b82f6"
        />
      </div>

      {/* TraceList（与 TraceBrowser 共用） */}
      <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1rem 1.25rem' }}>
        <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#0f172a', marginBottom: '0.75rem' }}>
          节点 Trace（点击展开 ReasoningChain）
        </div>
        {(task.traces || []).length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
            暂无 trace 记录
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {(task.traces || []).map((t) => (
              <button
                key={t.trace_id}
                onClick={() => onSelectTrace(t, t.node_id)}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '0.6rem 0.9rem',
                  background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px',
                  cursor: 'pointer', textAlign: 'left',
                }}
              >
                <span style={{ fontSize: '0.85rem', color: '#0f172a' }}>
                  {t.node_id} · {t.agent}
                  {t.error_message && t.error_message.includes('RC missing') && (
                    <span style={{ marginLeft: '0.5rem', color: '#ef4444', fontSize: '0.7rem' }}>⚠️ RC 缺失</span>
                  )}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  {(t.reasoning_chain?.length ?? 0)} 步推理
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
