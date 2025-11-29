import { api } from './client';

export interface NotificationPreferences {
  emailEnabled: boolean;
  digestEnabled: boolean;
  digestTime: string;
  timezone: string;
}

export interface UpdateNotificationPreferencesRequest {
  email_enabled?: boolean;
  digest_enabled?: boolean;
  digest_time?: string;
}

export interface DigestSettings {
  enabled: boolean;
  time: string;
  timezone: string;
  includeAllConfigs: boolean;
  configIds: string[];
}

export interface UpdateDigestSettingsRequest {
  enabled?: boolean;
  time?: string;
  timezone?: string;
  include_all_configs?: boolean;
  config_ids?: string[];
}

export const notificationsApi = {
  /**
   * Get notification preferences
   */
  getPreferences: () =>
    api.get<NotificationPreferences>('/api/v2/notifications/preferences'),

  /**
   * Update notification preferences
   */
  updatePreferences: (updates: UpdateNotificationPreferencesRequest) =>
    api.patch<NotificationPreferences>('/api/v2/notifications/preferences', updates),

  /**
   * Disable all notifications
   */
  disableAll: () =>
    api.post<void>('/api/v2/notifications/disable-all'),

  /**
   * Resubscribe to notifications
   */
  resubscribe: () =>
    api.post<void>('/api/v2/notifications/resubscribe'),

  /**
   * Get digest settings
   */
  getDigestSettings: () =>
    api.get<DigestSettings>('/api/v2/notifications/digest'),

  /**
   * Update digest settings
   */
  updateDigestSettings: (updates: UpdateDigestSettingsRequest) =>
    api.patch<DigestSettings>('/api/v2/notifications/digest', updates),

  /**
   * Trigger test digest email
   */
  triggerTestDigest: () =>
    api.post<void>('/api/v2/notifications/digest/test'),
};
