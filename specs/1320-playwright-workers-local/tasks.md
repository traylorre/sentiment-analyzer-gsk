# Feature 1320: Tasks

## Status: READY FOR IMPLEMENTATION

## Tasks

### T1: Edit Playwright Config

**File:** `frontend/playwright.config.ts`
**Line:** 15
**Action:** Change `undefined` to `4`

```diff
- workers: process.env.CI ? 1 : undefined,
+ workers: process.env.CI ? 1 : 4,
```

**Covers:** R1
**Estimated effort:** < 1 minute

### T2: Verify Locally

**Action:** Run Playwright test listing to confirm worker count.

```bash
cd frontend && npx playwright test --list
```

**Expected output contains:** "Using 4 workers"

**Covers:** R1, R2 (verify CI branch not affected by absence of `CI` env var)
**Estimated effort:** < 1 minute

## Requirement Coverage

| Requirement | Task(s) | Verified By |
| ----------- | ------- | ----------- |
| R1          | T1      | T2          |
| R2          | T1      | T2 + code inspection (ternary CI branch unchanged) |

## Task Dependencies

```
T1 (edit) -> T2 (verify)
```

No external blockers within this feature. Feature 1319 (ThreadingHTTPServer) is a cross-feature dependency that must be merged separately.

---

## Adversarial Review #3

### AR3-F1: Highest Risk

**Risk:** API server cannot handle 4 concurrent connections, causing test timeouts or flaky failures.
**Mitigation:** Feature 1319 adds `ThreadingHTTPServer` with handler serialization lock. Once 1319 is merged, the API server handles concurrent requests safely.
**Residual risk after 1319:** Negligible. `ThreadingHTTPServer` is a stdlib solution used broadly in Python development servers.

### AR3-F2: Most Likely Rework

**Risk:** Worker count of 4 causes flakiness on specific test suites (e.g., tests with shared state or timing assumptions).
**Likelihood:** Low -- `fullyParallel: true` is already set, so tests are already expected to be parallelism-safe.
**Rework path:** Reduce workers to 2 or 3, or mark specific tests as `test.describe.serial()`.

### AR3-F3: Implementation Completeness

**Check:** Two tasks cover the full scope -- one edit, one verification. No infrastructure changes, no new files, no config migrations. The change is atomic and trivially reversible.

### Gate: READY FOR IMPLEMENTATION.
