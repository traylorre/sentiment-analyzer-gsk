import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApiHealthBanner } from '@/components/ui/api-health-banner';

// Mock emitErrorEvent
const mockEmitErrorEvent = vi.fn();
vi.mock('@/lib/api/client', () => ({
  emitErrorEvent: (...args: unknown[]) => mockEmitErrorEvent(...args),
}));

// Mock the zustand store
const mockDismissBanner = vi.fn();
let mockStoreState = {
  isUnreachable: false,
  bannerDismissed: false,
  failures: [] as number[],
};

vi.mock('@/stores/api-health-store', () => ({
  useApiHealthStore: (selector: (state: typeof mockStoreState & { dismissBanner: () => void }) => unknown) =>
    selector({ ...mockStoreState, dismissBanner: mockDismissBanner }),
  selectBannerVisible: (state: { isUnreachable: boolean; bannerDismissed: boolean }) =>
    state.isUnreachable && !state.bannerDismissed,
  selectFailureCount: (state: { failures: number[] }) => state.failures.length,
}));

describe('ApiHealthBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStoreState = {
      isUnreachable: false,
      bannerDismissed: false,
      failures: [],
    };
  });

  it('should render banner text when isUnreachable=true and bannerDismissed=false', () => {
    mockStoreState = {
      isUnreachable: true,
      bannerDismissed: false,
      failures: [Date.now(), Date.now(), Date.now()],
    };

    render(<ApiHealthBanner />);

    expect(
      screen.getByText(/having trouble connecting to the server/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('should render null when isUnreachable=false', () => {
    mockStoreState = {
      isUnreachable: false,
      bannerDismissed: false,
      failures: [],
    };

    const { container } = render(<ApiHealthBanner />);

    expect(container.innerHTML).toBe('');
  });

  it('should render null when bannerDismissed=true', () => {
    mockStoreState = {
      isUnreachable: true,
      bannerDismissed: true,
      failures: [Date.now(), Date.now(), Date.now()],
    };

    const { container } = render(<ApiHealthBanner />);

    expect(container.innerHTML).toBe('');
  });

  it('should call dismissBanner when X button is clicked', async () => {
    mockStoreState = {
      isUnreachable: true,
      bannerDismissed: false,
      failures: [Date.now(), Date.now(), Date.now()],
    };

    const user = userEvent.setup();
    render(<ApiHealthBanner />);

    const dismissButton = screen.getByRole('button', {
      name: /dismiss connectivity warning/i,
    });
    await user.click(dismissButton);

    expect(mockDismissBanner).toHaveBeenCalledTimes(1);
  });

  it('should call emitErrorEvent with api_health_banner_shown when visible', () => {
    mockStoreState = {
      isUnreachable: true,
      bannerDismissed: false,
      failures: [Date.now(), Date.now(), Date.now()],
    };

    render(<ApiHealthBanner />);

    expect(mockEmitErrorEvent).toHaveBeenCalledWith(
      'api_health_banner_shown',
      expect.objectContaining({ failureCount: expect.any(Number) })
    );
  });
});
