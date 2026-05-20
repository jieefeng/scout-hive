import type { ReviewResult } from '../types';

interface ReviewTimelineProps { reviews: ReviewResult[]; }

const VERDICT_COLORS: Record<string, string> = { approved: '#4caf50', rejected: '#f44336' };
const VERDICT_LABELS: Record<string, string> = { approved: '通过', rejected: '驳回' };

export default function ReviewTimeline({ reviews }: ReviewTimelineProps) {
  if (!reviews.length) return <p>暂无审查记录</p>;
  return (
    <div style={{ position: 'relative', paddingLeft: '2rem' }}>
      <div style={{ position: 'absolute', left: '0.75rem', top: 0, bottom: 0, width: '2px', background: '#ddd' }} />
      {reviews.map((review) => (
        <div key={review.review_id} style={{ marginBottom: '1.5rem', position: 'relative' }}>
          <div style={{
            position: 'absolute', left: '-1.5rem', top: '0.25rem',
            width: '12px', height: '12px', borderRadius: '50%',
            background: VERDICT_COLORS[review.verdict] || '#9e9e9e', border: '2px solid #fff',
          }} />
          <div style={{ padding: '0.75rem', background: '#f5f5f5', borderRadius: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <strong>Round {review.round}</strong>
              <span style={{ color: VERDICT_COLORS[review.verdict] }}>{VERDICT_LABELS[review.verdict]}</span>
            </div>
            {review.checks.map((check, j) => (
              <div key={j} style={{ marginBottom: '0.5rem' }}>
                <span style={{ color: check.status === 'pass' ? '#4caf50' : '#f44336' }}>
                  {check.status === 'pass' ? '✓' : '✗'} {check.dimension}
                </span>
                {check.issues.map((issue, k) => (
                  <div key={k} style={{ marginLeft: '1rem', fontSize: '0.85rem', color: '#666' }}>
                    [{issue.severity}] {issue.description}
                    {issue.suggestion && <div>建议: {issue.suggestion}</div>}
                  </div>
                ))}
              </div>
            ))}
            {review.feedback_message && (
              <div style={{ marginTop: '0.5rem', padding: '0.5rem', background: '#fff3e0', borderRadius: '4px' }}>
                反馈给 {review.feedback_to}: {review.feedback_message}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
