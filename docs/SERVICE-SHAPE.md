# Service Shape

> **CANON**: verified against code.

What the sentiment analyzer is and how it is actually built. Load this when you need the service's
architecture: mapping it, hunting doc drift, or implementing against it. The constitution
(`.specify/memory/constitution.md`) carries the rules; this file carries the description.

Everything below is verified against the repo. The last section lists things the service is
frequently assumed to have and does not.

## What it does

Ingests financial news from external publishers, scores sentiment per item, persists the result,
and serves it to a customer dashboard and an internal admin dashboard.

Publishers are Tiingo and Finnhub, behind pluggable adapters in `src/lambdas/shared/adapters/`.

The live handler fetches them **concurrently** via `ParallelFetcher`
(`src/lambdas/ingestion/parallel_fetcher.py`, wired at `src/lambdas/ingestion/handler.py:1272`).
A `FailoverOrchestrator` also exists (`src/lambdas/shared/failover.py`) implementing
primary-then-secondary failover, but it has no production callers. It is not the ingestion path.

Two `generate_dedup_key` functions exist, and picking the wrong one changes behaviour. The live
handler uses the two-argument version at `src/lambdas/ingestion/dedup.py:59`, hashing headline and
publish date only, so the same story from two publishers collides on purpose. The three-argument
version at `src/lambdas/shared/utils/dedup.py:11` also hashes source and is not on the live path.

## Compute

Lambda only. No EC2, no ECS, no Fargate.

| Lambda | Role |
|---|---|
| `ingestion` | Fetches from Tiingo/Finnhub, dedupes, persists, publishes to SNS |
| `analysis` | Sentiment scoring and ATR calculation |
| `dashboard` | REST API behind API Gateway, Powertools resolver |
| `sse_streaming` | Server-sent events, RESPONSE_STREAM invoke, custom Runtime API bootstrap |
| `notification` | Email alerts via SendGrid |
| `metrics` | Metric publication |
| `canary` | Post-deploy smoke checks |
| `chaos_restore` | Chaos-experiment recovery |

## Scheduling and events

Ingestion is **scheduled polling**, not push. EventBridge rules in
`infrastructure/terraform/modules/eventbridge/main.tf` fire at `rate(5 minutes)`, `rate(1 minute)`,
and hourly.

SNS carries one application topic, `analysis_requests`, plus a separate `alarms` topic under
`modules/monitoring/`. There is exactly one SQS queue (`modules/sns/main.tf:5`), and despite
living in the SNS module it is not attached to the topic. It serves as the Lambda async-invoke DLQ
(`modules/lambda/main.tf:79`) and the EventBridge target DLQ (`modules/eventbridge/main.tf:24`).
There is no work-queue or buffering SQS tier.

## Persistence

Six DynamoDB tables (`infrastructure/terraform/modules/dynamodb/main.tf`): `sentiment_items`,
`feature_006_users`, `chaos_experiments`, `chaos_reports`, `sentiment_timeseries`, `ohlc_cache`.
Only `feature_006_users` is a single-table design. There is no relational database anywhere in the
service.

Key patterns are the `pk` and `sk` properties on the models in `src/lambdas/shared/models/`. Read
those; prose copies of the key set elsewhere in the repo have drifted from the code.

S3 holds model artifacts and the ticker list.

## API surface

Application routes are `/api/v2/*`, served by `src/lambdas/dashboard/handler.py`. Examples:
`/api/v2/articles`, `/api/v2/metrics`, `/api/v2/sentiment`, `/api/v2/trends`, `/api/v2/runtime`.
The same handler also serves `/`, `/api`, `/health`, `/favicon.ico` and `/static/<filename>`.

The dashboard Lambda has **no Function URL** (`create_function_url = false` at
`infrastructure/terraform/main.tf:508`); it is reached through API Gateway. The SSE Lambda is the
only one with a Function URL, in `RESPONSE_STREAM` mode (`main.tf:824`).

There are two separate dashboards with different stacks, different URLs, and different routes.
Confusing them has caused repeated incidents; the comparison table in `CLAUDE.md` is the reference
and should be checked before writing any dashboard code or test.

## Output schema

The stored record is a plain dict keyed `source_id` / `timestamp`, assembled by ingestion and then
amended by analysis. The Pydantic models that look authoritative, `news_item.py` and
`sentiment_result.py`, have no callers on any live path. Read `docs/MODELING.md` before trusting
either, and before assuming `score` is signed: the declarations allow `-1.0` to `1.0` and the live
scorer only ever emits a probability.

## Infrastructure and deploy

Terraform, with an **S3 backend** using partial backend configuration to separate preprod and prod
state (`infrastructure/terraform/main.tf`, plus `backend-preprod.hcl` and `backend-prod.hcl`).
Bootstrap scripts and older docs describe S3 native `.tflock` locking, but `use_lockfile` is set in
no backend block and there is no lock table, so treat state locking as unconfigured.

Modules present: `amplify`, `api_gateway`, `chaos`, `cloudfront_sse`, `cloudwatch-alarms`,
`cloudwatch-rum`, `cognito`, `dynamodb`, `eventbridge`, `iam`, `kms`, `lambda`, `monitoring`,
`secrets`, `sns`, `waf`, `xray`.

Deployment runs through GitHub Actions. Lambdas ship as container images or ZIPs depending on the
function.

## Local development

LocalStack via `docker-compose.yml`, started by `make test-integration` through the
`localstack-up` target.

The container starts on every integration run, but only `tests/integration/timeseries/` actually
consumes the LocalStack client fixtures defined in `tests/integration/conftest.py`. The rest of the
integration tier uses `moto`. Do not assume a LocalStack failure explains a failing integration
test until you have checked which mechanism that module uses.

## What does not exist

These appear in older documentation, specs, or assumptions. None of them is in the repo. Do not go
looking for them, and do not write code or audits that assume them.

| Assumed | Reality |
|---|---|
| Terraform Cloud, TFC workspaces, remote runs | S3 backend. No `app.terraform.io`, no `cloud {}` block |
| Sentinel / OPA / Conftest policy-as-code | None |
| `tflint` | Not in any hook or workflow |
| `tfsec` | Removed; replaced by a local trivy hook |
| SQS work queues, FIFO queues, a buffering tier | One SQS queue, used as a Lambda and EventBridge DLQ |
| SageMaker endpoints, Fargate inference | None |
| Blue/green or canary Lambda deployment strategy | None |
| Prometheus pushgateway | None |
| SQL database, ORM, prepared statements | DynamoDB only |
| `/v1/sources`, `/v1/outputs`, `/v1/analyze` | Never built. Real surface is `/api/v2/*` |
| Admin API to add/remove sources or pause/resume ingestion | Not built |
| Webhook-subscription ingestion | Scheduled EventBridge polling only |
| A 99.5% availability SLA or 500ms p90 budget | Asserted in no alarm, SLO, or monitor |
