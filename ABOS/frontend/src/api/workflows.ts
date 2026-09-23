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
 * Get all workflows
 */
export const getWorkflows = async (): Promise<Workflow[]> => {
  const response = await apiClient.get('/workflows');
  return response.data;
};
