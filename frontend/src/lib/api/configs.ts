import { api } from './client';
import type {
  Configuration,
  ConfigurationList,
  CreateConfigRequest,
  UpdateConfigRequest,
} from '@/types/config';

export const configsApi = {
  /**
   * List all configurations for the current user
   */
  list: () =>
    api.get<ConfigurationList>('/api/v2/configurations'),

  /**
   * Get a single configuration by ID
   */
  get: (configId: string) =>
    api.get<Configuration>(`/api/v2/configurations/${configId}`),

  /**
   * Create a new configuration
   */
  create: (config: CreateConfigRequest) =>
    api.post<Configuration>('/api/v2/configurations', config),

  /**
   * Update an existing configuration
   */
  update: (configId: string, updates: UpdateConfigRequest) =>
    api.patch<Configuration>(`/api/v2/configurations/${configId}`, updates),

  /**
   * Delete a configuration
   */
  delete: (configId: string) =>
    api.delete<void>(`/api/v2/configurations/${configId}`),
};
