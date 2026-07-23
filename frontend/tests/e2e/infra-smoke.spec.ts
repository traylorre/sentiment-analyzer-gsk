// Target: Customer Dashboard (Next.js/Amplify)
/**
 * WI-1 evidence-pipeline smoke test (Milestone 1).
 *
 * Proves the verification fixture works end to end against the real target:
 * named screenshots, manifest with auth request log (2xx included),
 * forbidden_requests evaluation, and interception detection. Deliberately
 * makes NO feature claims about auth; that is WI-3/WI-6 territory.
 */
import { test, expect } from './helpers/verification';

test.describe('infra-smoke: verification evidence pipeline', () => {
  test('landing page produces sealed evidence artifacts', async ({
    page,
    verify,
  }) => {
    // Negative-space demo rule: a single cold load must not mint more than
    // one anonymous session. (WI-3 will tighten this across reloads.)
    verify.forbid({
      method: 'POST',
      path: '/api/v2/auth/anonymous',
      status: 201,
      max_count: 1,
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await verify.shot('landing', {
      expected_ui_state:
        'Dashboard landing page rendered: header visible, no raw error page',
      probe: { selector: 'header' },
    });

    // The smoke test only asserts the pipeline itself functions; the page
    // rendered something (probe result and screenshot carry the evidence).
    expect(page.url()).toBeTruthy();
  });
});
