# Quickstart: Scope axe-core to Error Boundary Element

## Prerequisites

- Node.js 18+
- Playwright installed (`npx playwright install chromium`)
- Chaos dashboard running locally (`python scripts/run-local-api.py`)

## Setup

```bash
cd e2e/playwright
npm install @axe-core/playwright@^4.10.0
```

## Run accessibility tests

```bash
# Run all tests including accessibility
npx playwright test

# Run only accessibility tests
npx playwright test accessibility

# Run with headed browser for debugging
npx playwright test accessibility --headed
```

## Expected output

```
  accessibility.spec.ts
    ✓ main content container has no critical/serious violations
    ✓ reports view has no critical/serious violations when active
    ✓ modal dialog is accessible when open
```

## Interpreting failures

- **Critical/serious violations**: Test fails. Fix the HTML/CSS issue in chaos.html.
- **Moderate/minor violations**: Logged as warnings. Review but not blocking.
- **Readiness gate failure**: Dashboard didn't hydrate. Check if the local API server is running.
- **Scope selector not found**: `data-testid="chaos-dashboard-content"` missing from chaos.html.
