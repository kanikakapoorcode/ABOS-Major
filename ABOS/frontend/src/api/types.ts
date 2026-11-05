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

export type GoalStatus = 'pending' | 'planning' | 'executing' | 'completed' | 'failed';
export type GoalPriority = 'low' | 'medium' | 'high' | 'critical';

export interface Goal {
  id: string;
  user_id: string;
  title: string;
  description: string;
  priority: GoalPriority;
  status: GoalStatus;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface GoalCreateRequest {
  title: string;
  description: string;
  priority: GoalPriority;
}

export type StepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface WorkflowStep {
  step_index: number;
  title: string;
  assigned_agent: string;
  status: StepStatus;
  started_at?: string;
  completed_at?: string;
  latency_ms?: number;
  error_message?: string;
}

export interface Workflow {
  id: string;
  goal_id: string;
  goal: Goal;
  status: GoalStatus;
  steps: WorkflowStep[];
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface AgentProfile {
  agent_name: string;
  department: string;
  task_type: string;
  success_rate: number;
  avg_latency_ms: number;
  confidence_score: number;
  total_executions: number;
  last_execution?: string;
}

export interface ErrorResponse {
  detail: string;
}
