import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTaskStore } from '../stores/taskStore';
import DagViewer from '../components/DagViewer';
import AgentDetail from '../components/AgentDetail';
import TraceBrowser from '../components/TraceBrowser';
import ReviewTimeline from '../components/ReviewTimeline';
import type { TraceRecord } from '../types';

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>();
  const { currentTask, loading, loadTask } = useTaskStore();
  const [selectedTrace, setSelectedTrace] = useState<TraceRecord | null>(null);

  useEffect(() => { if (taskId) loadTask(taskId); }, [taskId, loadTask]);

  if (loading) return <p>加载中...</p>;
  if (!currentTask) return <p>任务不存在</p>;

  return (
    <div style={{ padding: '2rem' }}>
      <h1>任务详情: {currentTask.task_id.slice(0, 8)}</h1>
      <p>状态: {currentTask.status}</p>
      <p>竞品: {currentTask.competitors.join(', ')}</p>
      <div style={{ display: 'flex', gap: '2rem', marginTop: '2rem' }}>
        <div style={{ flex: 1, border: '1px solid #ddd', padding: '1rem', borderRadius: '8px' }}>
          <h2>DAG 执行图</h2>
          <DagViewer nodeStates={currentTask.node_states} onNodeClick={(id) => {
            const trace = currentTask.traces?.find(t => t.node_id === id);
            if (trace) setSelectedTrace(trace);
          }} />
        </div>
        <div style={{ flex: 1, border: '1px solid #ddd', padding: '1rem', borderRadius: '8px' }}>
          <h2>Agent 详情</h2>
          <AgentDetail trace={selectedTrace} />
        </div>
      </div>
      <div style={{ marginTop: '2rem' }}>
        <h2>溯源浏览器</h2>
        <div style={{ border: '1px solid #ddd', borderRadius: '8px', minHeight: '400px', overflow: 'hidden' }}>
          <TraceBrowser traces={currentTask.traces || []} />
        </div>
      </div>
      <div style={{ marginTop: '2rem' }}>
        <h2>审查时间轴</h2>
        <div style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '1rem' }}>
          <ReviewTimeline reviews={currentTask.reviews || []} />
        </div>
      </div>
    </div>
  );
}
