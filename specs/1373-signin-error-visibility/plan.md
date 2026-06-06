# Implementation Plan: Feature 1373 — Sign-In Error Visibility

## Technical Context

| Aspect | Value |
|---|---|
| Language | TypeScript 5.x, Next.js 14 (App Router, RSC + 'use client') |
| Files touched | `frontend/src/app/auth/signin/page.tsx`, `frontend/tests/unit/signin-page.test.tsx` (new) |
| Error class | `ApiClientError` from `@/lib/api/client` (status, code, message, details) |
| Test framework | Vitest (unit), Playwright (E2E — assertions only, no new tests) |
| Bundle impact | Negligible (≤200B added — one boolean state, one conditional render branch) |
| A11y | New element uses `role="status"` + `aria-live="polite"`, hardcoded text |

## Architecture Decisions

### AD1: Log `status` and `code`, NOT `message`

**Decision**: `console.error('[signin] OAuth providers fetch failed', {url, status, code})` — exclude `message` and `details` from the log.
**Why**: The backend may legitimately put context in `message` (e.g., "rate limited, retry in 30s") that's user-safe but could grow over time to include things like internal hostnames or stack traces. Logging only `status + code` is constant-shape and safe regardless of backend evolution.
**Alternatives**: Log everything including `message` and `details` — richer triage, larger leak surface.
**Source**: OWASP A09 (Security Logging and Monitoring Failures), specifically the "log enough but not too much" guidance.

### AD2: Distinguish failure from success-with-empty via separate state

**Decision**: New `providersFetchFailed: boolean` state, set true ONLY in catch.
**Alternatives**:
- Sentinel value (e.g., `availableProviders === null` for failure, `[]` for empty): saves a state slot but conflates absence and failure.
- Tagged union (`{state: "loading"} | {state: "error"} | {state: "loaded", providers: string[]}`): cleaner but requires refactoring three useState calls into one.
**Why**: Minimal change to existing component shape. Tagged union is the right long-term refactor but out of scope.

### AD3: Hint as inline text, not toast

**Decision**: Inline muted text above the magic-link form.
**Alternatives**: Toast (sonner is already a repo dep), inline alert with icon, banner above the entire card.
**Why**: A toast on page load is annoying. An alert with icon implies severity higher than "OAuth degraded." Inline muted text is the lightest-touch and matches the existing visual hierarchy of the sign-in card.

### AD4: No retry, no exponential backoff

**Decision**: Single fetch attempt on mount. No retry button. Refresh = retry.
**Why**: This isn't a transient-network use case the user can do anything about. Adding retry UI ups complexity without clear UX win. The user's path forward is "use email."

## Data Model

No external data model changes. Internal component state:

```typescript
const [availableProviders, setAvailableProviders] = useState<string[]>();
const [providersLoaded, setProvidersLoaded] = useState(false);
const [providersFetchFailed, setProvidersFetchFailed] = useState(false);  // new
```

## Contracts

No API contract changes.

## Constitution / Quality Gates

| Gate | Status |
|---|---|
| GPG-signed commits | Required. |
| `npm run typecheck` (frontend) | Must pass. |
| `npm test` (frontend Vitest) | Must pass; new test added. |
| `npm run test:e2e` against this page | Must pass; no new E2E tests required (existing tests cover the visible behavior). |
| `make validate` (Bandit, Semgrep) | Must pass. Frontend changes don't trigger SAST in this repo. |
| Bundle size | Negligible delta. No new deps. |
| A11y | Hint includes `role="status"` and `aria-live="polite"`. Existing `axe-core` checks (if any in this repo) should pass. |

## Implementation Steps

1. Add `providersFetchFailed: boolean` state to `SignInPage`.
2. Modify catch block:
   - `} catch (err: unknown) { ... }`
   - Extract `status` and `code` if `err instanceof ApiClientError`; else mark as `status: undefined, code: 'NETWORK'`.
   - `console.error('[signin] OAuth providers fetch failed', {url: '/api/v2/auth/oauth/urls', status, code})`.
   - `setProvidersFetchFailed(true)` + existing `setAvailableProviders([])`.
3. Add the hint render block:
   ```tsx
   {providersLoaded && providersFetchFailed && (
     <p role="status" aria-live="polite" className="text-xs text-muted-foreground text-center">
       Some sign-in options are temporarily unavailable. You can still sign in with email.
     </p>
   )}
   ```
   Position: between the OAuth block and the magic-link form (or above magic-link form when OAuth block hidden).
4. Add unit test `frontend/tests/unit/signin-page.test.tsx` covering:
   - Success with providers → no console.error, no hint, OAuth buttons rendered.
   - Success with empty providers → no console.error, no hint, no OAuth buttons.
   - `ApiClientError` thrown → console.error called with `{status, code}`, hint renders.
   - Network error (TypeError) thrown → console.error called with `{status: undefined, code: 'NETWORK'}`, hint renders.
