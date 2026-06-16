import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTaskStore } from '../stores/taskStore';
import { createTask, fetchDimensions } from '../api/client';

interface CompetitorEntry {
  id: string;
  name: string;
  domain: string;
  category?: string;
}

/** 预置竞品品类 */
const CATEGORIES = ['AI 助手', '办公协作', '搜索引擎', '其他'] as const;

/** 预置国内 AI 助手竞品列表（按品类分组） */
const DEFAULT_COMPETITORS: { name: string; domain: string; category: string }[] = [
  { name: '豆包', domain: 'doubao.com', category: 'AI 助手' },
  { name: '通义千问', domain: 'tongyi.aliyun.com', category: 'AI 助手' },
  { name: 'Kimi', domain: 'kimi.moonshot.cn', category: 'AI 助手' },
  { name: '文小言', domain: 'yiyan.baidu.com', category: 'AI 助手' },
  { name: '智谱清言', domain: 'chatglm.cn', category: 'AI 助手' },
  { name: '讯飞星火', domain: 'xinghuo.xfyun.cn', category: 'AI 助手' },
  { name: '百川智能', domain: 'baichuan-ai.com', category: 'AI 助手' },
  { name: '秘塔 AI 搜索', domain: 'metaso.cn', category: '搜索引擎' },
];

/** 默认勾选的竞品名称（前 5 个，与 demo 保持一致） */
const DEFAULT_SELECTED_NAMES = new Set(
  DEFAULT_COMPETITORS.slice(0, 5).map(c => c.name)
);

/** 从输入中提取纯域名（去掉协议、路径、端口） */
function extractDomain(input: string): string {
  let d = input.trim();
  // 补全协议以便 URL 解析
  if (d.includes('/') && !d.startsWith('http')) d = 'https://' + d;
  try {
    const url = new URL(d);
    return url.hostname;
  } catch {
    // 不是 URL，当纯域名处理
    return d.replace(/^(www\.)?/, '').split('/')[0].split(':')[0];
  }
}

/** 校验域名或 URL 是否合法 */
function isValidWebsite(input: string): boolean {
  const d = input.trim();
  if (!d) return false;
  const domain = extractDomain(d);
  if (!domain || domain.endsWith('.')) return false;
  return /^[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z]{2,})+$/.test(domain);
}

