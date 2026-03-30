# Implementation Plan: Accessibility Timing Audit

**Branch**: `1272-a11y-timing-audit` | **Date**: 2026-03-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1272-a11y-timing-audit/spec.md`

## Summary

Fix ARIA attribute assertion race conditions and replace `waitForTimeout()` blind waits with event-based waiting in 5 Playwright E2E test files plus the shared `triggerHealthBanner()` helper. The race condition occurs when `toHaveAttribute('aria-live')` or `toHaveAttribute('aria-pressed')` runs immediately after `toBeVisible()` before the browser's accessibility tree has stabilized. The fix adds explicit `{ timeout: 3000 }` to ARIA assertions and replaces all blind waits in the affected files with Playwright's built-in event-based waiting (waitForResponse, waitForLoadState, expect with timeout).

## Technical Context

**Language/Version**: TypeScript (Playwright test files targeting Node.js 18+)
**Primary Dependencies**: `@playwright/test ^1.57.0`, `@axe-core/playwright` (in chaos-accessibility.spec.ts)
**Storage**: N/A (test infrastructure only)
**Testing**: Playwright Test runner (`npx playwright test`)
**Target Platform**: CI runners (GitHub Actions) and local dev machines
**Project Type**: Web application (frontend E2E tests)
**Performance Goals**: Tests should be equal or faster than current blind-wait baseline
**Constraints**: Must work across all 5 Playwright projects (Mobile Chrome, Mobile Safari, Desktop Chrome, Firefox, WebKit)
**Scale/Scope**: 5 test files + 1 shared helper, ~35 `waitForTimeout` replacements + ~8 ARIA assertion timeout additions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Unit test accompaniment | N/A | This IS a test fix -- no application code changes |
| GPG-signed commits | PASS | Will use `git commit -S` |
| Pipeline bypass prohibition | PASS | No bypasses planned |
| Feature branch workflow | PASS | On branch `1272-a11y-timing-audit` |
| Environment testing matrix | PASS | E2E tests run in preprod per constitution |
| Local SAST | N/A | No Python code changes |
| Deterministic time handling | N/A | No time-dependent logic |
| Tech debt tracking | PASS | This feature reduces tech debt (removes blind waits) |

**Verdict**: PASS -- all applicable gates satisfied. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/1272-a11y-timing-audit/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── spec.md              # Feature specification
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (files to modify)

```text
frontend/tests/e2e/
├── chaos-degradation.spec.ts      # 7 waitForTimeout + 1 ARIA race
├── error-visibility-banner.spec.ts # 19 waitForTimeout + 1 ARIA race
├── chaos-cross-browser.spec.ts    # 3 waitForTimeout + 1 ARIA race
├── chaos-accessibility.spec.ts    # 3 waitForTimeout (no ARIA race -- fixed by 1270)
├── sanity.spec.ts                 # 0 waitForTimeout + 5 ARIA races
└── helpers/
    └── chaos-helpers.ts           # 3 waitForTimeout in triggerHealthBanner()
