export interface MemorySearchCaseMetric {
  case_id: string;
  latency_ms: number;
  returned_ids: string[];
  forbidden_returned_ids: string[];
  precision_at_k: number;
  recall_at_k: number;
  hit_rate: number;
  mrr: number;
  ndcg: number;
  exclusion_rate: number;
  contamination_rate: number;
  error?: string | null;
}

export interface MemoryCompactionCaseMetric {
  case_id: string;
  latency_ms: number;
  source_tokens: number;
  summary_tokens: number;
  compression_ratio: number;
  retention_rate: number;
  safety_rate: number;
  forbidden_terms_found: string[];
  over_budget: boolean;
  error?: string | null;
}

export interface MemoryArchitectureMetrics {
  index_exists: boolean;
  index_line_count: number;
  index_under_limit: boolean;
  topic_file_count: number;
  session_artifact_count: number;
  issue_count: number;
  issues_by_code: Record<string, number>;
  score: number;
}

export interface MemoryEvalReport {
  suite_name: string;
  backend_name: string;
  search_cases: MemorySearchCaseMetric[];
  compaction_cases: MemoryCompactionCaseMetric[];
  architecture?: MemoryArchitectureMetrics | null;
  summary: Record<string, number>;
}

export interface MemoryEvalRequest {
  backend?: "keyword" | "copaw";
  suite?: Record<string, unknown> | null;
}
