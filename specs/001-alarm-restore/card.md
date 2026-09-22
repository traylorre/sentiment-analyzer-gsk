# Card: re-add CloudWatch alarms

Status: CARDED, not started. Blocked on deciding alarms are wanted again; deletion was a
cost call (2026-08-06), not a verdict that alarms are useless.

## What happened

Every CloudWatch alarm this stack owned was deleted from Terraform to stop billing past the
10-alarm free tier. The full definitions last exist at main commit `d7547e1e`. Recover any
file with `git show d7547e1e:<path>`. The per-alarm register with state at deletion is the
Alarms section of `docs/OBSERVABILITY.md`.

## What was deleted

- `infrastructure/terraform/modules/cloudwatch-alarms/` (whole module) and its call in the
  root `main.tf`, gated by the also-deleted `enable_extended_cloudwatch_alarms` variable
- `modules/monitoring/api_alarms.tf`, `cost_alarm.tf`, `notification_alarm.tf`
- 25 inline `aws_cloudwatch_metric_alarm` blocks across `modules/{monitoring,lambda,dynamodb,api_gateway,waf,chaos}/main.tf`
- The alarm-status widget in `modules/monitoring/dashboard.tf`, alarm outputs in
  `modules/{monitoring,dynamodb}/outputs.tf`, and the `create_*_alarm`/`alarm_actions`
  variables threaded through the root module calls
- By CLI under the `dev-loop` profile, since no Terraform manages it: the orphan
  `sentiment-analyzer-dev-dlq-has-messages`

## Kept in place

- SNS topic `{env}-sentiment-alarms` and its email subscription (`modules/monitoring/main.tf`),
  so restored alarms have an action target immediately
- All metric emission, IAM `PutMetricData` grants, the CloudWatch dashboard, the AWS budget

## Re-add path

1. Pick alarms from the register; do not restore all 44. The free tier is 10 and the
   unrelated `dev-loop` stack occupies 8 slots in this account.
2. Fix dead namespaces first or the restored alarms cannot fire: `/Ingestion` and
   `/Reliability` need IAM grants, `/Alerts` and `/Notifications` have no emitter,
   `/Packaging`'s metric filter has never matched. See the namespace table in
   `docs/OBSERVABILITY.md`; both defects are carded on `CLEANUP-BOARD.html`.
3. `no-new-items-1h` sat in ALARM from 2025-12-05 until deletion. Investigate why
   `NewItemsIngested` stayed below threshold for eight months before rewiring it.
4. `git show d7547e1e:<path>` for each file, restore the wanted blocks, rewire
   `alarm_actions = [module.monitoring.alarm_topic_arn]`, and update the Alarms section of
   `docs/OBSERVABILITY.md` to match what exists again.
