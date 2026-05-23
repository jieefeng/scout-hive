import type { TraceRecord } from '../types';

interface ConfidenceHeatmapProps {
  traces: TraceRecord[];
  dimensions?: string[];
}

const LEVEL_COLORS: Record<string, string> = {
  high: '#22c55e',
  medium: '#f59e0b',
  low: '#ef4444',
};

export default function ConfidenceHeatmap({ traces, dimensions = [] }: ConfidenceHeatmapProps) {
  const matrix: Record<string, Record<string, { score: number; level: string }>> = {};

  for (const trace of traces) {
    if (!trace.output) continue;
    const competitor = (trace.output as Record<string, unknown>).competitor as string || trace.agent;
    if (!matrix[competitor]) matrix[competitor] = {};
    const dim = (trace.output as Record<string, unknown>).dimension as string || 'overall';
    if (!dimensions.includes(dim)) dimensions.push(dim);
    matrix[competitor][dim] = trace.confidence as { score: number; level: string };
  }

  return (
    <div style={{ overflow: 'auto', padding: '1rem' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: '400px' }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '0.5rem', borderBottom: '2px solid #e2e8f0' }}>竞品</th>
            {dimensions.map(d => (
              <th key={d} style={{ padding: '0.5rem', borderBottom: '2px solid #e2e8f0', textAlign: 'center' }}>{d}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(matrix).map(([competitor, dims]) => (
            <tr key={competitor}>
              <td style={{ padding: '0.5rem', fontWeight: 600, borderBottom: '1px solid #e2e8f0' }}>{competitor}</td>
              {dimensions.map(dim => {
                const cell = dims[dim] || { score: 0, level: 'low' };
                return (
                  <td
                    key={dim}
                    style={{
                      padding: '0.25rem',
                      borderBottom: '1px solid #e2e8f0',
                      textAlign: 'center',
                      background: `${LEVEL_COLORS[cell.level] || '#94a3b8'}22`,
                    }}
                  >
                    <div
                      style={{
                        height: '6px',
                        borderRadius: '3px',
                        background: LEVEL_COLORS[cell.level] || '#94a3b8',
                        width: `${(cell.score || 0) * 100}%`,
                        margin: '0 auto 2px',
                        maxWidth: '80px',
                      }}
                    />
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                      {Math.round((cell.score || 0) * 100)}%
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: '1rem', marginTop: '0.75rem', fontSize: '0.75rem' }}>
        {Object.entries(LEVEL_COLORS).map(([level, color]) => (
          <span key={level} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: color }} />
            {level}
          </span>
        ))}
      </div>
    </div>
  );
}