# AR#1: Adversarial Review of spec.md

## Attack Vectors

### AV1: Deleting SSE tests hides real reconnection bugs
**Attack**: The spec proposes deleting 8 tests across 2 files. SSE reconnection is a
critical resilience feature — users on flaky mobile connections depend on it. Deleting
these tests means reconnection regressions go undetected until production incidents.

**Assessment**: VALID CONCERN but ACCEPTED RISK. The spec correctly identifies that
these tests are the wrong type (E2E) for the behavior they test (client-side reconnection
logic). The reconnection logic is in `use-sse.ts` and `sse-connection.ts` — pure TypeScript
functions that can be unit tested with mock EventSource/fetch. E2E route intercepts are
inappropriate for testing timing-sensitive reconnection because:
1. Playwright's route intercept doesn't simulate real SSE connection drops
2. The 120s timeout per test makes CI feedback loops unacceptable
3. The tests never fire because SSE requires auth + active config

**Verdict**: PASS. The spec acknowledges R1 (reconnection untested) and calls for a
follow-up feature. The deletion is correct.

### AV2: "Fix auth timing" is hand-wavy
**Attack**: FR-003 says "use addInitScript to pre-seed the auth store" but doesn't
specify HOW. The auth store is a Zustand store. Pre-seeding it from `addInitScript`
requires knowing the store's internal structure and the window property it reads from.

**Assessment**: VALID. The spec should be more specific about the mechanism. Two options:
1. `addInitScript` sets `window.__MOCK_AUTH_TOKEN = 'mock-test-token'` and
   `useSessionInit()` checks this before calling the API
2. `addInitScript` directly calls the store's `setTokens()` — but Zustand stores aren't
   available in `addInitScript` (runs before React loads)

Option 1 requires production code changes (adding the window check to `useSessionInit`).
Option 2 is impossible.

The REAL fix is simpler: ensure `mockTickerDataApis()` is called before `page.goto('/')`.
It already is. The race is: Next.js loads -> React mounts -> `useSessionInit` fires
`POST /api/v2/auth/anonymous` -> Playwright's route intercept catches it -> mock response
returned -> auth store updated -> `hasAccessToken` becomes true -> queries fire.

This should work. If it doesn't, the issue is that `page.route()` registration hasn't
completed before the page starts loading. Fix: add `await page.goto('/', { waitUntil: 'commit' })`
or ensure all routes are registered before goto.

**Verdict**: NEEDS CLARIFICATION in plan. The fix mechanism must be validated in Stage 4.

### AV3: A11y violations assumed to be scanner noise
**Attack**: The spec says "if color contrast violations on known-good amber/red UI, add
axe rule exclusions." This is dangerous — assuming violations are false positives without
running the scanner first is how real a11y bugs get shipped.

**Assessment**: VALID. The spec correctly says "run locally, capture axe output" in FR-004.
The language should not pre-assume the violations are noise. Plan should include: run test,
capture violations, triage each one, then decide fix vs exclude.

**Verdict**: PASS with NOTE. The plan must include explicit triage of axe findings.

### AV4: T038-T040 are NOT SSE-prerequisite tests
**Attack**: FR-001 says "delete the file entirely" for chaos-sse-recovery.spec.ts, which
includes T038-T040. But T038 (SSE drop before first data), T039 (navigation during
reconnection), and T040 (overlapping chaos) all use `page.route('**/api/v2/stream**')`
to BLOCK SSE, not to WAIT for SSE. They should work even without an active SSE connection
because they're testing that the dashboard handles blocked SSE gracefully.

**Assessment**: PARTIALLY VALID. Let me re-read:
- T038: Aborts all SSE, reloads, checks "not error boundary" — this test works IF the
  dashboard loads without SSE. It doesn't depend on SSE connecting first.
- T039: Aborts SSE, navigates to /settings, checks no new SSE requests — this also
  doesn't require SSE to be active first.
- T040: Blocks SSE + all APIs, triggers health banner — this is actually testing the
  health banner, not SSE specifically.

However, all three route on `**/api/v2/stream**`. If the frontend never requests this
path (because no config is selected), the route intercept is irrelevant and the test
either passes vacuously or tests something unrelated.

T038 checks `page.getByText(/something went wrong/i)` is NOT visible — this passes
whether SSE exists or not.
T039 checks SSE request count <= 2 after nav — if no SSE requests are made at all, this
passes vacuously.
T040 checks health banner is visible — this works because it blocks `**/api/**` which
catches search API calls, not SSE.

**Verdict**: T038 and T039 are VACUOUS TESTS (pass trivially because the precondition is
never met). T040 is actually a health banner test that happens to also block SSE. The spec
should note that T038/T039 are vacuous and should still be deleted.

T040's test of "both health banner and SSE error coexist" is only meaningful when SSE is
active. Without SSE, it's just testing the health banner alone, which is covered by
`chaos-scenarios.spec.ts` and `error-visibility-banner.spec.ts`.

**Updated verdict**: PASS. Delete the entire file. T038-T040 are either vacuous or
duplicative.

### AV5: Deleting files loses test IDs
**Attack**: Tests T032-T040 are referenced in Feature 1265 specs. Deleting the files
breaks traceability.

**Assessment**: MINOR. NFR-002 addresses this by requiring documentation. The spec IDs
should be noted as "deleted, rationale: wrong test type" in the 1265 spec directory.

**Verdict**: PASS.

## Summary

| Vector | Severity | Verdict |
|--------|----------|---------|
| AV1: SSE untested | Medium | PASS (acknowledged risk, follow-up needed) |
| AV2: Auth fix unclear | Medium | NEEDS CLARIFICATION (Stage 4) |
| AV3: A11y assumptions | Low | PASS with NOTE |
| AV4: T038-T040 scope | Low | PASS (vacuous or duplicative) |
| AV5: Test ID traceability | Low | PASS (NFR-002 covers) |

## Disposition: PROCEED to Stage 3 with clarification on auth fix mechanism in Stage 4.
