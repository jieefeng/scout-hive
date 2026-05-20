const API_BASE = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

export async function fetchTasks() {
  const resp = await fetch(`${API_BASE}/api/tasks/`);
  return resp.json();
}

export async function fetchTask(taskId: string) {
  const resp = await fetch(`${API_BASE}/api/tasks/${taskId}`);
  return resp.json();
}

export async function createTask(message: string) {
  const resp = await fetch(`${API_BASE}/api/tasks/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  return resp.json();
}

export function connectWebSocket(onEvent: (event: unknown) => void) {
  const ws = new WebSocket(WS_URL);
  ws.onmessage = (msg) => { onEvent(JSON.parse(msg.data)); };
  return ws;
}
