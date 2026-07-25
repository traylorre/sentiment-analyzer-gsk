// Target: Customer Dashboard (Next.js/Amplify)
// Feature 1380: picture -> pictureUrl mapping (null -> undefined) for both
// /auth/me (getProfile) and /oauth/callback (exchangeOAuthCode).
import { describe, it, expect, vi, beforeEach } from 'vitest';

const post = vi.fn();
const get = vi.fn();

vi.mock('@/lib/api/client', () => ({
  api: {
    post: (...args: unknown[]) => post(...args),
    get: (...args: unknown[]) => get(...args),
  },
  setCsrfToken: vi.fn(),
  getCsrfToken: vi.fn(() => null),
}));

import { authApi } from '@/lib/api/auth';

const GOOD = 'https://lh3.googleusercontent.com/a/x=s96-c';

function meResponse(picture: string | null) {
  return {
    auth_type: 'google',
    email_masked: 'j***@example.com',
    configs_count: 0,
    max_configs: 2,
    session_expires_in_seconds: 100,
    role: 'free',
    linked_providers: ['google'],
    verification: 'verified',
    last_provider_used: 'google',
    picture,
  };
}

function callbackResponse(picture: string | null) {
  return {
    status: 'authenticated',
    email_masked: 'j***@example.com',
    auth_type: 'google',
    tokens: { id_token: 'i', access_token: 'a', expires_in: 900 },
    merged_anonymous_data: false,
    is_new_user: false,
    conflict: false,
    existing_provider: null,
    message: null,
    error: null,
    role: 'free',
    verification: 'verified',
    linked_providers: ['google'],
    last_provider_used: 'google',
    picture,
  };
}

describe('mapUserMeResponse via getProfile', () => {
  beforeEach(() => vi.clearAllMocks());

  it('maps picture -> pictureUrl', async () => {
    get.mockResolvedValueOnce(meResponse(GOOD));
    const profile = await authApi.getProfile();
    expect(profile.pictureUrl).toBe(GOOD);
  });

  it('maps null picture -> undefined', async () => {
    get.mockResolvedValueOnce(meResponse(null));
    const profile = await authApi.getProfile();
    expect(profile.pictureUrl).toBeUndefined();
  });
});

describe('mapOAuthCallbackResponse via exchangeOAuthCode', () => {
  beforeEach(() => vi.clearAllMocks());

  it('maps picture -> user.pictureUrl', async () => {
    post.mockResolvedValueOnce(callbackResponse(GOOD));
    const res = await authApi.exchangeOAuthCode('google', 'c', 's', 'https://app/cb');
    expect(res.user.pictureUrl).toBe(GOOD);
  });

  it('maps null picture -> undefined', async () => {
    post.mockResolvedValueOnce(callbackResponse(null));
    const res = await authApi.exchangeOAuthCode('google', 'c', 's', 'https://app/cb');
    expect(res.user.pictureUrl).toBeUndefined();
  });
});
