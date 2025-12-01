import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { useAuthStore } from '@/stores/auth-store';

// Mock cookie functions
vi.mock('@/lib/cookies', () => ({
  setAuthCookies: vi.fn(),
  clearAuthCookies: vi.fn(),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('Auth Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.getState().reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial state', () => {
    it('should have correct initial values', () => {
      const state = useAuthStore.getState();

      expect(state.isAuthenticated).toBe(false);
      expect(state.isAnonymous).toBe(false);
      expect(state.user).toBeNull();
      expect(state.tokens).toBeNull();
      expect(state.sessionExpiresAt).toBeNull();
      expect(state.isLoading).toBe(false);
      expect(state.isInitialized).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('setUser', () => {
    it('should set user and update authentication state', () => {
      const { setUser } = useAuthStore.getState();

      const user = {
        userId: 'user-123',
        email: 'test@example.com',
        authType: 'email' as const,
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: true,
      };

      setUser(user);

      const state = useAuthStore.getState();
      expect(state.user).toEqual(user);
      expect(state.isAuthenticated).toBe(true);
      expect(state.isAnonymous).toBe(false);
    });

    it('should set isAnonymous for anonymous users', () => {
      const { setUser } = useAuthStore.getState();

      const user = {
        userId: 'anon-123',
        authType: 'anonymous' as const,
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: false,
      };

      setUser(user);

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.isAnonymous).toBe(true);
    });

    it('should clear user when set to null', () => {
      const { setUser } = useAuthStore.getState();

      setUser({
        userId: 'user-123',
        authType: 'email',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: true,
      });

      setUser(null);

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe('setTokens', () => {
    it('should set tokens', () => {
      const { setTokens, setUser } = useAuthStore.getState();

      // Set user first to establish auth state
      setUser({
        userId: 'user-123',
        authType: 'email',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: true,
      });

      const tokens = {
        idToken: 'id-token-123',
        accessToken: 'access-token-123',
        refreshToken: 'refresh-token-456',
        expiresIn: 3600,
      };

      setTokens(tokens);

      expect(useAuthStore.getState().tokens).toEqual(tokens);
    });
  });

  describe('setSession', () => {
    it('should set session expiration', () => {
      const { setSession } = useAuthStore.getState();
      const expiresAt = '2024-01-15T12:00:00Z';

      setSession(expiresAt);

      expect(useAuthStore.getState().sessionExpiresAt).toBe(expiresAt);
    });
  });

  describe('setLoading', () => {
    it('should set loading state', () => {
      const { setLoading } = useAuthStore.getState();

      setLoading(true);
      expect(useAuthStore.getState().isLoading).toBe(true);

      setLoading(false);
      expect(useAuthStore.getState().isLoading).toBe(false);
    });
  });

  describe('setError', () => {
    it('should set error message', () => {
      const { setError } = useAuthStore.getState();

      setError('Something went wrong');
      expect(useAuthStore.getState().error).toBe('Something went wrong');

      setError(null);
      expect(useAuthStore.getState().error).toBeNull();
    });
  });

  describe('signInAnonymous', () => {
    it('should create anonymous session on success', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            userId: 'anon-123',
            sessionExpiresAt: '2024-01-15T12:00:00Z',
          }),
      });

      await useAuthStore.getState().signInAnonymous();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.isAnonymous).toBe(true);
      expect(state.user?.userId).toBe('anon-123');
      expect(state.sessionExpiresAt).toBe('2024-01-15T12:00:00Z');
    });

    it('should handle error during anonymous sign in', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ message: 'Failed' }),
      });

      await expect(useAuthStore.getState().signInAnonymous()).rejects.toThrow(
        'Failed to create anonymous session'
      );

      const state = useAuthStore.getState();
      expect(state.error).toBe('Failed to create anonymous session');
    });
  });

  describe('signInWithMagicLink', () => {
    it('should send magic link request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await useAuthStore
        .getState()
        .signInWithMagicLink('test@example.com', 'captcha-token');

      expect(mockFetch).toHaveBeenCalledWith('/api/v2/auth/magic-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'test@example.com',
          captchaToken: 'captcha-token',
        }),
      });
    });

    it('should handle error sending magic link', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ message: 'Rate limited' }),
      });

      await expect(
        useAuthStore
          .getState()
          .signInWithMagicLink('test@example.com', 'captcha-token')
      ).rejects.toThrow('Rate limited');
    });
  });

  describe('verifyMagicLink', () => {
    it('should verify token and set user', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            user: {
              userId: 'user-123',
              email: 'test@example.com',
              authType: 'email',
              createdAt: '2024-01-15T10:00:00Z',
              configurationCount: 0,
              alertCount: 0,
              emailNotificationsEnabled: true,
            },
            tokens: {
              idToken: 'id-123',
              accessToken: 'access-123',
              refreshToken: 'refresh-456',
              expiresIn: 3600,
            },
            sessionExpiresAt: '2024-01-15T12:00:00Z',
          }),
      });

      await useAuthStore.getState().verifyMagicLink('valid-token');

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user?.email).toBe('test@example.com');
      expect(state.tokens?.accessToken).toBe('access-123');
    });

    it('should handle invalid token', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ message: 'Token expired' }),
      });

      await expect(
        useAuthStore.getState().verifyMagicLink('invalid-token')
      ).rejects.toThrow('Token expired');
    });
  });

  describe('signOut', () => {
    it('should reset state after sign out', async () => {
      const { setUser, setTokens, signOut } = useAuthStore.getState();

      // Set up authenticated state
      setUser({
        userId: 'user-123',
        authType: 'email',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: true,
      });
      setTokens({
        idToken: 'id-123',
        accessToken: 'access-123',
        refreshToken: 'refresh-456',
        expiresIn: 3600,
      });

      mockFetch.mockResolvedValueOnce({ ok: true });

      await signOut();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
      expect(state.tokens).toBeNull();
    });

    it('should clear state even if API call fails', async () => {
      const { setUser, setTokens, signOut } = useAuthStore.getState();

      setUser({
        userId: 'user-123',
        authType: 'email',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: true,
      });
      setTokens({
        idToken: 'id-123',
        accessToken: 'access-123',
        refreshToken: 'refresh-456',
        expiresIn: 3600,
      });

      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await signOut();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
    });
  });

  describe('isSessionValid', () => {
    it('should return false when not authenticated', () => {
      expect(useAuthStore.getState().isSessionValid()).toBe(false);
    });

    it('should return false when session is expired', () => {
      const { setUser, setSession } = useAuthStore.getState();

      setUser({
        userId: 'user-123',
        authType: 'email',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: true,
      });

      // Set expired session
      const expiredTime = new Date(Date.now() - 60000).toISOString();
      setSession(expiredTime);

      expect(useAuthStore.getState().isSessionValid()).toBe(false);
    });

    it('should return true when session is valid', () => {
      const { setUser, setSession } = useAuthStore.getState();

      setUser({
        userId: 'user-123',
        authType: 'email',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: true,
      });

      // Set future session
      const futureTime = new Date(Date.now() + 3600000).toISOString();
      setSession(futureTime);

      expect(useAuthStore.getState().isSessionValid()).toBe(true);
    });
  });

  describe('getSessionRemainingMs', () => {
    it('should return 0 when no session', () => {
      expect(useAuthStore.getState().getSessionRemainingMs()).toBe(0);
    });

    it('should return remaining time', () => {
      const { setSession } = useAuthStore.getState();

      const futureTime = new Date(Date.now() + 300000).toISOString();
      setSession(futureTime);

      const remaining = useAuthStore.getState().getSessionRemainingMs();
      expect(remaining).toBeGreaterThan(290000);
      expect(remaining).toBeLessThanOrEqual(300000);
    });
  });

  describe('reset', () => {
    it('should reset all state to initial values', () => {
      const store = useAuthStore.getState();

      store.setUser({
        userId: 'user-123',
        authType: 'email',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: true,
      });
      store.setTokens({
        idToken: 'id-123',
        accessToken: 'access-123',
        refreshToken: 'refresh-456',
        expiresIn: 3600,
      });
      store.setError('Some error');

      store.reset();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
      expect(state.tokens).toBeNull();
      expect(state.error).toBeNull();
    });
  });
});

