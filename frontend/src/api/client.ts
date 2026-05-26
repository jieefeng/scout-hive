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
