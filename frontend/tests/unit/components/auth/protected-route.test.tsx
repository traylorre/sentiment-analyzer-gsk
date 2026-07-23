import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ProtectedRoute, AuthGuard, withProtectedRoute } from '@/components/auth/protected-route';

// Mock useRouter + usePathname
// M1 WI-5: ProtectedRoute now uses router.replace (no history entry for the
// gated page) and builds the redirect URL from the current pathname.
const mockPush = vi.fn();
const mockReplace = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
  usePathname: () => '/alerts',
}));

// framer-motion is mocked globally in tests/setup.ts

// Mock useAuth hook - will be modified per test
const mockUseAuth = vi.fn();
vi.mock('@/hooks/use-auth', () => ({
  useAuth: () => mockUseAuth(),
}));

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loading state', () => {
    it('should show loading spinner when not initialized', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: false,
        isAnonymous: false,
        isLoading: false,
        isInitialized: false,
      });

      render(
        <ProtectedRoute>
          <div>Protected content</div>
        </ProtectedRoute>
      );

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
      expect(screen.queryByText(/protected content/i)).not.toBeInTheDocument();
    });

    it('should show loading spinner when isLoading', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: true,
        isAnonymous: false,
        isLoading: true,
        isInitialized: true,
      });

      render(
        <ProtectedRoute>
          <div>Protected content</div>
        </ProtectedRoute>
      );

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });

  describe('authentication required', () => {
    it('should show children when authenticated', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: true,
        isAnonymous: false,
        isLoading: false,
        isInitialized: true,
      });

      render(
        <ProtectedRoute>
          <div>Protected content</div>
        </ProtectedRoute>
      );

      expect(screen.getByText(/protected content/i)).toBeInTheDocument();
    });

    it('should redirect when not authenticated', async () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: false,
        isAnonymous: false,
        isLoading: false,
        isInitialized: true,
      });

      render(
        <ProtectedRoute>
          <div>Protected content</div>
        </ProtectedRoute>
      );

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalledWith('/auth/signin?redirect=%2Falerts');
      });
    });

    it('should redirect to custom path', async () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: false,
        isAnonymous: false,
        isLoading: false,
        isInitialized: true,
      });

      render(
        <ProtectedRoute redirectTo="/custom-login">
          <div>Protected content</div>
        </ProtectedRoute>
      );

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalledWith('/custom-login?redirect=%2Falerts');
      });
    });

    it('should show fallback when not authenticated', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: false,
        isAnonymous: false,
        isLoading: false,
        isInitialized: true,
      });

      render(
        <ProtectedRoute fallback={<div>Please sign in</div>}>
          <div>Protected content</div>
        </ProtectedRoute>
      );

      expect(screen.getByText(/please sign in/i)).toBeInTheDocument();
      expect(screen.queryByText(/protected content/i)).not.toBeInTheDocument();
      // M1 WI-5: providing a fallback opts out of the redirect
      expect(mockReplace).not.toHaveBeenCalled();
    });
  });

  describe('upgraded auth required', () => {
    it('should show content for non-anonymous users', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: true,
        isAnonymous: false,
        isLoading: false,
        isInitialized: true,
      });

      render(
        <ProtectedRoute requireUpgraded>
          <div>Premium content</div>
        </ProtectedRoute>
      );

      expect(screen.getByText(/premium content/i)).toBeInTheDocument();
    });

    // M1 WI-5 (Q-M1-2): anonymous users on requireUpgraded routes are now
    // redirected (replace) to signin with redirect + upgrade params — the old
    // inline "Sign in required" prompt was removed (it rendered AND redirected).
    it('should redirect anonymous users with upgrade param', async () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: true,
        isAnonymous: true,
        isLoading: false,
        isInitialized: true,
      });

      render(
        <ProtectedRoute requireUpgraded>
          <div>Premium content</div>
        </ProtectedRoute>
      );

      expect(screen.queryByText(/premium content/i)).not.toBeInTheDocument();
      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalledWith(
          '/auth/signin?redirect=%2Falerts&upgrade=true'
        );
      });
    });

    it('should show redirect spinner while navigation is in flight', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: true,
        isAnonymous: true,
        isLoading: false,
        isInitialized: true,
      });

      render(
        <ProtectedRoute requireUpgraded>
          <div>Premium content</div>
        </ProtectedRoute>
      );

      expect(
        screen.getByRole('status', { name: /redirecting to sign in/i })
      ).toBeInTheDocument();
    });
  });

  describe('no auth required', () => {
    it('should show content without authentication when requireAuth is false', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isAuthenticated: false,
        isAnonymous: false,
        isLoading: false,
        isInitialized: true,
      });

      render(
        <ProtectedRoute requireAuth={false}>
          <div>Public content</div>
        </ProtectedRoute>
      );

      expect(screen.getByText(/public content/i)).toBeInTheDocument();
    });
  });
});

