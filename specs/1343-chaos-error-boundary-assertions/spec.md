# Feature 1343: Fix chaos-error-boundary.spec.ts Missing Assertions

## Status: DRAFT

## Problem Statement

`chaos-error-boundary.spec.ts` contains 3 tests (T022-T024) that validate the React
error boundary fallback. The tests have structural gaps:

1. **Missing banner-hidden assertion** (T023, line 79): A code comment says "Banner should
   no longer be visible (error boundary replaces entire dashboard content)" but NO
   assertion exists. The test checks that fallback buttons are visible but never verifies
   the banner disappeared. If the error boundary renders alongside the banner (instead of
   replacing it), the test would pass.

2. **No "Try Again" functionality test** (T022): Buttons are checked for visibility but
   not functionality. The "Try Again" button should at minimum be clickable, and ideally
   should reset the error boundary (either removing it or transitioning to a new state).

3. **File-local forceErrorBoundary()**: This helper is defined within the spec file
   (lines 25-33) but is useful for any error boundary test. It should be moved to
   chaos-helpers.ts for reuse.

4. **beforeEach uses waitForTimeout(2000)**: Should use page-ready signal.

5. **Keyboard test documents a known limitation**: The `.focus()` pattern (instead of
   Tab key) is documented as a headless Chromium limitation. This is correct and should
   be preserved, not "fixed."

## User Stories

### US-001: Banner-Hidden Assertion
**As a** chaos test author,
**I want** T023 to assert the health banner is NOT visible after the error boundary
activates,
**So that** the error boundary actually REPLACING the dashboard (not layering on top) is
verified.

### US-002: Try Again Button Functionality
**As a** chaos test author,
**I want** T022 to click "Try Again" and verify a state change occurs,
**So that** the button's functionality (not just existence) is tested.

### US-003: Shared forceErrorBoundary Helper
**As a** chaos test author,
**I want** `forceErrorBoundary()` in chaos-helpers.ts,
**So that** future error boundary tests don't duplicate the `addInitScript` pattern.

### US-004: Page-Ready beforeEach
**As a** chaos test author,
**I want** `beforeEach` to wait for page ready instead of `waitForTimeout(2000)`,
**So that** tests are deterministic and faster.

## Requirements

### Functional Requirements

| ID | Requirement | Source |
|----|-------------|--------|
| FR-001 | T023: Add `await expect(banner).not.toBeVisible({ timeout: 5000 })` after line 79 | US-001 |
| FR-002 | T022: After visibility checks, click "Try Again" and assert either error boundary disappears OR page reloads | US-002 |
| FR-003 | Move `forceErrorBoundary()` to chaos-helpers.ts and import in spec file | US-003 |
| FR-004 | `beforeEach`: Replace `waitForTimeout(2000)` with `expect(page.locator('main')).toBeVisible({ timeout: 10000 })` | US-004 |
| FR-005 | T024: Preserve `.focus()` pattern with existing documentation comment about headless Chromium | N/A (preserve) |

### Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-001 | No new dependencies added |
| NFR-002 | All 3 tests must still pass against current dashboard |
| NFR-003 | `forceErrorBoundary()` in chaos-helpers.ts must have full JSDoc |
| NFR-004 | Keyboard test behavior unchanged (focus-based, not tab-based) |

## Success Criteria

1. T023 FAILS if health banner remains visible after error boundary activates
2. T022 verifies "Try Again" button does something (not just exists)
3. `forceErrorBoundary()` importable from chaos-helpers.ts
4. T024 keyboard test unchanged (preserve documented limitation)

## Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| "Try Again" reloads the page (error boundary resets) | After click, error boundary text disappears OR page navigates |
| "Try Again" shows loading state then re-crashes | Error boundary reappears -- test should handle this gracefully |
| Error boundary renders in a portal (alongside banner) | FR-001 assertion catches this as a bug |
| forceErrorBoundary called multiple times | `addInitScript` is idempotent -- second call just adds another init script that sets the same flag |

## Out of Scope

- Changing the error boundary React component
- Testing "Reload Page" button functionality (it calls `window.location.reload()` which resets the test)
- Testing "Go Home" button navigation
- Fixing the headless Chromium Tab key limitation

---

## Appendix A: Adversarial Review #1 (Spec)

### AR1-Q1: What does "Try Again" actually do in the error boundary?
**Risk**: If "Try Again" calls `window.location.reload()`, it resets the
`__TEST_FORCE_ERROR` flag (which was set via `addInitScript`). The error boundary would
disappear because the error trigger is gone.
**Analysis**: Need to check the component. If "Try Again" reloads, the `addInitScript`
persists (addInitScript survives navigations -- it's registered on the browser context,
not the page). So the error boundary would RE-APPEAR after reload. The test should
handle this: after clicking "Try Again", either (a) error boundary disappears (component
resets without reload) or (b) error boundary reappears (page reloaded, addInitScript
fires again).

Actually, re-reading line 29-31: `addInitScript` runs before any page JS on EVERY
navigation. So if "Try Again" reloads the page, `__TEST_FORCE_ERROR` is set again, and
the error boundary fires again.

The correct test approach: click "Try Again", then check if the error boundary text is
STILL visible (if it reloaded and re-crashed) or NOT visible (if it reset without reload).
Either outcome is valid -- the test verifies the button DOES something (state change or
page reload).

**Revised approach**: After clicking "Try Again", wait briefly, then check page state.
Don't assert a specific outcome -- assert that EITHER the page reloaded (URL check) OR
the error boundary state changed.

Simpler: Just assert the click doesn't throw and the page is still functional (not
frozen). This is consistent with the test's purpose of validating recovery ACTIONS exist.
**Verdict**: ACCEPT -- click + no-throw is the right level of assertion. Add a wait
after click to confirm page didn't freeze.

### AR1-Q2: Moving forceErrorBoundary to chaos-helpers.ts -- import cycle?
**Risk**: chaos-helpers.ts is imported by all chaos specs. Adding forceErrorBoundary
there is fine unless it introduces a circular import.
**Analysis**: `forceErrorBoundary` depends only on Playwright's `Page` type which is
already imported in chaos-helpers.ts. No circular dependency.
**Verdict**: ACCEPT.

### AR1-Q3: Is FR-005 (preserve keyboard test) a requirement or non-action?
**Risk**: Listing "don't change this" as a requirement seems odd.
**Analysis**: It's explicitly called out because the audit identified `.focus()` as a
potential issue. FR-005 documents the decision NOT to change it, with rationale. This
prevents a future implementer from "fixing" something that's intentionally designed.
**Verdict**: ACCEPT -- documenting intentional non-changes is valuable.

---

## Appendix B: Clarifications

### C1: Should "Try Again" click test be in T022 or a new test?
Add it to T022 after the existing visibility assertions. T022 already tests "error
boundary fallback renders with recovery actions" -- verifying one action works is a
natural extension, not a new test case.

### C2: Does the forceErrorBoundary move require updating T023?
Yes. T023 (line 68-72) duplicates the `addInitScript + goto` pattern inline instead of
calling the file-local `forceErrorBoundary`. After the move, T023 should also import
and call the shared helper.

### C3: Is the "Go Home" button a link or button?
Line 53-55 shows it's matched as EITHER `role="link"` or `role="button"`:
```typescript
page.getByRole('link', { name: /go home/i }).or(
  page.getByRole('button', { name: /go home/i }),
)
```
T024 (line 98) uses only `role="button"`. This inconsistency exists but is out of scope
for this feature.
