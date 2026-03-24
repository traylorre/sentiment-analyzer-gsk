# Tasks: Chaos Security Hardening

## Phase 1: Auth + Environment Gating (handler.py)

- [x] T001 Remove anonymous exception in `_get_chaos_user_id_from_event()` (handler.py:163-179): Delete the conditional block at lines 174-176 that allows anonymous auth in local/dev/test. Always return None for `AuthType.ANONYMOUS`:
  ```python
  if auth_context.auth_type == AuthType.ANONYMOUS:
      return None
  ```

- [x] T002 Add environment gate to ALL 7 chaos route handlers (handler.py:743-990): First, ensure `_is_dev_environment()` and `_NOT_FOUND_RESPONSE` are available. If Feature 1249 is merged, they already exist. If not, define them locally (see T001 in Feature 1249 for pattern: `ENVIRONMENT.lower() in {"local", "dev", "test"}`). Then add `if not _is_dev_environment(): return _NOT_FOUND_RESPONSE` as the FIRST line of each handler, BEFORE `_get_chaos_user_id_from_event()`. Affected handlers:
  - `create_chaos_experiment()` (POST /chaos/experiments)
  - `list_chaos_experiments()` (GET /chaos/experiments)
  - `get_chaos_experiment()` (GET /chaos/experiments/{id})
  - `start_chaos_experiment()` (POST /chaos/experiments/{id}/start)
  - `stop_chaos_experiment()` (POST /chaos/experiments/{id}/stop)
  - `get_chaos_experiment_report()` (GET /chaos/experiments/{id}/report)
  - `delete_chaos_experiment()` (DELETE /chaos/experiments/{id})
  Import `_is_dev_environment` and `_NOT_FOUND_RESPONSE` from Feature 1249 (or define locally if 1249 not merged).

- [x] T003 Add auto-restore raw event handler in `lambda_handler()` (handler.py, insert at line ~1020, BEFORE `response = app.resolve(event, context)` at line 1021): Check `if event.get("action") == "chaos-auto-restore":` — if matched, extract `experiment_id` from event, call `_handle_auto_restore(experiment_id)`, return result dict directly. This bypasses Powertools routing because EventBridge Scheduler invokes Lambda directly with raw JSON, not HTTP-formatted events. Guard must be specific to avoid intercepting normal HTTP events (which never have an "action" key at top level).

## Phase 2: Chaos Core (chaos.py)

- [x] T004 Add `_check_rate_limit(user_id)` function to chaos.py: DynamoDB conditional write using `experiment_id=f"RATELIMIT#chaos#{user_id}"`, `created_at=ISO_timestamp`. If `ConditionalCheckFailedException`, return False (rate-limited). Uses existing chaos experiments table with synthetic experiment_id prefix. TTL=120s for auto-cleanup.

- [x] T005 Add `_acquire_scenario_lock(scenario_type, experiment_id)` and `_release_scenario_lock(scenario_type)` to chaos.py: DynamoDB conditional write using `experiment_id=f"CHAOSLOCK#{scenario_type}"`, `created_at="ACTIVE"`. Lock item has TTL=600s (safety net). If lock exists → ConditionalCheckFailedException → return False.

- [x] T006 Add `_emit_iam_metric(value)` function to chaos.py: Emit CloudWatch metric `ChaosIAMPolicyAttachment` (namespace=SentimentAnalyzer, value=1 for attach, value=0 for detach). Call after IAM policy attach in `start_experiment()` dynamodb_throttle scenario (~line 830) and after detach in `stop_experiment()` restore_dynamodb_access (~line 699).