```

**Structure Decision**: No new files or directories. All changes are edits to existing test files.

## Phase 0: Research

### R1: Playwright Event-Based Wait Patterns

**Decision**: Use these replacement patterns for each `waitForTimeout` context:

| Current Pattern | Context | Replacement |
|----------------|---------|-------------|
| `waitForTimeout(2000)` after `page.goto('/')` | React hydration | `page.waitForLoadState('networkidle')` |
| `waitForTimeout(1500)` after `searchInput.fill('X')` | Wait for API response | `page.waitForResponse(resp => resp.url().includes('/api/') && resp.status() !== 0)` or wrapping the fill + response wait in `Promise.all` |
| `waitForTimeout(1500)` between search interactions | Debounce + API call | `page.waitForResponse()` on the API route handler fulfillment |
| `waitForTimeout(2000)` after recovery action | Wait for banner state change | `expect(banner).not.toBeVisible({ timeout: 5000 })` (already present in some tests) |
| `waitForTimeout(1000)` after error boundary trigger | React re-render | `expect(page.getByText(...)).toBeVisible({ timeout: 5000 })` (already present after the wait) |
| `waitForTimeout(5000)` for SSE reconnection | Timer-based reconnection | `expect.poll(() => sseRequests.length, { timeout: 10000 }).toBeGreaterThanOrEqual(2)` |

**Rationale**: Playwright's auto-waiting and `expect` retries are designed for exactly these scenarios. `waitForResponse` is the most precise replacement for "wait for API call to complete" patterns.

**Alternatives considered**:
- `page.waitForSelector()` -- too low-level, prefer `expect(locator)` API
- Custom polling loops -- unnecessary when `expect.poll()` exists
- Increasing blind wait times -- defeats the purpose entirely

### R2: ARIA Assertion Timeout Pattern

**Decision**: Add `{ timeout: 3000 }` as the last argument to `toHaveAttribute()` calls that follow visibility checks.

**Rationale**: Playwright's `toHaveAttribute` has a default timeout (5000ms in most configs), but when checking attribute existence (not value), the behavior differs. The explicit `{ timeout: 3000 }` ensures the assertion retries for up to 3 seconds, which is sufficient for accessibility tree stabilization across all browsers.

**Key insight**: `toHaveAttribute('aria-pressed')` (existence check) may NOT auto-retry in the same way as `toHaveAttribute('aria-pressed', 'true')` (value check). The explicit timeout ensures both patterns behave consistently.

### R3: triggerHealthBanner() Refactoring Strategy

**Decision**: Replace the 3 `waitForTimeout(1500)` calls between search interactions with `waitForResponse()` that waits for the route handler to fulfill each request.

**Rationale**: The helper blocks all API calls with `page.route('**/api/**', ...)`. When `searchInput.fill('X')` triggers a React Query fetch, the route handler immediately fulfills with a 503. We can wait for that response instead of a blind 1500ms delay.

**Risk**: The `page.route()` handler fulfills synchronously, so `waitForResponse` should resolve almost immediately. If the search debounce (500ms) delays the actual request, the response wait handles that naturally.

### R4: Regression Risk for triggerHealthBanner() Callers

**Decision**: After modifying `triggerHealthBanner()`, run the full E2E suite to verify no regressions.

**Callers of triggerHealthBanner()**:
1. `chaos-degradation.spec.ts` (in scope)
2. `chaos-cross-browser.spec.ts` (in scope)
3. `chaos-accessibility.spec.ts` (in scope)
4. `chaos-error-boundary.spec.ts` (out of scope -- regression test only)

## Phase 1: Design

### Replacement Patterns by File

#### chaos-helpers.ts (triggerHealthBanner)

Current:
```typescript
await searchInput.fill('AAPL');
await page.waitForTimeout(1500);
```

After:
```typescript
await Promise.all([
  page.waitForResponse(resp => resp.url().includes('/api/') && resp.status() === 503),
  searchInput.fill('AAPL'),
]);
```

This waits for the route-intercepted 503 response that proves the search triggered the API call and the failure was recorded.

#### chaos-degradation.spec.ts

| Line(s) | Current | Replacement |
|---------|---------|-------------|
| 27 | `waitForTimeout(2000)` in beforeEach | `page.waitForLoadState('networkidle')` |
| 42 | `toHaveAttribute('aria-live', 'assertive')` | Add `{ timeout: 3000 }` |
| 132, 137 | `waitForTimeout(1500)` after search fill | `waitForResponse` pattern |
| 175, 180, 185 | `waitForTimeout(1500)` after search fill | `waitForResponse` pattern |
| 226 | `waitForTimeout(2000)` after recovery fill | `waitForResponse` on success route |

#### error-visibility-banner.spec.ts

| Line(s) | Current | Replacement |
|---------|---------|-------------|
| 41, 93, 141, 179, 202 | `waitForTimeout(2000)` after goto | `page.waitForLoadState('networkidle')` |
| 50/55/60, 98/101/104, 146/149/152, 207/210/213, 257/262 | `waitForTimeout(1500)` after search fill | `waitForResponse` pattern |
| 222 | `toHaveAttribute('aria-live', 'assertive')` | Add `{ timeout: 3000 }` |

#### chaos-cross-browser.spec.ts

| Line(s) | Current | Replacement |
|---------|---------|-------------|
| 22 | `waitForTimeout(2000)` in beforeEach | `page.waitForLoadState('networkidle')` |
| 30 | `toHaveAttribute('aria-live', 'assertive')` | Add `{ timeout: 3000 }` |
| 40 | `waitForTimeout(2000)` after blockAllApi | `expect(locator).not.toBeVisible()` or `waitForLoadState` |
| 64 | `waitForTimeout(5000)` for SSE reconnection | `expect.poll(() => sseRequests.length, { timeout: 10000 }).toBeGreaterThanOrEqual(2)` |

#### chaos-accessibility.spec.ts

| Line(s) | Current | Replacement |
|---------|---------|-------------|
| 20 | `waitForTimeout(2000)` in beforeEach | `page.waitForLoadState('networkidle')` |
| 63 | `waitForTimeout(1000)` after error trigger | Remove -- the `toBeVisible({ timeout: 5000 })` on line 65-67 already waits |
| 97 | `waitForTimeout(1000)` after error trigger | Remove -- the `toBeVisible({ timeout: 5000 })` on line 100-102 already waits |

#### sanity.spec.ts

| Line(s) | Current | Replacement |
|---------|---------|-------------|
| 176 | `toHaveAttribute('aria-pressed', 'true')` after `toBeVisible()` | Add `{ timeout: 3000 }` |
| 185 | `toHaveAttribute('aria-pressed', 'true')` after `toBeVisible()` | Add `{ timeout: 3000 }` |
| 790 | `toHaveAttribute('aria-pressed')` after `toBeVisible()` | Add `{ timeout: 3000 }` |
| 805 | `toHaveAttribute('aria-pressed')` after `toBeVisible()` | Add `{ timeout: 3000 }` |
| 806 | `toHaveAttribute('aria-pressed')` after `toBeVisible()` | Add `{ timeout: 3000 }` |

### No New Data Models or Contracts

This feature modifies test infrastructure only. No data models, API contracts, or application code are affected.

## Complexity Tracking

No constitution violations. No complexity justification needed.
