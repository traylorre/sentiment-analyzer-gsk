/**
 * Runtime configuration API
 * Feature 1100: SSE Runtime URL Discovery
 *
 * Fetches runtime configuration from the backend, including the SSE Lambda URL
 * for streaming connections.
 */

import type { RuntimeConfig } from '@/types/runtime';

/**
 * Fetch runtime configuration from /api/v2/runtime
 *
 * This endpoint returns:
 * - sse_url: The SSE Lambda URL for streaming (RESPONSE_STREAM mode)
 * - environment: Current environment (preprod, prod, etc.)
 *
 * @returns RuntimeConfig or null if fetch fails
 */
export async function fetchRuntimeConfig(): Promise<RuntimeConfig | null> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || '';

  try {
    const response = await fetch(`${baseUrl}/api/v2/runtime`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      // Short timeout - don't block app initialization
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      console.warn(`Runtime config fetch failed: ${response.status}`);
      return null;
    }

    const data = await response.json();

    return {
      sse_url: data.sse_url || null,
      environment: data.environment || 'unknown',
    };
  } catch (error) {
    // Log but don't throw - fallback to default behavior
    console.warn('Failed to fetch runtime config:', error);
    return null;
  }
}
