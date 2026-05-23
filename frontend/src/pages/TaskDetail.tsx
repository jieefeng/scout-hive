import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTaskStore } from '../stores/taskStore';
import DagViewer from '../components/DagViewer';
import AgentDetail from '../components/AgentDetail';
import TraceBrowser from '../components/TraceBrowser';
import ReviewTimeline from '../components/ReviewTimeline';
import ReportViewer from '../components/ReportViewer';
import type { TraceRecord } from '../types';

const POLL_INTERVAL = 3000;

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>();
  const { currentTask, loading, loadTask } = useTaskStore();
  const [selectedTrace, setSelectedTrace] = useState<TraceRecord | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => { if (taskId) loadTask(taskId); }, [taskId, loadTask]);

  useEffect(() => {
    if (!taskId) return;
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

  if (loading) return <p style={{ padding: '2rem' }}>加载中...</p>;
  if (!currentTask) return <p style={{ padding: '2rem' }}>任务不存在</p>;

  return (
    <div style={{ padding: '1.5rem 2rem' }}>
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700 }}>
          任务详情: {currentTask.task_id.slice(0, 8)}
        </h1>
        <div style={{ display: 'flex', gap: '1.5rem', marginTop: '0.5rem', fontSize: '0.9rem', color: '#64748b', alignItems: 'center' }}>
          <span>状态: <strong style={{ color: currentTask.status === 'running' ? '#3b82f6' : '#1e293b' }}>{currentTask.status}</strong></span>
          <span>竞品: {currentTask.competitors.map(c => c.name).join(', ')}</span>
          <span>维度: {currentTask.dimensions?.join(', ') || '加载中...'}</span>
          {currentTask.progress > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{ width: '80px', height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{
                  width: `${currentTask.progress * 100}%`,
                  height: '100%',
                  background: currentTask.status === 'running' ? '#3b82f6' : '#22c55e',
                  transition: 'width 0.3s'
                }} />
              </div>
              <span style={{ fontSize: '0.8rem' }}>{Math.round(currentTask.progress * 100)}%</span>
            </div>
          )}
        </div>
      </div>

      {/* Report Section — show when available */}
      {currentTask.report_html && (
        <div style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>分析报告</h2>
          <div style={{ border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden', background: '#fff' }}>
            <ReportViewer task={currentTask} />
          </div>
        </div>
      )}

      {/* DAG Section — full width, tall */}
      <div style={{
        border: '1px solid #e2e8f0',
        borderRadius: '12px',
        overflow: 'hidden',
        background: '#fff',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        position: 'relative',
      }}>
        <div style={{
          padding: '12px 20px',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#f8fafc',
        }}>
          <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>DAG 执行图</h2>
          <div style={{ display: 'flex', gap: '12px', fontSize: '0.75rem', color: '#64748b' }}>
            {Object.entries({ pending: '⏳ 等待', running: '🔄 运行中', completed: '✅ 完成', failed: '❌ 失败', skipped: '⏭️ 跳过' }).map(([key, label]) => (
              <span key={key}>{label}</span>
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

      {/* Agent Detail Drawer — slides in from right */}
      <div style={{
        position: 'fixed',
        top: 0,
        right: panelOpen ? 0 : '-480px',
        width: '460px',
        height: '100vh',
        background: '#fff',
        borderLeft: '1px solid #e2e8f0',
        boxShadow: panelOpen ? '-4px 0 24px rgba(0,0,0,0.1)' : 'none',
        transition: 'right 0.3s cubic-bezier(0.4,0,0.2,1)',
        zIndex: 100,
        overflow: 'auto',
      }}>
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          position: 'sticky',
          top: 0,
          background: '#fff',
          zIndex: 1,
        }}>
          <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Agent 详情</h2>
          <button
            onClick={closePanel}
            style={{
              background: 'none', border: '1px solid #e2e8f0', borderRadius: '6px',
              padding: '4px 10px', cursor: 'pointer', fontSize: '0.85rem', color: '#64748b',
            }}
          >
            关闭
          </button>
        </div>
        <AgentDetail trace={selectedTrace} nodeId={selectedNodeId} />
      </div>

      {/* Overlay when panel open */}
      {panelOpen && (
        <div
          onClick={closePanel}
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.15)', zIndex: 99,
          }}
        />
      )}

      {/* Below-the-fold sections */}
      <div style={{ marginTop: '2rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>溯源浏览器</h2>
        <div style={{ border: '1px solid #e2e8f0', borderRadius: '12px', minHeight: '400px', overflow: 'hidden', background: '#fff' }}>
          <TraceBrowser traces={currentTask.traces || []} />
        </div>
      </div>
      <div style={{ marginTop: '2rem', marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.75rem' }}>审查时间轴</h2>
        <div style={{ border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1rem', background: '#fff' }}>
          <ReviewTimeline reviews={currentTask.reviews || []} />
        </div>
      </div>
    </div>
  );
}
