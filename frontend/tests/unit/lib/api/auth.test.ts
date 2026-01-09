import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { authApi } from '@/lib/api/auth';
import { api } from '@/lib/api/client';

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

describe('authApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('exchangeOAuthCode', () => {
    it('should map successful OAuth response with federation fields', async () => {
      const mockBackendResponse = {
        status: 'authenticated',
        email_masked: 'j***@example.com',
        auth_type: 'google',
        tokens: {
          id_token: 'mock-id-token',
          access_token: 'mock-access-token',
          expires_in: 3600,
        },
        merged_anonymous_data: false,
        is_new_user: true,
        conflict: false,
        existing_provider: null,
        message: null,
        error: null,
        // Feature 1176: Federation fields
        role: 'free',
        verification: 'verified',
        linked_providers: ['google'],
        last_provider_used: 'google',
      };

      vi.mocked(api.post).mockResolvedValue(mockBackendResponse);

      const result = await authApi.exchangeOAuthCode('google', 'mock-code');

      expect(api.post).toHaveBeenCalledWith('/api/v2/auth/oauth/callback', {
        provider: 'google',
        code: 'mock-code',
      });

      // Verify federation fields are mapped correctly
      expect(result.user.role).toBe('free');
      expect(result.user.verification).toBe('verified');
      expect(result.user.linkedProviders).toEqual(['google']);
      expect(result.user.lastProviderUsed).toBe('google');

      // Verify other fields
      expect(result.user.authType).toBe('google');
      expect(result.user.email).toBe('j***@example.com');
      expect(result.tokens.idToken).toBe('mock-id-token');
      expect(result.tokens.accessToken).toBe('mock-access-token');
      expect(result.tokens.expiresIn).toBe(3600);
    });

    it('should use default federation values when not provided', async () => {
      const mockBackendResponse = {
        status: 'authenticated',
        email_masked: null,
        auth_type: null,
        tokens: {
          id_token: 'mock-id-token',
          access_token: 'mock-access-token',
          expires_in: 3600,
        },
        merged_anonymous_data: false,
        is_new_user: false,
        conflict: false,
        existing_provider: null,
        message: null,
        error: null,
        // Minimal federation fields (using defaults)
        role: 'anonymous',
        verification: 'none',
        linked_providers: [],
        last_provider_used: null,
      };

      vi.mocked(api.post).mockResolvedValue(mockBackendResponse);

      const result = await authApi.exchangeOAuthCode('github', 'mock-code');

      expect(result.user.role).toBe('anonymous');
      expect(result.user.verification).toBe('none');
      expect(result.user.linkedProviders).toEqual([]);
      expect(result.user.lastProviderUsed).toBeUndefined();
      expect(result.user.authType).toBe('anonymous');
    });

    it('should throw error on OAuth error response', async () => {
      const mockErrorResponse = {
        status: 'error',
        email_masked: null,
        auth_type: null,
        tokens: null,
        merged_anonymous_data: false,
        is_new_user: false,
        conflict: false,
        existing_provider: null,
        message: null,
        error: 'Invalid authorization code',
        role: 'anonymous',
        verification: 'none',
        linked_providers: [],
        last_provider_used: null,
      };

      vi.mocked(api.post).mockResolvedValue(mockErrorResponse);

      await expect(authApi.exchangeOAuthCode('google', 'invalid-code')).rejects.toThrow(
        'Invalid authorization code'
      );
    });

    it('should throw error on OAuth conflict response', async () => {
      const mockConflictResponse = {
        status: 'conflict',
        email_masked: 'j***@example.com',
        auth_type: null,
        tokens: null,
        merged_anonymous_data: false,
        is_new_user: false,
        conflict: true,
        existing_provider: 'google',
        message: 'An account with this email exists via google',
        error: null,
        role: 'anonymous',
        verification: 'none',
        linked_providers: [],
        last_provider_used: null,
      };

      vi.mocked(api.post).mockResolvedValue(mockConflictResponse);

      await expect(authApi.exchangeOAuthCode('github', 'mock-code')).rejects.toThrow(
        'An account with this email exists via google'
      );
    });

    it('should map GitHub OAuth response correctly', async () => {
      const mockBackendResponse = {
        status: 'authenticated',
        email_masked: 'u***@github.com',
        auth_type: 'github',
        tokens: {
          id_token: 'github-id-token',
          access_token: 'github-access-token',
          expires_in: 7200,
        },
        merged_anonymous_data: true,
        is_new_user: false,
        conflict: false,
        existing_provider: null,
        message: null,
        error: null,
        role: 'free',
        verification: 'verified',
        linked_providers: ['google', 'github'],
        last_provider_used: 'github',
      };

      vi.mocked(api.post).mockResolvedValue(mockBackendResponse);

      const result = await authApi.exchangeOAuthCode('github', 'github-code');

      expect(result.user.authType).toBe('github');
      expect(result.user.linkedProviders).toEqual(['google', 'github']);
      expect(result.user.lastProviderUsed).toBe('github');
    });
  });
});
