# Implementation Plan: Lambda Log Visibility

**Branch**: `001-lambda-log-visibility` | **Date**: 2026-07-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-lambda-log-visibility/spec.md`

## Summary

Surface INFO-level logs from all first-party modules in the six deployed
non-SSE Lambdas by raising the root logger level once per entrypoint via a
shared helper, while pinning third-party HTTP-client loggers to WARNING and
masking the PII in currently-dark notification lines. Mechanism O2+ (code-level
root wire with hardening riders) was selected over the platform-level route
(O1) and the powertools-propagation route (O3) because it is the only option
whose blast radius is exactly "new INFO lines appear" — every existing log
line, consumer, and format survives byte-identical by construction. Full
rationale and the rejected alternatives are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (Lambda base image `public.ecr.aws/lambda/python:3.13` for image Lambdas; managed python3.13 runtime for ZIP Lambdas)
**Primary Dependencies**: stdlib `logging` only for the mechanism; aws-lambda-powertools 3.23.0 already present (dashboard handler) and untouched
**Storage**: N/A (observability-only; no data-store changes)
**Testing**: pytest (unit: helper semantics + entrypoint-coverage guard; preprod E2E: log-group assertions via boto3 `filter_log_events`)
**Target Platform**: AWS Lambda — 6 functions: dashboard (image), analysis (image), ingestion (ZIP), metrics (ZIP), notification (ZIP), canary (ZIP)
**Project Type**: single (backend Lambdas + shared library)
**Performance Goals**: zero measurable request-latency impact (level check is an integer compare; handler I/O already async-buffered by runtime)
**Constraints**: no new AWS resources; SSE untouched (incl. via shared imports); Text log format preserved; existing consumers byte-compatible; INFO floor (never DEBUG)
**Scale/Scope**: 6 entrypoint files + 1 new shared helper + ~4 masking edits in notification module + 1 coverage-guard unit test + preprod verification additions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution requirement | Status |
|---|---|
| Observability: structured logs for requests (request id, latency, outcome) without raw input text | PASS — powertools JSON request lines (dashboard) unchanged; this feature adds module-level INFO without touching them; FR-012 masks PII before new lines become visible |
| Security & IAM: least privilege; no new secrets handling | PASS — no IAM change, no new resources (FR-005) |
| SAST/IaC checks in CI | PASS — code-only change rides existing gates (ruff, bandit, semgrep) |
| Git workflow: GPG-signed, feature branch, lint/format pre-push | PASS — standing practice on this branch |
| Rollback: quick rollback support | PASS — single revertable code commit; no config/schema migration |
| Dashboard/metrics contracts | PASS — no metric shape changes; the one log metric filter untouched (Text preserved) |

No violations. Complexity Tracking section not needed.

**Post-Phase-1 re-check (2026-07-25)**: design artifacts introduce no new
projects, resources, or patterns beyond one shared helper module; gates
unchanged — PASS.

## Project Structure

### Documentation (this feature)

```text
specs/001-lambda-log-visibility/
├── plan.md              # This file
├── research.md          # Phase 0: mechanism decision + verified facts
├── data-model.md        # Phase 1: logging-configuration entities
├── quickstart.md        # Phase 1: verify-INFO-visibility procedure
├── contracts/
│   └── logging-config.md  # Phase 1: helper API + log-shape contract
├── checklists/
│   └── requirements.md  # Stage 1 spec-quality checklist
└── tasks.md             # Stage 7 (/speckit.tasks — not this command)
```

### Source Code (repository root)

```text
src/lambdas/shared/
└── logging_config.py            # NEW: configure_lambda_logging() helper

src/lambdas/dashboard/handler.py     # + configure_lambda_logging() call
src/lambdas/ingestion/handler.py     # + call (keeps its own setLevel(INFO))
src/lambdas/analysis/handler.py      # + call (keeps its own setLevel(INFO))
src/lambdas/metrics/handler.py       # + call (currently configures nothing)
src/lambdas/notification/handler.py  # + call (keeps LOG_LEVEL env read)
src/lambdas/canary/handler.py        # + call (keeps its own setLevel)

src/lambdas/notification/sendgrid_service.py  # FR-012: mask recipient email
src/lambdas/notification/handler.py           # FR-012: stop raw-event dump widening (see research R-7)