- [x] T007 Add auto-restore scheduling to `start_experiment()` in chaos.py: After chaos injection succeeds but BEFORE updating status to `running`:
  1. Calculate restore time: `started_at + duration_seconds`
  2. Call `scheduler.create_schedule()` with:
     - `Name=f"chaos-auto-restore-{experiment_id}"`
     - `ScheduleExpression=f"at({restore_time_iso})"`
     - `ActionAfterCompletion="DELETE"`
     - `Target.Arn=DASHBOARD_LAMBDA_ARN`, `Target.RoleArn=SCHEDULER_ROLE_ARN`
     - `Target.Input=json.dumps({"action": "chaos-auto-restore", "experiment_id": experiment_id})`
  3. Store `auto_restore_rule_name` in experiment DynamoDB record
  4. If scheduling fails: immediately call `stop_experiment()`, mark experiment `failed`
  Add env vars at module top: `SCHEDULER_ROLE_ARN = os.environ.get("SCHEDULER_ROLE_ARN", "")`, `DASHBOARD_LAMBDA_ARN = os.environ.get("DASHBOARD_LAMBDA_ARN", "")`. These are provided at runtime by T014 (Terraform). For local development/tests, mock or set empty strings.

- [x] T008 Add rate limit and concurrent lock checks to `create_experiment()` and `start_experiment()`:
  - In handler.py `create_chaos_experiment()`: After auth check, call `_check_rate_limit(user_id)`. If False, return 429 with `Retry-After: 60`.
  - In chaos.py `start_experiment()`: Before injecting chaos, call `_acquire_scenario_lock(scenario_type, experiment_id)`. If False, raise `ChaosError(f"Experiment already running for {scenario_type}")`.
  - In handler.py `start_chaos_experiment()`: Catch ChaosError containing "already running" and return 409.

- [x] T009 Update `stop_experiment()` in chaos.py:
  1. Handle already-stopped gracefully: if status is `stopped` or `auto-stopped`, return experiment data without error (no-op).
  2. Delete scheduled auto-restore rule: `scheduler.delete_schedule(Name=f"chaos-auto-restore-{experiment_id}")`. Catch `ResourceNotFoundException` silently.
  3. Release scenario lock: call `_release_scenario_lock(scenario_type)`. This MUST be idempotent — if lock item doesn't exist (already released or expired via TTL), silently succeed.
  4. Support `auto_stopped=True` parameter: when set, update status to `auto-stopped` instead of `stopped`.

- [x] T010 Add `_handle_auto_restore(experiment_id)` function to handler.py (or chaos.py):
  1. Get experiment from DynamoDB. If not found or status not `running`, return `{"status": "no-op"}`.
  2. Call `stop_experiment(experiment_id, auto_stopped=True)`.
  3. Log the auto-restore event.
  4. Return `{"status": "restored", "experiment_id": experiment_id}`.

## Phase 3: Infrastructure (Terraform)

- [x] T011 Add EventBridge Scheduler IAM role to `infrastructure/terraform/modules/chaos/main.tf`:
  - Role: `{env}-chaos-scheduler-role`, assume_role_policy for `scheduler.amazonaws.com`
  - Policy: `lambda:InvokeFunction` on Dashboard Lambda ARN
  - Gated: `count = var.enable_chaos_testing && var.environment != "prod" ? 1 : 0`
  - Output: `chaos_scheduler_role_arn`

- [x] T012 Add Scheduler + metrics permissions to Dashboard Lambda IAM policy in `infrastructure/terraform/modules/iam/main.tf`:
  - Statement 1 — Scheduler actions: `scheduler:CreateSchedule`, `scheduler:DeleteSchedule`, `scheduler:GetSchedule` on Resource `arn:aws:scheduler:*:*:schedule/default/chaos-auto-restore-*`
  - Statement 2 — PassRole: `iam:PassRole` on Resource = Scheduler role ARN from T011 (required for `Target.RoleArn` in `create_schedule`)
  - Statement 3 — Metrics: `cloudwatch:PutMetricData` with condition `StringEquals: {"cloudwatch:namespace": "SentimentAnalyzer"}` (FR-006 requires emitting ChaosIAMPolicyAttachment metric)
  - Add all to existing chaos policy block (~line 490), gated on `var.environment != "prod"`