5. Run `npm run typecheck && npm test` from `frontend/`.
6. Manual smoke against local dev (block the `/urls` request via DevTools network throttling) to confirm console output and hint render.

## Adversarial Review #2

**Reviewer**: Self (cross-artifact, drift detection)
**Date**: 2026-04-29

### Drift between Stage 1 (spec) and Stage 3 (plan)

| Drift | Resolution |
|---|---|
| Spec R1 logs `error: err.message`. Plan AD1 changes this to `status + code` only. | **Drift**. Spec must be updated to match plan. Updating spec R1 below. |
| Spec mentions `cause: err instanceof Error ? err.cause : undefined` in R1. Plan drops this. | **Drift**. Same root cause as above (avoid leaking internals). Updating spec. |
| Spec edge cases say `aria-live="polite"`; AR#1 LOW says `aria-live="off"` would also be acceptable. Plan locks to `polite`. | Aligned to plan; clarification C1 below documents the choice. |

### Cross-artifact inconsistencies

| Inconsistency | Resolution |
|---|---|
| Spec hint text says "Some sign-in options are temporarily unavailable." Plan step 3 has the same text + "You can still sign in with email." | Plan version is preferred. Updating spec R3 to use the longer text (it was already there, just confirming). |

### Spec edits made in response to drift

- **Spec R1**: Replace the catch block snippet with one that uses `if (err instanceof ApiClientError) { status, code } else { 'NETWORK' }` and logs only `status + code`. Drop `error.message` and `cause`.

(Note: the spec.md AR#1 HIGH #1 explicitly deferred the leak decision to clarification — that's now resolved here in AR#2/C1 by adopting the more-conservative AD1.)

### Gate

**0 CRITICAL, 0 HIGH remaining.** Spec drift on log payload shape is reconciled by adopting plan AD1.

## Clarifications

### C1: What shape is `err` in the catch block? (resolves spec AR#1 HIGH #1)

**Answer**: `err` from `authApi.getOAuthUrls()` is one of:
- `ApiClientError` — if the response was non-2xx; carries `{status: number, code: string, message: string, details?: object}`. Source: `frontend/src/lib/api/client.ts:handleResponse`.
- `TypeError` — if `fetch` itself rejected (network down, CORS preflight failed, DNS failure). Standard browser error.
- Other Error subclasses — exotic (e.g., `AbortError` if a future timeout is added).

**Decision**: Log `{status, code}` only. For `TypeError`, both fields are `undefined`/`'NETWORK'`. This is enough for triage without leaking backend `message` content.

**Evidence**: Read `frontend/src/lib/api/client.ts` — `ApiClientError` constructor takes `(status, code, message, details)`. Backend errors flow into these fields via the JSON body (`errorBody.code`, `errorBody.message`).

### C2: `aria-live="polite"` vs `"off"`

**Question**: Should screen readers announce the hint?
**Answer**: `polite`. The hint conveys actionable info ("you should use email instead"). Announcing it helps the user understand why the page differs from the docs/marketing.
**Evidence**: WCAG 2.1 SC 4.1.3 (Status Messages) — "polite" matches the role of a live region updating with non-critical status info.

### C3: Where does the hint render relative to the OAuth block and the magic-link form?

**Question**: Spec says "above the magic-link form." But the OAuth block is conditionally rendered above magic-link too. Stack order matters.

**Answer**: When `hasOAuthProviders && providersFetchFailed` is logically impossible (failure → empty providers → no OAuth block). So the hint always renders directly above the magic-link form when present. No collision.

**Evidence**: `setProvidersFetchFailed(true)` only fires alongside `setAvailableProviders([])`. The OAuth block requires `availableProviders.length > 0`. Mutually exclusive.

### C4: Do existing E2E tests assert "no error in console" semantics?

**Question**: If we add a `console.error`, will any existing Playwright test fail because it asserts "console is clean"?

**Self-answer attempt**: Searched `frontend/tests/e2e/` for `page.on('console')` listeners that fail on errors. Some tests in this repo (e.g., `signin-interaction.spec.ts`) use `page.on('console')` for assertion (per Feature 1226 the codebase relies on console events for FE error visibility). Need to verify whether any test treats `console.error` as a hard failure.

**Evidence**: Will be verified during Stage 7 task `Verify no Playwright console.error guards exist`. Most likely: zero such guards, since Feature 1226 specifically standardized `console.error` as the error-visibility mechanism (see comment in `client.ts` referencing 1226).

**Conclusion**: Treat as a verification step in Stage 7. If a guard exists, the fix is one selector update.

### C5: Is `providersFetchFailed` worth a separate state, or can we infer from `availableProviders === undefined` post-load?

**Question**: Could we infer failure as `providersLoaded && availableProviders === undefined`?

**Answer**: No. Both branches set `availableProviders` to `[]` (success-empty) or `[]` (failure). They look identical without the flag. The flag is the cheapest carrier for the distinction.

**Conclusion**: Keep `providersFetchFailed`. Future refactor to discriminated union is fine but out of scope.
