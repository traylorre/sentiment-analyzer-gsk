# Implementation Plan: Alerts Quota-Burn Mitigation (restore delete/disable control)

**Branch**: `1387-alerts-snakecase-mapping` | **Date**: 2026-07-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1387-alerts-snakecase-mapping/spec.md`
**Scope**: MINIMAL mitigation only. Full snake↔camel remap DEFERRED to a board card.

## Summary

Add targeted field mapping to the alerts API client so the two controls that stop a firing
alert — delete and disable — actually target the real alert and work. Read paths
(`list`/`listByConfig`/`get`) map the snake_case backend response to the camelCase
`AlertRule` type; the `update` path maps the camelCase body to the snake_case body the
backend accepts. This restores user control and stops the quota burn. Confined to
`frontend/src/lib/api/alerts.ts` plus one Vitest regression spec. No backend change, no new
endpoints, no new AWS resources.

## Technical Context

**Language/Version**: TypeScript ^5 / Next.js 14.2.21 / React ^18
**Primary Dependencies**: @tanstack/react-query ^5.90.11 (consumers), no new deps
**Storage**: N/A (client mapping only)
**Testing**: Vitest (unit) — `frontend/vitest.config.ts`; sibling
`frontend/tests/unit/lib/api/configs.test.ts` is the pattern to mirror
**Target Platform**: Web browser (customer dashboard, AWS Amplify)
**Project Type**: Web application (frontend-only change)
**Constraints**: No new AWS resources; smallest safe diff; backend responses/requests are
authoritative and unchanged; mapping lives in the client layer because `client.ts:109`
does a bare `response.json()` with no global transform
**Scale/Scope**: 1 source file modified, 1 test file added, 2 P1 user stories (delete,
disable)

## Chosen Mitigation: Option A (targeted mapping) — rationale

Two options were evaluated:

- **Option A — targeted mapping.** Map the read responses for `list`/`listByConfig`/`get`
  (so `alertId`/`isEnabled`/`thresholdValue` are defined) and map the `update` request body
  camel→snake (so a disable is accepted). Smallest change that restores both delete and
  disable.
- **Option B — disable the offending path.** Hide the delete/toggle UI, or suppress the
  alert-email send, until the full remap lands.

**Chosen: Option A.** Option B is strictly worse for this harm:

- Hiding the delete/toggle UI removes the *only* user-facing lever to flip stored `status`
  (`alert_evaluator.py:157`) or delete the row, so the noisy alert fires **forever** — it
  hides the symptom while the burn continues.
- Suppressing the email send at the backend would silence *all* alerts, including wanted
  ones, is outside the customer-dashboard (`frontend/`) surface this ticket owns, and would
  need infra/Lambda changes — the opposite of a minimal frontend mitigation.

Option A is also the **already-accepted precedent** for the identical bug: the configs
client was fixed exactly this way in M1 WI-5 (`configs.ts:34-70`, explicit two-way
mappers). Lowest risk, most reviewable, minimal blast radius.

Why Option A must map more than the id field alone (partial-state hazard, see Adversarial
Review #1 in spec.md):

- `alert-card.tsx:107` computes the toggle target as `!alert.isEnabled` — needs `isEnabled`
  mapped, or disable is impossible (always computes "enable").
- `alert-card.tsx:94` calls `alert.thresholdValue.toFixed(2)` — needs `thresholdValue`
  mapped, or the card throws and the delete button is unreachable.
- `alerts.py:78-91` `AlertUpdateRequest` accepts `is_enabled`/alias `enabled`, not
  `isEnabled` — needs the update body mapped, or the accepted-but-empty update
  (`alerts.py:361-370`) silently changes nothing.

## The Exact Change (file:line)

### Source: `frontend/src/lib/api/alerts.ts` (currently 53 lines, no mapping)

1. Add a snake_case `RawAlert` interface mirroring `AlertResponse` (`alerts.py:47-60`) and a
   `RawAlertList` interface (`{ alerts, total, daily_email_quota }`, `alerts.py:62-67`).
2. Add `mapAlert(raw: RawAlert): AlertRule` — every field snake→camel; preserve
   `last_triggered_at: null` as `null`. Mirror `configs.ts:34-44`.
3. Add `mapAlertList(raw: RawAlertList): AlertList` — `(raw.alerts ?? []).map(mapAlert)`,
   `total`, and `dailyEmailQuota` from `daily_email_quota` (`resets_at`→`resetsAt`) with a
   safe default `{ used: 0, limit: 10, resetsAt: '' }` when absent. Mirror
   `configs.ts:46-51`.
4. Add `toUpdateBody(req: UpdateAlertRequest): Record<string, unknown>` — only-defined-keys,
   snake_case (`threshold_value`, `threshold_direction`, `is_enabled`). Mirror
   `configs.ts:59-70`.
5. Rewrite `list` (`alerts.ts:14-15`) and `listByConfig` (`alerts.ts:20-21`) to
   `api.get<RawAlertList>(...)` then `return mapAlertList(raw)`. **This is the line that
   makes `alert.alertId` resolve** so the delete dialog opens (`page.tsx:117`) and the
   toggle stops targeting `/api/v2/alerts/undefined` (`alert-card.tsx:107`).
6. Rewrite `get` (`alerts.ts:26-27`) to `api.get<RawAlert>(...)` then `mapAlert(raw)`.
7. Rewrite `update` (`alerts.ts:38-39`) to
   `api.patch<RawAlert>(..., toUpdateBody(updates))` then `mapAlert(raw)`. **This is the
   line that makes a disable actually persist.**
8. Add a short header comment mirroring `configs.ts:10-16`, referencing this feature, the
   config-delete precedent, and the DEFERRED full remap.

**Explicitly untouched (DEFERRED to board card)**: `create` (`alerts.ts:32-33`) and
`getNotifications` (`alerts.ts:50-51`). Neither burns quota; leaving them keeps the diff
minimal. `delete` (`alerts.ts:44-45`) is unchanged at the client level — it becomes
functional for free once FR-001 populates `alertId`.

### Backend truth (verified, no change)

- Response model: `alerts.py:47-60` (`AlertResponse`, snake_case), serializer
  `alerts.py:591-608`; quota shape `alerts.py:576-588` (`used/limit/remaining/resets_at`).
- Update contract: `alerts.py:78-91` (`AlertUpdateRequest`: `is_enabled`/alias `enabled`,
  `threshold`/`condition`; `populate_by_name=True`; camelCase not accepted).
- Burn mechanics: `alert_evaluator.py:157` (skip if `status != ENABLED`),
  `alert_evaluator.py:477` (`_increment_user_quota` on send). Confirms disabling/deleting
  the alert is what stops the burn.

### Reference fix to mirror

`frontend/src/lib/api/configs.ts:10-121` (same bug, accepted fix) and its test
`frontend/tests/unit/lib/api/configs.test.ts`.

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Implementation accompaniment (regression test) | PASS | New Vitest spec locks real-id delete/disable |
| GPG-signed commits | PASS | `git commit -S`; venv active for any pre-commit hcl2 hooks |
| No pipeline bypass | PASS | Standard PR flow |
| Security: no unauthenticated endpoints | PASS | No endpoint change |
| No new AWS resources | PASS | Frontend-only client mapping |
| Two-dashboard rule | PASS | Targets customer dashboard (`frontend/`) only |
| Smallest safe diff | PASS | 1 source file (read + update paths only), 1 test; create/notifications deferred |

## Project Structure

```text
frontend/src/lib/api/
└── alerts.ts                 # MODIFIED: RawAlert + mapAlert/mapAlertList + toUpdateBody;
                              #           rewrite list/listByConfig/get/update only

