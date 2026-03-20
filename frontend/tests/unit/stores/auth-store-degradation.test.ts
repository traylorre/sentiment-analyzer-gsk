import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAuthStore } from '@/stores/auth-store';

// Mock API client setters and emitErrorEvent
const mockEmitErrorEvent = vi.fn();
vi.mock('@/lib/api/client', () => ({
  setUserId: vi.fn(),
  setAccessToken: vi.fn(),
  emitErrorEvent: (...args: unknown[]) => mockEmitErrorEvent(...args),
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

// Mock authApi - refreshToken is the key method for degradation tests
const mockRefreshToken = vi.fn();
vi.mock('@/lib/api/auth', () => ({
  authApi: {
    createAnonymousSession: vi.fn(),
    requestMagicLink: vi.fn(),
    verifyMagicLink: vi.fn(),
    signOut: vi.fn(),
    getOAuthUrls: vi.fn(),
    exchangeOAuthCode: vi.fn(),
    refreshToken: () => mockRefreshToken(),
    getProfile: vi.fn(),
  },
}));

/**
 * Helper: set up authenticated state with a refresh token so
 * refreshSession() actually attempts the API call.
 */
function setupAuthenticatedUser() {
  const store = useAuthStore.getState();
  store.setUser({
    userId: 'user-degradation-test',
    authType: 'email',
    createdAt: '2024-01-15T10:00:00Z',
    configurationCount: 0,
    alertCount: 0,
    emailNotificationsEnabled: true,
  });
  store.setTokens({
    idToken: 'id-token',
    accessToken: 'access-token',
    refreshToken: 'refresh-token',
    expiresIn: 3600,
  });
}

describe('Auth Store Degradation Tracking (User Story 3)', () => {
  beforeEach(() => {
    useAuthStore.getState().reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial degradation state', () => {
    it('should have refreshFailureCount=0 and sessionDegraded=false initially', () => {
      const state = useAuthStore.getState();
      expect(state.refreshFailureCount).toBe(0);
      expect(state.sessionDegraded).toBe(false);
    });
  });

  describe('refreshFailureCount increments on refreshSession failure', () => {
    it('should increment refreshFailureCount by 1 on each failure', async () => {
      setupAuthenticatedUser();
      mockRefreshToken.mockRejectedValue(new Error('Token expired'));

      await useAuthStore.getState().refreshSession();
      expect(useAuthStore.getState().refreshFailureCount).toBe(1);

      await useAuthStore.getState().refreshSession();
      expect(useAuthStore.getState().refreshFailureCount).toBe(2);
    });
  });

  describe('sessionDegraded becomes true at count 2', () => {
    it('should set sessionDegraded=true when refreshFailureCount reaches 2', async () => {
      setupAuthenticatedUser();
      mockRefreshToken.mockRejectedValue(new Error('Token expired'));

      // First failure: not yet degraded
      await useAuthStore.getState().refreshSession();
      expect(useAuthStore.getState().sessionDegraded).toBe(false);
      expect(useAuthStore.getState().refreshFailureCount).toBe(1);

      // Second failure: now degraded
      await useAuthStore.getState().refreshSession();
      expect(useAuthStore.getState().sessionDegraded).toBe(true);
      expect(useAuthStore.getState().refreshFailureCount).toBe(2);
    });

    it('should remain degraded on subsequent failures beyond 2', async () => {
      setupAuthenticatedUser();
      mockRefreshToken.mockRejectedValue(new Error('Token expired'));

      await useAuthStore.getState().refreshSession();
      await useAuthStore.getState().refreshSession();
      await useAuthStore.getState().refreshSession();

      expect(useAuthStore.getState().sessionDegraded).toBe(true);
      expect(useAuthStore.getState().refreshFailureCount).toBe(3);
    });
  });

  describe('successful refresh resets degradation state', () => {
    it('should reset refreshFailureCount to 0 and sessionDegraded to false on success', async () => {
      setupAuthenticatedUser();

      // Fail twice to enter degraded state
      mockRefreshToken.mockRejectedValue(new Error('Token expired'));
      await useAuthStore.getState().refreshSession();
      await useAuthStore.getState().refreshSession();

      expect(useAuthStore.getState().sessionDegraded).toBe(true);
      expect(useAuthStore.getState().refreshFailureCount).toBe(2);

      // Succeed: should reset
      mockRefreshToken.mockResolvedValue({
        accessToken: 'new-access-token',
        idToken: 'new-id-token',
        expiresIn: 3600,
      });
      await useAuthStore.getState().refreshSession();

      expect(useAuthStore.getState().refreshFailureCount).toBe(0);
      expect(useAuthStore.getState().sessionDegraded).toBe(false);
    });
  });

  describe('emitErrorEvent called when sessionDegraded transitions to true', () => {
    it('should call emitErrorEvent with auth_degradation_warning when count reaches 2', async () => {
      setupAuthenticatedUser();
      mockRefreshToken.mockRejectedValue(new Error('Token expired'));

      // First failure: no emit yet
      await useAuthStore.getState().refreshSession();
      expect(mockEmitErrorEvent).not.toHaveBeenCalled();

      // Second failure: should emit
      await useAuthStore.getState().refreshSession();
      expect(mockEmitErrorEvent).toHaveBeenCalledWith(
        'auth_degradation_warning',
        { failureCount: 2 }
      );
    });

    it('should continue emitting on further failures', async () => {
      setupAuthenticatedUser();
      mockRefreshToken.mockRejectedValue(new Error('Token expired'));

      await useAuthStore.getState().refreshSession();
      await useAuthStore.getState().refreshSession();
      await useAuthStore.getState().refreshSession();

      // Called on count=2 and count=3
      expect(mockEmitErrorEvent).toHaveBeenCalledTimes(2);
      expect(mockEmitErrorEvent).toHaveBeenCalledWith(
        'auth_degradation_warning',
        { failureCount: 3 }
      );
    });
  });

  describe('no-op when no refresh token', () => {
    it('should not attempt refresh when tokens have no refreshToken', async () => {
      const store = useAuthStore.getState();
      store.setUser({
        userId: 'anon-user',
        authType: 'anonymous',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: false,
      });
      // Set tokens with empty refreshToken (anonymous pattern)
      store.setTokens({
        idToken: '',
        accessToken: 'anon-token',
        refreshToken: '',
        expiresIn: 0,
      });

      await useAuthStore.getState().refreshSession();

      // Should not have called the API at all
      expect(mockRefreshToken).not.toHaveBeenCalled();
      expect(useAuthStore.getState().refreshFailureCount).toBe(0);
    });
  });
});
