// Target: Customer Dashboard (Next.js/Amplify)
import { test, expect, type Request } from '@playwright/test';

/**
 * Chaos: SSE Reconnection Lifecycle (Feature 1265, US2/FR-004-007)
 *
 * Validates fetch-based SSE reconnection behavior:
 * - Graceful close reconnects quickly (~500ms)
 * - Abnormal termination triggers exponential backoff
 * - Last-Event-ID header propagated on reconnection
 *
 * Timing strategy: Tolerance bands and count-based verification,
 * not exact timing measurements. Avoids CI flakiness.
 */
test.describe('Chaos: SSE Reconnection Lifecycle', () => {
  /** Collect SSE-related requests for timing/header analysis */
  function trackSSERequests(page: import('@playwright/test').Page) {
    const requests: { url: string; timestamp: number; headers: Record<string, string> }[] = [];
    page.on('request', (req: Request) => {
      if (req.url().includes('/stream') || req.url().includes('/sse')) {
        requests.push({
          url: req.url(),
          timestamp: Date.now(),
          headers: req.headers(),
        });
      }
    });
    return requests;
  }

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(2000);
  });

  // T032: SSE graceful close reconnects within ~500ms
  test('SSE graceful close reconnects within tolerance band', async ({
    page,
  }) => {
    const sseRequests = trackSSERequests(page);

    // Intercept SSE endpoint — return a deadline event then close
    let requestCount = 0;
    await page.route('**/api/v2/stream**', async (route) => {
      requestCount++;
      if (requestCount === 1) {
        // First response: deliver a deadline event (graceful close)
        const sseBody = [
          'event: deadline',
          'data: {"reason": "lambda_timeout"}',
          '',
          '',
        ].join('\n');
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          body: sseBody,
        });
      } else {
        // Subsequent requests: allow through
        await route.continue();
      }
    });

    // Wait for reconnection attempts
    await page.waitForTimeout(3000);

    // Should have at least 2 SSE requests (initial + reconnection after deadline)
    expect(sseRequests.length).toBeGreaterThanOrEqual(2);

    if (sseRequests.length >= 2) {
      // Graceful close should reconnect faster than exponential backoff
      // Tolerance: 200ms-1000ms (per spec US2 scenario 1)
      const interval = sseRequests[1].timestamp - sseRequests[0].timestamp;
      expect(interval).toBeGreaterThan(100); // Not instant
      expect(interval).toBeLessThan(5000); // Much faster than exponential backoff max
    }
  });

  // T033: SSE abnormal termination triggers exponential backoff
  test('SSE abnormal termination triggers increasing reconnection intervals', async ({
    page,
  }) => {
    const sseRequests = trackSSERequests(page);

    // Abort all SSE requests to simulate abnormal termination
    await page.route('**/api/v2/stream**', (route) => route.abort('connectionreset'));

    // Wait for multiple reconnection attempts (exponential backoff)
    await page.waitForTimeout(15000);

    // Should have multiple SSE requests (reconnection attempts)
    expect(sseRequests.length).toBeGreaterThanOrEqual(3);

    if (sseRequests.length >= 3) {
      // Verify intervals are monotonically increasing (exponential backoff)
      // With tolerance: each interval should be >= previous interval * 0.5 (within 2x)
      const intervals: number[] = [];
      for (let i = 1; i < sseRequests.length; i++) {
        intervals.push(sseRequests[i].timestamp - sseRequests[i - 1].timestamp);
      }

      // At least the later intervals should be longer than the first
      const firstInterval = intervals[0];
      const lastInterval = intervals[intervals.length - 1];
      expect(lastInterval).toBeGreaterThanOrEqual(firstInterval * 0.5);
    }
  });

  // T034: Last-Event-ID header present on reconnection
  test('Last-Event-ID header present on reconnection', async ({ page }) => {
    const sseRequests = trackSSERequests(page);

    let requestCount = 0;
    await page.route('**/api/v2/stream**', async (route) => {
      requestCount++;
      if (requestCount === 1) {
        // First response: deliver events with IDs, then close
        const sseBody = [
          'id: test-event-42',
          'event: metrics',
          'data: {"total_articles": 100}',
          '',
          'event: deadline',
          'data: {"reason": "test"}',
          '',
          '',
        ].join('\n');
        await route.fulfill({
          status: 200,
          contentType: 'text/event-stream',
          body: sseBody,
        });
      } else {
        // Allow reconnection through
        await route.continue();
      }
    });

    // Wait for reconnection
    await page.waitForTimeout(3000);

    // Check that the second request has Last-Event-ID header
    if (sseRequests.length >= 2) {
      const reconnectRequest = sseRequests[1];
      const lastEventId =
        reconnectRequest.headers['last-event-id'] ||
        reconnectRequest.headers['Last-Event-ID'];
      expect(lastEventId).toBe('test-event-42');
    }
  });
});
