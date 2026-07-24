/**
 * Feature 1384: single-flight session bootstrap + no-clobber race tests.
 *
 * The bug: session init ran per-component. SessionProvider (useSessionInit) plus
 * 9 useAuth mount sites each raced to bootstrap. The shared isInitialized flag
 * was only set AFTER the async restore/mint finished, so concurrent callers all
 * passed the `!isInitialized` check and each fired restoreSession() AND, on a
 * miss, signInAnonymous(). Any anonymous mint issues a fresh refresh_token
 * cookie that clobbers the OAuth refresh cookie (same name/path) → the user is
 * logged out on reload.
 *
 * The fix under test: initializeSession() is a module-level single-flight that
 * runs restore-first EXACTLY ONCE for all concurrent callers, and refreshToken()
 * is collapsed into one in-flight request.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { useAuthStore } from '@/stores/auth-store';

vi.mock('@/lib/cookies', () => ({
  setAuthCookies: vi.fn(),
  clearAuthCookies: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  setUserId: vi.fn(),
  setAccessToken: vi.fn(),
  emitErrorEvent: vi.fn(),
  api: { post: vi.fn(), get: vi.fn() },
}));

const mockCreateAnonymousSession = vi.fn();
const mockRefreshToken = vi.fn();
const mockGetProfile = vi.fn();

vi.mock('@/lib/api/auth', () => ({
  authApi: {
    createAnonymousSession: () => mockCreateAnonymousSession(),
    requestMagicLink: vi.fn(),
    verifyMagicLink: vi.fn(),
    signOut: vi.fn(),
    getOAuthUrls: vi.fn(),
    exchangeOAuthCode: vi.fn(),
    refreshToken: () => mockRefreshToken(),
    getProfile: () => mockGetProfile(),
  },
}));

/** A restorable OAuth (Cognito-backed) refresh response. */
function oauthRefresh() {
  return {
    accessToken: 'oauth-access-token',
    idToken: 'oauth-id-token',
    expiresIn: 3600,
    userId: 'oauth-user-1',
    authType: 'email',
    sessionExpiresAt: new Date(Date.now() + 3600_000).toISOString(),
  };
}

/** A no-session refresh response (no restorable cookie). */
function emptyRefresh() {
  return {
    accessToken: null,
    idToken: null,
    expiresIn: 0,
    userId: null,
    authType: null,
    sessionExpiresAt: null,
  };
}

function anonMint() {
  return {
    userId: 'anon-user-1',
    token: 'anon-user-1',
    authType: 'anonymous',
    createdAt: new Date().toISOString(),
    sessionExpiresAt: new Date(Date.now() + 3600_000).toISOString(),
    storageHint: 'localStorage',
  };
}

describe('Feature 1384: single-flight session bootstrap', () => {
  beforeEach(() => {
    useAuthStore.getState().reset();
    vi.clearAllMocks();
    mockGetProfile.mockResolvedValue({});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('collapses concurrent initializeSession() calls into ONE restore, no anon mint', async () => {
    // Restorable OAuth session present.
    mockRefreshToken.mockResolvedValue(oauthRefresh());

    const { initializeSession } = useAuthStore.getState();

    // Simulate the 9 mount sites all bootstrapping at once.
    await Promise.all(Array.from({ length: 9 }, () => initializeSession()));

    // Single-flight: exactly one /refresh, and the anon mint that would clobber
    // the OAuth cookie is NEVER reached.
    expect(mockRefreshToken).toHaveBeenCalledTimes(1);
    expect(mockCreateAnonymousSession).not.toHaveBeenCalled();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.isAnonymous).toBe(false);
    expect(state.isInitialized).toBe(true);
    expect(state.user?.userId).toBe('oauth-user-1');
  });

  it('interleaved restore + anon-mint under load never double-mints (no clobber)', async () => {
    // No restorable session → exactly one anonymous mint even with N racers.
    mockRefreshToken.mockResolvedValue(emptyRefresh());
    mockCreateAnonymousSession.mockResolvedValue(anonMint());

    const { initializeSession } = useAuthStore.getState();
    await Promise.all(Array.from({ length: 9 }, () => initializeSession()));

    // Restore attempted once; anon minted once (not once-per-mount).
    expect(mockRefreshToken).toHaveBeenCalledTimes(1);
    expect(mockCreateAnonymousSession).toHaveBeenCalledTimes(1);

    const state = useAuthStore.getState();
    expect(state.isAnonymous).toBe(true);
    expect(state.isInitialized).toBe(true);
  });

  it('does not re-bootstrap once initialized', async () => {
    mockRefreshToken.mockResolvedValue(oauthRefresh());

    const { initializeSession } = useAuthStore.getState();
    await initializeSession();
    expect(mockRefreshToken).toHaveBeenCalledTimes(1);

    // A later mount calling initializeSession() must be a no-op.
    await initializeSession();
    expect(mockRefreshToken).toHaveBeenCalledTimes(1);
    expect(mockCreateAnonymousSession).not.toHaveBeenCalled();
  });

  it('restoreSession precedence: an OAuth restore blocks the anonymous fallback', async () => {
    // Even if a mint were queued, restore-first must win and skip it.
    mockRefreshToken.mockResolvedValue(oauthRefresh());
    mockCreateAnonymousSession.mockResolvedValue(anonMint());

    await useAuthStore.getState().initializeSession();

    expect(mockCreateAnonymousSession).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAnonymous).toBe(false);
  });
});

describe('Feature 1384: single-flight /refresh', () => {
  beforeEach(() => {
    useAuthStore.getState().reset();
    vi.clearAllMocks();
    mockGetProfile.mockResolvedValue({});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('collapses a concurrent restoreSession() + refreshSession() into one call', async () => {
    // Seed an authenticated session so refreshSession() does not early-return.
    useAuthStore.setState({
      tokens: {
        accessToken: 'seed',
        refreshToken: 'has-refresh',
        idToken: 'seed-id',
        expiresIn: 3600,
      },
    });

    // Never-resolving until both callers have subscribed, to prove they share
    // the SAME in-flight promise.
    let resolveRefresh: (v: unknown) => void = () => {};
    mockRefreshToken.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRefresh = resolve;
        })
    );

    const { restoreSession, refreshSession } = useAuthStore.getState();
    const p1 = restoreSession();
    const p2 = refreshSession();

    // Both callers issued while one request is in flight.
    expect(mockRefreshToken).toHaveBeenCalledTimes(1);

    resolveRefresh(oauthRefresh());
    await Promise.all([p1, p2]);

    expect(mockRefreshToken).toHaveBeenCalledTimes(1);
  });

  it('re-arms the single-flight after the in-flight request settles', async () => {
    mockRefreshToken.mockResolvedValue(oauthRefresh());

    await useAuthStore.getState().restoreSession();
    expect(mockRefreshToken).toHaveBeenCalledTimes(1);

    // A brand-new restore after settle issues a fresh request.
    await useAuthStore.getState().restoreSession();
    expect(mockRefreshToken).toHaveBeenCalledTimes(2);
  });
});
