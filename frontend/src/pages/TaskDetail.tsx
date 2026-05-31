import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTaskStore } from '../stores/taskStore';
import DagViewer from '../components/DagViewer';
import AgentDetail from '../components/AgentDetail';
import TraceBrowser from '../components/TraceBrowser';
import ReviewTimeline from '../components/ReviewTimeline';
import ReportViewer from '../components/ReportViewer';
import type { TraceRecord } from '../types';

const POLL_INTERVAL = 3000;

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string; icon: string }> = {
  pending:   { color: '#64748b', bg: '#f1f5f9', label: '等待中', icon: '⏳' },
  running:   { color: '#3b82f6', bg: '#eff6ff', label: '运行中', icon: '🔄' },
  completed: { color: '#10b981', bg: '#ecfdf5', label: '已完成', icon: '✅' },
  failed:    { color: '#ef4444', bg: '#fef2f2', label: '失败',   icon: '❌' },
  stopped:   { color: '#f59e0b', bg: '#fffbeb', label: '已停止', icon: '⏹️' },
};

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { currentTask, loading, loadTask } = useTaskStore();
  const [selectedTrace, setSelectedTrace] = useState<TraceRecord | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!taskId) return;
    loadTask(taskId);
  }, [taskId, loadTask]);

  useEffect(() => {
    if (!taskId) return;
    if (!currentTask) return;
    const isActive = currentTask?.status === 'pending' || currentTask?.status === 'running';
    if (isActive && !intervalRef.current) {
      intervalRef.current = setInterval(() => loadTask(taskId), POLL_INTERVAL);
    }
    if (!isActive && intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    return () => {
      if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    };
  }, [currentTask?.status, taskId, loadTask]);

  const handleNodeClick = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    const trace = currentTask?.traces?.find(t => t.node_id === nodeId) || null;
    setSelectedTrace(trace);
    setPanelOpen(true);
  };

  const closePanel = () => {
    setPanelOpen(false);
    setSelectedNodeId(null);
    setSelectedTrace(null);
  };

  if (loading && !currentTask) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: '60vh', gap: '16px',
      }}>
        <div style={{
          width: '48px', height: '48px', borderRadius: '50%',
          border: '3px solid #e2e8f0', borderTopColor: '#3b82f6',
          animation: 'spin 0.8s linear infinite',
        }} />
        <span style={{ color: '#64748b', fontSize: '0.95rem' }}>加载任务详情...</span>
      </div>
    );
  }

  if (!currentTask) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: '60vh', gap: '12px', color: '#94a3b8',
      }}>
        <span style={{ fontSize: '3rem' }}>🔍</span>
        <span style={{ fontSize: '1.1rem', fontWeight: 600, color: '#64748b' }}>任务不存在</span>
        <button
          onClick={() => navigate('/')}
          style={{
            marginTop: '8px', padding: '8px 20px', borderRadius: '8px',
            background: '#f1f5f9', border: '1px solid #e2e8f0', cursor: 'pointer',
            fontSize: '0.85rem', color: '#64748b', transition: 'all 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = '#e2e8f0'; }}
          onMouseLeave={e => { e.currentTarget.style.background = '#f1f5f9'; }}
        >
          返回任务列表
        </button>
      </div>
    );
  }

  const st = STATUS_CONFIG[currentTask.status] || STATUS_CONFIG.pending;
  const isActive = currentTask.status === 'pending' || currentTask.status === 'running';

  return (
    <div style={{ padding: '1.5rem 2rem' }}>
      {/* ── Header Card ── */}
      <div style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: '16px', padding: '24px 28px', marginBottom: '1.5rem',
        color: '#fff', position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: '-40px', right: '-40px', width: '160px', height: '160px',
          borderRadius: '50%', background: 'rgba(255,255,255,0.08)',
        }} />
        <div style={{
          position: 'absolute', bottom: '-60px', left: '30%', width: '200px', height: '200px',
          borderRadius: '50%', background: 'rgba(255,255,255,0.04)',
        }} />

        <div style={{ position: 'relative', zIndex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button
                onClick={() => navigate('/')}
                style={{
                  width: '32px', height: '32px', borderRadius: '8px',
                  background: 'rgba(255,255,255,0.15)', border: 'none', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontSize: '1rem', transition: 'background 0.15s',
                  backdropFilter: 'blur(4px)',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.25)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.15)'; }}
              >
                ←
              </button>
              <div>
                <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                  任务详情
                </h1>
                <span style={{ fontSize: '0.8rem', opacity: 0.7, fontFamily: 'monospace' }}>
                  {currentTask.task_id}
                </span>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                padding: '6px 14px', borderRadius: '20px', fontSize: '0.82rem', fontWeight: 600,
                background: 'rgba(255,255,255,0.18)', backdropFilter: 'blur(4px)',
                border: '1px solid rgba(255,255,255,0.2)',
              }}>
                {st.icon} {st.label}
              </span>
              {isActive && (
                <button
                  onClick={async () => {
                    if (!taskId) return;
                    await fetch(`/api/tasks/${taskId}/stop`, { method: "POST" });
                    loadTask(taskId);
                  }}
                  style={{
                    padding: '6px 16px', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600,
                    background: 'rgba(239,68,68,0.9)', color: '#fff', border: 'none', cursor: 'pointer',
                    transition: 'all 0.15s', backdropFilter: 'blur(4px)',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,1)'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.9)'; }}
                >
                  停止任务
                </button>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
            <div style={{
              padding: '8px 14px', borderRadius: '10px',
              background: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(4px)',
              border: '1px solid rgba(255,255,255,0.12)', fontSize: '0.82rem',
            }}>
              <span style={{ opacity: 0.7, marginRight: '6px' }}>竞品</span>
              <strong>{currentTask.competitors.map(c => c.name).join(' · ')}</strong>
            </div>
            <div style={{
              padding: '8px 14px', borderRadius: '10px',
              background: 'rgba(255,255,255,0.1)', backdropFilter: 'blur(4px)',
              border: '1px solid rgba(255,255,255,0.12)', fontSize: '0.82rem',
            }}>
              <span style={{ opacity: 0.7, marginRight: '6px' }}>维度</span>
              <strong>{currentTask.dimensions?.join(' · ') || '加载中...'}</strong>
            </div>
          </div>

          {currentTask.progress > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                flex: 1, height: '8px', background: 'rgba(255,255,255,0.15)',
                borderRadius: '4px', overflow: 'hidden', maxWidth: '400px',
              }}>
                <div style={{
                  width: `${currentTask.progress * 100}%`, height: '100%',
                  background: 'linear-gradient(90deg, rgba(255,255,255,0.7), rgba(255,255,255,0.95))',
                  borderRadius: '4px', transition: 'width 0.5s ease',
                  boxShadow: '0 0 12px rgba(255,255,255,0.3)',
                }} />
              </div>
              <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>
                {Math.round(currentTask.progress * 100)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ── Report Section ── */}
      {currentTask.report_html && (
        <div style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <span style={{
              width: '4px', height: '20px', borderRadius: '2px',
              background: 'linear-gradient(180deg, #10b981, #059669)',
            }} />
            <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#1e293b' }}>分析报告</h2>
          </div>
          <div style={{
            border: '1px solid #e2e8f0', borderRadius: '14px', overflow: 'hidden',
            background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03)',
          }}>
            <ReportViewer task={currentTask} />
          </div>
        </div>
      )}

      {/* ── DAG Section ── */}
      <div style={{
        border: '1px solid #e2e8f0', borderRadius: '14px', overflow: 'hidden',
        background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03)',
        position: 'relative',
      }}>
        <div style={{
          padding: '14px 20px', borderBottom: '1px solid #e2e8f0',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'linear-gradient(180deg, #fafbfc, #f8fafc)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              width: '4px', height: '20px', borderRadius: '2px',
              background: 'linear-gradient(180deg, #3b82f6, #2563eb)',
            }} />
            <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#1e293b' }}>DAG 执行图</h2>
          </div>
          <div style={{ display: 'flex', gap: '14px', fontSize: '0.72rem' }}>
            {[
              { icon: '⏳', label: '等待' },
              { icon: '🔄', label: '运行中' },
              { icon: '✅', label: '完成' },
              { icon: '❌', label: '失败' },
              { icon: '⏭️', label: '跳过' },
            ].map(item => (
              <span key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#64748b' }}>
                <span>{item.icon}</span><span>{item.label}</span>
              </span>
            ))}
          </div>
        </div>
        <div style={{ height: '60vh', minHeight: '500px' }}>
          <DagViewer
            nodeStates={currentTask.node_states}
            dagBlueprint={currentTask.dag_json}
            onNodeClick={handleNodeClick}
            selectedNodeId={selectedNodeId}
          />
        </div>
      </div>

      {/* ── Agent Detail Modal ── */}
      {panelOpen && (
        <>
          <div
            onClick={closePanel}
            style={{
              position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
              background: 'rgba(15,23,42,0.5)', backdropFilter: 'blur(6px)',
              zIndex: 99, animation: 'modalFadeIn 0.2s ease',
            }}
          />
          <div style={{
            position: 'fixed', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 'min(920px, 92vw)', maxHeight: '85vh',
            background: '#fff', borderRadius: '18px',
            boxShadow: '0 25px 80px rgba(0,0,0,0.25), 0 0 0 1px rgba(0,0,0,0.05)',
            zIndex: 100, overflow: 'hidden', display: 'flex', flexDirection: 'column',
            animation: 'modalSlideIn 0.25s ease',
          }}>
            <div style={{
              padding: '16px 20px', borderBottom: '1px solid #e2e8f0',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              position: 'sticky', top: 0,
              background: 'linear-gradient(180deg, #fafbfc, #f8fafc)',
              borderRadius: '18px 18px 0 0', zIndex: 1,
            }}>
              <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#1e293b' }}>节点详情</h2>
              <button
                onClick={closePanel}
                style={{
                  width: '32px', height: '32px', borderRadius: '8px',
                  background: '#f1f5f9', border: '1px solid #e2e8f0', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '1rem', color: '#64748b', lineHeight: 1, transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = '#e2e8f0'; e.currentTarget.style.color = '#1e293b'; }}
                onMouseLeave={e => { e.currentTarget.style.background = '#f1f5f9'; e.currentTarget.style.color = '#64748b'; }}
              >
                ✕
              </button>
            </div>
            <div style={{ overflow: 'auto', flex: 1 }}>
              <AgentDetail trace={selectedTrace} nodeId={selectedNodeId} />
            </div>
          </div>
        </>
      )}

      <style>{`
        @keyframes modalFadeIn { from { opacity: 0 } to { opacity: 1 } }
        @keyframes modalSlideIn { from { opacity: 0; transform: translate(-50%, -48%) scale(0.96) } to { opacity: 1; transform: translate(-50%, -50%) scale(1) } }
        @keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }
      `}</style>

      {/* ── Below-the-fold sections ── */}
      <div style={{ marginTop: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
          <span style={{
            width: '4px', height: '20px', borderRadius: '2px',
            background: 'linear-gradient(180deg, #8b5cf6, #7c3aed)',
          }} />
          <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#1e293b' }}>溯源浏览器</h2>
        </div>
        <div style={{
          border: '1px solid #e2e8f0', borderRadius: '14px', minHeight: '400px', overflow: 'hidden',
          background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03)',
        }}>
          <TraceBrowser traces={currentTask.traces || []} />
        </div>
      </div>

      <div style={{ marginTop: '2rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
          <span style={{
            width: '4px', height: '20px', borderRadius: '2px',
            background: 'linear-gradient(180deg, #f59e0b, #d97706)',
          }} />
          <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#1e293b' }}>审查时间轴</h2>
        </div>
        <div style={{
          border: '1px solid #e2e8f0', borderRadius: '14px', padding: '1.25rem',
          background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03)',
        }}>
          <ReviewTimeline reviews={currentTask.reviews || []} />
        </div>
      </div>
    </div>
  );
}
