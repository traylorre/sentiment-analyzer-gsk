# Tasks — Feature 1397: oauth-dup-cleanup

**Deliverable:** a safe-by-default, dry-run-by-default consolidation script (`scripts/consolidate_oauth_duplicates.py`) + moto tests. **No destructive execution in this feature.** The `--apply` step against live preprod is a SEPARATE, owner-approved action after Feature 1395 deploys and Open Q1 is answered.

Legend: [P] = parallelizable. Each task cites the FR(s) it satisfies.

---

## Phase 0 — Scaffolding

- **T001** Create `scripts/consolidate_oauth_duplicates.py` with argparse skeleton and module docstring. Args: `--table` (required, no default), `--cognito-sub` (required), `--apply`, `--backup-file`, `--allow-prod`, `--i-understand-destructive`, `--verify`, `--rollback`. Docstring MUST state: dry-run default, the deliberate inversion of the `migrate_status_field.py --dry-run` convention and why. (FR-010, FR-014)
- **T002** [P] Create `tests/unit/scripts/test_consolidate_oauth_duplicates.py` with a moto DynamoDB fixture that builds a table with `by_cognito_sub`, `by_provider_sub`, `by_email` GSIs and seeds a synthetic N-duplicate group. Mark `not preprod`.

## Phase 1 — Enumerate & select (non-destructive)

