# Feature Specification: Alerts Quota-Burn Mitigation (restore delete/disable control)

**Feature Branch**: `1387-alerts-snakecase-mapping`
**Date**: 2026-07-24
**Status**: Draft (RE-SCOPED to minimal mitigation)
**Target**: Customer Dashboard (Next.js/Amplify) — `frontend/`

## Re-Scope Notice

This spec was originally a full snake_case ↔ camelCase remap of the alerts API client
(read + write, all five methods + notifications, generic both-direction mapping). The owner
**re-scoped it to a minimal, safe mitigation** to stop an active harm: users cannot
delete or disable a noisy alert, so it keeps firing emails against their daily quota.

**The full remap is DEFERRED to a board card** (see "Deferred Work" below). This spec
covers ONLY the smallest change that restores the user's ability to delete or disable an
alert and thereby stops the quota burn.

## Summary — The Harm

The alerts API client (`frontend/src/lib/api/alerts.ts`) does no snake↔camel mapping.
`client.ts:109` does a bare `response.json()` with no transform, and `alerts.ts` casts the
raw snake_case backend response straight to the camelCase `AlertRule` type. So every
camelCase field a consumer reads is `undefined`, in particular `alert.alertId` and
`alert.isEnabled`.

Consequence — the two controls that let a user stop a firing alert are both broken:

- **Delete is unreachable.** `alert-list.tsx:84` calls `onDelete(alert.alertId)` (undefined)
  → `page.tsx:98` `setDeletingAlertId(undefined)` → the confirm dialog is gated on
  `!!deletingAlertId` (`page.tsx:117`) → **the dialog never opens**. The user cannot delete.
- **Disable is a no-op.** `alert-card.tsx:107` calls `onToggle(alert.alertId, !alert.isEnabled)`:
  `alertId` is undefined → `PATCH /api/v2/alerts/undefined` → backend `get_alert` returns
  `None` → 404 no-op (`alerts.py:317-338`). And `isEnabled` is undefined → `!undefined` is
  always `true`, so the toggle can only ever ask to *enable*, never disable. Even with a
  correct id, the camelCase body `{ isEnabled }` is not understood by the backend
  (`AlertUpdateRequest` accepts `is_enabled`/alias `enabled`, not `isEnabled` —
  `alerts.py:78-91`), so the PATCH changes nothing.

**Why this burns quota**: a firing alert keeps sending emails as long as its stored
`status` stays `enabled`. The evaluator only skips disabled alerts
(`alert_evaluator.py:157` — `if alert.status != ENABLED: continue`) and increments the
user's daily quota on every send (`alert_evaluator.py:477` `_increment_user_quota`). The
frontend delete/disable controls are the ONLY user-facing levers that flip `status` to
`disabled` or remove the row. Both are broken, so a user who wants to silence a noisy alert
**cannot**, and it keeps consuming the daily email quota (limit 10/day, `alert_rule.py:121`).

This is the same latent defect class already fixed for the configs client in M1 WI-5 (the
"config-delete bug"): `configsApi` never mapped snake↔camel, so `configId` was always
`undefined`, the delete dialog never opened, and DELETE silently no-op'd. The fix was
explicit two-way mappers (`configs.ts:34-70`). The alerts client has the identical gap.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Delete a noisy alert and have it actually delete (Priority: P1)

A signed-in user with a noisy alert opens the Alerts page, clicks the trash icon, confirms
deletion. The confirm dialog must open, and the alert must be removed on the backend and
disappear from the list — permanently stopping its emails.

**Why this priority**: Silent destructive no-op that directly causes the quota burn. The
user believes they can remove the alert; today they cannot even open the confirm dialog.

**Independent Test**: Mock `alertsApi.list()` to return one alert with backend-shape
`{ "alert_id": "al-9", ... }`. Render the Alerts page, click delete, confirm, and assert
`api.delete` was called with `/api/v2/alerts/al-9` — never `/api/v2/alerts/undefined`.

**Acceptance Scenarios**:

1. **Given** a backend alert `{ "alert_id": "al-9" }`, **When** the client maps it,
   **Then** `alert.alertId === "al-9"` (not `undefined`).
2. **Given** the mapped alert, **When** the user clicks delete, **Then** the confirm dialog
   opens (`!!deletingAlertId` is true) and confirming issues `DELETE /api/v2/alerts/al-9`.

### User Story 2 — Disable a noisy alert and have it persist (Priority: P1)

A user flips the enable/disable switch to OFF on a firing alert. The change must PATCH the
correct alert id with a body the backend accepts, flip stored `status` to `disabled`, and
persist — so the evaluator stops sending its emails.

**Why this priority**: Disabling is the non-destructive way to stop the quota burn. Today
the toggle targets `/alerts/undefined`, always computes "enable", and sends an unrecognized
camelCase body — three independent reasons it never disables anything.

**Independent Test**: Render a mapped, enabled alert; click the switch; assert
`api.patch` is called with `/api/v2/alerts/al-9` and body `{ is_enabled: false }`.

**Acceptance Scenarios**:

