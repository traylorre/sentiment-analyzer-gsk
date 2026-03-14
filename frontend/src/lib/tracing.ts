/**
 * X-Ray trace ID generator for browser-to-Lambda trace propagation.
 * 1220-xray-instrumentation-hardening FR-007
 *
 * Generates X-Ray format: Root=1-{hex_timestamp}-{96bit_hex};Parent={64bit_hex};Sampled=1
 * Sampled=1 is a request to the backend; the backend's sampling rules make the final decision.
 */

function randomHex(bytes: number): string {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Generate an X-Ray-format trace ID for outbound requests.
 * Returns null if crypto API is unavailable (fail-open per FR-010).
 */
export function generateXRayTraceId(): string | null {
  try {
    const timestamp = Math.floor(Date.now() / 1000).toString(16);
    const rootId = randomHex(12);
    const parentId = randomHex(8);
    return `Root=1-${timestamp}-${rootId};Parent=${parentId};Sampled=1`;
  } catch {
    // FR-010: fail-open if crypto unavailable
    if (typeof console !== "undefined") {
      console.warn("[tracing] X-Ray trace ID generation failed, proceeding without trace header");
    }
    return null;
  }
}
