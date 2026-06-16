import { create } from 'zustand';
import type { TaskSummary, WSEvent } from '../types';
import {
  fetchTasks, fetchTask, deleteTask as apiDeleteTask,
  fetchTaskMetrics, type TaskMetricsSnapshot,
} from '../api/client';

interface TaskStore {
  tasks: TaskSummary[];
  currentTask: TaskSummary | null;
  metrics: TaskMetricsSnapshot | null;
  wsEvents: WSEvent[];
  loading: boolean;
  // metrics 重拉的节流（per task_id）
  _lastMetricsFetch: Record<string, number>;
  loadTasks: () => Promise<void>;
  loadTask: (taskId: string) => Promise<void>;
  loadMetrics: (taskId: string, force?: boolean) => Promise<void>;
  deleteTask: (taskId: string) => Promise<void>;
  addWSEvent: (event: WSEvent) => Promise<void>;
}

const METRICS_THROTTLE_MS = 5000;

export const useTaskStore = create<TaskStore>((set, get) => ({
  tasks: [],
  currentTask: null,
  metrics: null,
  wsEvents: [],
  loading: false,
  _lastMetricsFetch: {},

  loadTasks: async () => {
    set({ loading: true });
    const tasks = await fetchTasks();
    set({ tasks, loading: false });
  },

  loadTask: async (taskId: string) => {
    set({ loading: true });
    try {
      const task = await fetchTask(taskId);
      set({ currentTask: task, loading: false });
    } catch {
      set({ currentTask: null, loading: false });
    }
  },

  loadMetrics: async (taskId: string, force = false) => {
    const now = Date.now();
    const last = get()._lastMetricsFetch[taskId] || 0;
    if (!force && now - last < METRICS_THROTTLE_MS) {
      return;
    }
    set((state) => ({
      _lastMetricsFetch: { ...state._lastMetricsFetch, [taskId]: now },
    }));
    const metrics = await fetchTaskMetrics(taskId);
    set({ metrics });
  },

  deleteTask: async (taskId: string) => {
    await apiDeleteTask(taskId);
    set((state) => ({ tasks: state.tasks.filter(t => t.task_id !== taskId) }));
  },

  addWSEvent: async (event: WSEvent) => {
    const MAX_WS_EVENTS = 100;
    set((state) => ({
      wsEvents: [...state.wsEvents.slice(-MAX_WS_EVENTS + 1), event],
    }));
    // 节点完成 → 节流重拉 metrics
    if (event.type === 'node_completed' && event.task_id) {
      await get().loadMetrics(event.task_id);
    }
  },
}));
