# Feature 1338: Cross-Artifact Analysis

## Consistency Check

### Spec <-> Plan Alignment

| Spec Sub-Issue | Plan Coverage | Status |
|----------------|---------------|--------|
| (a) Settings navigation: assert content not URL, fix unwind | Plan (a): content assertion + page.goto unwind | PASS |
| (b) Empty state: add waitForAuth, increase timeout | Plan (b): waitForAuth + 15s timeout | PASS |
| (c) Resolution: skip 1m | Plan (c): remove '1m' from array | PASS |
| (d) Chip remove: aria-label on component + simplified test selector | Plan (d): aria-label + getByRole direct match | PASS |
| (e) OAuth: fix mock redirect | Plan (e): sessionStorage + direct navigation | PASS |
| (f) Retry race: fix waitForResponse timing | Plan (f): setup promise before fill | PASS |
| (g) Outside click: safe coordinates | Plan (g): viewport-relative position | PASS |
| (h) Sign out: dialog-scoped confirm + animation wait | Plan (h): dialog scope + 300ms wait | PASS |
| (i) Magic link: increase timeout to 5s | Plan (i): 2_000 -> 5_000 | PASS |

### Plan <-> Tasks Alignment

| Plan Step | Task(s) | Status |
|-----------|---------|--------|
| (a) Replace URL assertion + fix unwind | T-a | PASS |
| (b) Add waitForAuth + increase timeout | T-b | PASS |
| (c) Remove '1m' from resolutions | T-c | PASS |
| (d) Add aria-label to component | T-d1 | PASS |
| (d) Simplify test selector | T-d2 | PASS |
| (e) Set sessionStorage + direct navigation | T-e | PASS |
| (f) Move waitForResponse before fill | T-f | PASS |
| (g) Use viewport-safe coordinates | T-g | PASS |
| (h) Scope to dialog + animation wait | T-h | PASS |
| (i) Increase timeout | T-i | PASS |
| Verification checks (10) | V1-V10 | PASS |

### Tasks <-> Spec Acceptance Criteria

| Acceptance Criterion | Implementing Task(s) | Status |
|---------------------|---------------------|--------|
| AC-a: Settings test passes with content assertion | T-a | COVERED |
| AC-b: Empty state test passes with waitForAuth | T-b | COVERED |
| AC-c: Resolution test passes without 1m | T-c | COVERED |
| AC-d: Chip remove test passes with aria-label | T-d1, T-d2 | COVERED |
| AC-e: OAuth test passes with direct navigation | T-e | COVERED |
| AC-f: Retry test passes with race-free wait | T-f | COVERED |
| AC-g: Outside click test passes with safe coords | T-g | COVERED |
| AC-h: Sign out test passes with scoped confirm | T-h | COVERED |
| AC-i: Magic link test passes with 5s timeout | T-i | COVERED |
| AC-10: No production changes except (d) aria-label | Only T-d1 touches production code | COVERED |

### Clarify <-> Spec Alignment

| Clarify Finding | Spec Update | Status |
|----------------|-------------|--------|
| Q1: URL DOES change, unwind is the problem | Spec (a) corrected from feature description | PASS |
| Q2: Regex matches, timing is the issue | Spec (b) identifies waitForAuth as fix | PASS |
| Q4: 302 doesn't redirect, not sessionStorage | Spec (e) corrected from feature description | PASS |
| Q5: Race condition, not auth mock ordering | Spec (f) corrected from feature description | PASS |
| Q7: Both animation and selector ambiguity | Spec (h) addresses both | PASS |

## Risk Analysis

### Identified Risks

1. **OAuth test (e) may still fail**: Direct navigation to `/auth/callback` means the
   page loads fresh. `signInWithOAuth` normally stores values before redirect, but in
   this test we call `page.evaluate` to set sessionStorage. The evaluate call runs in
   the browser context, so sessionStorage should persist across same-origin navigations.
   But if `/auth/callback` is a different Next.js route that triggers a full page load,
   sessionStorage may be read before React hydrates. Risk: LOW -- sessionStorage is
   synchronous and available immediately in `useEffect`.

2. **Outside click (g) position may hit mobile nav**: The mobile bottom nav is at the
   bottom of the viewport. Clicking at `(width/2, height-10)` in body coordinates
   (not viewport coordinates) might hit the mobile nav bar instead of empty space.
   Risk: LOW -- the Radix DropdownMenu closes on any click outside its bounds, even
   if the click hits another interactive element.

3. **Resolution test (c) reset target change**: Changing reset from `5m` to `15m`
   assumes 15m is not the currently pressed resolution after the cycle. Since the
   cycle ends at `D`, 15m should not be pressed. Risk: VERY LOW.

4. **Plan mentions cleaning up `mockOAuthRedirect` call but test imports it**: The
   test file imports `mockOAuthRedirect` from helpers. After the fix, the import
   becomes unused. This may cause lint warnings. Risk: LOW -- remove the import.

## Completeness Assessment

- **No orphan tasks**: Every task maps to a plan step and spec requirement
- **No orphan requirements**: Every spec acceptance criterion has implementing tasks
- **Dependency order valid**: Only T-d2 depends on T-d1; all others independent
- **File coverage complete**: 7 test files + 1 component file = 8 files total
- **Clarify corrections integrated**: All 5 corrected diagnoses reflected in spec and plan

## Verdict: PASS -- Ready for implementation
