# Implementation Plan: OAuth Session Persistence

**Branch**: `1381-oauth-session-persistence` | **Date**: 2026-07-23 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/1381-oauth-session-persistence/spec.md`

## Summary

Real Google OAuth login works on the Amplify customer frontend, but the session does not persist because `POST /api/v2/auth/refresh` fails the OAuth restore path. Root cause is a **two-defect chain**, not the originally-suspected cookie attributes (those were already unified/fixed in WI-3 #928):

- **Defect A** — the Cognito refresh round-trip returns 401 (either the refresh cookie is not sent on the deployed topology, or Cognito rejects the OAuth-issued token due to app-client/secret env drift under the Feature 1290 freeze).
- **Defect B** — even on a 200, the Cognito branch of `refresh_access_tokens` omits `user_id`, so the frontend `restoreSession` bails to `signInAnonymous()`.

Technical approach: (1) add backend diagnostics to identify which sub-cause of A is live on preprod; (2) fix Defect B by returning server-derived `user_id`/`auth_type` in the Cognito refresh response (low blast radius, no frontend change); (3) remediate the identified A sub-cause — correct Cognito client/secret via the CI env-sync path (never Terraform), or correct the cookie Path if a real deployed-scope mismatch is found; (4) verify end-to-end on the real Amplify frontend via an owner-performed interactive Google login.

## Technical Context

**Language/Version**: Python 3.13 (backend dashboard Lambda); TypeScript 5.x / Next.js 14 / React 18 (frontend, verification only)
**Primary Dependencies**: aws-lambda-powertools (routing/Response), httpx (Cognito token calls), PyJWT/joserfc (token decode), boto3 (DynamoDB); Zustand + React Query (frontend)
**Storage**: DynamoDB `{env}-sentiment-users` (single-table; existing GSIs `by_provider_sub`, `by_cognito_sub`, `by_email`). No schema change.
**Testing**: pytest (unit, `-m "not preprod"` locally); Playwright for customer E2E against the Amplify URL; owner-performed interactive Google login for real OAuth verification (Google consent cannot be automated).
**Target Platform**: AWS Lambda (dashboard) behind API Gateway; AWS Amplify (frontend); AWS Cognito (OAuth).
**Project Type**: Web (separate `frontend/` + `src/lambdas/dashboard/` backend).
**Performance Goals**: `/refresh` p95 within existing auth-endpoint budget; one Cognito round-trip per restore.
**Constraints**: Dashboard Lambda env FROZEN (Feature 1290) — env changes only via CI Step 2.5 / manual `update-function-configuration`. No new AWS resources. GPG-signed commits. Real-AWS preprod verification, no mocks for E2E. Customer dashboard only (ignore `src/dashboard/` HTMX).
**Scale/Scope**: Small, surgical fix. Primary change is one backend response-construction site plus diagnostics; optional config remediation; verification harness.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Security & Access Control (Constitution §3)**: Management/authenticated endpoints require auth; TLS everywhere; secrets in a managed store, not source. This feature preserves httpOnly refresh cookies, CSRF double-submit, and blocklist checks (SR-001..SR-006). Cognito client secret stays in env/secret store, never in code. **PASS.**
- **No raw user input into logs (Constitution §3, CWE-117/312)**: Diagnostics use hash prefixes / masking via existing `sanitize_for_log` (SR-006). **PASS.**
- **IaC / deployment (Constitution §5)**: No new infra; respects the Feature 1290 env-freeze delivery path (FR-009). **PASS.**
- **Least privilege / no schema churn**: Reuses existing DynamoDB tables and GSIs; `user_id` derived from validated claims. **PASS.**
- **Testing discipline**: Unit tests for the new response contract; preprod/real verification for the deployment-specific 401. **PASS.**

No violations → Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/1381-oauth-session-persistence/
├── plan.md              # This file
├── research.md          # Root-cause research (R1–R7)
├── spec.md              # Feature spec + Adversarial Review #1 + Clarifications
├── contracts/
│   └── auth-refresh.md  # /refresh response contract (adds user_id/auth_type)
└── tasks.md             # Stage 7 output
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
├── auth.py              # refresh_access_tokens (Cognito branch) → populate user_id/auth_type (Defect B); diagnostics
└── router_v2.py         # refresh_tokens handler → diagnostic logging hooks (FR-007); cookie helpers (verify only)

src/lambdas/shared/auth/
└── cognito.py           # refresh_tokens (Cognito call) — read-only reference; no change expected

frontend/src/
├── stores/auth-store.ts # restoreSession — consumer of the contract (verify; no change expected for core fix)
└── hooks/use-session-init.ts # SessionProvider restore-first flow (verify only)

tests/
├── unit/dashboard/      # unit tests for the refresh response contract (user_id present for Cognito branch)
└── (preprod verification is manual/owner-driven; documented in quickstart)

infrastructure / ops (no Terraform env change):
└── .github/workflows/deploy.yml  # CI Step 2.5 env-sync is the ONLY path to correct Cognito client/secret (FR-009)
```

