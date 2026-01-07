import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { SessionProvider } from '@/components/providers/session-provider';
import { useAuthStore } from '@/stores/auth-store';

// Mock cookie functions
vi.mock('@/lib/cookies', () => ({
  setAuthCookies: vi.fn(),
  clearAuthCookies: vi.fn(),
}));

// Mock API client setters (Feature 014: Sync userId/accessToken with API client)
vi.mock('@/lib/api/client', () => ({
  setUserId: vi.fn(),
  setAccessToken: vi.fn(),
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

// Mock authApi
const mockCreateAnonymousSession = vi.fn();

vi.mock('@/lib/api/auth', () => ({
  authApi: {
    createAnonymousSession: () => mockCreateAnonymousSession(),
    requestMagicLink: vi.fn(),
    verifyMagicLink: vi.fn(),
    signOut: vi.fn(),
    getOAuthUrls: vi.fn(),
    exchangeOAuthCode: vi.fn(),
    refreshToken: vi.fn(),
  },
}));

describe('SessionProvider', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.getState().reset();
    // Feature 1165: No hydration concept - memory-only store
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Feature 014: Automatic Session Initialization', () => {
    it('should show loading state initially', () => {
      // Feature 1165: Loading state shown until isInitialized is true

      render(
        <SessionProvider>
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

      expect(screen.getByText(/initializing session/i)).toBeInTheDocument();
      expect(screen.queryByTestId('content')).not.toBeInTheDocument();
    });

    it('should render children after session is initialized', async () => {
      mockCreateAnonymousSession.mockResolvedValueOnce({
        userId: 'test-user-123',
        authType: 'anonymous',
        createdAt: new Date().toISOString(),
        sessionExpiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      });

      render(
        <SessionProvider>
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('content')).toBeInTheDocument();
      });
    });

    it('should use custom loading component when provided', () => {
      // Feature 1165: Loading state shown until isInitialized is true

      render(
        <SessionProvider loadingComponent={<div>Custom Loading...</div>}>
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

      expect(screen.getByText('Custom Loading...')).toBeInTheDocument();
    });

    it('should render children immediately when showLoading=false', async () => {
      mockCreateAnonymousSession.mockResolvedValueOnce({
        userId: 'test-user-123',
        authType: 'anonymous',
        createdAt: new Date().toISOString(),
        sessionExpiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      });

      render(
        <SessionProvider showLoading={false}>
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

      // With showLoading=false, children render immediately
      expect(screen.getByTestId('content')).toBeInTheDocument();
    });

    it('should not create new session if valid session exists', async () => {
      // Pre-set a valid session in the store
      const { setUser, setSession, setInitialized } = useAuthStore.getState();

      setUser({
        userId: 'existing-user-456',
        authType: 'anonymous',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: false,
      });
      setSession(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString());
      setInitialized(true);

      render(
        <SessionProvider>
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

      // Should render immediately without API call
      expect(screen.getByTestId('content')).toBeInTheDocument();
      expect(mockCreateAnonymousSession).not.toHaveBeenCalled();
    });

    it('should show custom error component on session init failure', async () => {
      mockCreateAnonymousSession.mockRejectedValueOnce(new Error('Server error'));

      render(
        <SessionProvider
          errorComponent={<div data-testid="error">Session Error</div>}
        >
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('error')).toBeInTheDocument();
      });
    });
  });

  describe('Cross-tab session sharing', () => {
    it('should reuse session from localStorage on mount', async () => {
      // Simulate zustand persist restoring state
      const { setUser, setSession, setInitialized } = useAuthStore.getState();

      setUser({
        userId: 'restored-user-789',
        authType: 'anonymous',
        createdAt: '2024-01-15T10:00:00Z',
        configurationCount: 0,
        alertCount: 0,
        emailNotificationsEnabled: false,
      });
      setSession(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString());
      setInitialized(true);

      render(
        <SessionProvider>
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

      // Should not make API call - reuses localStorage session
      expect(mockCreateAnonymousSession).not.toHaveBeenCalled();
      expect(screen.getByTestId('content')).toBeInTheDocument();
    });
  });
});

describe('useSessionInit hook', () => {
  beforeEach(() => {
    useAuthStore.getState().reset();
    // Feature 1165: No hydration concept - memory-only store
    vi.clearAllMocks();
  });

  it('should call signInAnonymous when no session exists', async () => {
    mockCreateAnonymousSession.mockResolvedValueOnce({
      userId: 'new-anon-user',
      authType: 'anonymous',
      createdAt: new Date().toISOString(),
      sessionExpiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    });

    render(
      <SessionProvider>
        <div>Test</div>
      </SessionProvider>
    );

    await waitFor(() => {
      expect(mockCreateAnonymousSession).toHaveBeenCalled();
    });
  });

  it('should set isReady to true after successful initialization', async () => {
    mockCreateAnonymousSession.mockResolvedValueOnce({
      userId: 'ready-user',
      authType: 'anonymous',
      createdAt: new Date().toISOString(),
      sessionExpiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    });

    render(
      <SessionProvider>
        <div data-testid="content">Content</div>
      </SessionProvider>
    );

    await waitFor(() => {
      const state = useAuthStore.getState();
      expect(state.isInitialized).toBe(true);
      expect(state.isAuthenticated).toBe(true);
    });
  });
});
