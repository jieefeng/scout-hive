import type { TraceRecord } from '../types';

interface AgentDetailProps { trace: TraceRecord | null; }

export default function AgentDetail({ trace }: AgentDetailProps) {
  if (!trace) return <div style={{ padding: '1rem', color: '#666' }}>点击 DAG 节点查看 Agent 详情</div>;
  return (
    <div style={{ padding: '1rem' }}>
      <h3>{trace.agent} — {trace.node_id}</h3>
      <div style={{ marginBottom: '1rem' }}>
        <h4>输入</h4>
        <pre style={{ background: '#f5f5f5', padding: '0.5rem', borderRadius: '4px', overflow: 'auto' }}>
          {JSON.stringify(trace.input_refs, null, 2)}
        </pre>
      </div>
      <div style={{ marginBottom: '1rem' }}>
        <h4>输出</h4>
        <pre style={{ background: '#f5f5f5', padding: '0.5rem', borderRadius: '4px', overflow: 'auto', maxHeight: '200px' }}>
          {JSON.stringify(trace.output, null, 2)}
        </pre>
      </div>
      <div style={{ display: 'flex', gap: '2rem' }}>
        <div><h4>置信度</h4><span style={{ color: trace.confidence?.level === 'high' ? '#4caf50' : '#ff9800' }}>
          {Math.round((trace.confidence?.score || 0) * 100)}% ({trace.confidence?.level})
        </span></div>
        <div><h4>Token</h4><span>{trace.llm_metadata?.tokens_used}</span></div>
        <div><h4>耗时</h4><span>{trace.llm_metadata?.latency_ms}ms</span></div>
      </div>
    </div>
  );
}
