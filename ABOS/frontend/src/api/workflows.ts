import apiClient from './client';
import { Workflow } from './types';

/**
 * Get workflow details by ID
 */
export const getWorkflowById = async (workflowId: string): Promise<Workflow> => {
  const response = await apiClient.get(`/workflows/${workflowId}`);
  return response.data;
};

/**
 * Get all workflows (optionally filtered by goal_id)
 */
export const getWorkflows = async (goalId?: string): Promise<Workflow[]> => {
  const response = await apiClient.get<{ workflows: Workflow[]; total: number }>('/workflows/', {
    params: goalId ? { goal_id: goalId } : undefined,
  });
  return response.data.workflows;
};

/**
 * Re-queue a failed or incomplete workflow for execution
 */
export const retryWorkflow = async (
  workflowId: string
): Promise<{ detail: string; workflow_id: string }> => {
  const response = await apiClient.post(`/workflows/${workflowId}/retry`);
  return response.data;
};