export default function Dashboard() {
  const tasks = useTaskStore(s => s.tasks);
  const loading = useTaskStore(s => s.loading);
  const loadTasks = useTaskStore(s => s.loadTasks);
  const deleteTask = useTaskStore(s => s.deleteTask);
  const [selectedDefaults, setSelectedDefaults] = useState<Set<string>>(new Set(DEFAULT_SELECTED_NAMES));
  const [customCompetitors, setCustomCompetitors] = useState<CompetitorEntry[]>([]);
  const [creating, setCreating] = useState(false);
  const [nlpMessage, setNlpMessage] = useState('');
  const [dimensions, setDimensions] = useState<string[]>([]);
  const [selectedDimensions, setSelectedDimensions] = useState<Set<string>>(new Set());
  const navigate = useNavigate();

  useEffect(() => { loadTasks(); }, [loadTasks]);

  useEffect(() => {
    fetchDimensions()
      .then(dims => {
        setDimensions(dims);
        setSelectedDimensions(new Set(dims)); // 默认全选
      })
      .catch(err => console.error('获取维度列表失败:', err));
  }, []);

  const goToNlpParse = () => {
    const trimmed = nlpMessage.trim();
    if (!trimmed) {
      navigate('/parse');
    } else {
      navigate(`/parse?message=${encodeURIComponent(trimmed)}`);
    }
  };

  const toggleDefaultCompetitor = (name: string) => {
    setSelectedDefaults(prev => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  };

  const addCustomCompetitor = () => {
    setCustomCompetitors(prev => [...prev, { id: crypto.randomUUID(), name: '', domain: '' }]);
  };

  const updateCustomCompetitor = (id: string, field: 'name' | 'domain', value: string) => {
    setCustomCompetitors(prev => prev.map(c => c.id === id ? { ...c, [field]: value } : c));
  };

  /** 合并默认勾选 + 自定义输入的竞品 */
  const allCompetitors: CompetitorEntry[] = [
    ...DEFAULT_COMPETITORS
      .filter(c => selectedDefaults.has(c.name))
      .map(c => ({ id: `default_${c.name}`, name: c.name, domain: c.domain, category: c.category })),
    ...customCompetitors,
  ];

  const validCompetitors = allCompetitors.filter(c => c.name.trim() && isValidWebsite(c.domain.trim()));
  const canCreate = validCompetitors.length > 0 && selectedDimensions.size > 0;

  const toggleDimension = (dim: string) => {
    setSelectedDimensions(prev => {
      const next = new Set(prev);
      if (next.has(dim)) {
        next.delete(dim);
      } else {
        next.add(dim);
      }
      return next;
    });
  };

  const toggleAllDimensions = () => {
    setSelectedDimensions(prev =>
      prev.size === dimensions.length ? new Set() : new Set(dimensions)
    );
  };

  const handleDelete = async (taskId: string) => {
    if (!confirm('确定要删除该任务吗？')) return;
    try {
      await deleteTask(taskId);
    } catch (err) {
      console.error('删除任务失败:', err);
      alert('删除任务失败');
    }
  };

  const handleCreate = async () => {
    if (!canCreate) return;
    setCreating(true);
    try {
      const task = await createTask(
        validCompetitors.map(c => ({ name: c.name.trim(), domain: c.domain.trim() })),
        Array.from(selectedDimensions)
      );
      setSelectedDefaults(new Set(DEFAULT_SELECTED_NAMES));
      setCustomCompetitors([]);
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

      <section style={{ marginBottom: 24, padding: 16, background: '#f0f9ff', borderRadius: 8 }}>
        <h2 style={{ fontSize: 18, marginTop: 0 }}>用自然语言新建分析（AI 调研组长）</h2>
        <input
          value={nlpMessage}
          onChange={(e) => setNlpMessage(e.target.value)}
          placeholder="例：对比飞书、钉钉、企业微信的 AI 协作能力"
          style={{ width: '100%', padding: 8, fontSize: 14, boxSizing: 'border-box' }}
        />
        <button
          onClick={goToNlpParse}
          style={{ marginTop: 8, padding: '8px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
        >
          → AI 解析并预览
        </button>
      </section>

      <div style={{ marginBottom: '2rem', padding: '1.5rem', border: '1px solid #ddd', borderRadius: '8px', background: '#fafafa' }}>
        <h2 style={{ fontSize: '1.2rem', marginBottom: '0.75rem' }}>新建分析任务</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {/* 默认竞品多选列表 */}
          <div style={{ padding: '1rem', background: '#fff', border: '1px solid #e0e0e0', borderRadius: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span style={{ fontWeight: 500 }}>选择竞品</span>
              <button
                onClick={() => setSelectedDefaults(prev =>
                  prev.size === DEFAULT_COMPETITORS.length ? new Set() : new Set(DEFAULT_COMPETITORS.map(c => c.name))
                )}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', background: 'none', border: '1px solid #1976d2', color: '#1976d2', borderRadius: '4px', cursor: 'pointer' }}
              >
                {selectedDefaults.size === DEFAULT_COMPETITORS.length ? '取消全选' : '全选'}
              </button>
            </div>
            {/* 按品类分组展示 */}
            {CATEGORIES.map(cat => {
              const groupComps = DEFAULT_COMPETITORS.filter(c => c.category === cat);
              if (groupComps.length === 0) return null;
              return (
                <div key={cat} style={{ marginBottom: '0.5rem' }}>
                  <div style={{ fontSize: '0.8rem', color: '#888', marginBottom: '0.4rem', borderBottom: '1px solid #e0e0e0', paddingBottom: '0.2rem' }}>
                    {cat}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {groupComps.map(comp => (
                      <label
                        key={comp.name}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '0.4rem',
                          padding: '0.4rem 0.75rem', borderRadius: '4px', cursor: 'pointer',
                          background: selectedDefaults.has(comp.name) ? '#e3f2fd' : '#f5f5f5',
                          border: selectedDefaults.has(comp.name) ? '1px solid #1976d2' : '1px solid #e0e0e0',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedDefaults.has(comp.name)}
                          onChange={() => toggleDefaultCompetitor(comp.name)}
                          style={{ cursor: 'pointer' }}
                        />
                        <span style={{ fontSize: '0.9rem' }}>{comp.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* 自定义竞品输入 */}
          {customCompetitors.map(comp => (
            <div key={comp.id} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                value={comp.name}
                onChange={e => updateCustomCompetitor(comp.id, 'name', e.target.value)}
                placeholder="竞品名称，例如：飞书"
                style={{ flex: 1, padding: '0.75rem', fontSize: '1rem', border: '1px solid #ccc', borderRadius: '6px', outline: 'none' }}
              />
              <input
                type="text"
                value={comp.domain}
                onChange={e => updateCustomCompetitor(comp.id, 'domain', e.target.value)}
                placeholder="域名或网址，例如：feishu.cn"
                style={{ flex: 1, padding: '0.75rem', fontSize: '1rem', border: comp.domain && !isValidWebsite(comp.domain) ? '1px solid #e53935' : '1px solid #ccc', borderRadius: '6px', outline: 'none' }}
              />
            </div>
          ))}
          <button
            onClick={addCustomCompetitor}
            style={{ alignSelf: 'flex-start', padding: '0.5rem 1rem', fontSize: '0.9rem', background: '#fff', color: '#1976d2', border: '1px solid #1976d2', borderRadius: '6px', cursor: 'pointer' }}
          >
            + 添加自定义竞品
          </button>

          {dimensions.length > 0 && (
            <div style={{ marginTop: '0.5rem', padding: '1rem', background: '#fff', border: '1px solid #e0e0e0', borderRadius: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <span style={{ fontWeight: 500 }}>分析维度</span>
                <button
                  onClick={toggleAllDimensions}
                  style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem', background: 'none', border: '1px solid #1976d2', color: '#1976d2', borderRadius: '4px', cursor: 'pointer' }}
                >
                  {selectedDimensions.size === dimensions.length ? '取消全选' : '全选'}
                </button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {dimensions.map(dim => (
                  <label
                    key={dim}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '0.4rem',
                      padding: '0.4rem 0.75rem', borderRadius: '4px', cursor: 'pointer',
                      background: selectedDimensions.has(dim) ? '#e3f2fd' : '#f5f5f5',
                      border: selectedDimensions.has(dim) ? '1px solid #1976d2' : '1px solid #e0e0e0',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedDimensions.has(dim)}
                      onChange={() => toggleDimension(dim)}
                      style={{ cursor: 'pointer' }}
                    />
                    <span style={{ fontSize: '0.9rem' }}>{dim}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

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
            <div key={task.task_id} style={{ padding: '1rem', border: '1px solid #ddd', marginBottom: '0.5rem', borderRadius: '4px', display: 'flex', alignItems: 'center' }}>
              <Link to={`/task/${task.task_id}`} style={{ flex: 1 }}>
                任务 {task.task_id.slice(0, 8)} — {task.status}
              </Link>
              <span style={{ marginLeft: '1rem', color: '#666' }}>{task.competitors.map(c => c.name).join(', ')}</span>
              <button
                onClick={() => handleDelete(task.task_id)}
                style={{
                  marginLeft: '1rem', padding: '0.3rem 0.75rem', fontSize: '0.85rem',
                  background: '#fff', color: '#e53935', border: '1px solid #e53935',
                  borderRadius: '4px', cursor: 'pointer',
                }}
              >
                删除
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
