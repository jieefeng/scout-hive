import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTaskStore } from '../stores/taskStore';
import { createTask } from '../api/client';

interface CompetitorEntry {
  id: string;
  name: string;
  domain: string;
}

function isValidDomain(domain: string): boolean {
  return /\.[a-zA-Z]{2,}$/.test(domain.trim());
}

export default function Dashboard() {
  const { tasks, loading, loadTasks } = useTaskStore();
  const [competitors, setCompetitors] = useState<CompetitorEntry[]>([
    { id: '1', name: '', domain: '' },
  ]);
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { loadTasks(); }, [loadTasks]);

  const addCompetitor = () => {
    setCompetitors(prev => [...prev, { id: crypto.randomUUID(), name: '', domain: '' }]);
  };

  const removeCompetitor = (id: string) => {
    setCompetitors(prev => prev.filter(c => c.id !== id));
  };

  const updateCompetitor = (id: string, field: 'name' | 'domain', value: string) => {
    setCompetitors(prev => prev.map(c => c.id === id ? { ...c, [field]: value } : c));
  };

  const validCompetitors = competitors.filter(c => c.name.trim() && isValidDomain(c.domain.trim()));
  const canCreate = validCompetitors.length > 0;

  const handleCreate = async () => {
    if (!canCreate) return;
    setCreating(true);
    try {
      const task = await createTask(validCompetitors.map(c => ({ name: c.name.trim(), domain: c.domain.trim() })));
      setCompetitors([{ id: '1', name: '', domain: '' }]);
      await loadTasks();
      navigate(`/task/${task.task_id}`);
    } catch (err) {
      console.error('创建任务失败:', err);
      alert('创建任务失败，请检查后端是否正常运行');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div style={{ padding: '2rem' }}>
      <h1>竞品分析 Agent 系统</h1>

      <div style={{ marginBottom: '2rem', padding: '1.5rem', border: '1px solid #ddd', borderRadius: '8px', background: '#fafafa' }}>
        <h2 style={{ fontSize: '1.2rem', marginBottom: '0.75rem' }}>新建分析任务</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {competitors.map(comp => (
            <div key={comp.id} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                value={comp.name}
                onChange={e => updateCompetitor(comp.id, 'name', e.target.value)}
                placeholder="竞品名称，例如：飞书"
                style={{ flex: 1, padding: '0.75rem', fontSize: '1rem', border: '1px solid #ccc', borderRadius: '6px', outline: 'none' }}
              />
              <input
                type="text"
                value={comp.domain}
                onChange={e => updateCompetitor(comp.id, 'domain', e.target.value)}
                placeholder="域名，例如：feishu.cn"
                style={{ flex: 1, padding: '0.75rem', fontSize: '1rem', border: comp.domain && !isValidDomain(comp.domain) ? '1px solid #e53935' : '1px solid #ccc', borderRadius: '6px', outline: 'none' }}
              />
              <button
                onClick={() => removeCompetitor(comp.id)}
                disabled={competitors.length === 1}
                style={{ padding: '0.5rem 0.75rem', fontSize: '0.9rem', background: competitors.length === 1 ? '#eee' : '#e53935', color: '#fff', border: 'none', borderRadius: '6px', cursor: competitors.length === 1 ? 'not-allowed' : 'pointer' }}
              >
                删除
              </button>
            </div>
          ))}
          <button
            onClick={addCompetitor}
            style={{ alignSelf: 'flex-start', padding: '0.5rem 1rem', fontSize: '0.9rem', background: '#fff', color: '#1976d2', border: '1px solid #1976d2', borderRadius: '6px', cursor: 'pointer' }}
          >
            + 添加竞品
          </button>
          <button
            onClick={handleCreate}
            disabled={creating || !canCreate}
            style={{
              alignSelf: 'flex-end', padding: '0.75rem 1.5rem', fontSize: '1rem',
              background: creating || !canCreate ? '#ccc' : '#1976d2',
              color: '#fff', border: 'none', borderRadius: '6px',
              cursor: creating || !canCreate ? 'not-allowed' : 'pointer',
            }}
          >
            {creating ? '创建中...' : '开始分析'}
          </button>
        </div>
      </div>

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

      <h2 style={{ fontSize: '1.2rem', marginBottom: '0.75rem' }}>任务列表</h2>
      {loading ? <p>加载中...</p> : (
        <div>
          {tasks.length === 0 && <p style={{ color: '#999' }}>暂无任务，请在上方创建新任务</p>}
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
