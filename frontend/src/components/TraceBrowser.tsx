import { useState } from 'react';
import type { TraceRecord } from '../types';

interface TraceBrowserProps { traces: TraceRecord[]; }

export default function TraceBrowser({ traces }: TraceBrowserProps) {
  const [selectedTrace, setSelectedTrace] = useState<TraceRecord | null>(null);
  const [showSourcePanel, setShowSourcePanel] = useState(false);

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div style={{ flex: 1, overflow: 'auto', borderRight: '1px solid #ddd' }}>
        <h3>溯源记录</h3>
        {traces.map(trace => (
          <div key={trace.trace_id} onClick={() => setSelectedTrace(trace)}
            style={{ padding: '0.75rem', cursor: 'pointer',
              background: selectedTrace?.trace_id === trace.trace_id ? '#e3f2fd' : 'transparent',
              borderBottom: '1px solid #eee' }}>
            <strong>{trace.agent}</strong> — {trace.node_id}
            <div style={{ fontSize: '0.75rem', color: '#666' }}>{trace.timestamp}</div>
          </div>
        ))}
      </div>
      {selectedTrace && (
        <div style={{ flex: 2, overflow: 'auto', padding: '1rem' }}>
          <h3>推理链</h3>
          {selectedTrace.reasoning_chain.map((step, i) => (
            <div key={i} style={{ marginBottom: '1rem', padding: '0.75rem', background: '#f5f5f5', borderRadius: '4px' }}>
              <span style={{ fontWeight: 'bold' }}>步骤 {step.step}</span>
              <p>{step.thought}</p>
              {step.source_ref && (
                <button onClick={() => setShowSourcePanel(true)}
                  style={{ color: '#1976d2', cursor: 'pointer', background: 'none', border: 'none' }}>
                  查看原文 →
                </button>
              )}
            </div>
          ))}
          <h3>置信度</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ flex: 1, background: '#eee', borderRadius: '4px', height: '8px' }}>
              <div style={{
                width: `${(selectedTrace.confidence?.score || 0) * 100}%`,
                background: selectedTrace.confidence?.level === 'high' ? '#4caf50' : '#ff9800',
                height: '100%', borderRadius: '4px',
              }} />
            </div>
            <span>{Math.round((selectedTrace.confidence?.score || 0) * 100)}%</span>
          </div>
          <h3>LLM 元信息</h3>
          <p>模型: {selectedTrace.llm_metadata?.model}</p>
          <p>Token: {selectedTrace.llm_metadata?.tokens_used}</p>
          <p>耗时: {selectedTrace.llm_metadata?.latency_ms}ms</p>
        </div>
      )}
      {showSourcePanel && selectedTrace && (
        <div style={{ flex: 1, overflow: 'auto', padding: '1rem', background: '#fffde7' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <h3>原文</h3>
            <button onClick={() => setShowSourcePanel(false)}>关闭</button>
          </div>
          {selectedTrace.sources?.map(source => (
            <div key={source.source_id} style={{ marginBottom: '1rem' }}>
              <a href={source.url} target="_blank" rel="noopener noreferrer">{source.url}</a>
              <p style={{ background: '#fff9c4', padding: '0.5rem', borderRadius: '4px' }}>{source.snippet}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
