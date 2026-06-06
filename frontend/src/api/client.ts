const API_BASE = 'http://localhost:5010';
const WS_URL = 'ws://localhost:5010/ws';

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
