# Implementation Plan: Andon Cord Button

**Branch**: `1246-andon-cord` | **Date**: 2026-03-27 | **Spec**: [spec.md](spec.md)

## Summary

Implement a `POST /chaos/andon-cord` endpoint that sets the kill switch to "triggered" and restores all active chaos configurations by iterating SSM snapshots. Add a prominent red emergency stop button in chaos.html with a DaisyUI confirmation modal.

## Technical Context

**Language/Version**: Python 3.13, JavaScript (Alpine.js)
**Primary Dependencies**: boto3 (SSM, Lambda, IAM, Events), orjson (existing)
**Storage**: SSM Parameter Store (reads/deletes snapshots, writes kill switch)
**Target Platform**: AWS Lambda (existing dashboard Lambda)
**Constraints**: Kill switch set BEFORE restores; best-effort restoration; must work under degraded conditions
**Scale/Scope**: ~1-2 pulls/gameday (hopefully 0)

## Project Structure (in target repo: ../sentiment-analyzer-gsk/)

```text
src/lambdas/dashboard/
├── chaos.py       # MODIFY: Add pull_andon_cord() function (~60 lines)
├── handler.py     # MODIFY: Add POST /chaos/andon-cord route (~30 lines)

src/dashboard/
├── chaos.html     # MODIFY: Add emergency stop button + modal (~80 lines)

tests/unit/
├── test_chaos_andon_cord_api.py  # NEW: Endpoint + cord logic tests (~80 lines)
```

## Implementation (Single Phase)

### Step 1: Add pull_andon_cord() in chaos.py
Core logic:
1. Set kill switch to "triggered" via `_set_kill_switch("triggered")`. Capture success/failure.
2. List SSM parameters matching `/chaos/{env}/snapshot/` prefix to find active snapshots.
3. For each snapshot, call `_restore_from_ssm(scenario_type)`. Catch individual failures, continue to next.
4. Return summary dict: `kill_switch_set`, `experiments_found`, `restored`, `failed`, `errors`, `timestamp`.

Key design decisions:
- Kill switch FIRST (FR-002): even if restore fails, no new injections can start.
- Best-effort restore (FR-003): `try/except` around each individual restore, collect errors.
- SSM parameter listing to discover snapshots: `ssm.get_parameters_by_path(Path=f"/chaos/{env}/snapshot/")` to find all active scenario snapshots.
- Idempotent (FR-008): if kill switch already triggered and no snapshots exist, returns `{kill_switch_set: true, restored: 0}`.

### Step 2: Add POST /chaos/andon-cord endpoint in handler.py
- Auth: `_get_chaos_user_id_from_event(event)` — 401 if None
- Call `pull_andon_cord()`
- Return 200 with result summary (200 even for partial failures — the cord was "pulled" regardless)
- Only return 500 if the kill switch itself failed to set (catastrophic)
- Catch `EnvironmentNotAllowedError` → 403

### Step 3: Add UI button + modal in chaos.html
- Big red button: "EMERGENCY STOP" with warning icon. Positioned prominently (fixed bottom-right or in the header area).
- DaisyUI modal (not browser confirm): "Pull Andon Cord?" with explanation text and two buttons: "Cancel" and "PULL CORD" (red).
- Alpine.js state: `andonLoading: false`, `andonResult: null`, `showAndonModal: false`
- On button click: `showAndonModal = true`
- On confirm: `pullAndonCord()` — sets `andonLoading`, calls `POST /chaos/andon-cord`, stores result, closes modal.
- On success: show result summary (restored count, errors if any). Refresh gate state.
- Button disabled when `andonLoading` (prevents double-click per FR-007).
- Auth failure handling: show fallback CLI command.

### Step 4: Unit tests
- Test 200 with mocked successful cord pull (kill switch set, 2 restores)
- Test 200 with partial failure (1 restore fails, 1 succeeds)
- Test 200 when no snapshots exist (idempotent)
- Test 401 for unauthenticated
- Test kill-switch-first ordering (verify `_set_kill_switch` called before `_restore_from_ssm`)
