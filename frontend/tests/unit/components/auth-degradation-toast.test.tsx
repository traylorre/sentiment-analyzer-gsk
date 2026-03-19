import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { AuthDegradationToast } from '@/components/ui/auth-degradation-toast';

// Mock sonner toast
const mockToastWarning = vi.fn();
vi.mock('sonner', () => ({
  toast: {
    warning: (...args: unknown[]) => mockToastWarning(...args),
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

// Mock the auth store with controllable state
let mockSessionDegraded = false;
let mockUser: { userId: string; authType: string } | null = null;

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: (selector: (state: { sessionDegraded: boolean; user: typeof mockUser }) => unknown) =>
    selector({ sessionDegraded: mockSessionDegraded, user: mockUser }),
}));

describe('AuthDegradationToast', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSessionDegraded = false;
    mockUser = null;
    cleanup();
  });

  it('should call toast.warning when sessionDegraded transitions to true', () => {
    // Start with non-degraded, authenticated user
    mockSessionDegraded = false;
    mockUser = { userId: 'user-123', authType: 'email' };

    const { rerender } = render(<AuthDegradationToast />);

    // Transition to degraded
    mockSessionDegraded = true;
    rerender(<AuthDegradationToast />);

    expect(mockToastWarning).toHaveBeenCalledTimes(1);
    expect(mockToastWarning).toHaveBeenCalledWith(
      expect.stringContaining('session may expire soon'),
      expect.objectContaining({
        action: expect.objectContaining({
          label: 'Sign in again',
        }),
        duration: Infinity,
      })
    );
  });

  it('should NOT call toast when user is anonymous', () => {
    // Anonymous user
    mockSessionDegraded = false;
    mockUser = { userId: 'anon-123', authType: 'anonymous' };

    const { rerender } = render(<AuthDegradationToast />);

    // Transition to degraded
    mockSessionDegraded = true;
    rerender(<AuthDegradationToast />);

    expect(mockToastWarning).not.toHaveBeenCalled();
  });

  it('should NOT call toast when user is null', () => {
    mockSessionDegraded = false;
    mockUser = null;

    const { rerender } = render(<AuthDegradationToast />);

    mockSessionDegraded = true;
    rerender(<AuthDegradationToast />);

    expect(mockToastWarning).not.toHaveBeenCalled();
  });

  it('should include "Sign in again" action in the toast', () => {
    mockSessionDegraded = false;
    mockUser = { userId: 'user-456', authType: 'google' };

    const { rerender } = render(<AuthDegradationToast />);

    mockSessionDegraded = true;
    rerender(<AuthDegradationToast />);

    expect(mockToastWarning).toHaveBeenCalledTimes(1);
    const callArgs = mockToastWarning.mock.calls[0];
    const options = callArgs[1];
    expect(options.action).toBeDefined();
    expect(options.action.label).toBe('Sign in again');
    expect(typeof options.action.onClick).toBe('function');
  });

  it('should NOT fire toast on re-render when already degraded (no transition)', () => {
    // Start already degraded
    mockSessionDegraded = true;
    mockUser = { userId: 'user-789', authType: 'email' };

    const { rerender } = render(<AuthDegradationToast />);

    // Re-render with same degraded state
    rerender(<AuthDegradationToast />);
    rerender(<AuthDegradationToast />);

    // Should not fire because prevDegradedRef starts false, so the first render
    // sees a false->true transition. But subsequent rerenders should not fire again.
    // The first render triggers the effect (false->true), so exactly 1 call.
    expect(mockToastWarning).toHaveBeenCalledTimes(1);
  });
});
