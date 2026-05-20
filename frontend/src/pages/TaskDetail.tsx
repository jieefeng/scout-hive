import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useTaskStore } from '../stores/taskStore';
import DagViewer from '../components/DagViewer';

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>();
  const { currentTask, loading, loadTask } = useTaskStore();

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
          <DagViewer nodeStates={currentTask.node_states} onNodeClick={(id) => console.log('Clicked node:', id)} />
        </div>
        <div style={{ flex: 1, border: '1px solid #ddd', padding: '1rem', borderRadius: '8px' }}>
          <h2>Agent 详情</h2>
          <p>（详情面板将在后续任务中实现）</p>
        </div>
      </div>
    </div>
  );
}