tests/unit/shared/test_logging_config.py       # helper semantics (C-1..C-6, C-8)
tests/unit/test_entrypoint_logging_coverage.py # C-7 guard: GLOB src/lambdas/*/handler.py minus {sse_streaming, chaos_restore}
tests/e2e/test_log_visibility.py               # preprod: dark-line evidence per function (FR-008)
scripts/verify-log-visibility.py               # on-demand dashboard probe + SC-006 drill (AR#2 F6)
```

**Structure Decision**: single-project layout; the only new module is
`src/lambdas/shared/logging_config.py`. SSE (`src/lambdas/sse_streaming/`)
deliberately absent from the change set (FR-006); the helper has no
import-time side effects, so SSE importing other shared modules is unaffected.

## Mechanism Decision (core of this plan)

**Chosen: O2+ — shared root-wire helper with hardening riders.**

`configure_lambda_logging()` in `src/lambdas/shared/logging_config.py`:

1. `logging.getLogger().setLevel(logging.INFO)` — the one-line cure for the
   diagnosed mechanism (root handler exists on every awslambdaric Lambda;
   only the level is missing).
2. Pin noisy/dangerous third-party loggers: `httpx`, `httpcore` →
   `logging.WARNING` (FR-010; blocks the finnhub key-in-URL exposure path).
3. Explicitly NO handler creation, NO format change, NO powertools coupling —
   the function is a level-setter only, idempotent, callable at import time
   of each entrypoint.
4. Respects an optional `LOG_LEVEL` env override (existing notification
   pattern generalized), floor-clamped so DEBUG requires an explicit
   deliberate value and defaults remain INFO (FR-002).

Riders in the same change:

- FR-012 masking edits in the notification module (currently-dark lines that
  would newly expose recipient emails).
- Coverage-guard unit test: walks the six deployed entrypoints and fails if
  any does not call the helper — this is the testable form of the
  "future Lambda inherits the fix" design note (a new handler copied from an
  existing one carries the call; a new handler written from scratch fails
  the guard the moment it's added to the deployed set).
- Preprod E2E additions asserting an INFO line from a non-entrypoint module
  per function (FR-008), alias-qualified invocation for dashboard.

**Why not O1 (terraform `logging_config`, ApplicationLogLevel=INFO)**:
hard-coupled to JSON format → obligates in-change migration of the
`dashboard_import_errors` Text-pattern metric filter, re-validation of the
deploy-pipeline grep, and acceptance of runtime-JSON-wrapping around the
existing powertools/StructuredLogger JSON lines (nested-JSON consumers).
It is also NOT actually zero-code: FR-010's httpx pin is code regardless of
mechanism, because ALC raises the floor for every logger including
third-party. Post-incident risk appetite (7 defects closed 48h ago) argues
against the largest observable-shape change. Kept as the signposted future
migration (see research R-6) since it is the only mechanism that also
covers a hypothetical 8th Lambda with zero code.

**Why not O3 (powertools + `copy_config_to_registered_loggers`)**: changes
every stdlib line to JSON (same consumer migration as O1) and adds a
propagation-rewiring step across 71 registered loggers whose interaction
with the metrics module's self-handled logger and the five self-leveling
entrypoints multiplies the FR-004/FR-011 verification surface. The benefits
(correlation IDs on module lines) are real but belong in the signposted
structured-logging migration, not in the incident-follow-up visibility fix.

**Why not O4 (67-file sweep)**: maximal diff for the same observable outcome
as O3; rejected on scale alone.

## Verification Design (FR-008 / SC-001..007)

Universal evidence line (AR#2): the helper's C-8 self-test probe — one
static INFO line per cold start on the helper's own un-leveled child logger
— can only appear when root=INFO is live, in every function. Per-function
checks assert it PLUS the strongest function-specific dark line:

- **Dashboard (on demand)**: `scripts/verify-log-visibility.py` (owned by
  this feature) performs an alias-qualified invoke of the three session-
  refresh outcomes (no cookie / garbage cookie / valid session) then
  `filter_log_events` for `refresh.cookie_absent` / `refresh.rejected` /
  `refresh.success` (router_v2.py:742/757/762 — verified logger.info on the
  stdlib logger) — this IS the SC-006 drill.
- **Canary**: fires every 5 minutes; assert the C-8 self-test line within
  15 minutes of deploy (AR#2 F1: canary has NO first-party imports — any
  `[INFO]` grep is a false-positive verifier since its entrypoint self-
  levels today; only the probe line discriminates).
- **Ingestion/analysis**: next scheduled cycle; assert SPECIFIC dark module
  lines (ingestion: storage.py:184 "Storage operation complete"; analysis:
  sentiment.py INFO sites), not any-`[INFO]`.
- **Metrics**: C-8 self-test line only (AR#2 F2: no other dark INFO exists
  in this function; its StructuredLogger lines are visible pre-fix).
- **Notification**: synthetic empty-digest invoke (flat payload
  `{"notification_type": "digest"}`, handler accepts it directly); assert
  the DARK digest_service lines ("Found users due for digest" /
  "Digest processing complete") — AR#2 F3 established these exist and
  cannot appear pre-deploy. No email is sent; no test-mode path needed.
- **FR-004 baseline**: before deploy, capture 24h of metrics-Lambda log
  events and count StructuredLogger duplicates (the propagate=True question);
  re-run after deploy; assert no additional duplication.
- **SC-005 p50 procedure (AR#2 F7)**: fixed workload of 20 identical
  dashboard requests pre- and post-deploy; count INFO events per request-id;
  compare p50; assert delta ≤10.
- **SC-003 positive control (AR#2 F8)**: the metric filter's field order may
  never have matched application lines (pre-existing question, research
  R-9). Fire one synthetic ImportModuleError-shaped line pre- and
  post-deploy; identical filter behavior in both = no regression regardless
  of whether the filter was ever alive.
- **SC-007 content safety**: targeted queries for `token=` AND `@`-bearing
  address patterns in new INFO lines across all six groups during the first
  week (both patterns, per spec).

## Rollback

Single revert of the feature commit restores the status quo (root level
returns to WARNING). No infrastructure state, no data migration, no consumer
migration to unwind. This is the smallest-rollback option of the four — a
deliberate selection criterion 48 hours after a 7-defect incident.

## Adversarial Review #2

Independent cross-artifact reviewer (post-Clarifications): 14 findings —
0 CRITICAL, 3 HIGH, 5 MEDIUM, 6 LOW. All resolved in this revision.

**Drift found (Stage 1 → Stage 5)**: the Clarifications pass introduced a
factually wrong premise (notification empty-digest "exercises only
entrypoint INFO" — digest_service actually has dark INFO lines that fire on
every run), and the plan contradicted the settled no-test-mode-send decision.
Both corrected.

| # | Sev | Finding (compressed) | Resolution |
|---|-----|----------------------|------------|
| 1 | HIGH | Canary FR-008 unsatisfiable: no first-party imports exist; quickstart any-INFO grep passes PRE-deploy (false-positive verifier) | C-8 self-test probe line added to helper contract — the only line that discriminates; quickstart + FR-008 rewritten |
| 2 | HIGH | Metrics function has zero currently-dark INFO (StructuredLogger self-handled, visible today) — its check was circular, SC-002 vacuous for it | Same C-8 probe is its evidence; spec FR-008 amended honestly |
| 3 | HIGH | Notification Clarification premise false — empty digest DOES emit dark digest_service INFO (count=0 + completion lines, PII-safe); plan reopened settled decision with nonexistent "test-mode send" | Clarification rewritten to use digest_service lines as evidence; plan verification bullet corrected; stronger check than the compromise it replaces |
| 4 | MEDIUM | Coverage-guard set undefined — hardcoded list would make regression-resistance circular | C-7 now mandates glob src/lambdas/*/handler.py minus documented exclusions {sse_streaming, chaos_restore} |
| 5 | MEDIUM | C-4 latch contradicted C-1 (external mutation between calls) | Levels re-assert every call; latch scoped to self-test emission only; data-model updated |
| 6 | MEDIUM | quickstart invoked scripts/verify-log-visibility.py — absent from plan file list; FR-008 on-demand check had no owning artifact | Script added to Project Structure + tasks |
| 7 | MEDIUM | SC-005 p50 had no defined procedure (FR-004 comparison never touches dashboard) | 20-request fixed-workload p50 procedure added to Verification Design |
| 8 | MEDIUM | Contract line-shape vs metric-filter field order disagree — filter may never have matched (SC-003 vacuously true) | research R-9 records the pre-existing question; SC-003 gains a positive control; filter fix (if dead) carded separately |
| 9 | MEDIUM | FR-012 review record incomplete (digest_service, secrets.py, cognito.py unreviewed in R-8) | R-8 completed with reviewed-no-exposure verdicts; repo-wide PII-in-INFO grep recorded clean |
| 10 | LOW | notification handler:170/220 (+error paths) same already-visible email class as :56, unrecorded | Spec FR-012 recorded-not-endorsed bullet now covers the full set, one card |
| 11 | LOW | C-6 vs C-2 theoretical conflict if httpx ever deliberately configured | C-6 scoped to "other than root/httpx/httpcore" |
| 12 | LOW | C-5 wording could be misread vs call-at-entrypoint-import | Clarifying sentence added to C-5 |
| 13 | LOW | quickstart SC-007 grep missed @-pattern; SC-004 conflicts with deliberate DEBUG window | Both queries in quickstart; SC-004 caveat noted there |
| 14 | LOW | data-model "applied after root so pins win" — wrong rationale (order not load-bearing) | Rationale corrected (pins win via own explicit level) |

**Cross-artifact consistency**: verified post-edit — spec FR-008/Clarifications,
plan Verification Design, contract C-1..C-8, data-model, research R-8/R-9, and
quickstart all describe the same design (probe line + specific dark lines +
glob-based guard). Verified accurate by AR#2's independent reads:
router_v2.py:742/757/762 classification set matches the drill exactly; 7
terraform lambda instantiations confirm the six-function scope; exactly one
log metric filter repo-wide.

**Gate: 0 CRITICAL, 0 HIGH remaining.**
