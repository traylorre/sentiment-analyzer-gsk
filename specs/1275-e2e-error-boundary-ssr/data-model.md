# Feature 1275: e2e-error-boundary-ssr - Data Model

## Overview

This feature has no data storage changes. It modifies a single React component's internal state management.

## Component State Model

### Before (Broken)

```
ErrorTrigger
  State: none (stateless function component)
  Render: synchronous check of window.__TEST_FORCE_ERROR
  SSR behavior: skips check (typeof window === 'undefined')
  Hydration behavior: may or may not re-execute render
```

### After (Fixed)

```
ErrorTrigger (outer, stateless)
  Production: passthrough, zero overhead
  Non-production: delegates to ErrorTriggerInner

ErrorTriggerInner
  State: shouldError: boolean (default: false)
  Mount effect: checks window.__TEST_FORCE_ERROR, sets shouldError
  Render: if shouldError, throws Error (caught by ErrorBoundary)
  SSR behavior: renders children (useEffect doesn't fire on server)
  Hydration behavior: renders children (matches server), then effect fires
```

## State Transitions

```
[SSR]
  shouldError = false -> render children

[Hydration]
  shouldError = false -> render children (matches server HTML)

[useEffect fires]
  window.__TEST_FORCE_ERROR === true?
    YES -> setShouldError(true) -> re-render -> throw -> ErrorBoundary catches
    NO  -> no state change -> component remains transparent
```

## No Database/API/Infrastructure Changes

- No DynamoDB tables affected
- No API endpoints affected
- No Terraform resources affected
- No environment variables affected
