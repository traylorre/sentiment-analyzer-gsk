import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import VerifyPage from '@/app/auth/verify/page';

const mockPush = vi.fn();
const mockSearchParamsGet = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => ({ get: mockSearchParamsGet }),
}));

const mockVerifyToken = vi.fn();
vi.mock('@/hooks/use-auth', () => ({
  useAuth: () => ({ verifyToken: mockVerifyToken, isLoading: false, error: null }),
}));

function setToken(token: string | null) {
  mockSearchParamsGet.mockImplementation((key: string) => (key === 'token' ? token : null));
}

describe('Magic link verify page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('shows the invalid-link state without calling verifyToken when the token is missing', () => {
    setToken(null);

    render(<VerifyPage />);

    expect(screen.getByText(/invalid or expired link/i)).toBeInTheDocument();
    expect(mockVerifyToken).not.toHaveBeenCalled();
  });

  it('verifies the token and shows success', async () => {
    setToken('tok_123');
    mockVerifyToken.mockResolvedValueOnce(undefined);

    render(<VerifyPage />);

    expect(screen.queryByText(/invalid or expired link/i)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/redirecting you to the dashboard/i)).toBeInTheDocument();
    });
    expect(mockVerifyToken).toHaveBeenCalledWith('tok_123');
  });

  it('shows the invalid-link state when verification fails', async () => {
    setToken('tok_bad');
    mockVerifyToken.mockRejectedValueOnce(new Error('expired'));

    render(<VerifyPage />);

    await waitFor(() => {
      expect(screen.getByText(/invalid or expired link/i)).toBeInTheDocument();
    });
  });
});
