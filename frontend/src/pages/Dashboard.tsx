import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTaskStore } from '../stores/taskStore';

export default function Dashboard() {
  const { tasks, loading, loadTasks } = useTaskStore();
  useEffect(() => { loadTasks(); }, [loadTasks]);

  return (
    <div style={{ padding: '2rem' }}>
      <h1>竞品分析 Agent 系统</h1>
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
        <div style={{ padding: '1rem', background: '#e3f2fd', borderRadius: '8px' }}>
          进行中: {tasks.filter(t => t.status === 'running').length}
        </div>
        <div style={{ padding: '1rem', background: '#e8f5e9', borderRadius: '8px' }}>
          已完成: {tasks.filter(t => t.status === 'completed').length}
        </div>
        <div style={{ padding: '1rem', background: '#ffebee', borderRadius: '8px' }}>
          失败: {tasks.filter(t => t.status === 'failed').length}
        </div>
      </div>
      {loading ? <p>加载中...</p> : (
        <div>
          {tasks.map(task => (
            <div key={task.task_id} style={{ padding: '1rem', border: '1px solid #ddd', marginBottom: '0.5rem', borderRadius: '4px' }}>
              <Link to={`/task/${task.task_id}`}>
                任务 {task.task_id.slice(0, 8)} — {task.status}
              </Link>
              <span style={{ marginLeft: '1rem', color: '#666' }}>{task.competitors.join(', ')}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
