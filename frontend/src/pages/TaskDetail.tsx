import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTaskStore } from '../stores/taskStore';
import DagViewer from '../components/DagViewer';
import AgentDetail from '../components/AgentDetail';
import TraceBrowser from '../components/TraceBrowser';
import ReviewTimeline from '../components/ReviewTimeline';
import ReportViewer from '../components/ReportViewer';
import TaskOverviewTab from '../components/TaskOverviewTab';
import type { TraceRecord } from '../types';

const POLL_INTERVAL = 3000;

const STATUS_CONFIG: Record<string, { color: string; bg: string; label: string; icon: string }> = {
  pending:   { color: '#64748b', bg: '#f1f5f9', label: '等待中', icon: '⏳' },
  running:   { color: '#3b82f6', bg: '#eff6ff', label: '运行中', icon: '🔄' },
  completed: { color: '#10b981', bg: '#ecfdf5', label: '已完成', icon: '✅' },
  failed:    { color: '#ef4444', bg: '#fef2f2', label: '失败',   icon: '❌' },
  stopped:   { color: '#f59e0b', bg: '#fffbeb', label: '已停止', icon: '⏹️' },
};

type TabKey = 'overview' | 'dag' | 'report' | 'trace';

const TABS: Array<{ key: TabKey; label: string; icon: string }> = [
  { key: 'overview', label: '总览', icon: '📊' },
  { key: 'dag',      label: 'DAG', icon: '🕸️' },
  { key: 'report',   label: '报告', icon: '📄' },
  { key: 'trace',    label: 'Trace', icon: '🔍' },
];

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { currentTask, loading, loadTask, metrics, loadMetrics } = useTaskStore();
  const [selectedTrace, setSelectedTrace] = useState<TraceRecord | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!taskId) return;
    loadTask(taskId);
    loadMetrics(taskId, true);  // 首次强制拉
  }, [taskId, loadTask, loadMetrics]);

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

  if (loading) return <div style={{ padding: '2rem' }}>加载中...</div>;
  if (!currentTask) return <div style={{ padding: '2rem' }}>任务不存在</div>;

  const status = STATUS_CONFIG[currentTask.status] || STATUS_CONFIG.pending;

  return (
    <div style={{ padding: '1.5rem', maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
        <button onClick={() => navigate('/')} style={{ padding: '0.5rem 1rem', cursor: 'pointer' }}>← 返回</button>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>任务 {currentTask.task_id.slice(0, 8)}</h1>
        <span style={{ background: status.bg, color: status.color, padding: '0.25rem 0.75rem', borderRadius: '12px', fontSize: '0.85rem' }}>
          {status.icon} {status.label}
        </span>
      </div>

      {/* Tab 栏 */}
      <div style={{ display: 'flex', borderBottom: '2px solid #e2e8f0', marginBottom: '1.5rem', gap: '0.5rem' }}>
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '0.75rem 1.25rem',
              background: activeTab === tab.key ? '#eff6ff' : 'transparent',
              color: activeTab === tab.key ? '#3b82f6' : '#64748b',
              border: 'none',
              borderBottom: activeTab === tab.key ? '2px solid #3b82f6' : '2px solid transparent',
              marginBottom: '-2px',
              cursor: 'pointer',
              fontSize: '0.95rem',
              fontWeight: activeTab === tab.key ? 600 : 400,
            }}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 内容 */}
      {activeTab === 'overview' && (
        <TaskOverviewTab
          task={currentTask}
          metrics={metrics}
          onSelectTrace={(t, nodeId) => { setSelectedTrace(t); setSelectedNodeId(nodeId); setPanelOpen(true); }}
        />
      )}

      {activeTab === 'dag' && (
        <DagViewer
          task={currentTask}
          onSelectNode={(nodeId) => { setSelectedNodeId(nodeId); setPanelOpen(true); }}
        />
      )}

      {activeTab === 'report' && (
        <ReportViewer html={currentTask.report_html || ''} />
      )}

      {activeTab === 'trace' && (
        <TraceBrowser
          traces={currentTask.traces || []}
          onSelectTrace={(t, nodeId) => { setSelectedTrace(t); setSelectedNodeId(nodeId); setPanelOpen(true); }}
        />
      )}

      {/* Trace 侧栏（保留） */}
      {panelOpen && selectedTrace && (
        <AgentDetail
          trace={selectedTrace}
          nodeId={selectedNodeId}
          onClose={() => setPanelOpen(false)}
        />
      )}

      {/* Review Timeline（保留） */}
      {currentTask.reviews && currentTask.reviews.length > 0 && (
        <ReviewTimeline reviews={currentTask.reviews} />
      )}
    </div>
  );
}
