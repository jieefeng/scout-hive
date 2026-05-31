import type { ReviewResult } from '../types';

interface ReviewTimelineProps { reviews: ReviewResult[]; }

const VERDICT: Record<string, { color: string; bg: string; label: string; icon: string }> = {
  approved: { color: '#10b981', bg: '#ecfdf5', label: '通过', icon: '✓' },
  rejected: { color: '#ef4444', bg: '#fef2f2', label: '驳回', icon: '✗' },
};

const SEVERITY: Record<string, { color: string; bg: string }> = {
  critical: { color: '#ef4444', bg: '#fef2f2' },
  high:     { color: '#f59e0b', bg: '#fffbeb' },
  medium:   { color: '#3b82f6', bg: '#eff6ff' },
  low:      { color: '#64748b', bg: '#f1f5f9' },
};

export default function ReviewTimeline({ reviews }: ReviewTimelineProps) {
  if (!reviews.length) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: '2rem', color: '#94a3b8', gap: '8px',
      }}>
        <span style={{ fontSize: '2rem' }}>📋</span>
        <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#64748b' }}>暂无审查记录</span>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', paddingLeft: '2.5rem' }}>
      <div style={{
        position: 'absolute', left: '11px', top: 0, bottom: 0, width: '2px',
        background: 'linear-gradient(180deg, #e2e8f0, #f1f5f9)',
      }} />
      {reviews.map((review) => {
        const v = VERDICT[review.verdict] || { color: '#94a3b8', bg: '#f8fafc', label: review.verdict, icon: '?' };
        return (
          <div key={review.review_id} style={{ marginBottom: '1.5rem', position: 'relative' }}>
            <div style={{
              position: 'absolute', left: '-2.5rem', top: '6px',
              width: '14px', height: '14px', borderRadius: '50%',
              background: v.color, border: '3px solid #fff',
              boxShadow: `0 0 0 2px ${v.color}30`,
            }} />
            <div style={{
              padding: '16px 18px', background: '#fff', borderRadius: '12px',
              border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}>
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px',
              }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1e293b' }}>
                  第 {review.round} 轮审查
                </span>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: '4px',
                  padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 600,
                  color: v.color, background: v.bg,
                }}>
                  {v.icon} {v.label}
                </span>
              </div>

              {review.checks.map((check, j) => (
                <div key={j} style={{
                  marginBottom: '8px', padding: '10px 12px', borderRadius: '8px',
                  background: '#f8fafc', border: '1px solid #f1f5f9',
                }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: '4px',
                    fontSize: '0.82rem', fontWeight: 600,
                    color: check.status === 'pass' ? '#10b981' : '#ef4444',
                  }}>
                    {check.status === 'pass' ? '✓' : '✗'} {check.dimension}
                  </span>
                  {check.issues.map((issue, k) => {
                    const sev = SEVERITY[issue.severity] || SEVERITY.low;
                    return (
                      <div key={k} style={{
                        marginTop: '6px', marginLeft: '16px', fontSize: '0.8rem', color: '#475569',
                        display: 'flex', flexDirection: 'column', gap: '2px',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{
                            fontSize: '0.65rem', fontWeight: 600, color: sev.color,
                            background: sev.bg, padding: '1px 6px', borderRadius: '4px',
                            textTransform: 'uppercase',
                          }}>
                            {issue.severity}
                          </span>
                          <span>{issue.description}</span>
                        </div>
                        {issue.suggestion && (
                          <span style={{ fontSize: '0.78rem', color: '#94a3b8', marginLeft: '4px' }}>
                            建议: {issue.suggestion}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}

              {review.feedback_message && (
                <div style={{
                  marginTop: '10px', padding: '10px 14px', borderRadius: '8px',
                  background: '#fffbeb', border: '1px solid #fde68a',
                  fontSize: '0.82rem', color: '#92400e',
                }}>
                  <span style={{ fontWeight: 600, marginRight: '4px' }}>反馈给 {review.feedback_to}:</span>
                  {review.feedback_message}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
