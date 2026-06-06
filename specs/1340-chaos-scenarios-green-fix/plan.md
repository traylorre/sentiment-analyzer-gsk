# Implementation Plan -- Feature 1340: Fix Green Dashboard Syndrome in chaos-scenarios.spec.ts

## Files to Modify

### 1. `frontend/tests/e2e/chaos-scenarios.spec.ts` (PRIMARY -- only file)

All changes are within this single test file. No helper changes needed (1339 provides
infrastructure; this feature tightens the spec file's own assertions).

## Technical Context

### Current State (line references)

| Line | Current Code | Problem |
|------|-------------|---------|
| 24 | `await page.waitForTimeout(3000)` | Arbitrary wait, not page-ready |
| 59-61 | `textDuring` checked for `.length > 10` only | No comparison to `textBefore` |
| 65 | `if (await freshnessIndicator.isVisible(...).catch(() => false))` | Optional assertion |
| 89-95 | 3x `waitForTimeout(1500)` | Not response-driven |
| 122-124 | `await expect(skeletons.first()).toBeVisible(...).catch(() => {...})` | Catch swallows failure |
| 166-168 | Same as 59-61 for trigger failure | No comparison to `textBefore` |
| 172 | Same as 65 for trigger failure | Optional assertion |
| 191-197 | 3x `waitForTimeout(1500)` | Not response-driven |
| 205-208 | `bannerVisible \|\| hasContent` | OR should be AND |
| 235 | `await responsePromise.catch(() => null)` | Swallows timeout |
| 239 | `expect(response === null \|\| response.ok()).toBeTruthy()` | Null passes |

### Change Strategy

Each change is a surgical edit to an existing assertion or wait pattern. No structural
changes to test flow. The `simulateChaosScenario()` and `triggerHealthBanner()` helpers
from chaos-helpers.ts are not modified.

## Implementation Plan

### Step 1: Fix beforeEach (FR-008)

Replace:
```typescript
await page.waitForTimeout(3000);
```
With:
```typescript
await expect(page.locator('main')).toBeVisible({ timeout: 10000 });
```

### Step 2: Fix T016 -- ingestion failure (FR-001, FR-002)

**Content comparison (FR-001)**:
After `textDuring` assertions, add:
```typescript
const fragment = textBefore!.substring(0, 20);
expect(textDuring).toContain(fragment);
```

**Mandatory freshness (FR-002)**:
Replace lines 65-68:
```typescript
if (await freshnessIndicator.isVisible({ timeout: 3000 }).catch(() => false)) {
  const freshnessState = await freshnessIndicator.getAttribute('data-freshness-state');
  expect(['stale', 'critical']).toContain(freshnessState);
}
```
With:
```typescript
await expect(freshnessIndicator).toBeVisible({ timeout: 5000 });
const freshnessState = await freshnessIndicator.getAttribute('data-freshness-state');
expect(['stale', 'critical']).toContain(freshnessState);
```

### Step 3: Fix T017 -- database throttle (FR-006)

Replace each `waitForTimeout(1500)` after search fill with `waitForResponse`:
```typescript
await searchInput.fill('AAPL');
await page.waitForResponse((r) => r.url().includes('/api/') && r.status() === 503);
```
Repeat for GOOG and MSFT fills.

### Step 4: Fix T018 -- cold start (FR-007)

Remove `.catch(() => {...})` from skeleton assertion:
```typescript
// Before
await expect(skeletons.first()).toBeVisible({ timeout: 2000 }).catch(() => {});
// After
await expect(skeletons.first()).toBeVisible({ timeout: 2000 });
```

Replace `page.waitForTimeout(5000)` after skeleton with response-based wait:
```typescript
await page.waitForResponse((r) => r.url().includes('/api/') && r.ok(), { timeout: 10000 });
```

### Step 5: Fix T019 -- trigger failure (FR-001, FR-002)

Same pattern as Step 2: add content fragment comparison, make freshness assertion mandatory,
and change freshness state expectation to `'critical'` (20 min > 4x threshold).

### Step 6: Fix T020 -- API timeout (FR-005, FR-006)

**AND-logic (FR-005)**:
Replace:
```typescript
expect(bannerVisible || hasContent).toBeTruthy();
```
With:
```typescript
expect(bannerVisible).toBeTruthy();
expect(hasContent).toBeTruthy();
```

**Response-driven waits (FR-006)**:
Same pattern as Step 3 -- replace `waitForTimeout(1500)` with `waitForResponse` for 503.

### Step 7: Fix T021 -- recovery (FR-003, FR-004)

Remove `.catch(() => null)` and null-guard:
```typescript
// Before
const response = await responsePromise.catch(() => null);
expect(response === null || response.ok()).toBeTruthy();

// After
const response = await responsePromise;
expect(response.ok()).toBeTruthy();
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Freshness indicator not rendering in CI | Low | High (test fails) | Feature 1266 is merged; mock sentiment data triggers it |
| Skeleton assertion fails because cold start delay <2s | Low | Medium | Chaos scenario injects 3s delay via route handler |
| Recovery test timeout without any ok response | Low | Medium | Dashboard background refetches produce ok responses; 10s timeout |
| Content fragment match fails due to dynamic content | Low | Low | First 20 chars of main content are typically stable header text |

---

## Appendix A: Adversarial Review #2 (Plan)

### AR2-Q1: Is 20-char substring comparison robust enough?
**Challenge**: If the first 20 characters are a dynamic timestamp or counter, the
comparison could fail spuriously.
**Analysis**: The dashboard's main content starts with the ticker symbol or section
headers (e.g., "AAPL - Apple Inc" or "Sentiment Analysis"). These are stable across
chaos injection. Dynamic elements (timestamps, prices) appear later in the text.
**Verdict**: ACCEPT -- 20 chars from the start is stable enough. If it proves flaky,
increase to a known-stable `data-testid` element's text.

### AR2-Q2: Why not use 1339's assertContentPersistence() helper?
**Challenge**: Feature 1339 provides `assertContentPersistence()` which does structured
snapshot comparison. Why duplicate with substring matching?
**Analysis**: `assertContentPersistence()` requires both a before and after snapshot via
`captureContentSnapshot()`. This is heavier than needed for T016/T019 which already
have `textBefore` captured. The substring approach is simpler and sufficient for these
specific tests. Future chaos tests SHOULD use the 1339 helper.
**Verdict**: ACCEPT for now -- add a code comment noting that new tests should prefer
`assertContentPersistence()`.

### AR2-Q3: Removing `.catch()` from skeleton test -- what if page has cached data?
**Challenge**: Line 122-124's comment says "If no skeletons visible, the page may have
cached data -- still valid." Removing the catch makes the test strict.
**Analysis**: The test calls `page.reload()` AFTER applying `lambda_cold_start` chaos
which adds a 3s delay to all API responses. After reload, the page must re-fetch data
through the delayed routes. Skeletons SHOULD appear during this 3s window. If they
don't, either (a) the skeleton UI is broken or (b) the cold start scenario isn't
applying. Both are real bugs.
**Verdict**: ACCEPT -- cached data from before reload should not persist through a full
page reload.

### AR2-Q4: Will `waitForResponse` with status 503 match the right response?
**Challenge**: In T017/T020, after filling search, the dashboard fires requests to
multiple endpoints. The 503 response could come from any of them.
**Analysis**: That's fine -- we need ANY 503 to confirm the chaos route handler fired.
The exact endpoint doesn't matter for the wait. The important assertion is the banner
visibility afterward.
**Verdict**: ACCEPT.
