import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { configsApi } from '@/lib/api/configs';
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
const mockPost = api.post as unknown as ReturnType<typeof vi.fn>;
const mockPatch = api.patch as unknown as ReturnType<typeof vi.fn>;

// Raw backend shape is snake_case; the mapper must produce camelCase.
const rawConfig = {
  config_id: 'cfg-123',
  name: 'Tech Giants',
  tickers: [{ symbol: 'AAPL', name: 'Apple Inc', exchange: 'NASDAQ' }],
  timeframe_days: 30,
  include_extended_hours: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
};

describe('configsApi mapping (M1 WI-5)', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.resetAllMocks());

  describe('list', () => {
    it('maps snake_case list response to camelCase (config_id -> configId)', async () => {
      mockGet.mockResolvedValueOnce({
        configurations: [rawConfig],
        max_allowed: 5,
      });

      const result = await configsApi.list();

      expect(result.maxAllowed).toBe(5);
      const cfg = result.configurations[0];
      // The bug: these were undefined before the mapper existed.
      expect(cfg.configId).toBe('cfg-123');
      expect(cfg.updatedAt).toBe('2026-01-02T00:00:00Z');
      expect(cfg.timeframeDays).toBe(30);
      expect(cfg.includeExtendedHours).toBe(true);
      expect(cfg.tickers[0].symbol).toBe('AAPL');
    });

    it('tolerates a missing configurations array', async () => {
      mockGet.mockResolvedValueOnce({ max_allowed: 2 });
      const result = await configsApi.list();
      expect(result.configurations).toEqual([]);
      expect(result.maxAllowed).toBe(2);
    });
  });

  describe('get', () => {
    it('maps a single snake_case config to camelCase', async () => {
      mockGet.mockResolvedValueOnce(rawConfig);
      const cfg = await configsApi.get('cfg-123');
      expect(cfg.configId).toBe('cfg-123');
      expect(cfg.createdAt).toBe('2026-01-01T00:00:00Z');
    });
  });

  describe('create', () => {
    it('sends a snake_case body and maps the snake_case response', async () => {
      mockPost.mockResolvedValueOnce(rawConfig);

      const cfg = await configsApi.create({
        name: 'Tech Giants',
        tickers: ['AAPL'],
        timeframeDays: 30,
        includeExtendedHours: true,
      });

      // Request body must be snake_case (backend ignored camelCase -> defaults).
      const [, body] = mockPost.mock.calls[0];
      expect(body).toEqual({
        name: 'Tech Giants',
        tickers: ['AAPL'],
        timeframe_days: 30,
        include_extended_hours: true,
      });
      // Response mapped.
      expect(cfg.configId).toBe('cfg-123');
    });
  });

  describe('update', () => {
    it('sends only the provided fields in snake_case', async () => {
      mockPatch.mockResolvedValueOnce(rawConfig);

      await configsApi.update('cfg-123', { timeframeDays: 7 });

      const [, body] = mockPatch.mock.calls[0];
      expect(body).toEqual({ timeframe_days: 7 });
    });
  });
});
