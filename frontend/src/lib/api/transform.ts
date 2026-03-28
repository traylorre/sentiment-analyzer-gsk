/**
 * API response key transformation utilities (Feature 1266).
 *
 * Converts snake_case keys from the Python backend to camelCase
 * for the TypeScript frontend. Values are untouched — only object
 * keys are converted. Ticker symbols (BRK_B) in values are safe.
 */

function toCamelCase(str: string): string {
  return str.replace(/_([a-z])/g, (_, char) => char.toUpperCase());
}

/**
 * Recursively convert snake_case object keys to camelCase.
 * - Object keys are converted
 * - Array elements are recursed
 * - Primitive values pass through unchanged
 */
export function snakeToCamel<T>(obj: T): T {
  if (obj === null || obj === undefined || typeof obj !== 'object') {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => snakeToCamel(item)) as T;
  }

  const converted: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    converted[toCamelCase(key)] = snakeToCamel(value);
  }
  return converted as T;
}
