# Tasks: Verify CORS Fixes Deployed

**Input**: Design documents from `/specs/1283-cors-deploy-verify/`
**Prerequisites**: plan.md (required), spec.md (required)

## Phase 1: Credential Documentation (FR-005 Gate)

**Purpose**: Document all requirements before attempting verification. If requirements are not met, the feature is BLOCKED.

- [ ] T-001 [US1] Document credential requirements for preprod verification: (a) `PREPROD_FRONTEND_URL` environment variable pointing to Amplify preprod URL, (b) AWS credentials with access to preprod environment, (c) `gh` CLI authenticated to the repository. If any requirement is unavailable, mark subsequent preprod tasks as BLOCKED with the specific missing requirement.

**Checkpoint**: Requirements documented. Proceed if all available, or document BLOCKED status.

---

## Phase 2: Preprod Verification (Priority: P1)

**Goal**: Confirm CORS fixes from PRs #832-#834 are deployed and functional in preprod.

**Independent Test**: Run existing Playwright tests against preprod Amplify URL.

- [ ] T-002 [US1] Run existing sanity tests (`sanity.spec.ts`) and CORS tests (`cors-headers.spec.ts`) against preprod using `PREPROD_FRONTEND_URL`. Capture results with focus on CORS-specific outcomes: (a) verify no `ERR_FAILED` or CORS errors in browser console during API calls, (b) verify `Access-Control-Allow-Origin` header echoes the Amplify origin (not wildcard `*`), (c) verify `Access-Control-Allow-Credentials: true` is present, (d) verify `Access-Control-Allow-Headers` lists explicit headers (not `*`). Document pass/fail for each CORS assertion. If preprod access is unavailable, document as BLOCKED per T-001.

**Checkpoint**: Preprod CORS verification complete (or explicitly BLOCKED).

---

## Phase 3: Production Blocker Audit (Priority: P2)

**Goal**: Document exactly what must change before production CORS can be verified.

- [ ] T-003 [US2] Inspect `infra/prod.tfvars` and `.github/workflows/deploy.yml` in the target repo. Document: (a) whether `enable_amplify = true` is set in `prod.tfvars`, (b) whether `cors_allowed_origins` includes the Amplify production URL (not empty, not wildcard), (c) which production jobs in `deploy.yml` have `if: false` and what conditions would re-enable them, (d) any other production deployment prerequisites (e.g., DNS, SSL, Amplify app creation). Compile findings into a concrete production readiness checklist.

**Checkpoint**: Production blockers fully documented with specific file paths and required changes.

---

## Phase 4: Assessment Update

**Purpose**: Record verification results in the canonical readiness document.

- [ ] T-004 [US1/US2] Update the Gameday Readiness Assessment (`sentiment-analyzer-gsk-security/GAMEDAY_READINESS_ASSESSMENT_2026-03-26.md`) with: (a) preprod CORS verification results and timestamp, (b) production blocker checklist from T-003, (c) overall CORS readiness status (GREEN/YELLOW/RED). If preprod verification was BLOCKED, record YELLOW status with the blocking reason.

**Checkpoint**: Assessment updated with verification timestamp.

---

## Phase 5: Production CORS Readiness Checklist

**Purpose**: Create a standalone actionable checklist for enabling production CORS.

- [ ] T-005 [US2] Create a production CORS readiness checklist summarizing: (a) all `prod.tfvars` changes required (with exact key-value pairs), (b) all `deploy.yml` changes required (which `if: false` to remove), (c) post-deployment verification steps (which Playwright tests to run, expected CORS headers), (d) rollback procedure if production CORS breaks. This checklist is the deliverable for the production deployment team.

**Checkpoint**: Production readiness checklist complete. Feature complete.

---

## Dependencies & Execution Order

- **T-001** (Phase 1): No dependencies -- start immediately. Gates T-002.
- **T-002** (Phase 2): Depends on T-001 confirming credentials available. BLOCKED if credentials unavailable.
- **T-003** (Phase 3): No dependency on T-001/T-002 (reads config files, not preprod). Can run in parallel with T-002.
- **T-004** (Phase 4): Depends on T-002 and T-003 (needs results from both).
- **T-005** (Phase 5): Depends on T-003 (production blocker findings feed the checklist). Can run in parallel with T-004.

### Parallel Opportunities

- T-002 and T-003 can run in parallel (preprod testing vs. config file inspection).
- T-004 and T-005 can run in parallel after their respective dependencies complete.

---

## Adversarial Review #3

**Highest-risk task**: **T-002** (Preprod Verification). This is the only task that requires live environment access and external credentials. If preprod is down, credentials are expired, or the CORS PRs failed to deploy via the auto-deploy pipeline, this task fails and the feature's primary deliverable (SC-001: preprod CORS verification) cannot be achieved. There is no workaround -- you cannot verify deployed CORS behavior without accessing the deployed environment.

**Readiness assessment**: CONDITIONALLY READY. The spec and plan are sound -- existing tests cover the verification needs, CORS-specific pass criteria are well-scoped (SC-001 amendment), and production blockers can be documented regardless of preprod access. The condition is credential availability: if `PREPROD_FRONTEND_URL` and AWS credentials are available, this feature is straightforward execution. If not, T-002 is BLOCKED and the feature delivers documentation only (T-001, T-003, T-004 partial, T-005). This is an acceptable degraded outcome explicitly designed into the spec (FR-005).
