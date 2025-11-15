# Sentiment Analyzer — SPEC

Purpose
-------
This file is the actionable specification for the Sentiment Analyzer service. It contains concrete API contracts, data shapes, deployment/CI instructions, Terraform module interfaces, test cases and acceptance criteria derived from the higher-level `constitution.md`.

Location and usage
------------------
- Canonical spec: `SPEC.md` (this file).
- Architecture diagrams: see `diagrams/` and `diagrams/README.md` for Canva links and exports.

High-level architecture (short)
-------------------------------
- Event-driven, serverless pipeline on AWS.
- Ingestion adapters fetch from external publishing endpoints (RSS/Twitter-style APIs) and emit ingestion events.
- SNS topics publish ingestion events; SQS queues buffer and decouple work.
- AWS Lambda consumers perform inference and write a compact record to DynamoDB.
- Terraform + Terraform Cloud (TFC) manage infra; GitHub Actions run checks and publish artifacts.

Interfaces & Contracts
----------------------
1) Admin API: configure sources
- Endpoint: POST /v1/sources
- Purpose: create source subscriptions or update polling config
- Example request payload:
  {
    "id": "source-1",
    "type": "rss",            // or "twitter"
    "endpoint": "https://example.com/feed.xml",
    "auth": { "secret_ref": "arn:aws:secretsmanager:..." },
    "poll_interval_seconds": 60,
    "enabled": true
  }
- Validation rules: `id` unique and slug-safe; `type` in allowlist {"rss","twitter"}; `poll_interval_seconds` >= 15; `endpoint` must be a valid URL.

2) Output record (persisted / forwarded shape)
- Documented JSON schema (minimal):
  {
    "id": "string",                       // internal id
    "source": { "type": "string", "source_id": "string", "url": "string?" },
    "received_at": "ISO8601",
    "sentiment": "positive|neutral|negative",
    "score": 0.0,
    "model_version": "string"
  }
- Notes: by default do NOT persist full text; `text_snippet` may be included if approved and documented.

3) Downstream push/forward
- Optional webhook: POST <configured webhook URL> with the same output record.
- Headers: `X-Request-Id`, `X-Idempotency-Key` (when forwarding batch items), HMAC signature header if configured.
- Retry semantics: exponential backoff; honor 429/503 with backoff; DLQ on repeated failures.

4) Optional label submission API (for external labeling workflows)
- Endpoint: POST /v1/labels
- Payload example:
  { "item_id": "...", "labeler_id": "annotator-1", "label": "negative", "confidence": 0.9, "notes":"contains sarcasm", "timestamp":"...", "source_model_version":"v1.2.0" }
- Labels are stored with provenance and not used for training until validated and a retraining pipeline is triggered.

Operational Behaviors (must implement)
--------------------------------------
- Deduplication: prefer stable `source_id` from publishers; fallback to content hash (SHA-256) where `source_id` not available. Use DynamoDB conditional write (ConditionExpression attribute_not_exists(pk)) to dedupe atomically.
- Idempotency: every ingestion event includes an idempotency key; consumers must be idempotent and avoid double-processing.
- Watch filters: admin can set up to 5 watch keywords/hashtags per scope. Matching is token/hashtag exact match (case-insensitive). UI must reflect changes within ≤5s.
- Backpressure: use SQS retention and DLQs; tune visibility timeout > expected processing time; reserved concurrency for Lambdas to protect downstream.

Terraform module contracts (core)
--------------------------------
Provide reusable modules and document inputs/outputs. Minimal examples:

module "sns_topic" {
  source = "./modules/sns_topic"
  name   = "ingest-topic"
}

module "sqs_queue" {
  source = "./modules/sqs_queue"
  name   = "ingest-queue"
  fifo   = false
}

module "lambda_function" {
  source         = "./modules/lambda"
  name           = "inference-consumer"
  runtime        = "python3.11"
  handler        = "handler.lambda_handler"
  s3_key         = "artifacts/model-v1.2.0.zip"
  environment    = { MODEL_VERSION = "v1.2.0" }
  iam_role_arn   = var.lambda_role_arn
}

module "dynamodb_table" {
  source = "./modules/dynamodb_table"
  name   = "items"
  pk     = "id"
  gsi    = []
}

- Each module must document required inputs, optional inputs and outputs (e.g., topic_arn, queue_url, table_name).
- Conditional writes example for dedup (DynamoDB): PutItem with ConditionExpression: "attribute_not_exists(id)".

CI / CD
-------
- GitHub Actions responsibilities (PR):
  - Run `terraform fmt`, `terraform validate`, `tflint`.
  - Run security checks: `tfsec` (Terraform), `semgrep` or other SAST for code, dependency checks.
  - Run unit tests and build model artifact; upload artifact to S3 artifact bucket (versioned path) and publish artifact path as output for the TFC plan.
- Terraform Cloud integration:
  - Use VCS-connected TFC workspaces (one per environment). Merge to protected branches triggers TFC run.
  - TFC stores remote state and run logs. Require manual approvals or policy gates for production applies.
  - Store sensitive workspace variables in TFC as sensitive variables.

Acceptance tests & fixtures
--------------------------
- Provide a deterministic test fixture (JSONL) with a small set of feed items and expected output records.
- Integration test: push fixture into ingestion adapter mock (or simulate SNS event) → assert DynamoDB entry created with expected sentiment and model_version.
- Performance check: small synthetic load (e.g., 100 concurrent small events) to assert P90 <= 500ms for a single inference under nominal test environment.

Metrics & dashboard mapping
---------------------------
- Metric names (minimal):
  - `sentiment.request_count{source,model_version}`
  - `sentiment.error_count{source}`
  - `sentiment.latency_ms` (histogram for p50/p90/p99)
  - `sentiment.model_version_inferences{model_version}`
  - `sentiment.watch_match_count{filter}`
  - `sentiment.dedup_rate`
- Dashboard widgets must reference these exact metric names.

Security & privacy checklist
---------------------------
- TLS enforced for all external endpoints.
- Secrets stored in AWS Secrets Manager or TFC sensitive variables; not in repo.
- Default behavior: do not persist full raw text. When required, approvals and encryption-at-rest must be in place.
- DynamoDB conditional writes and ExpressionAttributeNames/Values used for all expressions that incorporate user-provided values.

Runbooks (short)
-----------------
- How to rollback model: change Lambda environment MODEL_VERSION to previous value and redeploy via Terraform; use Lambda alias/traffic shifting / CodeDeploy for canary.
- How to reprocess DLQ: inspect message, fix data if required, and requeue to the original queue; provide a reprocess script in `tools/`.

Files to add (recommended)
--------------------------
- `SPEC.md` (this file)
- `diagrams/` with exported SVG/PNG architecture diagram (see existing docs)
- `terraform/` modules and `terraform/live/<env>/` root modules
- `tests/fixtures/` with synthetic feed JSONL
- `ci/` or `.github/workflows/` GitHub Actions workflows for checks

Acceptance criteria (short)
---------------------------
- PR checks run and pass (format/validate/SAST/unit-tests).
- TFC workspaces configured and run on protected-branch merges.
- Integration test shows ingestion → inference → DynamoDB record for fixture.
- Dashboard shows the mapped metrics and watch filter metrics.

Contact / ownership
-------------------
- Core service owner: `scotthazlett@gmail.com`
- Infra owner (Terraform/TFC): `scotthazlett@gmail.com`
