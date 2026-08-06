# Observability: metrics, logs, and dashboard privacy

> **CANON**: verified against code.

What the service actually emits, and the rules that bind changes to it. Architecture is in
`docs/SERVICE-SHAPE.md`; the two dashboards are distinguished in `CLAUDE.md`. Tracing is in
`docs/x-ray.md`.

## Metric namespaces

There are eight, and only three are wired end to end. A query against the wrong namespace returns
empty rather than erroring, so check this table before concluding a metric is missing.

| Namespace | Code emits | IAM grants |
|---|---|---|
| `SentimentAnalyzer` | yes | yes |
| `SentimentAnalyzer/SSE` | yes | yes |
| `SentimentAnalyzer/Canary` | yes | yes |
| `SentimentAnalyzer/Ingestion` | yes | **no** |
| `SentimentAnalyzer/Reliability` | yes | **no** |
| `SentimentAnalyzer/Alerts` | **no** | no |
| `SentimentAnalyzer/Notifications` | **no** | no |
| `SentimentAnalyzer/Packaging` | log metric filter | n/a |

Every bolded cell is a metric that never arrives: `/Ingestion` and `/Reliability` are emitted but
the IAM grant is missing, `/Alerts` and `/Notifications` are never emitted at all. `/Packaging` is
broken by a third mechanism: its metric filter pattern has never matched a real log line. Both
defects are carded on `CLEANUP-BOARD.html`.

Emitters: `src/lib/metrics.py` (`emit_metric`, `emit_metrics_batch`, default namespace, accepts an
override), `ingestion/metrics.py`, `sse_streaming/metrics.py`, `canary/handler.py`, and inline
`namespace=` overrides in seven modules for `/Reliability` (`shared/circuit_breaker.py`,
`lib/timeseries/fanout.py`, and `ingestion/` storage, parallel_fetcher, audit, notification,
self_healing).

IAM grants are in `infrastructure/terraform/modules/iam/main.tf`: eight `PutMetricData` statements,
every one conditioned on `cloudwatch:namespace` with `StringEquals`. That is exact-match, so a
grant for `SentimentAnalyzer` does not cover `SentimentAnalyzer/Ingestion`. Adding a namespace
without adding its grant produces an `AccessDenied` that the emitters catch and log rather than
raise.

SSE carries its own emitter rather than importing `src/lib/metrics.py`, because an `src/lib/`
import breaks the SSE image build. See `docs/ci-gotchas.md`. Do not consolidate these without
reading that first.

Metric names are PascalCase (`NewItemsIngested`, `ConnectionCount`, `TiingoApiErrors`). Read the
emitter for the current list rather than copying one from a spec.

## Alarms

There are none. Every alarm this stack owned was deleted on 2026-08-06 to stop billing past the
10-alarm CloudWatch free tier, of which 8 slots are taken by the unrelated `dev-loop` stack in
the same account. The definitions last exist at main commit `d7547e1e`; recovery path and
preconditions are in `specs/001-alarm-restore/card.md`. The register below is what was removed
and the state each alarm was in at deletion. When alarms return they are Terraform, not code,
and adding a metric does not create an alarm for it.

At deletion, 35 of the 36 live alarms sat in OK and every one had actions enabled, notifying one
email subscriber (`scotthazlett+sentiment-alarm@gmail.com`). Only three had changed state in the
prior 30 days. Alarms were billed for existing, not for firing, so state never mattered to cost.

