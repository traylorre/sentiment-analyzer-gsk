# Implementation Checklist: Auth Retry Backoff

**Feature**: 1336-auth-retry-backoff
**Date**: 2026-04-05

## Pre-Implementation

- [ ] Verify auth-helper.ts loads without TypeScript errors
- [ ] Verify `createAnonymousSession` is called only by `setupAuthSession` (confirm blast radius)
- [ ] Confirm no other files import `createAnonymousSession` directly

## Phase 1: Core Retry Logic

- [ ] T-001: `sleep()` helper added (module-private, not exported)
- [ ] T-002: Retry loop wraps fetch call
- [ ] T-002: Retry constants defined (MAX_ATTEMPTS=3, BASE_DELAY_MS=1000)
- [ ] T-002: Success path (201) returns immediately on first attempt (no delay)
- [ ] T-002: HTTP error path throws immediately without retry
- [ ] T-002: TypeError (network) path waits exponentially then retries
- [ ] T-002: Final attempt TypeError includes attempt count in error message
- [ ] T-002: JSDoc updated to document retry behavior
- [ ] Verify: Function signature unchanged (same params, same return type)
- [ ] Verify: No new exports added to module

## Phase 2: Validation

- [ ] T-003: TypeScript compiles without errors
- [ ] T-004: alerts-crud.spec.ts imports resolve correctly
- [ ] T-004: navigation.spec.ts imports resolve correctly
- [ ] T-005: magic-link.spec.ts has zero changes (git diff confirms)
- [ ] T-005: session-lifecycle.spec.ts has zero changes (git diff confirms)

## Post-Implementation

- [ ] No `console.log` statements in retry logic (use `console.warn` for retry attempts)
- [ ] Error messages are descriptive (include attempt number, delay, original error)
- [ ] No external dependencies added
- [ ] No changes to playwright.config.ts
