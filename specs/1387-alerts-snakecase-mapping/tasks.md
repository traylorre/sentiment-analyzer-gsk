# Tasks: Alerts Quota-Burn Mitigation (restore delete/disable control)

**Input**: Design documents from `/specs/1387-alerts-snakecase-mapping/`
**Prerequisites**: plan.md, spec.md
**Scope**: MINIMAL mitigation. `create` + `getNotifications` DEFERRED to the full-remap
board card — no task here touches them.

**Tests**: A regression test is included per constitution (Implementation Accompaniment
Rule). Vitest, mirroring `frontend/tests/unit/lib/api/configs.test.ts`.

**Organization**: Foundation (Raw type + read mapper) → wire read paths (unblocks delete +
render) → wire update path (unblocks disable) → regression lock. One source file; test is
additive.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1 delete, US2 disable) the task serves
- Exact file paths included in every task

---

## Phase 1: Foundation — Raw type + read mappers (blocks the read paths)

- [ ] **T001** [US1,US2] Add snake_case `RawAlert` interface to
  `frontend/src/lib/api/alerts.ts` mirroring backend `AlertResponse`
  (`src/lambdas/dashboard/alerts.py:47-60`): `alert_id`, `config_id`, `ticker`,
  `alert_type`, `threshold_value`, `threshold_direction`, `is_enabled`,
  `last_triggered_at`, `trigger_count`, `created_at`; and `RawAlertList`
  (`{ alerts: RawAlert[]; total: number; daily_email_quota: { used; limit; remaining?;
  resets_at } }`, `alerts.py:62-67`). **Satisfies**: FR-001.
- [ ] **T002** [US1,US2] Add `mapAlert(raw: RawAlert): AlertRule` in `alerts.ts` — every
  field snake→camel, preserving `last_triggered_at: null` as `null`. MUST populate
  `alertId`, `isEnabled`, `thresholdValue`, `thresholdDirection`, `alertType`, `ticker`,
  `triggerCount`, `lastTriggeredAt`, `configId`, `createdAt`. Mirror `configs.ts:34-44`.
  **Satisfies**: FR-001. **Depends**: T001.
- [ ] **T003** [US1] Add `mapAlertList(raw: RawAlertList): AlertList` in `alerts.ts` —
  `(raw.alerts ?? []).map(mapAlert)`, `total`, and `dailyEmailQuota` from
  `daily_email_quota` (`resets_at`→`resetsAt`) with a safe default
  `{ used: 0, limit: 10, resetsAt: '' }` when the block is absent. Mirror `configs.ts:46-51`
  `?? []` guard. **Satisfies**: FR-001. **Depends**: T002.

**Checkpoint**: Read paths can produce fully-populated `AlertRule`s — `alertId`,
`isEnabled`, `thresholdValue` are no longer `undefined`.

---

## Phase 2: Wire read paths — unblocks delete + card render (destructive-path fix)

- [ ] **T004** [US1] Rewrite `list` (`alerts.ts:14-15`) and `listByConfig`
  (`alerts.ts:20-21`) to `api.get<RawAlertList>(...)` then `return mapAlertList(raw)`.
  **Satisfies**: FR-001, FR-003. **Depends**: T003. This is the task that opens the delete
  confirm dialog: `alert.alertId` now resolves, so `alert-list.tsx:84` →
  `page.tsx:98` sets a real `deletingAlertId`, the dialog un-gates (`page.tsx:117`), and
  confirming issues `DELETE /api/v2/alerts/{real-id}`. It also makes
  `alert-card.tsx:94` `thresholdValue.toFixed(2)` stop throwing.
- [ ] **T005** [US1] Rewrite `get` (`alerts.ts:26-27`) to `api.get<RawAlert>(...)` then
  `return mapAlert(raw)`. **Satisfies**: FR-001. **Depends**: T002.

**Checkpoint**: The Alerts page renders, the delete dialog opens, and delete targets the
real id — SC-001, SC-003.

---

## Phase 3: Wire update path — unblocks disable (stops the burn without deleting)

- [ ] **T006** [US2] Add `toUpdateBody(req: UpdateAlertRequest): Record<string, unknown>`
  in `alerts.ts` — only-defined-keys, snake_case (`threshold_value`, `threshold_direction`,
  `is_enabled`). Mirror `configs.ts:59-70`. **Satisfies**: FR-002.
- [ ] **T007** [US2] Rewrite `update` (`alerts.ts:38-39`) to
  `api.patch<RawAlert>(..., toUpdateBody(updates))` then `return mapAlert(raw)`.
  **Satisfies**: FR-002. **Depends**: T006, T002. With T004 supplying the real id and
  correct `isEnabled`, the toggle (`alert-card.tsx:107`) now sends
  `PATCH /api/v2/alerts/{real-id}` with `{ is_enabled: false }`, which the backend accepts
  (`alerts.py:78-91,361-370`), flipping stored `status` to `disabled` so
  `alert_evaluator.py:157` skips it and no further emails fire.

