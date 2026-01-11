import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CallbackPage from '@/app/auth/callback/page';

// Mock useRouter
const mockPush = vi.fn();

// Mock search params - will be set per test via mockSearchParamsGet
const mockSearchParamsGet = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  useSearchParams: () => ({
    get: mockSearchParamsGet,
  }),
}));

// Mock useAuth hook
const mockHandleCallback = vi.fn();
const mockUseAuth = vi.fn();

vi.mock('@/hooks/use-auth', () => ({
  useAuth: () => mockUseAuth(),
}));

// framer-motion is mocked globally in tests/setup.ts

// Helper to set up search params
function setSearchParams(params: Record<string, string | null>) {
  mockSearchParamsGet.mockImplementation((key: string) => params[key] ?? null);
}

// Helper to set up useAuth mock
function setUseAuth(overrides: Partial<ReturnType<typeof mockUseAuth>> = {}) {
  mockUseAuth.mockReturnValue({
    handleCallback: mockHandleCallback,
    isLoading: false,
    error: null,
    ...overrides,
  });
}

describe('OAuth Callback Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    // Default useAuth setup
    setUseAuth();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  describe('Loading State', () => {
    it('should render loading state initially with valid params', async () => {
      setSearchParams({ code: 'auth_code_123' });
      sessionStorage.setItem('oauth_provider', 'google');
      mockHandleCallback.mockImplementation(() => new Promise(() => {})); // Never resolves

      render(<CallbackPage />);

      await waitFor(() => {
        expect(screen.getByText(/completing sign in/i)).toBeInTheDocument();
      });
    });
  });

  describe('URL Parameter Extraction', () => {
    it('should extract code from URL params', async () => {
      setSearchParams({ code: 'test_auth_code' });
      sessionStorage.setItem('oauth_provider', 'google');
      mockHandleCallback.mockResolvedValueOnce(undefined);

      render(<CallbackPage />);

      await waitFor(() => {
        expect(mockHandleCallback).toHaveBeenCalledWith('test_auth_code', 'google');
      });
    });

    it('should show error when code is missing', async () => {
      setSearchParams({});
      sessionStorage.setItem('oauth_provider', 'google');

      render(<CallbackPage />);

      await waitFor(() => {
        expect(screen.getByText(/invalid callback/i)).toBeInTheDocument();
      });
    });
  });

  describe('Provider Retrieval', () => {
    it('should retrieve provider from sessionStorage', async () => {
      setSearchParams({ code: 'auth_code' });
      sessionStorage.setItem('oauth_provider', 'github');
      mockHandleCallback.mockResolvedValueOnce(undefined);

      render(<CallbackPage />);

      await waitFor(() => {
        expect(mockHandleCallback).toHaveBeenCalledWith('auth_code', 'github');
      });
    });

    it('should clear sessionStorage after retrieval', async () => {
      setSearchParams({ code: 'auth_code' });
      sessionStorage.setItem('oauth_provider', 'google');
      mockHandleCallback.mockResolvedValueOnce(undefined);

      render(<CallbackPage />);

      await waitFor(() => {
        expect(mockHandleCallback).toHaveBeenCalled();
      });
      // sessionStorage is cleared synchronously in the effect
      expect(sessionStorage.getItem('oauth_provider')).toBeNull();
    });

    it('should show error when provider is missing', async () => {
      setSearchParams({ code: 'auth_code' });
      // No provider in sessionStorage

      render(<CallbackPage />);

      await waitFor(() => {
        expect(screen.getByText(/authentication session expired/i)).toBeInTheDocument();
      });
    });

    it('should show error for invalid provider', async () => {
      setSearchParams({ code: 'auth_code' });
      sessionStorage.setItem('oauth_provider', 'invalid_provider');

      render(<CallbackPage />);

      await waitFor(() => {
        expect(screen.getByText(/invalid authentication provider/i)).toBeInTheDocument();
      });
    });
  });

  describe('Success Flow', () => {
    it('should show success state after successful callback', async () => {
      setSearchParams({ code: 'auth_code' });
      sessionStorage.setItem('oauth_provider', 'google');
      mockHandleCallback.mockResolvedValueOnce(undefined);

      render(<CallbackPage />);

      await waitFor(() => {
        expect(screen.getByText(/you're signed in/i)).toBeInTheDocument();
      });
    });

    it('should redirect to / after success', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      setSearchParams({ code: 'auth_code' });
      sessionStorage.setItem('oauth_provider', 'google');
      mockHandleCallback.mockResolvedValueOnce(undefined);

      await act(async () => {
        render(<CallbackPage />);
      });

      await act(async () => {
        // Allow promises to resolve
        await vi.runAllTimersAsync();
      });

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/');
      });

      vi.useRealTimers();
    });
  });

  describe('Error Handling', () => {
    it('should show error when provider denied (error param)', async () => {
      setSearchParams({ error: 'access_denied' });

      await act(async () => {
        render(<CallbackPage />);
      });

      await waitFor(() => {
        expect(screen.getByText(/authentication was cancelled/i)).toBeInTheDocument();
      });
    });

    it('should show error description when provided', async () => {
      setSearchParams({
        error: 'access_denied',
        error_description: 'User declined authorization',
      });

      await act(async () => {
        render(<CallbackPage />);
      });

      await waitFor(() => {
        expect(screen.getByText(/user declined authorization/i)).toBeInTheDocument();
      });
    });

    it('should show error when handleCallback fails', async () => {
      setSearchParams({ code: 'auth_code' });
      sessionStorage.setItem('oauth_provider', 'google');
      mockHandleCallback.mockRejectedValueOnce(new Error('Token exchange failed'));

      await act(async () => {
        render(<CallbackPage />);
      });

      await waitFor(() => {
        expect(screen.getByText(/token exchange failed/i)).toBeInTheDocument();
      });
    });

    it('should show conflict error message', async () => {
      setSearchParams({ code: 'auth_code' });
      sessionStorage.setItem('oauth_provider', 'google');
      mockHandleCallback.mockRejectedValueOnce(
        new Error('Account conflict: email already registered via email')
      );

      await act(async () => {
        render(<CallbackPage />);
      });

      await waitFor(() => {
        expect(screen.getByText(/already registered/i)).toBeInTheDocument();
      });
    });
  });

  describe('Retry Button', () => {
    it('should navigate to signin when retry button clicked', async () => {
      const user = userEvent.setup();
      setSearchParams({ error: 'access_denied' });

      await act(async () => {
        render(<CallbackPage />);
      });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /try again/i }));

      expect(mockPush).toHaveBeenCalledWith('/auth/signin');
    });
  });
});