1. **Given** a mapped enabled alert (`alert.isEnabled === true`), **When** the user clicks
   the switch, **Then** `toggleAlert` is called with the real id and `false` (because
   `!alert.isEnabled` now evaluates correctly).
2. **Given** an update `{ isEnabled: false }`, **When** the client builds the PATCH body,
   **Then** the body is `{ is_enabled: false }` (snake_case the backend accepts), so the
   stored `status` flips to `disabled` and `alert_evaluator.py:157` skips it thereafter.

### Edge Cases

- **Missing `alerts` array** in the list response → map to `[]` (mirrors configs
  `raw.configurations ?? []`), so `.map` in the list never throws.
- **Missing `daily_email_quota`** → fall back to a well-formed
  `{ used: 0, limit: 10, resetsAt: '' }` so `use-alerts.ts` consumers do not read
  `undefined`.
- **`last_triggered_at: null`** → preserve `null` (do not coerce to `undefined`).
- **Card render precondition** — `alert-card.tsx:94` calls `alert.thresholdValue.toFixed(2)`.
  If `thresholdValue` stays `undefined`, the card throws at render and the user never
  reaches the delete/toggle controls. The read mapper therefore MUST populate the full
  AlertRule read shape (not just `alertId`), or the mitigation does not actually restore
  control. This is why the mitigation maps the whole read object, not only the id field.
- **Partial update** (`{ isEnabled }` only) → body contains only the provided field, so a
  toggle does not blank out `threshold_value`.

## Adversarial Review #1

**Posture**: Attack the minimal map. Does mapping only the id leave a partial-state hazard?
Could a "disable the path" mitigation hide a still-firing alert? Does the mitigation
actually stop the quota burn, or only the UI symptom?

**Findings**

- **A1 (CRITICAL) — "map only the id" is insufficient and leaves a partial-state hazard.**
  If we map `alert_id`→`alertId` but not `is_enabled`→`isEnabled`, the toggle
  (`alert-card.tsx:107` `!alert.isEnabled`) still reads `undefined`, so `!undefined` is
  always `true` — the switch can only ever request *enable*, never disable. A user trying
  to silence an alert would flip the switch, see no effect, and the alert keeps firing. And
  if we map neither `is_enabled` nor `threshold_value`, `alert-card.tsx:94`
  `thresholdValue.toFixed(2)` throws, the card never renders, and the delete button is
  unreachable. **Resolution**: the mitigation maps the full AlertRule read shape (at minimum
  `alertId`, `isEnabled`, `thresholdValue`, `thresholdDirection`, `alertType`, `ticker`,
  `triggerCount`, `lastTriggeredAt`) for `list`/`listByConfig`/`get`. FR-001. RESOLVED.

- **A2 (CRITICAL) — id fixed but PATCH body still ignored.** Even with a correct id, the
  update sends `{ isEnabled }`, which `AlertUpdateRequest` (`alerts.py:78-91`) does not
  recognize (`populate_by_name` accepts `is_enabled` or alias `enabled`, not `isEnabled`).
  `update_alert` then builds an empty update expression (`alerts.py:361-370`) and returns
  the existing alert unchanged — the disable silently fails and the alert keeps firing.
  **Resolution**: the mitigation maps the update request body camel→snake (`isEnabled`→
  `is_enabled`, `thresholdValue`→`threshold_value`, `thresholdDirection`→
  `threshold_direction`). FR-002. RESOLVED.

- **A3 (HIGH, rejected alternative) — "disable the path" (Option B) hides a still-firing
  alert.** Disabling the delete/toggle UI removes the only user lever, so the alert fires
  forever. Disabling the alert-email send at the backend would silence *all* alerts
  (including wanted ones) and is out of the customer-dashboard scope, plus it hides the
  problem instead of restoring control. Option B does not stop *this* user's burn without
  collateral. **Resolution**: rejected in favor of Option A (targeted mapping). See plan.md.
  RESOLVED (documented, not implemented).

- **A4 (MEDIUM) — quota already burned before the fix.** The mitigation stops *future*
  burn once the user disables/deletes; it does not refund quota already consumed. That is
  acceptable — the daily quota resets (`_get_daily_email_quota`, `alerts.py:576-588`) and no
  refund mechanism is in scope. Noted, not addressed.

- **A5 (LOW) — create + notifications remain broken.** `create` still posts a camelCase
  body the backend rejects, and `getNotifications` still mis-shapes its response. Neither
  burns quota (a broken create makes no new firing alert; notifications are read-only
  history). Both are explicitly DEFERRED to the full-remap board card so this mitigation
  stays minimal. Noted.

**Gate**: 0 CRITICAL remaining (A1, A2 resolved by FR-001/FR-002). 0 HIGH remaining (A3
resolved by choosing Option A). MEDIUM/LOW noted or deferred. **PASS.**

## Clarifications

### Session 2026-07-24 (self-answered, ≤5)

1. **Q**: Does mapping only `alert_id` stop the burn?
   **A**: No. Disable also needs `is_enabled` mapped on the way in (so `!alert.isEnabled`
   computes correctly) AND the PATCH body mapped on the way out (so the backend accepts it).
   Delete additionally needs the card to render, which needs `threshold_value` mapped
   (`alert-card.tsx:94`). Evidence: `alert-card.tsx:94,107`, `alerts.py:78-91,361-370`.