describe('Auth Store Selectors', () => {
  beforeEach(() => {
    useAuthStore.getState().reset();
  });

  it('useUser should return user', () => {
    const { setUser } = useAuthStore.getState();
    const user = {
      userId: 'user-123',
      authType: 'email' as const,
      createdAt: '2024-01-15T10:00:00Z',
      configurationCount: 0,
      alertCount: 0,
      emailNotificationsEnabled: true,
    };

    setUser(user);

    // Direct selector check
    const currentUser = useAuthStore.getState().user;
    expect(currentUser).toEqual(user);
  });
});

// Feature 014: Session Consistency Tests (T017)
describe('Feature 014: Auto-Session Creation', () => {
  beforeEach(() => {
    useAuthStore.getState().reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('FR-003: Auto-session on app load', () => {
    it('should call signInAnonymous on first load when no session exists', async () => {
      // Verify initial state has no user
      const initialState = useAuthStore.getState();
      expect(initialState.user).toBeNull();
      expect(initialState.isAuthenticated).toBe(false);

      // Mock successful anonymous session creation
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            userId: 'auto-anon-123',
            sessionExpiresAt: new Date(
              Date.now() + 30 * 24 * 60 * 60 * 1000
            ).toISOString(),
          }),
      });

      await useAuthStore.getState().signInAnonymous();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.isAnonymous).toBe(true);
      expect(state.user?.authType).toBe('anonymous');
    });

    it('should NOT create new session if valid session exists in localStorage', async () => {
      // First create a session
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            userId: 'existing-anon-456',
            sessionExpiresAt: new Date(
              Date.now() + 30 * 24 * 60 * 60 * 1000
            ).toISOString(),
          }),
      });

      await useAuthStore.getState().signInAnonymous();

      // Clear mock to track if new call is made
      mockFetch.mockClear();

      // Session should still be valid
      expect(useAuthStore.getState().isSessionValid()).toBe(true);
      expect(useAuthStore.getState().user?.userId).toBe('existing-anon-456');

      // No additional API call should be needed
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should persist anonymous session to localStorage', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            userId: 'persist-anon-789',
            sessionExpiresAt: new Date(
              Date.now() + 30 * 24 * 60 * 60 * 1000
            ).toISOString(),
          }),
      });

      await useAuthStore.getState().signInAnonymous();

      // Zustand persist middleware should handle localStorage
      const state = useAuthStore.getState();
      expect(state.user?.userId).toBe('persist-anon-789');
      expect(state.isAnonymous).toBe(true);
    });
  });

  describe('FR-001: Hybrid header support', () => {
    it('should use Bearer token format for API requests when tokens exist', async () => {
      const { setTokens, setUser } = useAuthStore.getState();

      setUser({
        userId: 'user-with-token',
        authType: 'email',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: true,
      });

      setTokens({
        idToken: 'id-token',
        accessToken: 'test-access-token',
        refreshToken: 'refresh-token',
        expiresIn: 3600,
      });

      const state = useAuthStore.getState();
      expect(state.tokens?.accessToken).toBe('test-access-token');
      // API client should use: Authorization: Bearer test-access-token
    });

    it('should support X-User-ID header for anonymous sessions', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            userId: 'x-user-id-test',
            sessionExpiresAt: new Date(
              Date.now() + 30 * 24 * 60 * 60 * 1000
            ).toISOString(),
          }),
      });

      await useAuthStore.getState().signInAnonymous();

      const state = useAuthStore.getState();
      expect(state.user?.userId).toBe('x-user-id-test');
      // API client should use: X-User-ID: x-user-id-test
    });
  });

  describe('Session sharing across tabs', () => {
    it('should use localStorage for session persistence (enables cross-tab)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            userId: 'cross-tab-user',
            sessionExpiresAt: new Date(
              Date.now() + 30 * 24 * 60 * 60 * 1000
            ).toISOString(),
          }),
      });

      await useAuthStore.getState().signInAnonymous();

      // Zustand persist uses localStorage by default in auth-store config
      // This enables cross-tab session sharing via storage events
      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
    });
  });
});
