# Plan: 1279-playwright-verify

## Implementation Strategy

This is a verification feature with 3 phases:
1. **Code Change**: Apply pydantic pin to `requirements-dev.txt`
2. **CI Trigger**: Create PR, push, wait for full CI run
3. **Analysis**: Download artifacts, document results

## Phase 1: Code Change

### Step 1.1: Create feature branch
- Branch from `origin/main`
- Name: `A-1279-playwright-verify`

### Step 1.2: Apply pydantic pin
- File: `requirements-dev.txt`
- Add after the `-r requirements.txt` include line:
  ```
  # Override: moto[all]==5.1.22 requires pydantic<=2.12.4, but requirements.txt pins 2.12.5
  pydantic==2.12.4
  ```
- Placement: After the `-r requirements.txt` line so it overrides the transitive pin

### Step 1.3: Commit
- Message: `fix(deps): Pin pydantic==2.12.4 in requirements-dev.txt (moto compat)`
- Signed commit required

## Phase 2: CI Trigger

### Step 2.1: Push branch
- `git push -u origin A-1279-playwright-verify`

### Step 2.2: Create PR
- Title: `fix(deps): Pin pydantic in dev requirements for Playwright CI verification`
- Body: Explain this is a verification PR -- do NOT enable auto-merge
- Explicitly do NOT use `--auto` flag

### Step 2.3: Wait for CI
- Monitor all jobs until completion
- Key job: `Playwright Chaos Tests` -- must reach COMPLETED (not CANCELLED)
- Expected total time: ~10-15 minutes

## Phase 3: Analysis

### Step 3.1: Download artifacts
- `gh run download` for the specific run
- Target artifacts: `playwright-chaos-report`, `playwright-chaos-results`

### Step 3.2: Analyze results
- Parse HTML report for pass/fail counts
- Extract error messages from failed tests
- Document in `specs/1279-playwright-verify/results.md`

## Files Modified
| File | Change | Lines |
|------|--------|-------|
| `requirements-dev.txt` | Add pydantic pin + comment | +2 |

## Files Created
| File | Purpose |
|------|---------|
| `specs/1279-playwright-verify/results.md` | CI analysis results |

## Risk Mitigation
- If Playwright still fails: That IS the result. Document and close.
- If pip install fails: Check for additional conflicts. The pin should resolve the known one.
- If PR gets auto-merged: PR Merge workflow only auto-merges when the actor is dependabot or
  auto-merge is explicitly enabled. Neither applies here.
