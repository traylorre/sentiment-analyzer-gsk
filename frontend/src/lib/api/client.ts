import { API_URL, TIMEOUT_ERROR_MESSAGE } from '@/lib/constants';
import { joinUrl } from '@/lib/utils/url';

/**
 * Feature 1112: Error codes for API client errors
 */
export type ErrorCode =
  | 'NETWORK_ERROR'
  | 'TIMEOUT'
  | 'AUTH_ERROR'
  | 'SERVER_ERROR'
  | 'CLIENT_ERROR'
  | 'UNKNOWN_ERROR';

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiClientError';
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
  /**
   * Feature 1112: Request timeout in milliseconds.
   * When specified, the request will be aborted after this duration.
   */
  timeout?: number;
}

let accessToken: string | null = null;
let userId: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

/**
 * Feature 014: Set user ID for display purposes.
 * Feature 1146: X-User-ID header fallback REMOVED for security (CVSS 9.1).
 *
 * DEPRECATED: This function no longer sets headers. Use setAccessToken() instead.
 * For anonymous sessions, the userId IS the accessToken.
 */
export function setUserId(id: string | null) {
  userId = id;
  // Feature 1146: Also set as access token for anonymous sessions
  // This ensures Bearer token is always used
  if (id && !accessToken) {
    accessToken = id;
  }
}

export function getUserId(): string | null {
  return userId;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorBody: ApiError;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = {
        code: 'UNKNOWN_ERROR',
        message: response.statusText || 'An unknown error occurred',
      };
    }
    throw new ApiClientError(
      response.status,
      errorBody.code,
      errorBody.message,
      errorBody.details
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, timeout, ...fetchOptions } = options;

  // Build URL with query params
  // Feature 1118: Use joinUrl to prevent double-slash issues
  const url = new URL(joinUrl(API_URL, endpoint));
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.append(key, String(value));
      }
    });
  }

  // Set default headers
  const headers = new Headers(fetchOptions.headers);
  if (!headers.has('Content-Type') && fetchOptions.body) {
    headers.set('Content-Type', 'application/json');
  }

  // Feature 1146: Bearer-only authentication (X-User-ID fallback removed)
  // Security fix: All requests must use Authorization: Bearer header
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }
  // Note: X-User-ID fallback removed for security (CVSS 9.1)

  // Feature 1112: AbortController-based timeout support
  // Properly cancels the request (no orphaned connections)
  // Feature 1159: Include credentials for cross-origin cookie transmission
  const fetchOptionsWithSignal = {
    ...fetchOptions,
    headers,
    credentials: 'include' as RequestCredentials,
  } as RequestInit;
  if (timeout !== undefined && timeout > 0) {
    fetchOptionsWithSignal.signal = AbortSignal.timeout(timeout);
  }

  try {
    const response = await fetch(url.toString(), fetchOptionsWithSignal);
    return handleResponse<T>(response);
  } catch (error) {
    // Feature 1112: Handle AbortError (timeout) separately
    if (error instanceof Error && error.name === 'TimeoutError') {
      throw new ApiClientError(0, 'TIMEOUT', TIMEOUT_ERROR_MESSAGE);
    }
    // Handle other abort errors (e.g., manual abort)
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError(0, 'TIMEOUT', TIMEOUT_ERROR_MESSAGE);
    }
    // Handle network errors
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiClientError(0, 'NETWORK_ERROR', 'Unable to connect. Please check your internet connection.');
    }
    // Re-throw ApiClientError as-is
    if (error instanceof ApiClientError) {
      throw error;
    }
    // Unknown errors
    throw new ApiClientError(0, 'UNKNOWN_ERROR', error instanceof Error ? error.message : 'An unknown error occurred');
  }
}

// Convenience methods
export const api = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    apiClient<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    apiClient<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    apiClient<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: 'DELETE' }),
};