2. **Q**: Is the delete/disable failure actually what burns quota, or is there another path?
   **A**: It is the path. Emails fire only for alerts whose stored `status == enabled`
   (`alert_evaluator.py:157`) and every send increments the quota
   (`alert_evaluator.py:477`). The frontend delete/disable controls are the only
   user-facing way to flip `status`/remove the row. Both broken ⇒ no way to stop it.

3. **Q**: Any backend change required?
   **A**: No. The backend already returns correct snake_case and already accepts a
   snake_case update body (`is_enabled`/alias `enabled`). This is a frontend-only client
   mapping fix. No new AWS resources.

4. **Q**: Why not just apply the existing generic `snakeToCamel` util (`transform.ts`) to
   every alerts method now?
   **A**: That is essentially the deferred full remap. The mitigation stays narrow
   (read mapping for list/get + update body only) to keep the diff and blast radius minimal
   and reviewable, mirroring the accepted `configs.ts` precedent. The generic approach is
   the board card's job.

5. **Q**: Does the `dailyEmailQuota.limit` default of 100 in `use-alerts.ts:119` matter?
   **A**: No. The backend limit is 10 (`alert_rule.py:121`); the mapper passes the real
   backend value through. The hook's hardcoded 100 only shows on a truly-absent response
   and is out of scope. Noted, not changed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The alerts client MUST map the backend `AlertResponse` (snake_case,
  `alerts.py:47-60`) to the camelCase `AlertRule` type (`types/alert.ts:4-15`) for the read
  paths that feed the delete/disable controls (`get`, and each item in `list` /
  `listByConfig`), populating at minimum `alertId`, `configId`, `alertType`,
  `thresholdValue`, `thresholdDirection`, `isEnabled`, `lastTriggeredAt` (preserving
  `null`), `triggerCount`, `createdAt`, plus pass-through `ticker`. The list envelope MUST
  also map `daily_email_quota { used, limit, resets_at }` → `dailyEmailQuota { used, limit,
  resetsAt }`, tolerate a missing `alerts` array (→ `[]`) and a missing quota block (→
  `{ used: 0, limit: 10, resetsAt: '' }`).
- **FR-002**: The alerts client MUST map the `update` request body camel→snake, including
  ONLY the provided fields among `threshold_value`, `threshold_direction`, `is_enabled`, so
  the backend accepts a disable (`{ is_enabled: false }`) and flips stored `status`.
- **FR-003**: With FR-001 in place, deleting an alert MUST issue
  `DELETE /api/v2/alerts/{real-id}` (the confirm dialog opens because `alertId` is now
  defined); the literal string `undefined` MUST NOT appear in any alert request path.
- **FR-004**: A regression test MUST lock FR-001..FR-003: it asserts `mapAlert` populates
  `alertId`/`isEnabled`/`thresholdValue` from a snake_case fixture, that delete targets the
  real id (never `/alerts/undefined`), and that a disable produces a `{ is_enabled: false }`
  PATCH body against the real id.
- **FR-005**: No backend change, no new endpoints, no new AWS resources. Frontend-only,
  confined to `frontend/src/lib/api/alerts.ts` plus one test file.

### Deferred Work (board card — NOT in this mitigation)

The following are the identical defect class but do NOT burn quota, and are DEFERRED to a
separate board card for a later batch:

- `create` request-body mapping (camelCase POST body rejected by `AlertRuleCreate`,
  `alert_rule.py:97-104`) — a broken create makes no new firing alert, so no burn.
- `getNotifications` envelope + field mapping (wrong root shape `{ notifications: [...] }`
  + snake_case items) — read-only history, no burn.
- A generic both-directions transform across all alert endpoints and full type
  reconciliation (the original "full remap" scope).

### Key Entities

- **AlertRule** (`frontend/src/types/alert.ts:4-15`) — camelCase consumer type (unchanged).
- **RawAlert** (NEW, internal to `alerts.ts`) — snake_case shape mirroring `AlertResponse`
  (`alerts.py:47-60`), for the read mapper only.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can delete an alert: the confirm dialog opens and
  `DELETE /api/v2/alerts/{real-id}` is issued; `undefined` never appears in the path.
- **SC-002**: A user can disable an alert: the toggle issues
  `PATCH /api/v2/alerts/{real-id}` with body `{ is_enabled: false }`, flipping stored
  `status` to `disabled` so `alert_evaluator.py:157` skips it and no further emails fire.
- **SC-003**: `alert.thresholdValue.toFixed(2)` executes without throwing for a mapped
  alert (the card renders, so the controls are reachable).
- **SC-004**: The regression test passes and locks the real-id delete/disable behavior;
  existing frontend tests remain green.

## Assumptions

- Backend response/request shapes in `src/lambdas/dashboard/alerts.py` are authoritative
  and stable (verified at authoring time).
- `client.ts` continues to do a bare `response.json()` with no global transform, so
  per-client mapping remains the correct layer (consistent with the configs fix).
</content>
</invoke>
