// Chaos experiment and report types
// Maps to Python backend at src/lambdas/dashboard/chaos.py

export type ScenarioType = 'dynamodb_throttle' | 'ingestion_failure' | 'lambda_cold_start';

export type ExperimentStatus = 'created' | 'pending' | 'running' | 'completed' | 'failed' | 'stopped';

export type Verdict =
  | 'CLEAN'
  | 'COMPROMISED'
  | 'DRY_RUN_CLEAN'
  | 'RECOVERY_INCOMPLETE'
  | 'INCONCLUSIVE';

export type GateState = 'armed' | 'disarmed' | 'triggered';

// --- Experiment types ---

export interface Experiment {
  experiment_id: string;
  scenario_type: ScenarioType;
  status: ExperimentStatus;
  blast_radius: number;
  duration_seconds: number;
  created_at: string;
  fis_status?: string;
  parameters?: Record<string, unknown> | null;
}

export interface CreateExperimentRequest {
  scenario_type: ScenarioType;
  blast_radius: number;
  duration_seconds: number;
  parameters?: Record<string, unknown> | null;
}

// --- Report types ---

export interface DependencyStatus {
  status: 'healthy' | 'degraded';
  latency_ms?: number;
  error_rate?: number;
  error?: string;
}

export interface HealthSnapshot {
  dependencies: Record<string, DependencyStatus>;
  all_healthy?: boolean;
  degraded_services?: string[];
  captured_at?: string;
}

export interface ScenarioSummary {
  scenario_type: string;
  verdict: Verdict;
  summary: string;
}

export interface AssertionResult {
  assertion_id?: string;
  type?: string;
  description?: string;
  status: 'PASS' | 'FAIL' | 'SKIPPED';
  pass?: boolean;
  actual?: unknown;
  expected?: unknown;
  observed_value?: string;
  threshold?: string;
  notes?: string;
}

export interface PlanReport {
  scenarios: ScenarioSummary[];
  assertion_results?: AssertionResult[];
}

export interface ExperimentReport {
  experiment_id: string;
  scenario_type: ScenarioType;
  verdict: Verdict;
  verdict_reason: string;
  dry_run: boolean;
  baseline_health: HealthSnapshot;
  post_chaos_health: HealthSnapshot;
  plan_report?: PlanReport;
  configuration?: {
    blast_radius: number;
    duration_seconds: number;
    environment: string;
    injection_method?: string;
  };
}

export interface Report {
  report_id: string;
  experiment_id?: string;
  scenario_type: string;
  verdict: Verdict;
  created_at: string;
  environment: string;
  duration_seconds: number;
  dry_run: boolean;
  verdict_reason?: string;
  baseline_health?: HealthSnapshot;
  post_chaos_health?: HealthSnapshot;
  plan_report?: PlanReport;
}

export interface ReportListResponse {
  reports: Report[];
  next_cursor?: string | null;
}

// --- Comparison types ---

export interface DependencyChange {
  dependency: string;
  direction: 'improved' | 'regressed';
  from_status: string;
  to_status: string;
}

export interface ComparisonResult {
  baseline: {
    report_id: string;
    verdict: Verdict;
    created_at: string;
    post_chaos_health: HealthSnapshot;
  };
  current: {
    report_id: string;
    verdict: Verdict;
    created_at: string;
    post_chaos_health: HealthSnapshot;
  };
  direction: 'improved' | 'regressed' | 'neutral';
  changes: DependencyChange[];
}

// --- Trend types ---

export interface TrendDataPoint {
  report_id: string;
  created_at: string;
  verdict: Verdict;
}

// --- Safety control types ---

export interface HealthCheck {
  all_healthy: boolean;
  degraded_services: string[];
  dependencies: Record<string, DependencyStatus>;
}

export interface GateResponse {
  state: GateState;
}

export interface AndonResult {
  kill_switch_set: boolean;
  experiments_found: number;
  restored: number;
  failed: number;
  errors: string[];
}

// --- Metrics types ---

export interface MetricsSeries {
  label: string;
  timestamps: string[];
  values: number[];
  color: string;
}

export interface MetricsGroup {
  title: string;
  series: MetricsSeries[];
}

export interface MetricsResponse {
  groups: MetricsGroup[];
}

// --- Scenario metadata (client-side) ---

export interface ScenarioInfo {
  type: ScenarioType;
  title: string;
  description: string;
  icon: string;
}

export const SCENARIOS: ScenarioInfo[] = [
  {
    type: 'dynamodb_throttle',
    title: 'DynamoDB Throttle',
    description: 'Attach deny-write IAM policy to simulate write failures and retry behavior.',
    icon: 'database',
  },
  {
    type: 'ingestion_failure',
    title: 'Ingestion Failure',
    description: 'Set Lambda concurrency to 0 to throttle all ingestion invocations.',
    icon: 'upload',
  },
  {
    type: 'lambda_cold_start',
    title: 'Lambda Cold Start',
    description: 'Reduce Lambda memory to 128MB to force cold starts and increase latency.',
    icon: 'zap',
  },
];

export const SCENARIO_NAMES: Record<ScenarioType, string> = {
  dynamodb_throttle: 'DynamoDB Throttle',
  ingestion_failure: 'Ingestion Failure',
  lambda_cold_start: 'Lambda Cold Start',
};
