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

/**
 * Feature 1112: Session initialization timeout configuration
 * Default timeout for anonymous session creation API call (milliseconds)
 */
export const SESSION_INIT_TIMEOUT_MS = 10000; // 10 seconds

/**
 * Feature 1112: Maximum time allowed for complete session initialization
 * Includes timeout + UI transition time (for documentation/reference)
 */
export const MAX_INIT_TIME_MS = 15000; // 15 seconds

/**
 * Feature 1112: User-friendly timeout error message
 */
export const TIMEOUT_ERROR_MESSAGE = 'Connection timed out. Please check your network and try again.';

export const LOCAL_STORAGE_KEYS = {
  userId: 'sentiment_user_id',
  authType: 'sentiment_auth_type',
  sessionExpires: 'sentiment_session_expires',
  tokens: 'sentiment_tokens',
  hapticEnabled: 'sentiment_haptic_enabled',
  reducedMotion: 'sentiment_reduced_motion',
  configCache: 'sentiment_config_cache',
} as const;
