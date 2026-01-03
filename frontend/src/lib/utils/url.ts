/**
 * URL utility functions for API client
 * Feature 1118: Fix double-slash URL in API requests
 */

/**
 * Joins a base URL and path, ensuring no double slashes.
 *
 * @param baseUrl - The API base URL (e.g., from NEXT_PUBLIC_API_URL)
 * @param path - The endpoint path (e.g., '/api/v2/auth/anonymous')
 * @returns Properly formatted URL with single slash between base and path
 *
 * @example
 * joinUrl('https://api.example.com', '/api/v2/auth')
 * // => 'https://api.example.com/api/v2/auth'
 *
 * joinUrl('https://api.example.com/', '/api/v2/auth')
 * // => 'https://api.example.com/api/v2/auth'
 *
 * @throws Error if baseUrl is empty or undefined
 */
export function joinUrl(baseUrl: string, path: string): string {
  if (!baseUrl) {
    throw new Error('API base URL is required but was empty or undefined');
  }

  // Handle empty path - return base URL as-is (without trailing slashes)
  if (!path) {
    return baseUrl.replace(/\/+$/, '');
  }

  // Remove trailing slashes from base URL
  const normalizedBase = baseUrl.replace(/\/+$/, '');

  // Remove leading slashes from path
  const normalizedPath = path.replace(/^\/+/, '');

  return `${normalizedBase}/${normalizedPath}`;
}
