# Implementation Plan: Feature 1374 — OAuth Spec Reconciliation

## Technical Context

| Aspect | Value |
|---|---|
| Type | Bookkeeping + test-fixture update |
| Code deliverables | Updated `frontend/tests/e2e/helpers/auth-helper.ts` (via 1331's task list completion); decision doc; archived files |
| No infra changes | This feature does not touch Terraform, Lambda, frontend app code (except test fixtures). |

## Architecture Decisions

### AD1: Capture observed response as JSON, strip CSRF state

**Decision**: `specs/1374-oauth-spec-reconciliation/observed-response.json`
is committed; `state` field is redacted to `"<redacted>"`.
**Why**: The shape is what's reusable; the state is per-request.

### AD2: Default 1323 to "Ship as-is" unless owner objects

**Decision**: Pre-pick the Ship-as-is path for 1323. Lightest-touch outcome.
**Alternative**: "Revise" creates a real local OAuth client; "Archive"
loses context.
**Why**: Local dev with mock Cognito is a low-cost improvement; revising
to a real local OAuth client is out of proportion to the value.

### AD3: 1331 task list runs to completion as part of 1374

**Decision**: 1374 doesn't just point at 1331; it includes the actual
test fixes as tasks. After 1374 ships, 1331 is closed.
**Why**: 1331 has been sitting uncommitted since at least 2026-04 (spec
date in current repo). It needs an owner; 1374 takes ownership.

## Implementation Steps

1. After 1371's preprod apply, capture `/urls` response. Redact state.
   Commit as `observed-response.json`.
2. Write decision doc for 1323 (default: Ship as-is).
3. Update `frontend/tests/e2e/helpers/auth-helper.ts` `mockOAuthUrls()`
   to match the captured shape.
4. Run 1331's tasks.md T1-T11 to completion (assertion fixes + route
   mocks). Open per-task PRs or one combined PR.
5. Confirm `cd frontend && npx playwright test magic-link.spec.ts
   oauth-flow.spec.ts auth.spec.ts signin-interaction.spec.ts` runs all
   green.
6. Open PR for 1374's changes (decision doc + test helper update +
   1331 closeout).

## Adversarial Review #2

**Reviewer**: Self
**Date**: 2026-04-29

### Drift between Stage 1 and Stage 3

None — spec and plan are tightly aligned.

### Cross-artifact inconsistencies

None.

### Gate

**0 CRITICAL, 0 HIGH remaining.**

## Clarifications

### C1: Who owns the 1323 decision?

**Self-answer**: The user (Scott) is the de facto owner of all
uncommitted spec dirs in this repo. Plan AD2 pre-picks Ship-as-is to
unblock progress; user can override.

**Conclusion**: Surface in Phase 2 summary as a user-input opportunity.

### C2: Should we wait for prod (1372) before reconciling, or is preprod (1371) shape enough?

**Self-answer**: preprod is enough. The `/urls` response shape is
determined by `OAuthURLsResponse` Pydantic model in `auth.py:1440`,
which is environment-independent. preprod = prod shape.

**Conclusion**: Only depend on 1371. Don't wait for 1372.

### C3: Do 1331's existing assertion fixes (B1-B4) need to be re-validated against the deployed flow?

**Self-answer**: B1-B4 are pure assertion fixes (test asserts text X but
component renders text Y). They don't depend on deployed state — they
depend on component code that is independent of provisioning. Can be
fixed independently.

**Conclusion**: B1-B4 can land in 1374 immediately, even before 1371's
apply. A1-A5b (route mock additions) need the captured response shape.
