import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ProtectedRoute, AuthGuard, withProtectedRoute } from '@/components/auth/protected-route';

// Mock useRouter
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
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
        hasHydrated: true,
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
        hasHydrated: true,
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
        hasHydrated: true,
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
        hasHydrated: true,
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
        expect(mockPush).toHaveBeenCalledWith('/auth/signin');
      });
    });

    it('should redirect to custom path', async () => {
      mockUseAuth.mockReturnValue({
        hasHydrated: true,
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
        expect(mockPush).toHaveBeenCalledWith('/custom-login');
      });
    });

    it('should show fallback when not authenticated', () => {
      mockUseAuth.mockReturnValue({
        hasHydrated: true,
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
    });
  });

  describe('upgraded auth required', () => {
    it('should show content for non-anonymous users', () => {
      mockUseAuth.mockReturnValue({
        hasHydrated: true,
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

    it('should show upgrade prompt for anonymous users', () => {
      mockUseAuth.mockReturnValue({
        hasHydrated: true,
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

      expect(screen.getByText(/sign in required/i)).toBeInTheDocument();
      expect(screen.queryByText(/premium content/i)).not.toBeInTheDocument();
    });

    it('should have sign in button in upgrade prompt', () => {
      mockUseAuth.mockReturnValue({
        hasHydrated: true,
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

      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });
  });

  describe('no auth required', () => {
    it('should show content without authentication when requireAuth is false', () => {
      mockUseAuth.mockReturnValue({
        hasHydrated: true,
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
      hasHydrated: true,
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
      hasHydrated: true,
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
      hasHydrated: true,
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
        hasHydrated: true,
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
        hasHydrated: true,
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
        hasHydrated: true,
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

  it('should pass options to ProtectedRoute', () => {
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

    // Should show upgrade prompt for anonymous user
    expect(screen.getByText(/sign in required/i)).toBeInTheDocument();
    expect(screen.queryByText(/premium hoc content/i)).not.toBeInTheDocument();
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
