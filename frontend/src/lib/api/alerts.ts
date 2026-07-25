import { api } from './client';
import type { AlertRule, AlertList, CreateAlertRequest, Notification } from '@/types/alert';

// Feature 1387: same latent defect class as the config-delete bug (M1 WI-5,
// see configs.ts). The backend speaks snake_case (alert_id, is_enabled,
// threshold_value) and client.ts does a bare response.json() with no transform,
// but alertsApi cast the raw response straight to the camelCase AlertRule type.
// So `alertId`/`isEnabled`/`thresholdValue` were ALWAYS undefined: the delete
// dialog (gated on `!!deletingAlertId`) never opened, the toggle PATCHed
// /alerts/undefined with a body the backend ignores, and a noisy alert kept
// burning the daily email quota because neither user lever could stop it.
// Fix: map explicitly, both directions — mirrors configs.ts.
//
// DEFERRED (full remap board card): `create` and `getNotifications` still pass
// through unmapped. This minimal mitigation covers only the read + update paths
// that restore delete/disable.

/** Raw snake_case alert as returned by the backend (AlertResponse). */
interface RawAlert {
  alert_id: string;
  config_id: string;
  ticker: string;
  alert_type: AlertRule['alertType'];
  threshold_value: number;
  threshold_direction: AlertRule['thresholdDirection'];
  is_enabled: boolean;
  last_triggered_at: string | null;
  trigger_count: number;
  created_at: string;
}

/** Raw snake_case alert list envelope (AlertListResponse). */
interface RawAlertList {
  alerts: RawAlert[];
  total: number;
  daily_email_quota: {
    used: number;
    limit: number;
    remaining?: number;
    resets_at: string;
  };
}

function mapAlert(raw: RawAlert): AlertRule {
  return {
    alertId: raw.alert_id,
    configId: raw.config_id,
    ticker: raw.ticker,
    alertType: raw.alert_type,
    thresholdValue: raw.threshold_value,
    thresholdDirection: raw.threshold_direction,
    isEnabled: raw.is_enabled,
    lastTriggeredAt: raw.last_triggered_at ?? null,
    triggerCount: raw.trigger_count,
    createdAt: raw.created_at,
  };
}

function mapAlertList(raw: RawAlertList): AlertList {
  const quota = raw.daily_email_quota;
  return {
    alerts: (raw.alerts ?? []).map(mapAlert),
    total: raw.total,
    dailyEmailQuota: quota
      ? {
          used: quota.used,
          limit: quota.limit,
          resetsAt: quota.resets_at,
        }
      : { used: 0, limit: 10, resetsAt: '' },
  };
}

/**
 * Map a camelCase update request to the snake_case body the backend expects.
 * Only-defined-keys, so an untouched field is never sent. Without this the
 * camelCase `{ isEnabled }` body is ignored by AlertUpdateRequest (accepts
 * `is_enabled`/alias `enabled`, not `isEnabled`) and the disable never persists.
 */
function toUpdateBody(req: UpdateAlertRequest): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (req.thresholdValue !== undefined) body.threshold_value = req.thresholdValue;
  if (req.thresholdDirection !== undefined) {
    body.threshold_direction = req.thresholdDirection;
  }
  if (req.isEnabled !== undefined) body.is_enabled = req.isEnabled;
  return body;
}

export interface UpdateAlertRequest {
  thresholdValue?: number;
  thresholdDirection?: 'above' | 'below';
  isEnabled?: boolean;
}

export const alertsApi = {
  /**
   * List all alerts for the current user
   */
  list: async (): Promise<AlertList> => {
    const raw = await api.get<RawAlertList>('/api/v2/alerts');
    return mapAlertList(raw);
  },

  /**
   * List alerts for a specific configuration
   */
  listByConfig: async (configId: string): Promise<AlertList> => {
    const raw = await api.get<RawAlertList>(
      `/api/v2/configurations/${configId}/alerts`
    );
    return mapAlertList(raw);
  },

  /**
   * Get a single alert by ID
   */
  get: async (alertId: string): Promise<AlertRule> => {
    const raw = await api.get<RawAlert>(`/api/v2/alerts/${alertId}`);
    return mapAlert(raw);
  },

  /**
   * Create a new alert
   *
   * DEFERRED: still passes the camelCase request through unmapped (full-remap
   * board card).
   */
  create: (alert: CreateAlertRequest) =>
    api.post<AlertRule>('/api/v2/alerts', alert),

  /**
   * Update an existing alert
   */
  update: async (
    alertId: string,
    updates: UpdateAlertRequest
  ): Promise<AlertRule> => {
    const raw = await api.patch<RawAlert>(
      `/api/v2/alerts/${alertId}`,
      toUpdateBody(updates)
    );
    return mapAlert(raw);
  },

  /**
   * Delete an alert
   */
  delete: (alertId: string) =>
    api.delete<void>(`/api/v2/alerts/${alertId}`),

  /**
   * Get notification history
   *
   * DEFERRED: response still passes through unmapped (full-remap board card).
   */
  getNotifications: (limit?: number) =>
    api.get<Notification[]>('/api/v2/notifications', { params: { limit } }),
};
