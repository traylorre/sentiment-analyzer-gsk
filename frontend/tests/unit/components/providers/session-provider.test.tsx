import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { SessionProvider } from '@/components/providers/session-provider';
import { useAuthStore } from '@/stores/auth-store';

// Mock cookie functions
vi.mock('@/lib/cookies', () => ({
  setAuthCookies: vi.fn(),
  clearAuthCookies: vi.fn(),
}));

// Mock fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('SessionProvider', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.getState().reset();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Feature 014: Automatic Session Initialization', () => {
    it('should show loading state initially', () => {
      // Don't resolve fetch yet to keep in loading state
      mockFetch.mockImplementation(() => new Promise(() => {}));

      render(
        <SessionProvider>
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

      expect(screen.getByText(/initializing session/i)).toBeInTheDocument();
      expect(screen.queryByTestId('content')).not.toBeInTheDocument();
    });

    it('should render children after session is initialized', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            userId: 'test-user-123',
            sessionExpiresAt: new Date(
              Date.now() + 30 * 24 * 60 * 60 * 1000
            ).toISOString(),
          }),
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
      mockFetch.mockImplementation(() => new Promise(() => {}));

      render(
        <SessionProvider loadingComponent={<div>Custom Loading...</div>}>
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

      expect(screen.getByText('Custom Loading...')).toBeInTheDocument();
    });

    it('should render children immediately when showLoading=false', () => {
      mockFetch.mockImplementation(() => new Promise(() => {}));

      render(
        <SessionProvider showLoading={false}>
          <div data-testid="content">Content</div>
        </SessionProvider>
      );

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

      // Should render immediately without fetch call
      expect(screen.getByTestId('content')).toBeInTheDocument();
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('should show custom error component on session init failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ message: 'Server error' }),
      });

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
      expect(mockFetch).not.toHaveBeenCalled();
      expect(screen.getByTestId('content')).toBeInTheDocument();
    });
  });
});

describe('useSessionInit hook', () => {
  beforeEach(() => {
    useAuthStore.getState().reset();
    vi.clearAllMocks();
  });

  it('should call signInAnonymous when no session exists', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          userId: 'new-anon-user',
          sessionExpiresAt: new Date(
            Date.now() + 30 * 24 * 60 * 60 * 1000
          ).toISOString(),
        }),
    });

    render(
      <SessionProvider>
        <div>Test</div>
      </SessionProvider>
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/v2/auth/anonymous', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  it('should set isReady to true after successful initialization', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          userId: 'ready-user',
          sessionExpiresAt: new Date(
            Date.now() + 30 * 24 * 60 * 60 * 1000
          ).toISOString(),
        }),
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
