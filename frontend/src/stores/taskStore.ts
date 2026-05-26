import { create } from 'zustand';
import type { TaskSummary, WSEvent } from '../types';
import { fetchTasks, fetchTask, deleteTask as apiDeleteTask } from '../api/client';

interface TaskStore {
  tasks: TaskSummary[];
  currentTask: TaskSummary | null;
  wsEvents: WSEvent[];
  loading: boolean;
  loadTasks: () => Promise<void>;
  loadTask: (taskId: string) => Promise<void>;
  deleteTask: (taskId: string) => Promise<void>;
  addWSEvent: (event: WSEvent) => void;
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: [],
  currentTask: null,
  wsEvents: [],
  loading: false,
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
  deleteTask: async (taskId: string) => {
    await apiDeleteTask(taskId);
    set((state) => ({ tasks: state.tasks.filter(t => t.task_id !== taskId) }));
  },
  addWSEvent: (event: WSEvent) => {
    set((state) => ({ wsEvents: [...state.wsEvents, event] }));
  },
}));
