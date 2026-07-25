import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { alertsApi } from '@/lib/api/alerts';
import { api } from '@/lib/api/client';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockGet = api.get as unknown as ReturnType<typeof vi.fn>;
const mockPatch = api.patch as unknown as ReturnType<typeof vi.fn>;
const mockDelete = api.delete as unknown as ReturnType<typeof vi.fn>;

// Raw backend shape is snake_case; the mapper must produce camelCase.
const rawAlert = {
  alert_id: 'al-9',
  config_id: 'cfg-1',
  ticker: 'AAPL',
  alert_type: 'sentiment_threshold',
  threshold_value: 0.75,
  threshold_direction: 'above',
  is_enabled: true,
  last_triggered_at: null,
  trigger_count: 3,
  created_at: '2026-01-01T00:00:00Z',
};

describe('alertsApi mapping (Feature 1387)', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.resetAllMocks());

  describe('list', () => {
    it('maps snake_case list response to camelCase (alert_id -> alertId)', async () => {
      mockGet.mockResolvedValueOnce({
        alerts: [rawAlert],
        total: 1,
        daily_email_quota: { used: 2, limit: 10, remaining: 8, resets_at: '2026-01-02T00:00:00Z' },
      });

      const result = await alertsApi.list();

      expect(result.total).toBe(1);
      const alert = result.alerts[0];
      // The bug: these were undefined before the mapper existed.
      expect(alert.alertId).toBe('al-9');
      expect(alert.isEnabled).toBe(true);
      expect(alert.thresholdValue).toBe(0.75);
      expect(alert.thresholdDirection).toBe('above');
      expect(alert.alertType).toBe('sentiment_threshold');
      expect(alert.ticker).toBe('AAPL');
      expect(alert.configId).toBe('cfg-1');
      expect(alert.triggerCount).toBe(3);
      expect(alert.createdAt).toBe('2026-01-01T00:00:00Z');
      // null preserved as null (not undefined).
      expect(alert.lastTriggeredAt).toBeNull();
      // quota resets_at -> resetsAt.
      expect(result.dailyEmailQuota.resetsAt).toBe('2026-01-02T00:00:00Z');
      expect(result.dailyEmailQuota.used).toBe(2);
      expect(result.dailyEmailQuota.limit).toBe(10);
    });

    it('tolerates a missing alerts array', async () => {
      mockGet.mockResolvedValueOnce({ total: 0 });
      const result = await alertsApi.list();
      expect(result.alerts).toEqual([]);
    });

    it('supplies a safe quota default when the block is absent', async () => {
      mockGet.mockResolvedValueOnce({ alerts: [rawAlert], total: 1 });
      const result = await alertsApi.list();
      expect(result.dailyEmailQuota).toEqual({ used: 0, limit: 10, resetsAt: '' });
    });
  });

  describe('listByConfig', () => {
    it('maps the config-scoped list too', async () => {
      mockGet.mockResolvedValueOnce({
        alerts: [rawAlert],
        total: 1,
        daily_email_quota: { used: 0, limit: 10, resets_at: '' },
      });
      const result = await alertsApi.listByConfig('cfg-1');
      expect(result.alerts[0].alertId).toBe('al-9');
      expect(result.alerts[0].isEnabled).toBe(true);
    });
  });

  describe('get', () => {
    it('maps a single snake_case alert to camelCase', async () => {
      mockGet.mockResolvedValueOnce(rawAlert);
      const alert = await alertsApi.get('al-9');
      expect(alert.alertId).toBe('al-9');
      expect(alert.thresholdValue).toBe(0.75);
    });
  });

  describe('delete real-id guard', () => {
    it('after list, deletes the real id (never /alerts/undefined)', async () => {
      mockGet.mockResolvedValueOnce({
        alerts: [rawAlert],
        total: 1,
        daily_email_quota: { used: 0, limit: 10, resets_at: '' },
      });
      const result = await alertsApi.list();
      await alertsApi.delete(result.alerts[0].alertId);

      const [path] = mockDelete.mock.calls[0];
      expect(path).toBe('/api/v2/alerts/al-9');
      expect(path).not.toContain('undefined');
    });
  });

  describe('update disable', () => {
    it('sends a snake_case body { is_enabled: false } to the real id', async () => {
      mockPatch.mockResolvedValueOnce(rawAlert);

      await alertsApi.update('al-9', { isEnabled: false });

      const [path, body] = mockPatch.mock.calls[0];
      expect(path).toBe('/api/v2/alerts/al-9');
      // Body must be snake_case; backend ignores camelCase { isEnabled }.
      expect(body).toEqual({ is_enabled: false });
    });

    it('sends only the provided fields in snake_case', async () => {
      mockPatch.mockResolvedValueOnce(rawAlert);
      await alertsApi.update('al-9', { thresholdValue: 0.9 });
      const [, body] = mockPatch.mock.calls[0];
      expect(body).toEqual({ threshold_value: 0.9 });
    });
  });
});