- [x] T013 Add CloudWatch alarm for ChaosIAMPolicyAttachment to `infrastructure/terraform/modules/chaos/main.tf`:
  - Alarm name: `{env}-chaos-iam-policy-attachment`
  - Metric: `ChaosIAMPolicyAttachment`, namespace: `SentimentAnalyzer`
  - Threshold: 0, comparison: `GreaterThanThreshold`
  - Period: 60s, evaluation_periods: 1
  - Action: SNS topic ARN (from var)
  - Gated: `count = var.enable_chaos_testing && var.environment != "prod" ? 1 : 0`

- [x] T014 Add `SCHEDULER_ROLE_ARN` and `DASHBOARD_LAMBDA_ARN` environment variables to Dashboard Lambda in `infrastructure/terraform/main.tf`:
  - `SCHEDULER_ROLE_ARN = try(module.chaos.chaos_scheduler_role_arn, "")`
  - `DASHBOARD_LAMBDA_ARN = module.dashboard_lambda.function_arn`

## Phase 4: Tests

- [x] T015 Add unit tests `tests/unit/test_chaos_security.py`:
  1. `test_anonymous_rejected_in_all_envs` — UUID token returns None from `_get_chaos_user_id_from_event()` in local/dev/test/preprod
  2. `test_authenticated_accepted` — JWT token returns user_id
  3. `test_chaos_routes_return_404_in_preprod` — mock ENVIRONMENT=preprod, POST /chaos/experiments → 404
  4. `test_chaos_routes_work_in_dev` — mock ENVIRONMENT=dev, POST /chaos/experiments with JWT → 201
  5. `test_rate_limit_blocks_rapid_creation` — second create within 60s → `_check_rate_limit` returns False
  6. `test_rate_limit_allows_after_window` — create after 61s → passes
  7. `test_scenario_lock_prevents_concurrent` — `_acquire_scenario_lock` returns False when lock exists
  8. `test_scenario_lock_releases_on_stop` — lock released after `_release_scenario_lock`
  9. `test_auto_restore_scheduled_on_start` — mock scheduler, verify `create_schedule` called with correct params
  10. `test_auto_restore_scheduling_failure_restores_immediately` — mock scheduler.create_schedule to raise, verify stop_experiment called and status=failed
  11. `test_auto_restore_noop_when_already_stopped` — `_handle_auto_restore` returns no-op when status != running
  12. `test_auto_restore_raw_event_routing` — send raw `{"action": "chaos-auto-restore"}` to lambda_handler, verify routing
  13. `test_iam_metric_emitted_on_dynamodb_throttle` — verify `put_metric_data` called during dynamodb_throttle start
  14. `test_stop_deletes_scheduled_rule` — verify `scheduler.delete_schedule` called during stop
  15. `test_stop_handles_already_stopped_gracefully` — stop on stopped experiment returns data without error

- [x] T016 Add E2E tests `tests/e2e/test_chaos_lockdown_preprod.py` with marker `@pytest.mark.preprod`:
  1. `test_chaos_create_returns_404` — POST /chaos/experiments → 404
  2. `test_chaos_list_returns_404` — GET /chaos/experiments → 404
  3. `test_chaos_start_returns_404` — POST /chaos/experiments/fake/start → 404
  4. `test_chaos_stop_returns_404` — POST /chaos/experiments/fake/stop → 404
  5. `test_chaos_delete_returns_404` — DELETE /chaos/experiments/fake → 404
  6. `test_chaos_report_returns_404` — GET /chaos/experiments/fake/report → 404

- [x] T017 Update existing chaos tests (`tests/unit/test_chaos_fis.py`): Add mock for session validation and environment check. Ensure all existing tests still pass by:
  - Mocking `_is_dev_environment()` to return True
  - Mocking `_get_chaos_user_id_from_event()` to return a valid authenticated user_id
  - Adding `_mock_scheduler` fixture for auto-restore scheduling

## Phase 5: Verify

- [x] T018 Run backend unit tests: `python -m pytest tests/unit/ -x -q --timeout=120 -p no:playwright`
- [x] T019 Run `make validate` (lint + security)
- [x] T020 **[MANUAL]** After deploy: curl preprod chaos endpoints to verify 404 (SC-002)
