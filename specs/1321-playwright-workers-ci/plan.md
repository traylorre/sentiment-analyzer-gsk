# Plan: Feature 1321 — Playwright Workers CI

## Change 1: `frontend/playwright.config.ts` (line 15)

### Current Code

```typescript
workers: process.env.CI ? 1 : undefined,
```

### New Code

```typescript
workers: process.env.CI ? 4 : 4,
```

### Rationale

- CI: 4 workers to utilize all 4 vCPUs on ubuntu-latest
- Local: 4 workers (previously `undefined` which defaults to half of CPUs; explicit 4
  is consistent and predictable). Note: Feature 1320 may further adjust local behavior,
  but this sets a sane default.
- Belt-and-suspenders with the CLI flag in Change 2

### Impact

- Only affects Playwright worker count
- No other config properties change
- `fullyParallel: true` remains unchanged (already enabled)

## Change 2: `.github/workflows/pr-checks.yml` (lines 318-324)

### Current Command (approximate)

```yaml
run: npx playwright test --retries=0
```

### New Command

```yaml
run: npx playwright test --retries=0 --workers=4
```

### Rationale

- CLI `--workers=4` explicitly overrides any config value
- Ensures 4 workers even if someone modifies `playwright.config.ts`
- `--retries=0` is preserved (R2 requirement)
- No timeout change needed (R3 -- 305s projected vs 900s limit)

### Impact

- Only affects the Playwright test step in the E2E job
- No changes to other workflow jobs
- No changes to timeout (900s remains)

---

## Adversarial Review #2: Cross-Check

### XC1: Config vs CLI Consistency

| Setting | Config (`playwright.config.ts`) | CLI (`pr-checks.yml`) |
|---------|-------------------------------|----------------------|
| Workers (CI) | 4 | 4 |
| Workers (local) | 4 | N/A (not in CI) |
| Retries | 0 (config default) | 0 (explicit) |
| fullyParallel | true | N/A (config only) |

**Verdict**: Config and CLI are consistent. CLI is explicit override. No drift possible.

### XC2: Dependency Chain Validation

| Dependency | Required For | Status |
|-----------|-------------|--------|
| Feature 1319 (API thread safety) | Concurrent API requests from workers | Hard dep -- merge 1319 first for full benefit |
| Feature 1320 (Local workers) | Local dev experience | No conflict -- 1320 may override local worker count |

**Verdict**: No conflicts. 1321 is safe to implement and merge independently. Full
benefit realized after 1319 lands.

### XC3: File Completeness

| File | Changes | Verified |
|------|---------|----------|
| `frontend/playwright.config.ts` | Line 15: `1` -> `4`, `undefined` -> `4` | YES |
| `.github/workflows/pr-checks.yml` | Add `--workers=4` to Playwright command | YES |

Two files. Two changes. No new files. No deletions. Scope is minimal.
