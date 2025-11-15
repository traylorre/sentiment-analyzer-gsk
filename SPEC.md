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

Technology Stack
----------------
- AWS Region: us-west-2 (Oregon)
- Lambda Runtime: Python 3.11
- Sentiment Analysis: VADER (vaderSentiment library) - lightweight rule-based analyzer optimized for social media, sub-100ms inference, <5MB package size
- Ingestion Libraries: feedparser (RSS/Atom), tweepy (Twitter API v2)
- Infrastructure: Terraform >= 1.5.0, AWS provider ~> 5.0
- Testing: pytest, moto (AWS mocking), LocalStack (integration tests)

Data Residency & Compliance
----------------------------
- Primary region: us-west-2 (all data at rest stored in Oregon)
- No cross-region replication initially (single-region deployment)
- Data retention: 90-day TTL on DynamoDB items, 7-year CloudWatch Logs retention for compliance
- Encryption: Server-side encryption (SSE) enabled on DynamoDB, S3 artifacts encrypted with AWS-managed keys (SSE-S3)
- No PII storage by default; text snippets require explicit approval and must be minimal

Interfaces & Contracts
----------------------
1) Admin API: configure sources
- Implementation: AWS API Gateway (REST API) + Lambda (Python 3.11)
- Authentication: API Gateway API Keys with usage plans (1000 requests/day per key, 10 requests/second burst)
- Endpoint: POST /v1/sources
- Purpose: create source subscriptions or update polling config
- Headers required: `X-API-Key: <api-key-value>`
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
- Additional endpoints: GET /v1/sources (list all sources), GET /v1/sources/{id} (get source details), PATCH /v1/sources/{id} (update source), DELETE /v1/sources/{id} (remove source)

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
  pk     = "source_key"     # Format: "source_type#source_id" (e.g., "rss#source-1")
  sk     = "item_id"        # Content hash (SHA-256) or publisher's stable ID
  gsi    = [
    {
      name = "model-version-index"
      pk   = "model_version"
      sk   = "received_at"
    }
  ]
  ttl_attribute = "ttl_timestamp"
}

DynamoDB Schema Details:
- Partition Key (PK): `source_key` (STRING) - composite format "source_type#source_id" distributes writes across sources
- Sort Key (SK): `item_id` (STRING) - content hash (SHA-256) or publisher's stable ID for deduplication
- Attributes: received_at (ISO8601), sentiment (STRING), score (NUMBER), model_version (STRING), text_snippet (STRING, optional), ttl_timestamp (NUMBER)
- GSI-1 (model-version-index): PK=model_version, SK=received_at - enables model performance queries and A/B testing
- TTL: ttl_timestamp field (90 days from received_at, configurable)

- Each module must document required inputs, optional inputs and outputs (e.g., topic_arn, queue_url, table_name).
- Conditional writes example for dedup (DynamoDB): PutItem with ConditionExpression: "attribute_not_exists(source_key) AND attribute_not_exists(item_id)".

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
- Dashboard Implementation: AWS CloudWatch Dashboard
- Access Control: IAM-based authentication (read-only role for operators/auditors, admin role for full access)
- Update Frequency: Near real-time (CloudWatch standard 1-minute metric resolution, 5-second resolution for custom metrics via high-resolution)
- Metric names (minimal):
  - `sentiment.request_count{source,model_version}`
  - `sentiment.error_count{source}`
  - `sentiment.latency_ms` (histogram for p50/p90/p99)
  - `sentiment.model_version_inferences{model_version}`
  - `sentiment.watch_match_count{filter}`
  - `sentiment.dedup_rate`
- Dashboard widgets must reference these exact metric names.
- Admin Controls: Feed switching and watch filter management implemented via Admin API endpoints (GET/POST /v1/dashboard/config), UI can be added later as separate lightweight web interface

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

## Clarifications

### Session 2025-11-15

- Q: Which sentiment analysis approach should the Lambda inference function use? → A: VADER (Valence Aware Dictionary and sEntiment Reasoner) - Lightweight rule-based analyzer, <5MB, no cold starts, sub-100ms inference, good for social media text
- Q: What should be the DynamoDB table partition key (PK) and sort key (SK) design for the items table? → A: PK: `source_type#source_id` (e.g., "rss#source-1"), SK: `item_id` (content hash or publisher ID) - Distributes writes across sources, supports per-source queries
- Q: How should the Admin API (POST /v1/sources, etc.) authenticate requests? → A: API Gateway API Keys with usage plans - Simplest implementation, built-in rate limiting, easy rotation via Terraform, suitable for service-to-service or small admin team
- Q: Which AWS region should host the infrastructure? → A: us-west-2 (Oregon) - Good alternative to us-east-1, slightly higher availability due to fewer outages historically, minimal cost difference
- Q: What technology should implement the externally-facing dashboard with metrics and admin controls? → A: CloudWatch Dashboard (native AWS) - Zero infrastructure overhead, direct metric integration, built-in auth via IAM/SSO, limited customization for admin controls