**Structure Decision**: Web app. The core fix is backend-only in `src/lambdas/dashboard/auth.py` (response construction) plus diagnostics in `router_v2.py`. Frontend is verification-only because the existing `restoreSession` contract is already satisfied once the backend returns `user_id`. Any Cognito config remediation is an ops action through the CI env-sync, not code/Terraform.

## Phased Approach

- **Phase 0 — Diagnose (blocking)**: Ship FR-007 diagnostics; on preprod, capture which 401 sub-cause is live (cookie-absent vs Cognito-reject) and whether the cookie is being sent. This decides whether Phase 2 is a Cognito-config action or a cookie-Path correction.
- **Phase 1 — Backend contract fix (Defect B)**: Populate `user_id`/`auth_type` in the Cognito refresh response, derived from validated id-token claims → internal user lookup. Unit-test it. This is required regardless of the Phase 0 outcome.
- **Phase 2 — Remediate Defect A (gated by Phase 0)**: If Cognito-reject → correct client/secret via CI Step 2.5 and verify against live function config (FR-009). If cookie-absent → correct the deployed cookie Path/scope (FR-008).
- **Phase 3 — Verify (real, no mocks)**: Owner-performed interactive Google login on the Amplify frontend; confirm 200 refresh, persisted identity, responsive left-nav, and no security regression (SC-001..SC-006).

## Complexity Tracking

No constitution violations; table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

---

## Adversarial Review #2

Re-read spec.md (incl. AR#1 + Clarifications), research.md, contracts/auth-refresh.md, and plan.md for drift introduced by the Stage 4 clarifications and for cross-artifact inconsistency.

| # | Sev | Drift / inconsistency | Resolution |
|---|-----|------------------------|------------|
| 1 | HIGH | **Non-existent function cited.** Q2 and research R5 referenced `get_user_by_cognito_sub`, which does not exist in `auth.py` (only `get_user_by_id:411`, `get_user_by_email_gsi:476`, `get_user_by_provider_sub:527`). An implementer would call a phantom symbol. | Corrected Q2 (spec) and R5 (research) to reuse `get_user_by_provider_sub(table, provider, sub)` (+ optional `by_cognito_sub` GSI helper). Verified names via grep. |
| 2 | MED | **`table` availability for the new lookup.** Adding a DB lookup in `refresh_access_tokens` assumes `table` is present; the signature defaults it to `None`. | Confirmed the live router path passes `table` (`router_v2.py:667-668`); noted in Q2. Tasks include a guard: if `table is None`, fall back to deriving identity from claims without a hard failure. |
| 3 | MED | **Provider unknown at refresh.** `get_user_by_provider_sub` needs `provider`; a bare Cognito refresh id-token may not carry the OAuth provider directly. | Tasks specify: read provider from the id-token `identities`/`cognito:username` claim, else use the `by_cognito_sub` GSI. Kept as a concrete implementation decision, not left ambiguous. |
| 4 | MED | **Phase 0 diagnostics vs "no frontend change" claim.** If Phase 0 shows the cookie is genuinely not sent (Path/scope), the fix is backend cookie-Path, still no frontend change — consistent. But the spec's US2 left-nav symptom could, in a worst case, be a separate UI bug. | Clarification Q5 already scopes a residual UI-only lockup as a deferred follow-up; plan Phase 3 verifies it. Consistent; no edit needed. |
| 5 | LOW | **Contract lists `auth_type: "google"` example** but FR-003 allows other providers. | Acceptable — example is illustrative; contract text says "so the client rebuilds identity." No change. |

**Gate: 0 CRITICAL, 0 HIGH remaining.** The one HIGH (phantom function) is fixed and grep-verified. Remaining MEDs are converted into explicit task-level implementation decisions, not open ambiguities. Cross-artifact references (spec ↔ research ↔ contract ↔ plan) are now consistent on: backend-first fix, `user_id` from validated claims via `get_user_by_provider_sub`, env-freeze delivery path, and no-frontend-change scope.
