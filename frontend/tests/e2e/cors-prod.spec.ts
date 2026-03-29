// Feature 1269: Production CORS validation via Playwright
// Target: Customer Dashboard (Next.js/Amplify)
//
// Verifies that the frontend can communicate with the API without
// CORS blocking. Uses page.evaluate() fetch calls and content-presence
// assertions rather than unreliable CORS error message parsing.
//
// AR3-FINDING-4: CORS failures are opaque by spec — browsers report
// "Failed to fetch" not "CORS error". We detect CORS issues by verifying
// content renders (if CORS blocks, no data loads).
import { test, expect } from '@playwright/test';

const PROD_URL = process.env.PROD_AMPLIFY_URL;
const PROD_API_URL = process.env.PROD_API_GATEWAY_URL || process.env.PROD_API_URL;

test.describe('Production CORS (Feature 1269)', () => {
  test.skip(!PROD_URL, 'PROD_AMPLIFY_URL not set — skipping prod CORS tests');

  test('dashboard loads without failed network requests', async ({ page }) => {
    const failedRequests: string[] = [];
    page.on('requestfailed', (request) => {
      failedRequests.push(`${request.url()} - ${request.failure()?.errorText}`);
    });

    await page.goto(PROD_URL!);
    await page.waitForLoadState('networkidle');

    expect(failedRequests).toHaveLength(0);
  });

  test('dashboard renders content (not empty CORS-blocked state)', async ({
    page,
  }) => {
    await page.goto(PROD_URL!);
    // Wait for the page to finish loading
    await page.waitForLoadState('networkidle');

    // The page should have meaningful content, not just an empty shell.
    // If CORS is blocking API calls, the dashboard will show empty state.
    const bodyText = await page.textContent('body');
    expect(bodyText).toBeTruthy();
    expect(bodyText!.length).toBeGreaterThan(50);
  });

  test('API fetch from page context succeeds', async ({ page }) => {
    test.skip(!PROD_API_URL, 'PROD_API_GATEWAY_URL not set');

    await page.goto(PROD_URL!);
    await page.waitForLoadState('networkidle');

    // Use page.evaluate to make a fetch call from the browser context.
    // This tests real CORS behavior — the browser enforces CORS policy.
    // AR3-FINDING-5: If API Gateway CORS is not configured (Feature 1253),
    // this test will correctly fail, surfacing the gap.
    const result = await page.evaluate(async (apiUrl: string) => {
      try {
        const response = await fetch(`${apiUrl}/api/v2/health`, {
          method: 'GET',
          credentials: 'include',
          headers: { Accept: 'application/json' },
        });
        return {
          ok: response.ok,
          status: response.status,
          corsOrigin: response.headers.get('access-control-allow-origin'),
        };
      } catch (e: any) {
        return { ok: false, status: 0, error: e.message };
      }
    }, PROD_API_URL!);

    expect(result.ok).toBe(true);
  });
});