| Group (Terraform source at `d7547e1e`) | Alarms | State at deletion |
|---|---|---|
| Lambda errors and duration (`modules/lambda/main.tf`, `modules/monitoring/main.tf`) | `{ingestion,analysis,dashboard,notification,metrics,canary,sse-streaming}-errors`, `analysis-duration`, `lambda-{ingestion,analysis,dashboard}-errors`, `{analysis,dashboard}-latency-high` | OK; functional (AWS/Lambda metrics always arrive) |
| DynamoDB (`modules/dynamodb/main.tf`) | `dynamodb-{user-errors,system-errors,write-throttles,high-read-capacity}` | OK; functional; write-throttles last flapped 2026-08-05 |
| Queue and SNS (`modules/monitoring/main.tf`) | `dlq-depth-exceeded`, `sns-delivery-failures` | OK; functional |
| Daily cost guards (`modules/monitoring/cost_alarm.tf`) | `dynamodb-daily-cost-high`, `lambda-daily-invocations-high`, `sns-daily-messages-high` | OK; functional (metric math over AWS namespaces) |
| Ingestion health (`modules/monitoring/main.tf`) | `{tiingo,finnhub}-error-rate-high`, `circuit-breaker-open`, `collision-rate-{high,low}`, `anomalous-collision-rate` | OK but could never fire: `/Ingestion` namespace is IAM-blocked (table above) |
| Notifications (`modules/monitoring/notification_alarm.tf`) | `notification-delivery-low`, `notification-lambda-errors`, `sendgrid-quota-{50,80}-percent` | OK; SendGrid pair could never fire: `/Notifications` is never emitted |
| Pipeline liveness (`modules/monitoring/main.tf`) | `no-new-items-1h` | stuck in ALARM since 2025-12-05; investigate `NewItemsIngested` before restoring |
| Misc | `alert-triggers-high` (`/Alerts`, never emitted), `dashboard-import-errors` (`/Packaging`, filter never matches), `chaos-iam-policy-attachment` (functional) | OK |
| Never deployed (gated off by `enable_extended_cloudwatch_alarms`) | `modules/cloudwatch-alarms/` (canary heartbeat/completeness, silent-failure composite, per-Lambda extended set), `api-gateway-{4xx,5xx,latency}`, `waf-blocked-requests` | existed only in Terraform, count = 0 |

Still live: `sentiment-analyzer-dev-dlq-has-messages`, an orphan from an old dev deploy that no
current Terraform manages. Deleting it needs `cloudwatch:DeleteAlarms`, which the deployer IAM
user does not hold, so it is an owner action:
`aws cloudwatch delete-alarms --alarm-names sentiment-analyzer-dev-dlq-has-messages`.

## Privacy rules

These bind. The constitution carries the log-side rule; these are the dashboard-side ones.

- Raw item text and PII do not reach dashboard responses. `sanitize_item_for_response()` in
  `src/lambdas/dashboard/metrics.py` strips internal fields; add anything newly sensitive to its
  hidden-field set.
- Request logs are structured and do not carry raw input text. Use `sanitize_for_log()` from
  `src/lambdas/shared/logging_utils.py`.

## Access control

Roles are `anonymous`, `free`, `paid`, `operator` (`src/lambdas/shared/auth/enums.py`,
`roles.py`). `operator` is the administrative role and implies the others. Anonymous sessions
cannot hold any other role.

Chaos endpoints are gated to `local`, `dev` and `test` only, fail-closed: unset, unknown,
`preprod` and `prod` all return 404 (`src/lambdas/dashboard/handler.py`, `_is_dev_environment`).

Rate limiting is per-user and applied where the route opts in, not globally
(`src/lambdas/shared/middleware/rate_limit.py`).

## Operational flows

- Cadences: ingestion runs every 5 minutes, the metrics Lambda every 1 minute
  (`infrastructure/terraform/modules/eventbridge/main.tf:6` and `:48`).
- A stuck item is `status='pending'` older than 5 minutes, found via the `by_status` GSI
  (`modules/dynamodb/main.tf:66-69`).
- `StuckItems` is a metric only: the metrics Lambda emits it and no CloudWatch alarm is wired to
  it. Quick check: query the `StuckItems` metric, then a COUNT over `by_status`.
- Every DynamoDB table is on-demand (`PAY_PER_REQUEST`), so a throttling response means
  hot-partition investigation, never a capacity raise.

## Not built

Named here because the constitution's earlier observability section described them and an agent
will otherwise go looking: there is no CSV or JSON metric export, no scheduled report generation,
no admin feed-switch control, no watch-keyword filters, and no drift metric. No source-management
endpoint exists either; see the "What does not exist" table in `docs/SERVICE-SHAPE.md`.
