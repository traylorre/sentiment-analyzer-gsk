import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DesktopNav } from '@/components/navigation/desktop-nav';

// framer-motion is mocked globally in tests/setup.ts

// Feature 1394: nav routes via the App Router; active state derives from pathname.
const mockPush = vi.fn();
const mockUsePathname = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockUsePathname(),
}));

const mockHapticLight = vi.fn();
vi.mock('@/hooks/use-haptic', () => ({
  useHaptic: () => ({ light: mockHapticLight, medium: vi.fn(), heavy: vi.fn() }),
}));

// Default: not an operator (admin section hidden). Overridden per test.
const mockUseIsOperator = vi.fn(() => false);
vi.mock('@/hooks/use-operator', () => ({
  useIsOperator: () => mockUseIsOperator(),
}));

// Stub heavy children — this suite is about nav routing, not their internals.
vi.mock('@/components/auth/user-menu', () => ({
  UserMenu: () => <div data-testid="user-menu" />,
}));
vi.mock('@/components/dashboard/data-freshness-indicator', () => ({
  DataFreshnessIndicator: () => <div data-testid="freshness" />,
}));

describe('DesktopNav — Feature 1394 real routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePathname.mockReturnValue('/');
    mockUseIsOperator.mockReturnValue(false);
  });

  it('renders the primary nav items', () => {
    render(<DesktopNav />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Configurations')).toBeInTheDocument();
    expect(screen.getByText('Alerts')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('routes via router.push (not a view-store mutation) when a nav item is clicked', async () => {
    const user = userEvent.setup();
    mockUsePathname.mockReturnValue('/'); // currently on dashboard
    render(<DesktopNav />);

    await user.click(screen.getByText('Configurations'));

    expect(mockPush).toHaveBeenCalledWith('/configs');
    expect(mockHapticLight).toHaveBeenCalled();
  });

  it('routes each item to its file-routed destination', async () => {
    const user = userEvent.setup();
    render(<DesktopNav />);

    await user.click(screen.getByText('Alerts'));
    expect(mockPush).toHaveBeenCalledWith('/alerts');

    await user.click(screen.getByText('Settings'));
    expect(mockPush).toHaveBeenCalledWith('/settings');
  });

  it('does not route when clicking the item for the current pathname', async () => {
    const user = userEvent.setup();
    mockUsePathname.mockReturnValue('/settings');
    render(<DesktopNav />);

    await user.click(screen.getByText('Settings'));

    expect(mockPush).not.toHaveBeenCalled();
  });

  it('derives active highlight from pathname, not the view-store', () => {
    mockUsePathname.mockReturnValue('/alerts');
    render(<DesktopNav />);

    // The active item gets the accent text color; others get muted-foreground.
    const alerts = screen.getByText('Alerts').closest('button')!;
    const dashboard = screen.getByText('Dashboard').closest('button')!;

    expect(alerts.className).toContain('text-accent');
    expect(dashboard.className).not.toContain('text-accent');
    expect(dashboard.className).toContain('text-muted-foreground');
  });

  it('marks dashboard active only on exact "/" match', () => {
    mockUsePathname.mockReturnValue('/');
    render(<DesktopNav />);

    const dashboard = screen.getByText('Dashboard').closest('button')!;
    const configs = screen.getByText('Configurations').closest('button')!;

    expect(dashboard.className).toContain('text-accent');
    expect(configs.className).not.toContain('text-accent');
  });
});
