# Observability: metrics, logs, and dashboard privacy

> **CANON**: verified against code.

What the service actually emits, and the rules that bind changes to it. Architecture is in
`docs/SERVICE-SHAPE.md`; the two dashboards are distinguished in `CLAUDE.md`. Tracing is in
`docs/x-ray.md`.

## Metric namespaces

There are eight, and only three are wired end to end. A query against the wrong namespace returns
empty rather than erroring, so check this table before concluding a metric is missing.

| Namespace | Code emits | IAM grants | Alarms on it |
|---|---|---|---|
| `SentimentAnalyzer` | yes | yes | yes |
| `SentimentAnalyzer/SSE` | yes | yes | yes |
| `SentimentAnalyzer/Canary` | yes | yes | yes |
| `SentimentAnalyzer/Ingestion` | yes | **no** | yes |
| `SentimentAnalyzer/Reliability` | yes | **no** | yes |
| `SentimentAnalyzer/Alerts` | **no** | no | yes |
| `SentimentAnalyzer/Notifications` | **no** | no | yes |
| `SentimentAnalyzer/Packaging` | log metric filter | n/a | yes |

Every bolded cell is an alarm on a metric that never arrives. `/Packaging` is broken too, by a
third mechanism: its metric filter pattern has never matched a real log line. So five of the eight
namespaces carry alarms that cannot fire. Do not read a green alarm on any of them as a healthy
signal. Both defects are carded on `CLEANUP-BOARD.html`.

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

Alarms are Terraform, not code: `infrastructure/terraform/modules/monitoring/` and
`modules/cloudwatch-alarms/`. Adding a metric does not create an alarm for it.

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