- **T003** Implement `enumerate_group(table, cognito_sub)`: paginate `by_cognito_sub` GSI, then strongly-consistent GetItem each PROFILE. Cross-check shared email + provider_sub; return group + divergence report. Never trust `Limit=1`. (FR-001, FR-003, EC-3, EC-5)
- **T004** Implement `select_canonical(group)`: sort by `(created_at asc, user_id asc)`; null/malformed `created_at` sorts LAST and never becomes canonical (flag). Return canonical + non-canonical list. (FR-002, A6)
- **T005** Implement `coordination_gate()`: assert canonical rule == documented 1395 tie-break; if unconfirmed (Open Q1), set `apply_blocked=True` with reason. (FR-002a)
- **T006** Implement `inventory_owned(table, user_id)`: paginate `PK=USER#{id}`, classify by SK prefix (PROFILE/CONFIG#/ALERT#/NOTIF#/PREF#/SESSION#/unknown). Unknown reported, never dropped. (FR-004)
- **T007** Implement `render_report(...)`: canonical, 9 non-canonical, per-record inventory, planned per-item action. **Dry-run ends here — zero writes.** (US1, FR-010)

## Phase 2 — Backup & rollback

- **T008** Implement `backup_group(group, path)`: full-fidelity local JSON export of all affected items (PROFILEs + owned). Then `validate_backup(path, expected_count)`: re-open, parse, assert count match; abort on mismatch. No S3 / no new AWS resource. (FR-011, A5)
- **T009** Implement `rollback(table, backup_file)`: `put_item` every exported item verbatim; idempotent; runs from file alone. (FR-015)

## Phase 3 — Apply (destructive core — gated, not executed here)

- **T010** Implement `reassign_item(table, item, canonical_id)`: reassign-then-delete. Target `PK=USER#{canonical}`, same SK. On collision, write loser under `SK={SK}#dup-{src_short}` with `merged_from` + `collision=true`; else conditional put with `merged_from`. Delete source ONLY after target write confirmed; else mark `partial`, do NOT delete. Skip any item already carrying `merged_from`. (FR-005, FR-006, FR-012, FR-013, A1, A4)
- **T011** Implement `discard_sessions(table, user_id)`: delete SESSION# items, log each. (FR-007)
- **T012** Implement `delete_noncanonical_profile(table, user_id)`: only after ALL children resolved; else retain + `partial`. Backup+audit the PROFILE before delete. (FR-008, A4)
- **T013** Implement `apply(...)` orchestration: gates (require `--apply` + `--i-understand-destructive` + validated backup + not `apply_blocked` + env guard), low-traffic advisory (FR-017), then per-non-canonical: reassign children → discard sessions → delete PROFILE. Returns `completed | partial | already-consolidated`. (FR-010, FR-011, FR-013, FR-014, FR-017)

## Phase 4 — Verify & audit

- **T014** Implement `verify(table, canonical, shared_ids)`: query each GSI for shared cognito_sub/provider_sub/email; assert exactly one USER item == canonical; FAIL loudly otherwise. (FR-009, US5)
- **T015** Implement `audit_log`: append-only JSONL `{ts, action, source_key, target_key, outcome}` for every reassign/divert/delete; use `sanitize_for_log` for identifiers. (FR-012, constitution log-injection)

## Phase 5 — Tests (moto, `not preprod`)

- **T016** [P] `test_dry_run_makes_no_writes`: seed 10-dup group, run default mode, assert zero mutations (spy on put/update/delete) and report names earliest-created canonical. (SC-1, FR-010)
- **T017** [P] `test_consolidation_preserves_owned_data`: seed group where a NON-canonical owns configs/alerts/notifs; run apply; assert all present under canonical, none lost. (SC-3, US2, FR-005)
- **T018** [P] `test_collision_preserves_loser`: canonical + non-canonical own same-SK config; apply; assert canonical item untouched, loser present under `#dup-` SK with `collision=true`, nothing dropped. (FR-006, EC-1)
- **T019** [P] `test_idempotent_apply`: run apply twice; second run makes zero destructive writes, returns `already-consolidated`. (SC-4, FR-013, A1)
- **T020** [P] `test_partial_failure_resumable`: inject a reassignment failure on 1 of 3 children; assert source NOT deleted, PROFILE retained, run=`partial`; re-run completes. (FR-012, A4, EC-4)
- **T021** [P] `test_rollback_restores_all`: apply, then rollback from backup; assert all original records byte-for-byte restored. (SC-5, FR-015)
- **T022** [P] `test_prod_guard`: table name containing `prod` without `--allow-prod` hard-stops before any read/write. (SC-6, FR-014)
- **T023** [P] `test_verify_asserts_single`: post-apply verify passes on one record; a synthetic orphan projection makes verify FAIL. (FR-009, US5)
- **T024** [P] `test_null_created_at_never_canonical`: a record with missing `created_at` never selected canonical, sorts last, flags. (FR-002, A6)
- **T025** [P] `test_apply_blocked_until_coordination`: `apply_blocked` (Open Q1 unconfirmed) prevents any destructive write even with all flags. (FR-002a)

## Phase 6 — Owner gate (NOT executed by this feature)

- **T026** [GATED] Open Q1 rule alignment is CONFIRMED via 1395 FR-004 (earliest-`created_at`, `user_id` asc — both crown `dd0da3c8`). Residual: confirm with owner that **Feature 1395 is DEPLOYED** (live, preventing new fragmentation) before proceeding. BLOCKS T027. (T004's canonical rule needs no change — 1395 agrees.)
- **T027** [GATED — OWNER APPROVAL REQUIRED] Live preprod `--apply` run: dry-run review → backup → `--apply --i-understand-destructive` → `--verify`. Requires: 1395 deployed, Q1 answered, explicit owner go (Q4). **This feature does NOT perform T027.**

---

## FR → Task coverage

| FR | Tasks |
|---|---|
| FR-001 | T003 |
| FR-002 / 002a | T004, T005, T024, T025, T026 |
| FR-003 | T003 |
| FR-004 | T006 |
| FR-005 | T010, T017 |
| FR-006 | T010, T018 |
| FR-007 | T011 |
| FR-008 | T012 |
| FR-009 | T014, T023 |
| FR-010 | T001, T007, T013, T016 |
| FR-011 | T008, T013 |
| FR-012 | T010, T015, T020 |
| FR-013 | T010, T013, T019 |
| FR-014 | T001, T013, T022 |
| FR-015 | T009, T021 |
| FR-016 | (design, plan §4 — no code reuse) |
| FR-017 | T013 |

---

## Adversarial Review #3 — Highest-risk task, rework likelihood, ship gate

**Highest-risk task: T027 (live preprod `--apply`) — and by design it is the one gated task.**

| Risk | Task | Analysis |
|---|---|---|
| Irreversible data loss on live records | T027 | The only truly destructive step. Mitigated by: dry-run default (T001/T016), mandatory validated backup (T008), reassign-then-delete (T010), rollback (T009/T021), idempotency (T019), env guard (T022). But no amount of code makes a live delete of 9 USER records something a script should do unsupervised. |
| Canonical mismatch with 1395 | T005/T026 | Rule alignment is CONFIRMED: 1395's spec exists (`specs/1395-oauth-account-integrity/`) and FR-004 pins the same earliest-`created_at` rule, so both crown `dd0da3c8`. T026 narrows to confirming 1395 is DEPLOYED (operational status), which BLOCKS T027. The residual dependency is 1395's deploy status, not a rule negotiation. |
| Rework likelihood | T010, T004 | **Medium.** T010's collision/idempotency semantics are the most subtle code (borrowed-but-corrected from `merge.py`); expect 1–2 iterations against T018/T019/T020. T004 canonical rule may need a one-line change if T026 reveals 1395 picks differently — cheap rework, isolated to one function. |
| Lowest rework | T003, T006, T007, T008 | Enumeration/inventory/report/backup are straightforward reads + serialization; well-specified, low churn. |

**Most-likely rework:** T010 (reassign/collision/idempotency edge cases surfaced by T018/T019/T020) and possibly T004 (canonical rule) if Q1 resolves against the assumption. Both are localized, single-function changes — no cross-cutting redesign expected.

### Gate — Adversarial Review #3

**READY FOR IMPLEMENTATION — of everything EXCEPT the destructive execution.**

Phases 0–5 (the script logic, all safety rails, and the full moto test suite) are ready to implement now: they are non-destructive, fully specified, and consistent across spec/plan/tasks. T026–T027 are **BLOCKED — OWNER APPROVAL REQUIRED**, and that block is CORRECT, not a defect. The destructive `--apply` against live preprod must NOT run until:

1. **Feature 1395 is deployed** (stops new fragmentation), AND
2. **Feature 1395 confirmed DEPLOYED** — Open Q1's rule alignment is already settled (1395 FR-004 == earliest-`created_at`, `user_id` asc; both crown `dd0da3c8`); the residual is confirming 1395 is live so post-cleanup single-record reads are deterministic, AND
3. **Explicit owner go/no-go (Open Q4)** on running the destructive step, AND
4. **A validated backup exists** for the run.

**Ship the plan + script skeleton + tests. Do NOT ship a live consolidation.** The gate on T027 is the intended terminal state of this feature.
