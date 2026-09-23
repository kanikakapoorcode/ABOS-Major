import apiClient from './client';
import { AgentProfile } from './types';

/**
 * Get all agent performance profiles
 */
export const getAgentProfiles = async (): Promise<AgentProfile[]> => {
  const response = await apiClient.get('/agents');
  return response.data;
};

/**
 * Get a specific agent profile
 */
export const getAgentProfile = async (agentName: string): Promise<AgentProfile> => {
  const response = await apiClient.get(`/agents/${agentName}`);
  return response.data;
};
