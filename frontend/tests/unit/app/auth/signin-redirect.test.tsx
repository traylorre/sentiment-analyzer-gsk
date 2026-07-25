import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import SignInPage from '@/app/auth/signin/page';

// framer-motion is mocked globally in tests/setup.ts

// OAuth provider fetch — keep it quiet (empty providers) so the effect under
// test is the only interesting side effect.
vi.mock('@/lib/api/auth', () => ({
  authApi: { getOAuthUrls: () => Promise.resolve({ providers: {}, state: '' }) },
}));

vi.mock('@/components/auth/magic-link-form', () => ({
  MagicLinkForm: () => <div data-testid="magic-link-form" />,
}));
vi.mock('@/components/auth/oauth-buttons', () => ({
  OAuthButtons: () => <div data-testid="oauth-buttons" />,
  AuthDivider: () => <hr />,
}));

const realLocation = window.location;

function setSearch(search: string) {
  Object.defineProperty(window, 'location', {
    value: { ...realLocation, search },
    writable: true,
    configurable: true,
  });
}

describe('SignInPage — Feature 1394 redirect persistence', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: realLocation,
      writable: true,
      configurable: true,
    });
    sessionStorage.clear();
  });

  it('persists a `redirect` query param to sessionStorage for the completion flow', async () => {
    setSearch('?redirect=/settings');
    render(<SignInPage />);

    await waitFor(() => {
      expect(sessionStorage.getItem('auth_redirect')).toBe('/settings');
    });
  });

  it('persists the raw value (guarding happens at consumption time)', async () => {
    // The signin page stores verbatim; safeInternalPath rejects it on consume.
    setSearch('?redirect=' + encodeURIComponent('//evil.com'));
    render(<SignInPage />);

    await waitFor(() => {
      expect(sessionStorage.getItem('auth_redirect')).toBe('//evil.com');
    });
  });

  it('clears a stale redirect when landing on signin without a redirect param', async () => {
    sessionStorage.setItem('auth_redirect', '/old-stale-target');
    setSearch('');
    render(<SignInPage />);

    await waitFor(() => {
      expect(sessionStorage.getItem('auth_redirect')).toBeNull();
    });
  });
});
