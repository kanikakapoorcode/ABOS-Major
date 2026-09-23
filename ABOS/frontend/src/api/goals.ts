import apiClient from './client';
import { Goal, GoalCreateRequest } from './types';

/**
 * Create a new goal
 */
export const createGoal = async (data: GoalCreateRequest): Promise<Goal> => {
  const response = await apiClient.post('/goals', data);
  return response.data;
};

/**
 * Get all goals for the current user
 */
export const getGoals = async (): Promise<Goal[]> => {
  const response = await apiClient.get('/goals');
  return response.data;
};

/**
 * Get a specific goal by ID
 */
export const getGoalById = async (goalId: string): Promise<Goal> => {
  const response = await apiClient.get(`/goals/${goalId}`);
  return response.data;
};
