import { api } from './client';
import type { AlertRule, AlertList, CreateAlertRequest, Notification } from '@/types/alert';

export interface UpdateAlertRequest {
  thresholdValue?: number;
  thresholdDirection?: 'above' | 'below';
  isEnabled?: boolean;
}

export const alertsApi = {
  /**
   * List all alerts for the current user
   */
  list: () =>
    api.get<AlertList>('/api/v2/alerts'),

  /**
   * List alerts for a specific configuration
   */
  listByConfig: (configId: string) =>
    api.get<AlertList>(`/api/v2/configurations/${configId}/alerts`),

  /**
   * Get a single alert by ID
   */
  get: (alertId: string) =>
    api.get<AlertRule>(`/api/v2/alerts/${alertId}`),

  /**
   * Create a new alert
   */
  create: (alert: CreateAlertRequest) =>
    api.post<AlertRule>('/api/v2/alerts', alert),

  /**
   * Update an existing alert
   */
  update: (alertId: string, updates: UpdateAlertRequest) =>
    api.patch<AlertRule>(`/api/v2/alerts/${alertId}`, updates),

  /**
   * Delete an alert
   */
  delete: (alertId: string) =>
    api.delete<void>(`/api/v2/alerts/${alertId}`),

  /**
   * Get notification history
   */
  getNotifications: (limit?: number) =>
    api.get<Notification[]>('/api/v2/notifications', { params: { limit } }),
};
