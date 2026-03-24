# Feature Specification: Chaos Security Hardening

**Feature Branch**: `G-chaos-security-hardening`
**Created**: 2026-03-24
**Status**: Draft (post-adversarial-review-v1)
**Input**: "Harden chaos testing API endpoints against unauthenticated access, enforce experiment duration limits, add audit alerting, and prevent abuse"

## Context

The sentiment analyzer includes a chaos testing framework for resilience validation. The framework can directly modify AWS infrastructure: set Lambda concurrency to 0, attach IAM deny-write policies, disable EventBridge rules, reduce memory/timeout. These operations are controlled via REST API endpoints (`/chaos/experiments/*`) on the Dashboard Lambda Function URL.

Currently, anonymous users (UUID-only Bearer tokens) can execute chaos operations in non-production environments. The Lambda Function URL has `authorization_type = NONE`, making these endpoints reachable by anyone who discovers the URL. Additionally, experiment duration (5-300s) is validated at creation but never enforced at runtime — infrastructure stays degraded until someone manually calls `/stop`.

### Out of Scope

- Moving chaos to a dedicated Lambda (architecture change)
- Adding WAF rules (separate feature)
- Changing Lambda Function URL authorization_type (affects all endpoints)
- Admin dashboard route lockdown (completed in Feature 1249)
- FIS (Fault Injection Service) integration (blocked by AWS provider bug #41208)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Authenticated-Only Chaos Access (Priority: P1)

Only authenticated users (JWT-based, non-anonymous) can execute chaos operations in any environment. Anonymous sessions with UUID-only tokens are rejected with 401.

**Why this priority**: This is the single highest-risk finding — anonymous users can degrade infrastructure. A discovered Function URL becomes a one-step attack vector.

**Independent Test**: Send a chaos API request with a UUID Bearer token (anonymous session) and verify 401 rejection.

**Acceptance Scenarios**:

1. **Given** a user with an anonymous UUID session token, **When** they POST to `/chaos/experiments`, **Then** they receive HTTP 401.
2. **Given** a user with a valid JWT (authenticated session), **When** they POST to `/chaos/experiments` with valid parameters in a dev environment, **Then** the experiment is created (HTTP 201).
3. **Given** the environment is `local` and an anonymous user sends a chaos request, **When** the handler processes the request, **Then** it returns 401 (anonymous exception removed for ALL environments).

---

### User Story 2 — Chaos API Environment Gating (Priority: P1)

Chaos API endpoints return 404 in production and preprod environments. Only local/dev/test environments serve chaos functionality. The 404 is returned BEFORE any authentication check — attackers learn nothing about whether the endpoint exists.

**Why this priority**: Even with authenticated-only access, chaos operations should not be available in preprod/prod. Defense in depth.

**Independent Test**: Deploy to preprod, call any `/chaos/*` endpoint with a valid JWT, verify 404.

**Acceptance Scenarios**:

4. **Given** the environment is `preprod`, **When** an authenticated user POSTs to `/chaos/experiments`, **Then** they receive HTTP 404 (not 401 or 403).
5. **Given** the environment is `dev`, **When** an authenticated user POSTs to `/chaos/experiments`, **Then** the experiment is created normally.
6. **Given** the environment is `prod`, **When** any request hits `/chaos/experiments` (with or without auth), **Then** HTTP 404 — the 404 is checked BEFORE auth, so no information leakage about whether the endpoint exists.

---

### User Story 3 — Automatic Experiment Timeout (Priority: P1)

When a chaos experiment is started, the system automatically restores infrastructure after `duration_seconds` expires, even if no one calls `/stop`. This prevents indefinite infrastructure degradation.

**Why this priority**: Without enforcement, a started experiment with no `/stop` call leaves Lambda concurrency at 0 or IAM deny policies attached permanently.

**Independent Test**: Start an experiment with duration_seconds=10, wait 15 seconds, verify infrastructure is restored without calling /stop.

**Acceptance Scenarios**:

7. **Given** an experiment is started with `duration_seconds=30`, **When** 30 seconds pass without a `/stop` call, **Then** the system automatically restores the original configuration and marks the experiment as `auto-stopped`.
8. **Given** the auto-restore scheduling fails after the experiment starts (infrastructure already degraded), **When** the scheduling failure is detected, **Then** the system immediately calls `stop_experiment()` to restore and marks the experiment as `failed`. The experiment MUST NOT be left in `running` status without a scheduled restore.
9. **Given** a user manually calls `/stop` before the timeout, **Then** the scheduled restore is deleted. If the scheduled restore fires anyway (race), it checks experiment status and silently exits if status is not `running`.

---

### User Story 4 — Chaos Rate Limiting (Priority: P2)

Users cannot create more than 1 chaos experiment per 60 seconds. This prevents flooding the system with experiments that each modify infrastructure.

**Why this priority**: Without rate limiting, an authenticated user (or compromised credential) could create hundreds of experiments in rapid succession, overwhelming DynamoDB and creating cascading infrastructure changes.

**Independent Test**: Create an experiment, immediately try to create another, verify rate limit rejection.

**Acceptance Scenarios**:

10. **Given** user A created an experiment 30 seconds ago, **When** user A tries to create another experiment, **Then** they receive HTTP 429 with a retry-after header.
11. **Given** user A created an experiment 61 seconds ago, **When** user A creates another experiment, **Then** it succeeds.
12. **Given** user A created an experiment 10 seconds ago, **When** user B creates an experiment, **Then** user B succeeds (rate limit is per-user).

---

### User Story 5 — Concurrent Experiment Prevention (Priority: P2)

Only one experiment per scenario type may be in `running` status at a time. This prevents snapshot corruption (second experiment overwrites first experiment's pre-chaos snapshot) and double-restore confusion.

**Why this priority**: Without this, two `ingestion_failure` experiments could both set concurrency=0, but when experiment A auto-restores, it reads experiment B's snapshot — restoring the wrong config.

**Independent Test**: Start an experiment, attempt to start a second with the same scenario_type, verify 409.

**Acceptance Scenarios**:

15. **Given** experiment A with `scenario_type=ingestion_failure` is in `running` status, **When** a user tries to start experiment B with the same scenario_type, **Then** they receive HTTP 409 Conflict.
16. **Given** experiment A with `scenario_type=ingestion_failure` is `running`, **When** a user starts experiment B with `scenario_type=lambda_cold_start`, **Then** experiment B starts successfully (different scenario type).
17. **Given** experiment A is `stopped`, **When** a user starts a new experiment with the same scenario_type, **Then** it succeeds.

---

### User Story 6 — IAM Change Alerting (Priority: P3)

When the chaos system attaches or detaches IAM policies (the `dynamodb_throttle` scenario), a CloudWatch alarm fires to alert operators. This provides audit visibility for the most dangerous chaos operation.

**Why this priority**: IAM policy attachment is the highest-blast-radius operation — it blocks DynamoDB writes across Lambda functions. Even legitimate use should be visible.

**Independent Test**: Start a `dynamodb_throttle` experiment, verify CloudWatch alarm transitions to ALARM state.

**Acceptance Scenarios**:

13. **Given** a `dynamodb_throttle` experiment is started, **When** the deny-write policy is attached, **Then** a CloudWatch metric `ChaosIAMPolicyAttachment` is emitted with value 1.
14. **Given** the `ChaosIAMPolicyAttachment` metric exceeds threshold (>0 in 60s window), **When** CloudWatch evaluates the alarm, **Then** it transitions to ALARM state.

---

### Edge Cases

- What if the auto-restore Lambda is itself throttled or erroring? The auto-restore scheduling mechanism uses EventBridge Scheduler with a Lambda target. If the target Lambda fails, EventBridge Scheduler retries automatically (built-in retry policy).
- What if two experiments of the same scenario type are running concurrently? FR-008 prevents this with a status check before starting.
- What if the DynamoDB chaos table is unreachable during rate limit check? Fail-closed: reject the request with 503.
- What if the SSM kill switch is set to "triggered" when the auto-restore fires? The auto-restore should proceed — "triggered" means "stop all chaos," so restoration is the correct action.
- What if `enable_chaos_testing` is false in Terraform? The application-level gating still applies — chaos routes return 404 regardless of whether Terraform resources exist.
- What if the auto-restore scheduling succeeds but the experiment status update to `running` fails? The schedule fires but experiment is still `pending`. Auto-restore checks status — if not `running`, it becomes a no-op and the scheduled rule is cleaned up.
- What if Feature 1249 has not merged yet? This feature includes its own `_is_dev_environment()` helper if the import is not available (defensive fallback).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `_get_chaos_user_id_from_event()` function MUST reject anonymous sessions (AuthType.ANONYMOUS) in ALL environments, including local/dev/test. Remove the environment-conditional anonymous exception at handler.py line 175.
- **FR-002**: All seven chaos API route handlers MUST check environment FIRST (before auth). Return HTTP 404 when the environment is NOT `local`, `dev`, or `test`. Use the `_is_dev_environment()` helper. The 404 MUST be returned before `_get_chaos_user_id_from_event()` is called — no information leakage.
- **FR-003**: When `start_experiment()` successfully injects chaos, the system MUST schedule an automatic restore via EventBridge Scheduler (NOT EventBridge Rules — Scheduler supports `at()` one-time expressions). The schedule MUST be created BEFORE updating experiment status to `running`. If scheduling fails, the experiment MUST be immediately restored and marked `failed`.
- **FR-004**: Manual `/stop` MUST delete the scheduled restore rule. If the auto-restore fires for an experiment already in `stopped` or `auto-stopped` status, it MUST silently exit (no-op) without error.
- **FR-005**: Experiment creation (`POST /chaos/experiments`) MUST be rate-limited to 1 request per user per 60 seconds. Return HTTP 429 with `Retry-After` header when rate-limited. If the rate limit check fails (DynamoDB unreachable), fail-closed: reject with 503.
- **FR-006**: The `dynamodb_throttle` scenario MUST emit a custom CloudWatch metric `ChaosIAMPolicyAttachment` (value=1, namespace=SentimentAnalyzer) when attaching IAM policies, and value=0 when detaching.
- **FR-007**: A CloudWatch alarm MUST fire when the `ChaosIAMPolicyAttachment` metric exceeds 0 in any 60-second evaluation period.
- **FR-008**: Only one experiment per scenario type may be in `running` status at any time. Before starting an experiment, the system MUST query for running experiments with the same scenario_type. If found, return HTTP 409 Conflict. This prevents snapshot corruption from overlapping experiments.

### Key Entities

- **Chaos Experiment**: Represents a planned or active infrastructure degradation. Key attributes: experiment_id, scenario_type, status (pending/running/stopped/auto-stopped/failed), duration_seconds, blast_radius, created_at, started_at, stopped_at, auto_restore_rule_name, user_id.
- **Auto-Restore Schedule**: A one-time EventBridge Scheduler schedule that triggers experiment restoration after timeout. Named `chaos-auto-restore-{experiment_id}`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Anonymous chaos requests return 401 in ALL environments (verified by unit test with UUID token in local/dev/test/preprod).
- **SC-002**: All chaos endpoints return 404 on preprod (verified by E2E curl test post-deploy).
- **SC-003**: An experiment started with duration_seconds=30 is auto-stopped within 35 seconds (5-second tolerance) without manual intervention.
- **SC-004**: A second experiment creation within 60 seconds by the same user returns 429.
- **SC-005**: The `dynamodb_throttle` scenario triggers a CloudWatch alarm for IAM policy attachment.
- **SC-006**: No concurrent experiments of the same scenario type can reach `running` status (409 returned).
- **SC-007**: Existing chaos unit tests (tests/unit/test_chaos_injection.py, tests/unit/test_chaos_fis.py) continue to pass with zero regressions.
- **SC-008**: If auto-restore scheduling fails after chaos injection, infrastructure is immediately restored and experiment marked `failed`.

## Assumptions

- Feature 1249 (admin dashboard lockdown) is expected to merge before this feature (PR #798 in auto-merge queue). If it has not merged, this feature includes a standalone `_is_dev_environment()` implementation.
- The auto-restore uses AWS EventBridge Scheduler (boto3 client `scheduler`), NOT EventBridge Rules (boto3 client `events`). EventBridge Scheduler supports `at()` one-time expressions; EventBridge Rules do not.
- Rate limiting queries the existing chaos experiments DynamoDB table by user_id + created_at, using the existing `by_status` GSI or a new GSI if needed.
- The `enable_chaos_testing` Terraform flag remains false in prod — the application-level 404 gating is the primary defense.
- CloudWatch alarm SNS topic already exists from the DynamoDB monitoring feature (Feature 1248).
- The auto-restore EventBridge Scheduler requires an IAM role that allows it to invoke the Dashboard Lambda. This role must be created in Terraform.
