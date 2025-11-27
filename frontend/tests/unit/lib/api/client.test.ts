import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api, ApiClientError, setAccessToken } from '@/lib/api/client';

describe('API Client', () => {
  beforeEach(() => {
    setAccessToken(null);
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('api.get', () => {
    it('should make a GET request with correct URL', async () => {
      const mockResponse = { data: 'test' };
      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const result = await api.get('/test');

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/test'),
        expect.objectContaining({ method: 'GET' })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should include query params in URL', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      } as Response);

      await api.get('/test', { params: { foo: 'bar', num: 123 } });

      expect(fetch).toHaveBeenCalledWith(
        expect.stringMatching(/foo=bar/),
        expect.any(Object)
      );
      expect(fetch).toHaveBeenCalledWith(
        expect.stringMatching(/num=123/),
        expect.any(Object)
      );
    });
  });

  describe('api.post', () => {
    it('should make a POST request with JSON body', async () => {
      const mockResponse = { id: '123' };
      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        status: 201,
        json: () => Promise.resolve(mockResponse),
      } as Response);

      const body = { name: 'Test' };
      const result = await api.post('/test', body);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/test'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(body),
        })
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe('authentication', () => {
    it('should include Authorization header when token is set', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      } as Response);

      setAccessToken('test-token');
      await api.get('/test');

      const [, options] = vi.mocked(fetch).mock.calls[0];
      const headers = options?.headers as Headers;
      expect(headers.get('Authorization')).toBe('Bearer test-token');
    });

    it('should not include Authorization header when no token', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      } as Response);

      setAccessToken(null);
      await api.get('/test');

      const [, options] = vi.mocked(fetch).mock.calls[0];
      const headers = options?.headers as Headers;
      expect(headers.get('Authorization')).toBeNull();
    });
  });

  describe('error handling', () => {
    it('should throw ApiClientError for non-ok responses', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 400,
        json: () =>
          Promise.resolve({
            code: 'VALIDATION_ERROR',
            message: 'Invalid input',
          }),
      } as Response);

      await expect(api.get('/test')).rejects.toThrow(ApiClientError);
    });

    it('should include error details in ApiClientError', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 404,
        json: () =>
          Promise.resolve({
            code: 'NOT_FOUND',
            message: 'Resource not found',
            details: { resource: 'config' },
          }),
      } as Response);

      try {
        await api.get('/test');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ApiClientError);
        const apiError = error as ApiClientError;
        expect(apiError.status).toBe(404);
        expect(apiError.code).toBe('NOT_FOUND');
        expect(apiError.message).toBe('Resource not found');
        expect(apiError.details).toEqual({ resource: 'config' });
      }
    });

    it('should handle non-JSON error responses', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.reject(new Error('Not JSON')),
      } as Response);

      try {
        await api.get('/test');
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ApiClientError);
        const apiError = error as ApiClientError;
        expect(apiError.status).toBe(500);
        expect(apiError.code).toBe('UNKNOWN_ERROR');
      }
    });
  });

  describe('204 No Content', () => {
    it('should return undefined for 204 responses', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        status: 204,
        json: () => Promise.reject(new Error('No content')),
      } as Response);

      const result = await api.delete('/test');

      expect(result).toBeUndefined();
    });
  });
});
