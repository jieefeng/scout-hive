import type { TaskSummary, TraceRecord } from '../types';
import type { TaskMetricsSnapshot } from '../api/client';

interface TaskOverviewTabProps {
  task: TaskSummary;
  metrics: TaskMetricsSnapshot | null;
  onSelectTrace: (trace: TraceRecord, nodeId: string | null) => void;
}

export default function TaskOverviewTab(_props: TaskOverviewTabProps) {
  return <div>Overview Tab (Task 13 will implement)</div>;
}
