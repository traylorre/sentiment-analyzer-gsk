/**
 * Runtime configuration types
 * Feature 1100: SSE Runtime URL Discovery
 */

export interface RuntimeConfig {
  /** SSE Lambda URL for streaming connections (may be null if not configured) */
  sse_url: string | null;
  /** Current environment (e.g., 'preprod', 'prod') */
  environment: string;
}

export interface RuntimeState {
  /** Runtime configuration from /api/v2/runtime */
  config: RuntimeConfig | null;
  /** Whether runtime config has been fetched */
  isLoaded: boolean;
  /** Whether a fetch is in progress */
  isLoading: boolean;
  /** Error message if fetch failed */
  error: string | null;
}
