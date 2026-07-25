import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SettingsPage from '@/app/(dashboard)/settings/page';

// framer-motion is mocked globally in tests/setup.ts

// Feature 1394: "Upgrade Now" routes to /auth/signin via the App Router.
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockUseAuth = vi.fn();
vi.mock('@/hooks/use-auth', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('@/stores/animation-store', () => ({
  useAnimationStore: () => ({
    reducedMotion: false,
    hapticEnabled: false,
    setReducedMotion: vi.fn(),
    setHapticEnabled: vi.fn(),
  }),
}));

// Stub children with their own dependency graphs.
vi.mock('@/components/dashboard/notification-preferences', () => ({
  NotificationPreferences: () => <div data-testid="notif-prefs" />,
}));
vi.mock('@/components/auth/sign-out-dialog', () => ({
  SignOutDialog: () => <div data-testid="sign-out-dialog" />,
}));
vi.mock('@/lib/api', () => ({
  notificationsApi: { updatePreferences: vi.fn() },
}));

describe('SettingsPage — Feature 1394 Upgrade Now button', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderAnonymous() {
    mockUseAuth.mockReturnValue({
      isInitialized: true,
      isAuthenticated: true,
      isAnonymous: true,
      isLoading: false,
      signOut: vi.fn(),
      user: {
        userId: 'anon-1',
        authType: 'anonymous',
        configurationCount: 0,
        alertCount: 0,
        createdAt: new Date().toISOString(),
        emailNotificationsEnabled: true,
      },
    });
    render(<SettingsPage />);
  }

  it('renders the Upgrade Now button for anonymous users', () => {
    renderAnonymous();
    expect(screen.getByRole('button', { name: /upgrade now/i })).toBeInTheDocument();
  });

  it('routes to /auth/signin when Upgrade Now is clicked', async () => {
    const user = userEvent.setup();
    renderAnonymous();

    await user.click(screen.getByRole('button', { name: /upgrade now/i }));

    expect(mockPush).toHaveBeenCalledWith('/auth/signin');
  });
});
