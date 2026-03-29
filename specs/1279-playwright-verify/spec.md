# Spec: 1279-playwright-verify

## Problem Statement

Playwright Chaos Tests have been CANCELLED on every PR since their introduction (PRs #835-#838).
The auto-merge workflow kills the CI run as soon as the 3 required checks (Secrets Scan, Lint,
Run Tests) pass, before the non-required Playwright job completes. Additionally,
`requirements-dev.txt` has a pydantic version conflict that would cause pip install failures.

We have accumulated 4 PRs of Playwright fixes but have ZERO evidence they work in CI. This is
a verification/observability feature -- not a code fix.

## Requirements

### Functional
1. Apply the pydantic==2.12.4 pin to `requirements-dev.txt` (matching CI pattern from 1278)
2. Create a PR that triggers ALL CI jobs including Playwright Chaos Tests
3. The PR MUST NOT have auto-merge enabled
4. Wait for CI to complete ALL jobs
5. Download the `playwright-chaos-report` and `playwright-chaos-results` artifacts
6. Document which tests pass, which fail, and actual error messages

### Non-Functional
1. `requirements-ci.txt` MUST NOT be modified (already correct)
2. `requirements.txt` MUST NOT be modified (production stays at 2.12.5)
3. No test code changes -- this is pure observation
4. No workflow changes -- artifact upload already configured

## Acceptance Criteria
- [ ] `requirements-dev.txt` contains `pydantic==2.12.4` pin with explanatory comment
- [ ] PR created WITHOUT auto-merge
- [ ] Playwright Chaos Tests job runs to completion (not CANCELLED)
- [ ] Artifacts downloaded and analyzed
- [ ] Results documented: pass/fail count, error messages if any

## Scope
- 1 file modified: `requirements-dev.txt` (2 lines added)
- 1 PR created (manual merge only)
- 1 CI run observed end-to-end
- 1 results document produced

## Risk Assessment
- **Risk**: MINIMAL. Adding a version pin and observing CI.
- **Rollback**: Delete the PR.
- **Blast radius**: Zero production impact. Dev environment improvement only.

## Dependencies
- Feature 1277 (artifact upload) -- MERGED in PR #838
- Feature 1278 (pydantic pin spec) -- spec exists, code not yet applied
