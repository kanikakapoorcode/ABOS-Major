import apiClient from './client';
import { AgentProfile, AgentTaskProfile } from './types';

/**
 * Get all agent performance profiles
 */
export const getAgentProfiles = async (): Promise<AgentProfile[]> => {
  const response = await apiClient.get<{ agents: AgentProfile[] }>('/agents/');
  return response.data.agents;
};

/**
 * Get Tier-1 task-specific performance profiles
 */
export const getAgentTaskProfiles = async (
  department?: string,
  taskType?: string
): Promise<AgentTaskProfile[]> => {
  const response = await apiClient.get<{ task_profiles: AgentTaskProfile[] }>(
    '/agents/task-profiles',
    {
      params: {
        ...(department ? { department } : {}),
        ...(taskType ? { task_type: taskType } : {}),
      },
    }
  );
  return response.data.task_profiles;
};

/**
 * Get a specific agent profile
 */
export const getAgentProfile = async (agentName: string): Promise<AgentProfile> => {
  const response = await apiClient.get(`/agents/${agentName}`);
  return response.data;
};
