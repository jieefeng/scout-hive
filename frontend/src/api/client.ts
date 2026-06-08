const API_BASE = 'http://localhost:5010';
const WS_URL = 'ws://localhost:5010/ws';

export interface SlowNode {
  node_id: string;
  agent: string;
  elapsed_ms: number;
  cost_cny: number;
}

export interface AgentBreakdown {
  count: number;
  tokens: number;
  cost_cny: number;
  elapsed_ms: number;
}

export interface QualityMetrics {
  feedback_rounds: number;
  passed_count: number;
}

export interface TaskMetricsSnapshot {
  task_id: string;
  created_at: string;
  total_elapsed_ms: number;
  node_count: number;
  completed_count: number;
  failed_count: number;
  feedback_rounds: number;
  total_tokens: number;
  total_cost_cny: number;
  llm_call_count: number;
  slow_nodes: SlowNode[];
  agent_breakdown: Record<string, AgentBreakdown>;
  quality: QualityMetrics;
  rc_missing_count: number;
  available?: boolean;
  reason?: string;
}

export async function fetchTasks() {
  const resp = await fetch(`${API_BASE}/api/tasks/`);
  return resp.json();
}

export async function fetchTask(taskId: string) {
  const resp = await fetch(`${API_BASE}/api/tasks/${taskId}`);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`fetchTask failed: ${resp.status}`);
  return resp.json();
}

export async function fetchTaskMetrics(taskId: string): Promise<TaskMetricsSnapshot | null> {
  const resp = await fetch(`${API_BASE}/api/tasks/${taskId}/metrics`);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`fetchTaskMetrics failed: ${resp.status}`);
  return resp.json();
}

export async function createTask(competitors: Array<{name: string, domain: string}>) {
  const resp = await fetch(`${API_BASE}/api/tasks/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ competitors }),
  });
  return resp.json();
}

export async function deleteTask(taskId: string) {
  const resp = await fetch(`${API_BASE}/api/tasks/${taskId}`, {
    method: 'DELETE',
  });
  if (!resp.ok) throw new Error(`deleteTask failed: ${resp.status}`);
  return resp.json();
}

export function connectWebSocket(onEvent: (event: unknown) => void) {
  const ws = new WebSocket(WS_URL);
  ws.onmessage = (msg) => { onEvent(JSON.parse(msg.data)); };
  return ws;
}

export interface ParseResponse {
  blueprint: { nodes: any[]; edges: any[]; feedback_edges?: any[] };
  competitors: string[];
  dimensions: string[];
  summary: string;
}

export interface ParseConfirmResponse {
  task_id: string;
  status: string;
  // 其他字段由后端 TaskResponse 决定，TS 端不强校验
  [key: string]: unknown;
}

export class ParseError extends Error {
  status: number;
  detail: {
    error_type: string;
    raw_response?: string;
    hint?: string;
    error_message?: string;
    // 硬收窄(2026-06-08):后端在 error_type === 'dim_not_in_schema' 时附带这两个字段
    invalid_dims?: string[];
    allowed?: string[];
  };
  constructor(status: number, detail: any) {
    super(detail?.error_type ?? `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export async function parseTaskBlueprint(message: string) {
  const resp = await fetch(`${API_BASE}/api/tasks/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new ParseError(resp.status, detail?.detail ?? { error_type: 'unknown' });
  }
  return resp.json();
}

export async function confirmParse(blueprint: object) {
  const resp = await fetch(`${API_BASE}/api/tasks/parse/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ blueprint }),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(`confirm failed: ${resp.status} ${JSON.stringify(detail)}`);
  }
  return resp.json();
}
