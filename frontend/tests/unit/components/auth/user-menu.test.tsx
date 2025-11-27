import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UserMenu, SessionTimer } from '@/components/auth/user-menu';

// framer-motion is mocked globally in tests/setup.ts

// Mock useAuth hook
const mockSignOut = vi.fn();
const mockRefreshSession = vi.fn();
const mockUseAuth = vi.fn();
vi.mock('@/hooks/use-auth', () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock window.location
const mockLocation = { href: '' };
Object.defineProperty(window, 'location', {
  value: mockLocation,
  writable: true,
});

describe('UserMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocation.href = '';
  });

  describe('unauthenticated state', () => {
    it('should show sign in button when not authenticated', () => {
      mockUseAuth.mockReturnValue({
        isAuthenticated: false,
        isAnonymous: false,
        user: null,
        signOut: mockSignOut,
        isLoading: false,
      });

      render(<UserMenu />);

      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });

    it('should redirect to sign in page when clicked', async () => {
      const user = userEvent.setup();
      mockUseAuth.mockReturnValue({
        isAuthenticated: false,
        isAnonymous: false,
        user: null,
        signOut: mockSignOut,
        isLoading: false,
      });

      render(<UserMenu />);

      const button = screen.getByRole('button', { name: /sign in/i });
      await user.click(button);

      expect(mockLocation.href).toBe('/auth/signin');
    });
  });

  describe('authenticated state', () => {
    it('should show user display name', () => {
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        isAnonymous: false,
        user: {
          userId: 'user-123',
          email: 'john@example.com',
          authType: 'magic_link',
        },
        signOut: mockSignOut,
        isLoading: false,
      });

      render(<UserMenu />);

      expect(screen.getByText('john')).toBeInTheDocument();
    });

    it('should show Guest for anonymous users', () => {
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        isAnonymous: true,
        user: {
          userId: 'anon-123',
          authType: 'anonymous',
        },
        signOut: mockSignOut,
        isLoading: false,
      });

      render(<UserMenu />);

      expect(screen.getByText('Guest')).toBeInTheDocument();
    });
  });

  describe('dropdown menu', () => {
    it('should toggle dropdown on click', async () => {
      const user = userEvent.setup();
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        isAnonymous: false,
        user: {
          userId: 'user-123',
          email: 'john@example.com',
          authType: 'magic_link',
        },
        signOut: mockSignOut,
        isLoading: false,
      });

      render(<UserMenu />);

      // Initially closed
      expect(screen.queryByText(/settings/i)).not.toBeInTheDocument();

      // Open dropdown
      const menuButton = screen.getByRole('button');
      await user.click(menuButton);

      // Menu items visible
      expect(screen.getByText(/settings/i)).toBeInTheDocument();
      expect(screen.getByText(/sign out/i)).toBeInTheDocument();
    });

    it('should show sign in with email option for anonymous users', async () => {
      const user = userEvent.setup();
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        isAnonymous: true,
        user: {
          userId: 'anon-123',
          authType: 'anonymous',
        },
        signOut: mockSignOut,
        isLoading: false,
      });

      render(<UserMenu />);

      const menuButton = screen.getByRole('button');
      await user.click(menuButton);

      expect(screen.getByText(/sign in with email/i)).toBeInTheDocument();
    });

    it('should show auth type label', async () => {
      const user = userEvent.setup();
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        isAnonymous: false,
        user: {
          userId: 'user-123',
          email: 'john@example.com',
          authType: 'google',
        },
        signOut: mockSignOut,
        isLoading: false,
      });

      render(<UserMenu />);

      const menuButton = screen.getByRole('button');
      await user.click(menuButton);

      expect(screen.getByText(/signed in via google/i)).toBeInTheDocument();
    });

    it('should call signOut when sign out clicked', async () => {
      const user = userEvent.setup();
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        isAnonymous: false,
        user: {
          userId: 'user-123',
          email: 'john@example.com',
          authType: 'magic_link',
        },
        signOut: mockSignOut,
        isLoading: false,
      });

      render(<UserMenu />);

      const menuButton = screen.getByRole('button');
      await user.click(menuButton);

      const signOutButton = screen.getByText(/sign out/i);
      await user.click(signOutButton);

      expect(mockSignOut).toHaveBeenCalled();
    });

    it('should navigate to settings when settings clicked', async () => {
      const user = userEvent.setup();
      mockUseAuth.mockReturnValue({
        isAuthenticated: true,
        isAnonymous: false,
        user: {
          userId: 'user-123',
          email: 'john@example.com',
          authType: 'magic_link',
        },
        signOut: mockSignOut,
        isLoading: false,
      });

      render(<UserMenu />);

      const menuButton = screen.getByRole('button');
      await user.click(menuButton);

      const settingsButton = screen.getByText(/settings/i);
      await user.click(settingsButton);

      expect(mockLocation.href).toBe('/settings');
    });
  });
});

describe('SessionTimer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should not render when session is invalid', () => {
    mockUseAuth.mockReturnValue({
      isSessionValid: false,
      remainingSessionMs: 0,
      refreshSession: mockRefreshSession,
      isLoading: false,
    });

    const { container } = render(<SessionTimer />);

    expect(container).toBeEmptyDOMElement();
  });

  it('should display remaining time', () => {
    mockUseAuth.mockReturnValue({
      isSessionValid: true,
      remainingSessionMs: 600000, // 10 minutes
      refreshSession: mockRefreshSession,
      isLoading: false,
    });

    render(<SessionTimer />);

    expect(screen.getByText(/session: 10:00/i)).toBeInTheDocument();
  });

  it('should show extend button when session expiring soon', () => {
    mockUseAuth.mockReturnValue({
      isSessionValid: true,
      remainingSessionMs: 180000, // 3 minutes
      refreshSession: mockRefreshSession,
      isLoading: false,
    });

    render(<SessionTimer />);

    expect(screen.getByText(/extend/i)).toBeInTheDocument();
  });

  it('should not show extend button when plenty of time left', () => {
    mockUseAuth.mockReturnValue({
      isSessionValid: true,
      remainingSessionMs: 1800000, // 30 minutes
      refreshSession: mockRefreshSession,
      isLoading: false,
    });

    render(<SessionTimer />);

    expect(screen.queryByText(/extend/i)).not.toBeInTheDocument();
  });

  it('should call refreshSession when extend clicked', async () => {
    const user = userEvent.setup();
    mockUseAuth.mockReturnValue({
      isSessionValid: true,
      remainingSessionMs: 180000, // 3 minutes
      refreshSession: mockRefreshSession,
      isLoading: false,
    });

    render(<SessionTimer />);

    const extendButton = screen.getByText(/extend/i);
    await user.click(extendButton);

    expect(mockRefreshSession).toHaveBeenCalled();
  });
});