describe('AuthGuard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show children when authenticated', () => {
    mockUseAuth.mockReturnValue({
      // Feature 1165: Use isInitialized instead of hasHydrated
      isInitialized: true,
      isAuthenticated: true,
      isAnonymous: false,
    });

    render(
      <AuthGuard>
        <div>Guarded content</div>
      </AuthGuard>
    );

    expect(screen.getByText(/guarded content/i)).toBeInTheDocument();
  });

  it('should show nothing when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      // Feature 1165: Use isInitialized instead of hasHydrated
      isInitialized: true,
      isAuthenticated: false,
      isAnonymous: false,
    });

    const { container } = render(
      <AuthGuard>
        <div>Guarded content</div>
      </AuthGuard>
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('should show fallback when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      // Feature 1165: Use isInitialized instead of hasHydrated
      isInitialized: true,
      isAuthenticated: false,
      isAnonymous: false,
    });

    render(
      <AuthGuard fallback={<div>Not authorized</div>}>
        <div>Guarded content</div>
      </AuthGuard>
    );

    expect(screen.getByText(/not authorized/i)).toBeInTheDocument();
  });

  describe('feature guards', () => {
    it('should require upgrade for alerts feature when anonymous', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isInitialized: true,
        isAuthenticated: true,
        isAnonymous: true,
      });

      render(
        <AuthGuard feature="alerts">
          <div>Alerts content</div>
        </AuthGuard>
      );

      expect(screen.getByText(/sign in to access alerts/i)).toBeInTheDocument();
      expect(screen.queryByText(/alerts content/i)).not.toBeInTheDocument();
    });

    it('should show alerts for non-anonymous users', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isInitialized: true,
        isAuthenticated: true,
        isAnonymous: false,
      });

      render(
        <AuthGuard feature="alerts">
          <div>Alerts content</div>
        </AuthGuard>
      );

      expect(screen.getByText(/alerts content/i)).toBeInTheDocument();
    });

    it('should show configs for anonymous users', () => {
      mockUseAuth.mockReturnValue({
        // Feature 1165: Use isInitialized instead of hasHydrated
        isInitialized: true,
        isAuthenticated: true,
        isAnonymous: true,
      });

      render(
        <AuthGuard feature="configs">
          <div>Configs content</div>
        </AuthGuard>
      );

      expect(screen.getByText(/configs content/i)).toBeInTheDocument();
    });
  });
});

describe('withProtectedRoute HOC', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should wrap component with ProtectedRoute', () => {
    mockUseAuth.mockReturnValue({
      hasHydrated: true,
      isAuthenticated: true,
      isAnonymous: false,
      isLoading: false,
      isInitialized: true,
    });

    function TestComponent() {
      return <div>HOC wrapped content</div>;
    }

    const ProtectedTestComponent = withProtectedRoute(TestComponent);

    render(<ProtectedTestComponent />);

    expect(screen.getByText(/hoc wrapped content/i)).toBeInTheDocument();
  });

  it('should pass options to ProtectedRoute', async () => {
    mockUseAuth.mockReturnValue({
      hasHydrated: true,
      isAuthenticated: true,
      isAnonymous: true,
      isLoading: false,
      isInitialized: true,
    });

    function TestComponent() {
      return <div>Premium HOC content</div>;
    }

    const ProtectedTestComponent = withProtectedRoute(TestComponent, {
      requireUpgraded: true,
    });

    render(<ProtectedTestComponent />);

    // M1 WI-5: anonymous user on requireUpgraded route → redirect, not prompt
    expect(screen.queryByText(/premium hoc content/i)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith(
        '/auth/signin?redirect=%2Falerts&upgrade=true'
      );
    });
  });

  it('should pass props to wrapped component', () => {
    mockUseAuth.mockReturnValue({
      hasHydrated: true,
      isAuthenticated: true,
      isAnonymous: false,
      isLoading: false,
      isInitialized: true,
    });

    interface TestProps {
      message: string;
    }

    function TestComponent({ message }: TestProps) {
      return <div>{message}</div>;
    }

    const ProtectedTestComponent = withProtectedRoute(TestComponent);

    render(<ProtectedTestComponent message="Hello from props!" />);

    expect(screen.getByText(/hello from props!/i)).toBeInTheDocument();
  });
});
