export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const COGNITO_CONFIG = {
  userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || '',
  clientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || '',
  domain: process.env.NEXT_PUBLIC_COGNITO_DOMAIN || '',
} as const;

export const REFRESH_INTERVAL_SECONDS = 300; // 5 minutes

export const STALE_TIME_MS = 5 * 60 * 1000; // 5 minutes

export const MAX_RECONNECT_ATTEMPTS = 5;

export const RECONNECT_DELAY_MS = 3000;

export const HAPTIC_ENABLED = process.env.NEXT_PUBLIC_ENABLE_HAPTICS !== 'false';

export const LOCAL_STORAGE_KEYS = {
  userId: 'sentiment_user_id',
  authType: 'sentiment_auth_type',
  sessionExpires: 'sentiment_session_expires',
  tokens: 'sentiment_tokens',
  hapticEnabled: 'sentiment_haptic_enabled',
  reducedMotion: 'sentiment_reduced_motion',
  configCache: 'sentiment_config_cache',
} as const;
