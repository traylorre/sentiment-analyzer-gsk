# Customer Dashboard E2E Tests

This directory contains Playwright E2E tests for the **customer-facing Next.js dashboard** hosted on AWS Amplify.

## Target Dashboard

All tests in this directory target the **Customer Dashboard (Next.js/Amplify)** — the app at `https://main.d29tlmksqcx494.amplifyapp.com/`.

For admin dashboard (Lambda HTMX) tests, see `tests/e2e/` at the repository root.

## Running Tests

```bash
# Against local dev server (default)
cd frontend && npx playwright test

# Against deployed Amplify app
PREPROD_FRONTEND_URL=https://main.d29tlmksqcx494.amplifyapp.com/ npx playwright test

# Run a specific test file
npx playwright test sentiment-visibility
npx playwright test signin-interaction
```

## Verification runs (Milestone 1 evidence pipeline)

Verification runs produce the screenshot + manifest evidence a verifier agent
attests against (trust contract: `docs/cleanup-pristine/milestone-1-verifiable-auth.md`).
Specs opt in by importing from `./helpers/verification` instead of `@playwright/test`
and calling `verify.shot()` at each evidence step.

```bash
# Evidence run against preprod (target of record — the only target whose
# evidence counts toward a Definition of Done):
cd frontend && \
VERIFICATION=1 \
PREPROD_FRONTEND_URL=https://main.d29tlmksqcx494.amplifyapp.com \
npx playwright test infra-smoke --project="Desktop Chrome"
```

Artifacts land in `test-results/verification/{run-id}/{project}/`:

- `{spec}-{NN}-{step}.png` — full-page screenshot per step, captured on every run
- `{spec}.manifest.json` — per-step page URL, main-document status, every
  `/api/v2/auth/*` request (2xx included), API errors >= 400, console/page errors,
  DOM probe, `interception` flag (any `page.route()`/`context.route()` registration
  taints the run), and `forbidden_requests` results. Schema:
  `schemas/verification-manifest.schema.json`.

Rules:

- `VERIFICATION=1` forces full Playwright traces (`trace: 'on'`) so the verifier
  can cross-check the manifest against raw network entries.
- Evidence with `target: localhost-mock` never counts toward a DoD.
- A `target: preprod` manifest with `interception.clean: false` is hard-failed by
  the verifier: mocking against the real URL is exactly the failure mode the
  contract exists to catch.
- Set `VERIFICATION_RUN_ID` in CI for stable artifact naming (defaults to a
  timestamp locally).

## Adding New Tests

1. Create a new `.spec.ts` file in this directory
2. **Required**: Add this as the first line:
   ```typescript
   // Target: Customer Dashboard (Next.js/Amplify)
   ```
3. Use `page.getByRole()`, `page.getByLabel()`, `page.getByPlaceholder()` selectors (accessibility-first)
4. Tests must work against both `localhost:3000` and `PREPROD_FRONTEND_URL`

## Two-Dashboard Architecture

| Dashboard | Directory | URL | Tech |
|-----------|-----------|-----|------|
| Customer (this dir) | `frontend/tests/e2e/` | Amplify or localhost:3000 | Next.js/React |
| Admin | `tests/e2e/` (repo root) | Lambda Function URL | HTMX/Chart.js |

The `make check-test-target-headers` target enforces that all Playwright test files have a `Target:` header comment.
