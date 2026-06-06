import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { parseTaskBlueprint, confirmParse, ParseError, ParseResponse } from '../api/client';

export default function ParsePreview() {
  const [params] = useSearchParams();
  const initialMessage = params.get('message') ?? '';
  const navigate = useNavigate();

  const [message, setMessage] = useState(initialMessage);
  const [loading, setLoading] = useState(false);
  const [parseResult, setParseResult] = useState<ParseResponse | null>(null);
  const [blueprintJson, setBlueprintJson] = useState<string>('');
  const [error, setError] = useState<{ type: string; raw?: string; hint?: string } | null>(null);

  async function handleParse() {
    setLoading(true);
    setError(null);
    setParseResult(null);
    try {
      const r = await parseTaskBlueprint(message);
      setParseResult(r);
      setBlueprintJson(JSON.stringify(r.blueprint, null, 2));
    } catch (e) {
      if (e instanceof ParseError) {
        setError({
          type: e.detail.error_type,
          raw: e.detail.raw_response,
          hint: e.detail.hint,
        });
      } else {
        setError({ type: 'network', hint: String(e) });
      }
    } finally {
      setLoading(false);
    }
  }

  // 路由进来时如果带了 message 就自动 parse
  useEffect(() => {
    if (initialMessage && !parseResult && !loading) {
      handleParse();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleConfirm() {
    if (!blueprintJson.trim()) return;
    let blueprint: object;
    try {
      blueprint = JSON.parse(blueprintJson);
    } catch {
      setError({ type: 'json_parse', hint: '蓝图 JSON 格式有误' });
      return;
    }
    setLoading(true);
    try {
      const task = await confirmParse(blueprint);
      navigate(`/task/${task.task_id}`);
    } catch (e) {
      setError({ type: 'confirm_failed', hint: String(e) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto', fontFamily: 'sans-serif' }}>
      <h1 style={{ fontSize: 22 }}>解析自然语言需求</h1>

      <label style={{ display: 'block', marginTop: 16, fontWeight: 600 }}>
        需求描述
      </label>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={4}
        style={{ width: '100%', padding: 8, fontSize: 14, fontFamily: 'inherit' }}
        placeholder="例：对比飞书、钉钉、企业微信的 AI 协作能力"
      />
      <button
        onClick={handleParse}
        disabled={loading || !message.trim()}
        style={{ marginTop: 8, padding: '8px 16px' }}
      >
        {loading ? '解析中...' : '解析'}
      </button>

      {error && (
        <div
          style={{
            marginTop: 16, padding: 12, background: '#fef2f2',
            border: '1px solid #fca5a5', borderRadius: 4,
          }}
        >
          <div style={{ color: '#b91c1c', fontWeight: 600 }}>
            解析失败: {error.type}
          </div>
          {error.hint && <div style={{ marginTop: 4, color: '#7f1d1d' }}>{error.hint}</div>}
          {error.raw && (
            <details style={{ marginTop: 8 }}>
              <summary>查看 AI 原始输出</summary>
              <pre style={{ background: '#fff', padding: 8, fontSize: 12, overflow: 'auto' }}>
                {error.raw}
              </pre>
            </details>
          )}
        </div>
      )}

      {parseResult && (
        <>
          <section style={{ marginTop: 24 }}>
            <h2 style={{ fontSize: 18 }}>AI 调研组长的理解</h2>
            {parseResult.summary && <p>{parseResult.summary}</p>}
            <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
              <div>
                <strong>竞品：</strong>
                {parseResult.competitors.join('、')}
              </div>
              <div>
                <strong>维度：</strong>
                {parseResult.dimensions.join('、')}
              </div>
              <div>
                <strong>节点数：</strong>
                {parseResult.blueprint.nodes.length}
              </div>
            </div>
          </section>

          <section style={{ marginTop: 16 }}>
            <h2 style={{ fontSize: 18 }}>DAG 蓝图（可编辑 JSON）</h2>
            <textarea
              value={blueprintJson}
              onChange={(e) => setBlueprintJson(e.target.value)}
              rows={20}
              style={{
                width: '100%', padding: 8, fontFamily: 'monospace', fontSize: 12,
                background: '#f9fafb',
              }}
            />
          </section>

          <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <button
              onClick={handleConfirm}
              disabled={loading}
              style={{
                padding: '8px 16px', background: '#10b981', color: '#fff',
                border: 'none', borderRadius: 4, cursor: 'pointer',
              }}
            >
              {loading ? '启动中...' : '确认执行'}
            </button>
            <button
              onClick={() => navigate('/')}
              style={{ padding: '8px 16px' }}
            >
              取消
            </button>
          </div>
        </>
      )}
    </div>
  );
}
