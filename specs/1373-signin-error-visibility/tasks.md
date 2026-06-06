# Tasks: Feature 1373 — Sign-In Error Visibility

**Plan**: [plan.md](plan.md)
**Spec**: [spec.md](spec.md)

## Phase 1: Component Changes

- [ ] **T1**: Add `providersFetchFailed: boolean` state (default false) to
  `SignInPage` in `frontend/src/app/auth/signin/page.tsx`.
  - **Maps to**: spec R2, plan AD2
  - **Deps**: none

- [ ] **T2**: Update the catch block to:
  - Use `} catch (err: unknown) { ... }`.
  - Discriminate `err instanceof ApiClientError` to extract `status` and `code`.
  - For non-`ApiClientError`: `status = undefined`, `code = 'NETWORK'`.
  - Call `console.error('[signin] OAuth providers fetch failed', {url, status, code})` — log nothing else.
  - Call `setProvidersFetchFailed(true)` alongside the existing `setAvailableProviders([])`.
  - Import `ApiClientError` from `@/lib/api/client`.
  - **File**: `frontend/src/app/auth/signin/page.tsx`
  - **Maps to**: spec R1, plan AD1
  - **Deps**: T1

- [ ] **T3**: Add the hint render block between the OAuth block (or where it
  would have been) and the magic-link form:
  ```tsx
  {providersLoaded && providersFetchFailed && (
    <p role="status" aria-live="polite" className="text-xs text-muted-foreground text-center">
      Some sign-in options are temporarily unavailable. You can still sign in with email.
    </p>
  )}
  ```
  - **File**: `frontend/src/app/auth/signin/page.tsx`
  - **Maps to**: spec R3
  - **Deps**: T1

## Phase 2: Tests

- [ ] **T4**: Create `frontend/tests/unit/signin-page.test.tsx`. Cover four
  scenarios:
  - **Scenario A**: `getOAuthUrls` resolves with `{providers: {google: {...}, github: {...}}}` — assert OAuth buttons render, no `console.error`, no hint.
  - **Scenario B**: `getOAuthUrls` resolves with `{providers: {}}` — assert OAuth buttons NOT rendered, no `console.error`, no hint.
  - **Scenario C**: `getOAuthUrls` rejects with `new ApiClientError(500, 'INTERNAL', 'oops')` — assert `console.error` called with `{status: 500, code: 'INTERNAL'}`, hint renders, magic-link form still rendered.
  - **Scenario D**: `getOAuthUrls` rejects with `new TypeError('Failed to fetch')` — assert `console.error` called with `{status: undefined, code: 'NETWORK'}`, hint renders.
  - Mock `console.error` via `vi.spyOn`; restore after each test.
  - Mock `authApi.getOAuthUrls` per scenario.
  - **File**: `frontend/tests/unit/signin-page.test.tsx`
  - **Maps to**: spec success metric #5, plan step 4
  - **Deps**: T1, T2, T3

- [ ] **T5**: Verify no existing Playwright test in `frontend/tests/e2e/`
  asserts "console is clean" or fails on `console.error` events that would
  trigger on the sign-in page. Search:
  ```
  grep -rn "page.on('console'" frontend/tests/e2e/
  ```
  - For each match, check whether it filters by message prefix. If any
    treats unfiltered `console.error` as failure on the sign-in page, fix
    the selector or add a `[signin]` prefix exclusion.
  - **File**: read-only, possibly minor edits
  - **Maps to**: plan C4
  - **Deps**: T2 (the new console.error must exist before checking)

## Phase 3: Verification

- [ ] **T6**: Run `cd frontend && npm run typecheck`. Must pass.
  - **Deps**: T2, T3

- [ ] **T7**: Run `cd frontend && npm test -- signin-page`. New unit test
  must pass. No existing unit tests should fail.
  - **Deps**: T4

- [ ] **T8**: Run `cd frontend && npm run test:e2e -- signin auth oauth-flow magic-link`.
  All listed E2E specs must pass (or remain at the same skip count as
  before this feature).
  - **Deps**: T5

- [ ] **T9**: Manual smoke against local dev:
  - Start `npm run dev` and the local API.
  - Block `/api/v2/auth/oauth/urls` via DevTools Network → "Block request URL."
  - Reload `/auth/signin`. Assert: console error logged with `[signin]`
    prefix, hint renders, magic-link form works.
  - Unblock. Reload. Assert: hint disappears (success-empty path is
    silent, no false positives).
  - **Deps**: T2, T3

## Phase 4: PR

- [ ] **T10**: Open PR titled `feat(1373): sign-in OAuth error visibility`.
  - Body: link to spec.md, plan.md. Include before/after screenshot pair
    of the hint state.
  - GPG-signed commits.
  - **Deps**: T1-T9

## Adversarial Review #3

**Reviewer**: Self (implementation readiness, risk assessment)
**Date**: 2026-04-29

### Coverage check

| Requirement | Mapped Tasks |
|---|---|
| R1 (catch + log) | T2 |
| R2 (separate state flag) | T1 |
| R3 (render hint) | T3 |
| R4 (preserve graceful degradation) | T8 (E2E regression check), T4 scenarios A and B |

All requirements have ≥1 mapped task. ✓

### Highest-risk task

**T2** — the catch block rewrite. Risks:
1. Forgetting to import `ApiClientError` (TypeScript will catch this).
2. Inverting the boolean (e.g., `setProvidersFetchFailed(false)` in catch).
   T4 scenario C catches this.
3. Logging additional fields by accident (e.g., a leftover `error: err.message`).
   Reviewer should diff against plan AD1.

### Most likely source of rework

**T5 / C4 verification**. If a Playwright test in this repo currently
asserts `console.error` count == 0 on the sign-in page, this feature breaks
it. Fix is a selector update — 5 minutes — but if the fix is non-obvious
(e.g., a global `page.on('console')` in a setup file), it could grow.

Less likely but possible rework: **A11y team feedback on `aria-live="polite"`**.
If the team prefers `role="alert"` (assertive) for transient outages, the
hint announces immediately on render. Plan C2 documents the choice as
WCAG-aligned, so push back unless there's a specific failure mode.

### Failure modes (3am production check)

- **Backend returns 200 with `{providers: null}`**: `Object.keys(null)` throws
  → caught → hint renders. Acceptable. (Should not happen — backend always
  returns an object.)
- **`ApiClientError` shape changes**: TypeScript catches this if the import
  changes. Runtime safe due to `instanceof` check.
- **Logging is disabled in production**: many production sites strip
  `console.*` via webpack/Vite plugins. Verify Next.js doesn't strip. If it
  does, the log is silent in prod — but the hint still renders, which is the
  user-facing signal. Operator triage in prod would rely on the hint visually.
  Acceptable.
- **CSP `default-src 'none'`**: doesn't affect `console.error`. Safe.

### Cross-feature impact

This feature is orthogonal to 1370/1371/1372. Shipping 1373 first (before
provisioning) means:
- During the gap, every user load of the sign-in page logs the
  "providers fetch failed" error to console — assuming the backend returns a
  successful empty `{providers: {}}` response, this is the success path and
  does NOT log. **Verified safe**: backend's `get_oauth_urls()` returns 200
  with empty object, not an error, when env var is empty.

### Gate

**READY FOR IMPLEMENTATION.**
0 CRITICAL, 0 HIGH unresolved.
