export interface CompetitorInfo {
  name: string;
  domain: string;
}

export interface TaskSummary {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number; // 0.0 - 1.0
  competitors: CompetitorInfo[];
  dimensions: string[];
  node_states: Record<string, string>;
  dag_json?: { nodes?: { id: string; agent: string; action: string; depends_on?: string[] }[]; edges?: { from_node?: string; from?: string; to_node?: string; to?: string }[]; feedback_edges?: { from_node?: string; from?: string; to_node?: string; to?: string; condition?: string }[] };
  created_at: string;
  updated_at: string;
  report_html: string;
  traces: TraceRecord[];
  reviews: ReviewResult[];
}

export interface TraceRecord {
  trace_id: string;
  node_id: string;
  agent: string;
  timestamp: string;
  input_refs: Record<string, unknown>;
  output: Record<string, unknown>;
  reasoning_chain: ReasoningStep[];
  sources: TraceSource[];
  confidence: { score: number; level: string };
  llm_metadata: { model: string; tokens_used: number; latency_ms: number };
}

export interface ReasoningStep {
  step: number;
  thought: string;
  source_ref?: string;
}

export interface TraceSource {
  source_id: string;
  type: string;
  url: string;
  snippet: string;
}

export interface ReviewResult {
  review_id: string;
  round: number;
  verdict: 'approved' | 'rejected';
  checks: ReviewCheck[];
  feedback_to: string;
  feedback_message: string;
}

export interface ReviewCheck {
  dimension: string;
  status: 'pass' | 'fail';
  issues: ReviewIssue[];
}

export interface ReviewIssue {
  finding_id: string;
  severity: 'critical' | 'warning';
  description: string;
  suggestion: string;
}

export interface WSEvent {
  type: string;
  task_id: string;
  node_id?: string;
  data?: Record<string, unknown>;
}
