import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import SignInPage from '@/app/auth/signin/page';
import { ApiClientError } from '@/lib/api/client';

// Mock authApi.getOAuthUrls per test
const mockGetOAuthUrls = vi.fn();
vi.mock('@/lib/api/auth', () => ({
  authApi: {
    getOAuthUrls: () => mockGetOAuthUrls(),
  },
}));

// MagicLinkForm has its own dependencies; stub it to keep this test focused.
vi.mock('@/components/auth/magic-link-form', () => ({
  MagicLinkForm: () => <div data-testid="magic-link-form">magic-link</div>,
}));

// OAuthButtons depends on useAuth; stub to a simple visibility marker.
vi.mock('@/components/auth/oauth-buttons', () => ({
  OAuthButtons: ({ availableProviders }: { availableProviders?: string[] }) => (
    <div data-testid="oauth-buttons">{(availableProviders ?? []).join(',')}</div>
  ),
  AuthDivider: () => <hr data-testid="auth-divider" />,
}));

// framer-motion is mocked globally in tests/setup.ts

const HINT_TEXT = /Some sign-in options are temporarily unavailable/;

describe('SignInPage — Feature 1373 OAuth error visibility', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    mockGetOAuthUrls.mockReset();
  });

  it('renders OAuth buttons and stays silent when providers exist', async () => {
    mockGetOAuthUrls.mockResolvedValue({
      providers: {
        google: { authorize_url: 'https://example/oauth2/authorize?p=google', icon: 'google', state: 'abc' },
        github: { authorize_url: 'https://example/oauth2/authorize?p=github', icon: 'github', state: 'abc' },
      },
      state: 'abc',
    });

    render(<SignInPage />);

    await waitFor(() => {
      expect(screen.getByTestId('oauth-buttons')).toHaveTextContent('google,github');
    });
    expect(screen.queryByText(HINT_TEXT)).not.toBeInTheDocument();
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    expect(screen.getByTestId('magic-link-form')).toBeInTheDocument();
  });

  it('hides OAuth block, no hint, no console.error when providers are intentionally empty', async () => {
    mockGetOAuthUrls.mockResolvedValue({ providers: {}, state: '' });

    render(<SignInPage />);

    await waitFor(() => {
      expect(screen.getByTestId('magic-link-form')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('oauth-buttons')).not.toBeInTheDocument();
    expect(screen.queryByText(HINT_TEXT)).not.toBeInTheDocument();
    expect(consoleErrorSpy).not.toHaveBeenCalled();
  });

  it('logs status+code (no message) and renders the hint on ApiClientError', async () => {
    mockGetOAuthUrls.mockRejectedValue(
      new ApiClientError(500, 'INTERNAL', 'leaky backend message that must NOT appear in logs', { secret: 'x' }),
    );

    render(<SignInPage />);

    await waitFor(() => {
      expect(screen.getByText(HINT_TEXT)).toBeInTheDocument();
    });
    expect(screen.queryByTestId('oauth-buttons')).not.toBeInTheDocument();
    expect(consoleErrorSpy).toHaveBeenCalledTimes(1);

    const [label, payload] = consoleErrorSpy.mock.calls[0];
    expect(label).toBe('[signin] OAuth providers fetch failed');
    expect(payload).toEqual({
      url: '/api/v2/auth/oauth/urls',
      status: 500,
      code: 'INTERNAL',
    });
    // Defense-in-depth: backend-controlled fields must NOT be in the log payload.
    expect(JSON.stringify(payload)).not.toContain('leaky backend message');
    expect(JSON.stringify(payload)).not.toContain('secret');

    expect(screen.getByTestId('magic-link-form')).toBeInTheDocument();
  });

  it('treats non-ApiClientError as code=NETWORK, logs and renders hint', async () => {
    mockGetOAuthUrls.mockRejectedValue(new TypeError('Failed to fetch'));

    render(<SignInPage />);

    await waitFor(() => {
      expect(screen.getByText(HINT_TEXT)).toBeInTheDocument();
    });
    expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
    const [, payload] = consoleErrorSpy.mock.calls[0];
    expect(payload).toEqual({
      url: '/api/v2/auth/oauth/urls',
      status: undefined,
      code: 'NETWORK',
    });
  });

  it('hint has accessible role+live attributes (US2 a11y)', async () => {
    mockGetOAuthUrls.mockRejectedValue(new TypeError('Failed to fetch'));

    render(<SignInPage />);

    const hint = await screen.findByText(HINT_TEXT);
    expect(hint).toHaveAttribute('role', 'status');
    expect(hint).toHaveAttribute('aria-live', 'polite');
  });
});
