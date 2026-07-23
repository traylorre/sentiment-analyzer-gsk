// Target: Customer Dashboard (Next.js/Amplify)
/**
 * M1 WI-3: guest session with restore across reload.
 * M1 WI-5: guest gated off /alerts client-side (step 04, Q-M1-2 resolved).
 *
 * Canonical rows auth-guest-01..04 (docs/cleanup-pristine/m1-verifier-convention.md).
 * The core claim is negative-space: a reload must NOT mint a second anonymous
 * user (forbidden_requests), and MUST restore via POST /refresh 200.
 *
 * user_id equality across the reload is asserted from the auth response
 * bodies observed via a response LISTENER (allowed; route() interception is
 * banned and detected). The verifier cross-checks these from the raw
 * Playwright trace per the convention's spot-check procedure.
 */
import { test, expect } from './helpers/verification';

test.describe('auth-guest: session with restore', () => {
  test('guest session survives reload without minting a second user', async ({
    page,
    verify,
  }) => {
    verify.forbid({
      method: 'POST',
      path: '/api/v2/auth/anonymous',
      status: 201,
      max_count: 1,
    });

    // Observe auth response bodies (listener only, no interception).
    const authBodies: Array<{ path: string; user_id?: string }> = [];
    page.on('response', (r) => {
      let pathname: string;
      try {
        // Normalize stage prefixes (API Gateway paths are /{stage}/api/v2/...)
        const raw = new URL(r.url()).pathname;
        const apiIdx = raw.indexOf('/api/');
        pathname = apiIdx !== -1 ? raw.slice(apiIdx) : raw;
      } catch {
        return;
      }
      if (
        pathname === '/api/v2/auth/anonymous' ||
        pathname === '/api/v2/auth/refresh'
      ) {
        r.json()
          .then((body: { user_id?: string }) =>
            authBodies.push({ path: pathname, user_id: body.user_id })
          )
          .catch(() => authBodies.push({ path: pathname }));
      }
    });

    // ── Step 1: cold load mints exactly one anonymous session ──
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await verify.shot('landing', {
      expected_ui_state:
        'Header UserMenu shows Guest; anonymous 201 in auth log',
      probe: {
        selector: '[data-testid="user-menu-trigger"]',
        expect_text: 'Guest',
      },
    });

    // ── Step 2: open menu (session chip + sign-in upsell) ──
    await page
      .locator('[data-testid="user-menu-trigger"]:visible')
      .first()
      .click();
    await page.waitForTimeout(300); // menu animation settle
    await verify.shot('menu-open', {
      expected_ui_state:
        'Open user menu: Guest identity + anonymous "Sign in with email" upsell (session chip lives in the header)',
      probe: { selector: 'text=Sign in with email' },
    });
    await page.keyboard.press('Escape');

    // ── Step 3: reload restores the SAME session via /refresh ──
    await page.reload();
    await page.waitForLoadState('networkidle');
    await verify.shot('post-reload', {
      expected_ui_state:
        'Still Guest after F5; refresh 200 in auth log; no second anonymous 201',
      probe: {
        selector: '[data-testid="user-menu-trigger"]',
        expect_text: 'Guest',
      },
    });

    // ── Step 4 (M1 WI-5, Q-M1-2): guest bounced off /alerts client-side ──
    // Middleware gating was stripped; ProtectedRoute (requireUpgraded) in the
    // alerts layout redirects via router.replace, so the guest lands on
    // /auth/signin?redirect=%2Falerts&upgrade=true. No backend leg involved.
    await page.goto('/alerts');
    await page.waitForURL('**/auth/signin**');
    await page.waitForLoadState('networkidle');
    await verify.shot('alerts-redirect', {
      expected_ui_state:
        'Guest redirected off /alerts to signin; page_url has redirect=%2Falerts and upgrade=true',
      probe: { selector: '[data-testid="signin-heading"]' },
    });
    const redirectedUrl = new URL(page.url());
    expect(redirectedUrl.pathname, 'guest lands on signin, not /alerts').toBe(
      '/auth/signin'
    );
    expect(redirectedUrl.searchParams.get('redirect')).toBe('/alerts');
    expect(redirectedUrl.searchParams.get('upgrade')).toBe('true');

    // Assertions (necessary, never sufficient - attestation is the gate):
    const minted = authBodies.filter((b) => b.path.endsWith('/anonymous'));
    const refreshed = authBodies.filter((b) => b.path.endsWith('/refresh'));
    expect(minted, 'exactly one anonymous session minted').toHaveLength(1);
    expect(
      refreshed.length,
      'reload restored via POST /refresh'
    ).toBeGreaterThanOrEqual(1);
    expect(
      refreshed[refreshed.length - 1].user_id,
      'restored session has the SAME user_id as the minted one'
    ).toBe(minted[0].user_id);
  });
});