frontend/tests/unit/lib/api/
└── alerts.test.ts            # NEW: regression test — real-id delete/disable, mapAlert fields
```

**Structure Decision**: Frontend-only. One source file changed (read paths + update path),
one sibling test added next to `configs.test.ts`. No new directories, no backend, no infra.

## Adversarial Review #2

**Posture**: Drift between artifacts, and drift between the plan and the actual code.

- **D1 — Scope drift (mitigation vs full remap).** Spec re-scope note, FR list, and
  Deferred Work section all agree with this plan: read mapping for `list`/`listByConfig`/
  `get` + `update` body only; `create` and `getNotifications` deferred. No task in tasks.md
  touches the deferred methods. Cross-artifact consistent. RESOLVED.

- **D2 — "map only id" temptation.** A reviewer might trim the mapper to just `alertId` to
  minimize the diff. Plan and spec (Adversarial Review #1, A1) explicitly require mapping
  `isEnabled` and `thresholdValue` too, because `alert-card.tsx:94,107` read them and the
  card crashes / the toggle inverts without them. The regression test (FR-004) asserts all
  three are populated, blocking that trim. RESOLVED.

- **D3 — Update-body drift.** Plan requires `toUpdateBody` to emit snake_case. Verified
  against `alerts.py:78-91`: backend accepts `is_enabled` (or alias `enabled`), not
  `isEnabled`; `populate_by_name=True` means canonical snake_case is accepted. Sending
  `is_enabled` is correct. RESOLVED.

- **D4 — Components need editing?** No. `alert-card.tsx`, `alert-list.tsx`, `page.tsx`
  already read camelCase (`alert.alertId`, `alert.isEnabled`, `alert.thresholdValue`);
  they were correct all along and only received `undefined`. Fixing the client alone
  restores them. Verified at `alert-list.tsx:84`, `alert-card.tsx:94,107`, `page.tsx:98,117`.
  RESOLVED.

- **D5 — Quota default mismatch.** `use-alerts.ts:119` defaults `limit` to 100; backend
  limit is 10 (`alert_rule.py:121`). The mapper passes the real backend value through and
  uses `10` only in the absent-response default. Spec Clarification #5 marks the hook's 100
  out of scope. Consistent. RESOLVED.

**Gate**: 0 CRITICAL, 0 HIGH cross-artifact inconsistencies. Plan matches spec and matches
the code as read at authoring time. **PASS.**
</content>