**Checkpoint**: A user can disable a noisy alert and it persists — SC-002.

---

## Phase 4: Regression lock + docs

- [ ] **T008** [P] Add a header comment to `alerts.ts` mirroring `configs.ts:10-16` —
  reference feature 1387, the config-delete precedent, the "map explicitly" decision, and
  the DEFERRED full remap (create + notifications). **Satisfies**: FR-005 (traceability).
- [ ] **T009** [US1,US2] Create `frontend/tests/unit/lib/api/alerts.test.ts` mirroring
  `frontend/tests/unit/lib/api/configs.test.ts`. Mock `@/lib/api/client`. Assert:
  - **Field mapping**: given a snake_case `RawAlert` fixture, `mapAlert` yields
    `alertId`, `isEnabled`, `thresholdValue` (and the rest) defined and correct;
    `last_triggered_at: null` preserved as `null`; `daily_email_quota.resets_at`→
    `dailyEmailQuota.resetsAt`; `?? []` tolerance for a missing `alerts` array; safe quota
    default when absent.
  - **Delete real-id guard**: after `list`, the mapped alert's `alertId` is the real id,
    and a delete call issues `DELETE /api/v2/alerts/{real-id}` — the string `undefined`
    never appears in the path.
  - **Disable real-id + snake body**: `update("al-9", { isEnabled: false })` issues
    `PATCH /api/v2/alerts/al-9` with body `{ is_enabled: false }` (not `{ isEnabled }`, not
    `/alerts/undefined`).
  **Satisfies**: FR-004; locks SC-001..SC-004. **Depends**: T004, T005, T007.
- [ ] **T010** Run `cd frontend && npm test -- alerts` (Vitest); confirm green and that the
  existing `configs.test.ts` still passes (shared-harness regression check). **Depends**:
  T009.

---

## Dependency Graph

```text
T001 ─ T002 ─┬─ T003 ─ T004 ─┐
             ├─ T005 ────────┤
             │               ├─ T009 ─ T010
T006 ─ T007 ─┘               │
T008 (parallel) ─────────────┘
```

## Requirement → Task Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 (read mapper: alertId/isEnabled/thresholdValue + list envelope + tolerances) | T001, T002, T003, T004, T005 |
| FR-002 (update body camel→snake, accepted disable) | T006, T007 |
| FR-003 (delete hits real id, no `undefined` in path) | T004, T009 |
| FR-004 (regression test locks real-id delete/disable) | T009, T010 |
| FR-005 (frontend-only, deferral traceability) | T008 |

## Adversarial Review #3

**Highest-risk task**: **T004** (rewrite `list`/`listByConfig` to map). It is the single
task that converts `alert.alertId` and `alert.isEnabled` from `undefined` to real values —
the precondition for the delete dialog opening, the card rendering, and the toggle
computing the correct new state. If the `daily_email_quota` sub-object is mismapped or the
`?? []` guard is dropped, `use-alerts.ts` consumers read `undefined` and the page can still
crash on `thresholdValue.toFixed` (`alert-card.tsx:94`), leaving the delete button
unreachable and the burn unstopped. It also touches the one field whose shape differs
between backend (`used/limit/remaining/resets_at`) and frontend (`used/limit/resetsAt`) —
the most likely silent-drop spot.

**Likely rework**: the `daily_email_quota` mapping and the empty-response default. Two
concrete traps — (1) forgetting `resets_at`→`resetsAt` leaves the reset time blank; (2)
copying `use-alerts.ts:119`'s `limit: 100` default contradicts the backend limit of 10
(`alert_rule.py:121`). T003/T009 pin both: the test asserts `resetsAt` maps and the default
is `{ used: 0, limit: 10, resetsAt: '' }`.

**Second-order risk**: a reviewer trimming `mapAlert` to only `alertId` to shrink the diff.
That reintroduces the partial-state hazard (spec Adversarial Review #1, A1): the toggle
inverts and the card crashes. T009 asserts `isEnabled` and `thresholdValue` are populated,
blocking the trim.

**Status**: **READY.** No blockers. Backend shapes and burn mechanics verified at authoring
time (`alerts.py:47-60,78-91,361-370`, `alert_evaluator.py:157,477`); the reference fix and
its test exist (`configs.ts`, `configs.test.ts`); no new dependencies, no backend change, no
new AWS resources. Single-file source change (read + update paths only) plus one additive
regression test keeps blast radius minimal. `create` and `getNotifications` are DEFERRED,
so their brokenness is out of scope by design (documented in spec Deferred Work).
</content>
