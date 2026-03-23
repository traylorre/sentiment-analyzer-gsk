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
