// API Response Types

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
}

export type GoalStatus =
  | 'pending'
  | 'planning'
  | 'ready'
  | 'executing'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'compliance_blocked';
export type GoalPriority = 'low' | 'medium' | 'high' | 'critical';

export interface Goal {
  id: string;
  user_id: string;
  title: string;
  description: string;
  priority: GoalPriority;
  status: GoalStatus;
  target_departments?: string[] | null;
  context?: Record<string, unknown> | null;
  preferred_language?: string | null;
  created_at: string;
  updated_at: string;
}

export interface GoalCreateRequest {
  title: string;
  description: string;
  priority: GoalPriority;
  target_departments?: string[] | null;
  context?: Record<string, unknown> | null;
  preferred_language?: string | null;
}

export type StepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'retrying'
  | 'compliance_failed';

export type WorkflowStatus =
  | 'pending'
  | 'executing'
  | 'completed'
  | 'failed'
  | 'partially_completed';

export interface WorkflowStep {
  id: string;
  workflow_id: string;
  step_index: number;
  title: string;
  description: string;
  assigned_department: string;
  assigned_agent: string;
  task_type?: string | null;
  input_data?: Record<string, unknown> | null;
  output_data?: Record<string, unknown> | null;
  status: StepStatus;
  retry_count: number;
  latency_ms?: number | null;
  created_at: string;
  updated_at: string;
}

export interface Workflow {
  id: string;
  goal_id: string;
  user_id: string;
  status: WorkflowStatus;
  steps: WorkflowStep[];
  total_steps: number;
  completed_steps: number;
  failed_steps: number;
  total_latency_ms?: number | null;
  detected_language?: string | null;
  summary?: string | null;
  localised_summary?: string | null;
  compliance_flags?: string[] | null;
  localised_compliance_flags?: string[] | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentProfile {
  agent_name: string;
  department: string;
  success_rate: number;
  avg_latency_ms: number;
  confidence_score: number;
  total_executions: number;
  window_size: number;
  last_updated?: string | null;
}

export interface AgentTaskProfile extends AgentProfile {
  task_type: string;
}

export interface ErrorResponse {
  detail: string;
}
