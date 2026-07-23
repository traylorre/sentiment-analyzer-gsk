// Target: Customer Dashboard (Next.js/Amplify)
/**
 * M1 WI-6: Google OAuth sign-in, verifiable on preprod.
 *
 * Canonical rows auth-oauth-01..05 (docs/cleanup-pristine/m1-verifier-convention.md,
 * as amended for WI-6: capture_mode=interactive, row-02 page_url {/auth/callback*, /}
 * gated on POST /oauth/callback 200, rows 03-05 lineage-tied to the row-02 login,
 * row-04 forbidden anonymous 201 max_count:1).
 *
 * WHY THIS IS INTERACTIVE, NOT HEADLESS (spec 1375, AR#1):
 * Google bot-detects automated browsers on its consent screen, so rows 02-05 cannot
 * be produced by a repeatable headless run. This spec is captured ONCE, HEADED, with a
 * real human completing the Google login in a CLEAN browser context (cookies cleared,
 * so the Google leg genuinely runs and no stale Cognito state is reused). Attested
 * capture_mode: interactive. The verifier proves the identity is really Google by
 * checking id_token.iss = accounts.google.com in the raw trace before it is destroyed.
 *
 * DO NOT run this before WI-6 is deployed (PR #932 applied + google-oauth secret
 * populated). Before enablement, /oauth/urls is empty and the button is absent: a red
 * here is EXPECTED, not a spec defect.
 *
 * RUN (preprod, headed, one interactive login):
 *   PREPROD_FRONTEND_URL=https://main.d29tlmksqcx494.amplifyapp.com VERIFICATION=1 \
 *     npx playwright test auth-oauth --project="Desktop Chrome" --headed
 */
import { test, expect } from './helpers/verification';

// 3 minutes: a human completes the Google consent screen mid-test.
test.setTimeout(180_000);

test.describe('auth-oauth: Google sign-in (interactive capture)', () => {
  test('Google user signs in, identity survives reload, reaches /alerts', async ({
    page,
    context,
    verify,
  }) => {
    // One inherent pre-login guest mint is allowed: the root-layout SessionProvider
    // (app/layout.tsx) mints an anonymous session on the clean-context signin load.
    // A SECOND would mean a signed-in reload silently re-guested (the real regression).
    verify.forbid({
      method: 'POST',
      path: '/api/v2/auth/anonymous',
      status: 201,
      max_count: 1,
    });

    // Clean context so the Google leg truly runs (R-3: no reused Cognito session).
    await context.clearCookies();

    // Observe auth response bodies/statuses via LISTENER only (interception is banned
    // + detected on preprod). Normalizes API Gateway stage prefixes like /{stage}/api/..
    type AuthObs = { path: string; status: number; user_id?: string };
    const auth: AuthObs[] = [];
    page.on('response', (r) => {
      let pathname: string;
      try {
        const raw = new URL(r.url()).pathname;
        const apiIdx = raw.indexOf('/api/');
        pathname = apiIdx !== -1 ? raw.slice(apiIdx) : raw;
      } catch {
        return;
      }
      if (!pathname.startsWith('/api/v2/auth/')) return;
      const status = r.status();
      const rec: AuthObs = { path: pathname, status };
      auth.push(rec);
      if (pathname.endsWith('/anonymous') || pathname.endsWith('/refresh')) {
        r.json()
          .then((b: { user_id?: string }) => (rec.user_id = b.user_id))
          .catch(() => {});
      }
    });

    const waitForAuth = async (
      pred: (a: AuthObs) => boolean,
      timeout = 170_000
    ): Promise<AuthObs> => {
      const deadline = Date.now() + timeout;
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const hit = auth.find(pred);
        if (hit) return hit;
        if (Date.now() > deadline)
          throw new Error('timed out waiting for a matching auth request');
        await page.waitForTimeout(500);
      }
    };

    // ── Row 01: Google button visible on signin; /oauth/urls 200 non-empty ──
    await page.goto('/auth/signin');
    await page.waitForLoadState('networkidle');
    const urls = auth.find((a) => a.path.endsWith('/oauth/urls'));
    expect(
      urls?.status,
      'GET /oauth/urls returned 200 (run this AFTER WI-6 is deployed)'
    ).toBe(200);
    const googleButton = page.getByRole('button', {
      name: /Continue with Google/i,
    });
    await expect(
      googleButton,
      'Google button rendered (providers non-empty)'
    ).toBeVisible();
    await verify.shot('signin-buttons', {
      expected_ui_state:
        'Signin page shows "Continue with Google"; GET /oauth/urls 200 non-empty providers',
      probe: { selector: 'text=Continue with Google' },
    });

    // ── ACTION REQUIRED: human completes the Google login ──
    // Clicking triggers window.location.href = authorize_url (full nav to Cognito →
    // Google). The owner signs in with the test Google account on the real consent
    // screen. Playwright waits for the callback POST to land.
    // eslint-disable-next-line no-console
    console.log(
      '\n\n>>> ACTION REQUIRED: complete the Google sign-in in the browser window. <<<\n\n'
    );
    await googleButton.click();

    // ── Row 02: callback completes — POST /oauth/callback 200 is the real gate ──
    // (page_url may be /auth/callback* OR already / by screenshot time — amendment (a))
    const callback = await waitForAuth((a) => a.path.endsWith('/oauth/callback'));
    expect(callback.status, 'POST /oauth/callback returned 200').toBe(200);
    await verify.shot('callback-return', {
      expected_ui_state:
        'OAuth callback completed: POST /oauth/callback 200 in auth log (page may have redirected to /)',
    });

    // Land on the dashboard for the identity probes.
    await page.waitForURL((u) => new URL(u).pathname === '/', { timeout: 30_000 });
    await page.waitForLoadState('networkidle');

    // ── Row 03: UserMenu shows a non-Guest identity ──
    const trigger = page.locator('[data-testid="user-menu-trigger"]').first();
    await expect(trigger).toBeVisible();
    const identityRow03 = (await trigger.innerText()).trim();
    expect(identityRow03, 'signed-in identity is not "Guest"').not.toBe('Guest');
    await verify.shot('identity', {
      expected_ui_state:
        'Header UserMenu shows the Google display name / masked email (NOT "Guest")',
      probe: { selector: '[data-testid="user-menu-trigger"]' },
    });

    // ── Row 04: same identity after F5; POST /refresh 200; no second anonymous ──
    const authCountBeforeReload = auth.length;
    await page.reload();
    await page.waitForLoadState('networkidle');
    await verify.shot('post-reload', {
      expected_ui_state:
        'After F5, still the same Google identity; POST /refresh 200; no new anonymous 201',
      probe: { selector: '[data-testid="user-menu-trigger"]' },
    });
    const identityRow04 = (await trigger.innerText()).trim();
    expect(identityRow04, 'identity unchanged across reload').toBe(identityRow03);
    const refreshedAfterReload = auth
      .slice(authCountBeforeReload)
      .some((a) => a.path.endsWith('/refresh') && a.status === 200);
    expect(refreshedAfterReload, 'reload restored via POST /refresh 200').toBe(true);

    // ── Row 05: signed-in Google user reaches /alerts (WI-5 gate lets them through) ──
    await page.goto('/alerts');
    await page.waitForLoadState('networkidle');
    expect(new URL(page.url()).pathname, 'authenticated user stays on /alerts').toBe(
      '/alerts'
    );
    await verify.shot('alerts-page', {
      expected_ui_state:
        'Alerts page rendered for the signed-in Google user (page_url ends /alerts)',
      probe: { selector: 'h1:has-text("Alerts")' },
    });
  });
});
