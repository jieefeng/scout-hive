import type { TraceRecord } from '../types';

interface AgentDetailProps { trace: TraceRecord | null; nodeId?: string | null; }

export default function AgentDetail({ trace, nodeId }: AgentDetailProps) {
  if (!nodeId) return <div style={{ padding: '2rem', color: '#94a3b8', textAlign: 'center' }}>点击 DAG 节点查看详情</div>;

  if (!trace) return (
    <div style={{ padding: '2rem', color: '#64748b' }}>
      <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>节点: {nodeId}</p>
      <p>该节点尚无执行记录，等待运行后将显示详情。</p>
    </div>
  );

  return (
    <div style={{ padding: '1.25rem' }}>
      <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', fontWeight: 600 }}>{trace.agent} — {trace.node_id}</h3>
      <div style={{ marginBottom: '1rem' }}>
        <h4 style={{ margin: '0 0 0.4rem', fontSize: '0.85rem', color: '#64748b' }}>输入</h4>
        <pre style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', overflow: 'auto', fontSize: '0.8rem', border: '1px solid #e2e8f0' }}>
          {JSON.stringify(trace.input_refs, null, 2)}
        </pre>
      </div>
      <div style={{ marginBottom: '1rem' }}>
        <h4 style={{ margin: '0 0 0.4rem', fontSize: '0.85rem', color: '#64748b' }}>输出</h4>
        <pre style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', overflow: 'auto', maxHeight: '200px', fontSize: '0.8rem', border: '1px solid #e2e8f0' }}>
          {JSON.stringify(trace.output, null, 2)}
        </pre>
      </div>
      <div style={{ display: 'flex', gap: '2rem', fontSize: '0.85rem' }}>
        <div><h4 style={{ margin: '0 0 0.2rem', fontSize: '0.8rem', color: '#64748b' }}>置信度</h4><span style={{ color: trace.confidence?.level === 'high' ? '#22c55e' : '#f59e0b' }}>
          {Math.round((trace.confidence?.score || 0) * 100)}% ({trace.confidence?.level})
        </span></div>
        <div><h4 style={{ margin: '0 0 0.2rem', fontSize: '0.8rem', color: '#64748b' }}>Token</h4><span>{trace.llm_metadata?.tokens_used}</span></div>
        <div><h4 style={{ margin: '0 0 0.2rem', fontSize: '0.8rem', color: '#64748b' }}>耗时</h4><span>{trace.llm_metadata?.latency_ms}ms</span></div>
      </div>
    </div>
  );
}
