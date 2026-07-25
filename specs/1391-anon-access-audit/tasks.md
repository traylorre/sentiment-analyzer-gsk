# Tasks — Feature 1391 anon-access-audit (RE-SCOPED)

**Spec:** `./spec.md` · **Plan:** `./plan.md` · **Branch:** `1381-session-persistence` (worktree)
**Nature:** Two Dashboard-Lambda access-control fixes (GAP-2, GAP-3). Dependency-ordered.
`[P]` = parallelizable with siblings.

> Planning artifact only. Do NOT execute (`/speckit.implement` not invoked). SSE / GAP-1 is
> **deferred** — no tasks here touch `src/lambdas/sse_streaming/*` or `src/lambdas/dashboard/sse.py`.

---

## Phase 0 — Baselines (capture "before")

- **T001 [P]** GAP-2 baseline: unit repro showing `POST /api/v2/configurations/{any}/refresh` with
  **no** credential currently returns 202. Record as failing baseline. (Covers: GAP-2, AR#1 H1.)
- **T002 [P]** GAP-3 baseline: a free (non-operator) JWT hits `PUT /chaos/gate` /
  `POST /chaos/andon-cord` in a preprod-like env (`ENVIRONMENT` in the allowlist) and is accepted.
  Record baseline. (Covers: GAP-3, AR#1 M1.)

## Phase 1 — GAP-2 (MEDIUM, gated): authenticated + owned refresh

- **T003** In `router_v2.py::trigger_refresh` (`:1320-1324`) adopt the sibling `get_refresh_status`
  (`:1302-1317`) shape: `event = config_router.current_event.raw_event`; `table =
  get_users_table()`; `_require_user_id(event, table=table)` (401 on failure); `_get_config_with_
  tickers(table, user_id, config_id)` (404 on non-owner); then `market_service.trigger_refresh`.
  Owner → 202 (unchanged). Keep the diff confined to this function (NFR-005 / 1384). (Covers:
  FR-001; resolves AR#1 H1.)
- **T004 [P]** Contract/unit tests: `POST .../refresh` → 401 (no auth), 404 (valid session,
  non-owner config; assert no id echo), 202 (owner), 202 (anonymous-session owner). (Covers: FR-004,
  SC-001.) **Depends: T003.**

## Phase 2 — GAP-3 (MEDIUM, gated): operator-gate chaos routes

- **T005** Attach `middlewares=[require_role_middleware("operator")]` to the **mutating/control**
  chaos routes: `PUT /chaos/gate` (`:1578`), `POST /chaos/andon-cord` (`:1626`),
  `POST /chaos/reports` (`:1238`), `POST /chaos/reports/plan` (`:1302`),
  `DELETE /chaos/reports/<id>` (`:1484`). Ensure `require_role_middleware` is imported from
  `src.lambdas.shared.middleware`. (Covers: FR-002; resolves AR#1 M1/M2.)
- **T006** Attach the same middleware to the **experiment** mutations (`POST /chaos/experiments`
  `:954`, `.../start` `:1079`, `.../stop` `:1128`, `DELETE /chaos/experiments/<id>` `:1206`) while
  **retaining** their `_is_dev_environment()`→404 gate (additive DiD). (Covers: FR-002, NFR-002.)
  **Depends: T005** (shared import / pattern).
- **T007** Attach the same middleware to the **read-only** chaos routes: `GET /chaos/gate` (`:1546`),
  `GET /chaos/health` (`:1514`), `GET /chaos/metrics` (`:1659`), `GET /chaos/reports` (`:1348`),
  `GET /chaos/reports/<id>` (`:1413`), `GET /chaos/reports/<id>/compare` (`:1440`),
  `GET /chaos/reports/trends/<scenario_type>` (`:1384`), `GET /chaos/experiments*` (`:1017,1050`).
  Per FR-003 justification (operator-only clients, no anon read flow, internals disclosure).
  (Covers: FR-003; resolves AR#1 L1.) **Depends: T005.**
- **T008 [P]** Decide the inline `_get_chaos_user_id_from_event → 401` block: keep as harmless second
  gate OR remove. If removed, add/keep a test proving anonymous/no-token still yields 401 via the
  middleware. Retain `check_environment_allowed()` on gate/andon/health/metrics untouched. (Covers:
  FR-002, spec §6, AR#2 D4.) **Depends: T005–T007.**
- **T009 [P]** Tests: for `PUT /chaos/gate` + `POST /chaos/andon-cord` (mutating) and `GET
  /chaos/gate` (read): 401 (no/anonymous), 403 (free JWT without `operator`), allowed (operator
  JWT). OPTIONS preflight → NOT 401/403. Experiment route: retained `_is_dev_environment()` 404 in
  non-dev stacks with the role gate. (Covers: FR-004, SC-002, AR#1 M1/M2, §6 preflight.)
  **Depends: T005–T007.**

## Phase 3 — Regression, static validation, close-out

- **T010 [P]** Regression (FR-005): frontend owner-refresh still 202 (session credential path);
  operator admin chaos access intact; `GET /health` still anon 200; anon-ok reference routes
  unchanged. (Covers: FR-005, SC-003, US-1/US-3.)
- **T011** `ruff check src/ tests/ && ruff format --check`; `bandit -c pyproject.toml -r src/ -ll`.
  venv active. (Covers: NFR-003, NFR-004.)
- **T012** `pytest tests/unit/ tests/contract/ -m "not preprod"` green, including the new
  auth-/role-posture tests (T004, T009). (Covers: FR-004.)
- **T013** Record in Issue #501: GAP-2 + GAP-3 closed on the Dashboard Lambda (with the Appendix A
  inventory as evidence); **GAP-1 (SSE) explicitly carried as CRITICAL-deferred** — #501 remains
  **open** pending the separate SSE feature. Do NOT close #501. (Covers: FR-006, SC-004.)
- **T014 [P]** Coordinate the `router_v2.py` GAP-2 diff with **Feature 1384** (shared hotspot):
  confirm rebase ordering / no overlapping edit to `trigger_refresh`'s surrounding region before
  merge. (Covers: NFR-005.)

---

## Requirement → Task Map

| Requirement | Tasks |
|---|---|
| FR-001 refresh auth+ownership (GAP-2) | T001, T003, T004 |
| FR-002 operator gate mutating/control chaos (GAP-3) | T002, T005, T006, T008, T009 |
| FR-003 operator gate read-only chaos (GAP-3) | T007, T009 |
| FR-004 posture tests | T004, T009, T012 |
| FR-005 no regression | T010 |
| FR-006 GAP-1 deferral recorded, #501 stays open | T013 |
| NFR-001 no new AWS | (whole plan — code only) |
| NFR-002 Bearer+role boundary | T005, T006, T007 |
| NFR-003/004 SAST/GPG/venv | T011 |
| NFR-005 1384 serialization | T003, T014 |

---

## Adversarial Review #3 (execution risk — READY/BLOCKED)

- **Highest risk = over-gating a chaos route a legitimate non-operator flow needs.** FR-003 gates the
  **read-only** chaos routes on `operator` too. If any non-operator client legitimately reads
  `/chaos/*`, this breaks it. **Assessed:** the only consumer is the operator-gated `(admin)`
  dashboard (`frontend/src/app/(admin)/layout.tsx:30-33`, `useIsOperator` + comment "backend
  require_role_middleware('operator') remains"); the anon liveness probe is the separate
  `GET /health`, untouched. So over-gating risk is **LOW**, but it is the highest-consequence
  unknown. **Mitigation:** T010 pins the operator flow green and `GET /health` anon-200 before merge;
  if a non-operator chaos reader surfaces in preprod, that route drops back to `_get_chaos_user_id_
  from_event` (auth-only) with a documented justification rather than blocking the whole feature.
  **Rework likelihood: LOW–MEDIUM**, isolated to the read-route subset (T007).
- **Second risk = no operator principal to test GAP-3.** T002/T009 need a JWT whose `roles` claim
  contains `operator`. Locally this is minted in the test fixture (moto/JWT helper), so unit tests
  are unblocked. **Preprod** verification of a real operator needs an account with `is_operator=true`
  (`roles.py:78-81`). **OPEN QUESTION (owner):** does a preprod operator principal exist to smoke the
  live 403-for-free / allow-for-operator path? A check, not a planning gate — unit coverage suffices
  for merge.
- **Third risk = 1384 merge collision on `router_v2.py`.** GAP-2 edits `trigger_refresh`
  (`:1320-1324`). If 1384 rewrites the surrounding router, a rebase conflict is possible.
  **Mitigation:** T014 confines the diff and coordinates ordering; the change is a 5-line function
  body mirroring an existing sibling, trivially re-appliable.
- **Fourth risk = redundant/removed inline chaos check.** T008 removing the inline non-anon check
  could regress the anonymous-401 behavior if the middleware ordering differs. **Mitigation:** T009
  explicitly asserts anonymous→401 post-change; safest path is to keep the inline check.

**Status: READY.** Dependencies ordered (baselines T001/T002 → fixes T003/T005–T007 → tests
T004/T009 → close-out). No planning blocker. One owner check outstanding (preprod operator principal
for live GAP-3 verification) — does not gate implementation, which is fully unit-testable. SSE/GAP-1
intentionally absent (deferred).
