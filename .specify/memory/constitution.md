# Sentiment Analyzer — Constitution

Purpose
---------
Provide the minimal, unambiguous requirements for a cloud-hosted sentiment analyzer service so teams can implement, operate, and validate it safely and reliably.

Scope
---------
This constitution covers the service that ingests text, returns sentiment labels/scores, and runs in a cloud environment (API + batch). It excludes downstream UX and external labeling workflows.

Minimal Requirements (Bare Minimum)
-----------------------------------
1) Functional Requirements
	- Ingest text by fetching from configured external publishing endpoints (examples: Twitter tweet feed, RSS/Atom feeds, or other public publisher APIs).
	- Support multiple source types with pluggable adapters: at minimum support RSS/Atom and a Twitter-style timeline API adapter.
	- Support both near-real-time ingestion (webhook subscription or short-interval polling) and periodic batch polling for feeds that do not offer push.
	- Deduplicate items (by stable id or content hash) to avoid re-processing the same published item.
	- After ingest, return or persist a sentiment result for each item (at minimum: positive/neutral/negative and a confidence score 0.0–1.0) and the source metadata.
	- Provide an administrative API (or config) to add/remove source subscriptions and to pause/resume ingestion for a source.

2) Non-Functional Requirements
	- Availability: 99.5% service availability SLA for API endpoints.
	- Latency: P90 response time ≤ 500ms for single-item inference under normal load (documented test conditions).
	- Throughput: Service must scale (autoscale) to handle load spikes without manual intervention.

3) Security & Access Control
	- All external-facing management/admin endpoints must require authentication (API keys, OAuth, or cloud IAM). No unauthenticated management access.
	- When calling external publisher APIs, use appropriate authentication flows (OAuth for Twitter, API tokens for private RSS endpoints) and rotate/store credentials securely.
	- Respect third-party API terms-of-service and rate-limits. Adapters must implement backoff and retry policies and honor provided rate-limit headers.
	- All network traffic must use TLS (HTTPS) in transit.
	- Secrets (API keys, model credentials) stored in a managed secrets service — not in source control.

	- Preventing SQL injection and unsafe DB access
	  - All database queries must use parameterized queries / prepared statements or the ORM's parameter binding. Avoid constructing SQL by concatenating user-controlled strings.
	  - Disallow direct interpolation of unvalidated input into query strings. If raw SQL is required, it must be reviewed and approved in code review and use strict parameter binding.
	  - Validate and constrain inputs before they reach the database layer (types, length limits, allowlists where feasible). Reject or sanitize inputs that exceed limits or contain control characters.
	  - Use least-privilege database credentials: separate read-only and write roles, and do not run the service with a superuser/DB owner account.
	  - Prefer safe query builders or ORM abstractions that abstract parameter handling; if using stored procedures, pass parameters rather than concatenating SQL.
	  - Protect logs and dashboard displays: do not write raw user-provided text into logs or dashboard fields without redaction or encoding to avoid log injection and leakage.
	  - Mitigations and defenses: enable DB-side protections where available (parameterized/stored-procedure enforcement, query auditing), deploy a WAF when appropriate, and apply connection/statement timeouts.
	  - Scanning and testing: include SAST/secret scanning and dependency checks in CI; add unit/integration tests that include malicious / injection-style payloads to verify defenses.
	  - Operational monitoring: emit alerts for anomalous query patterns, repeated query errors, or suspicious high-rate requests that may indicate injection attempts.
	  - Documentation & code review: document any justified uses of raw SQL and require explicit review/approval and test coverage for those code paths.


4) Data & Model Requirements
	- Output schema (minimal): { id, source: { type, source_id, url }, text_snippet?: string, sentiment: [positive|neutral|negative], score: float(0-1), model_version }
	- By default do NOT persist full raw text unless explicitly required and approved; if a text_snippet is stored it must be minimal (e.g., first N characters) and the storage policy must be documented.
	- Model versioning: Every deployed model must have a version string and changelog.
	- Reproducibility: Ability to re-run inference using a specified model_version and configuration; record source item id + fetch timestamp so replays are possible.

5) Deployment Requirements
	- Deploy as containerized workload (e.g., Docker) using infrastructure-as-code (Terraform/CloudFormation) or platform templates.
	- Use a managed hosting environment (cloud VMs, serverless, or managed containers). Avoid ad-hoc single-host deployments.
	- Health-check endpoints for liveness and readiness.

5) Deployment Requirements (Serverless / Event-driven preferred)
	- Preferred architecture: event-driven, serverless implementation on AWS using Lambda for compute, SNS for pub/sub events, SQS for durable queues and decoupling, and DynamoDB for persistence. This stack must be described in the deployment docs and implemented via IaC.
	- Infrastructure as Code: use Terraform for all deployments and adopt Terraform Cloud (TFC) as the canonical remote execution and state backend. Use GitHub (VCS) integration with TFC workspaces for dev/staging/prod. Pin provider and module versions in Terraform configs and implement a clear module layout for core components (sns_topic, sqs_queue, lambda_function, dynamodb_table, iam_roles, s3_artifacts).
	  - Terraform Cloud specifics:
	    - Workspaces: create one workspace per environment (dev/staging/prod) or use workspace-per-branch patterns. Connect TFC workspaces to the repository via VCS so TFC runs plan/apply when branches are merged or via API triggers.
	    - Remote runs & state: use TFC remote runs to execute plans/applies and to serve as the authoritative remote state store. This provides locking, run history, and plan logs.
	    - Variables & secrets: store Terraform variables and sensitive values in TFC workspace variables (sensitive vars) or reference Secrets Manager/Parameter Store via data sources; avoid storing plaintext secrets in repos or state.
	    - Policy as code: use Sentinel (TFC) or OPA/Conftest integrated into CI to enforce org policies (encryption required, no public S3, allowed instance sizes, IAM least-privilege checks) before apply.
	    - Runs & approvals: require TFC run approvals for production applies (either manual approval in TFC or via policy gates); maintain a run-approver group for prod changes.

	  - CI/CD integration (GitHub Actions + TFC):
	    - GitHub Actions runs on PRs/branches and performs fast checks: `terraform fmt`, `terraform validate`, `tflint`, `tfsec`/`checkov`, unit tests, and build packaging for Lambda/model artifacts.
	    - For Terraform plan/apply, prefer TFC VCS-driven runs: push branch → Actions runs checks → merge to protected branch triggers TFC workspace run that performs plan/apply. Alternatively, Actions can use the TFC API to queue runs if programmatic trigger is needed.
	    - Actions should upload any built artifacts (model packages) to a controlled S3 artifact bucket with versioned paths before TFC run so the plan references published artifacts.
	    - Ensure GitHub Actions uses a short-lived TFC token or a GitHub App with least-privilege permissions; store tokens as GitHub Secrets.
	  - Provider & module version pinning: explicitly pin AWS provider and module versions in `required_providers` and `required_version` blocks to keep builds reproducible.

	- Scalability & decoupling
	  - Use SNS topics to fan-out ingestion events (per-source or per-purpose topics). Use SQS queues to buffer work and allow horizontal scaling of Lambda consumers.
	  - Design consumers (Lambdas) to be idempotent. Use message deduplication (SQS FIFO or application-level idempotency keys persisted in DynamoDB) to avoid double-processing.
	  - Configure DLQs (dead-letter queues) for messages that fail processing after retries; include alerting for DLQ accumulation.
	  - Visibility timeout and concurrency: tune SQS visibility timeouts to exceed typical Lambda processing time; set reserved concurrency limits to control downstream systems and to protect model inference endpoints.
	- Persistence (DynamoDB)
	  - Use DynamoDB as the primary persistence layer for items, metadata, and lightweight indices. Define clear primary key patterns (partition key + sort key) and GSIs for query access patterns.
	  - Use conditional writes (PutItem with ConditionExpression) to implement atomic deduplication and optimistic concurrency where needed.
	  - Consider on-demand capacity mode for unpredictable workloads; if provisioned mode is used, include autoscaling policies and cost/throughput guidance.
	  - Enable server-side encryption (SSE), point-in-time recovery (PITR) per-table, and daily backups as required by governance.
	- Model artifacts and inference
	  - Model binaries/artifacts should be stored in an immutable artifact store (S3) with versioning and signed access controls; Lambda functions or containers should reference model_version explicitly.
	  - If heavy inference is required, consider using a managed inference service (SageMaker endpoints or containerized inference on Fargate) triggered by events; document latency expectations and autoscaling settings.
	- Deployment & CI/CD
	  - CI/CD pipelines must build, test, and deploy IaC and function artefacts; include unit and integration tests, SAST, and IaC linting checks.
	  - Blue/green or canary deployment strategies are recommended for Lambda and model updates to minimize risk.
	- Observability & cost
	  - Integrate with CloudWatch metrics/logs, X-Ray tracing for end-to-end latency, and a metrics backend (Prometheus pushgateway or CloudWatch metrics exported to the dashboard) so the dashboard metrics map to real telemetry.
	  - Add budgeting and alerts for unexpected cost growth (e.g., spikes in Lambda invocations, DynamoDB read/write units).
	- Local development & testing
	  - Provide a local testing story (SAM local, LocalStack, or an integration test harness) so developers can simulate SNS/SQS/DynamoDB interactions in CI and locally.

Architecture & Tech Stack Notes
	- Event model: represent each source ingestion as an event with a stable id, source metadata, and a minimal payload (avoid shipping raw full text in events unless approved). Events should include model_version when forwarded to inference consumers.
	- Security & IAM: use least-privilege IAM roles per Lambda; grant narrow access to SNS topics, SQS queues, S3 model artifacts, and DynamoDB tables. Manage secrets with AWS Secrets Manager or Parameter Store and restrict which roles can read secrets.
	- NoSQL/Expression safety: when using DynamoDB expressions (UpdateExpression, ConditionExpression), always use ExpressionAttributeNames and ExpressionAttributeValues to avoid injection-like issues from user-controlled values.
	- Idempotency & replay: store an ingestion record with source_id + fetch_timestamp; provide an easy way to re-run inference for a given source_id and model_version (replay endpoint or job triggered via event).
	- Backpressure & graceful degradation: if downstream systems (e.g., inference endpoint, external APIs) are slow or rate-limited, queue messages in SQS with appropriate retention and scale Lambda concurrency gradually.
	- DLQ & manual remediation: provide tooling and runbooks for inspecting DLQ messages, reprocessing them, and resolving data issues.

Acceptance Criteria (serverless stack)
	- Terraform configs/modules are present and deploy a working stack for dev/staging/prod via the documented CI/CD pipeline.
	- CI verifies `terraform fmt`, `terraform validate`, and `terraform plan` on branches and requires a reviewed plan for prod deploys.
	- SNS topics and SQS queues are configured with DLQs, visibility timeout, and access policies.
	- Lambda consumers are idempotent and pass an integration test that demonstrates deduplication and replay for a sample feed.
	- DynamoDB tables exist with documented key design, PITR enabled, encryption at rest enabled, and an example conditional write that prevents duplicate inserts.
	- Observability: CloudWatch/X-Ray traces available end-to-end for a sample ingestion -> inference -> persist flow; dashboard metrics map to live telemetry.
	- Security: IAM roles follow least-privilege, secrets are stored in Secrets Manager/Parameter Store, and SAST/IaC checks run in CI.

6) Observability & Monitoring
	- Emit structured logs for requests (request id, model_version, latency, outcome) without logging raw input text by default.
	- Export metrics: request_count, error_count, latency_histogram, model_version_inferences, and data_drift indicators.
	- Alerting: critical alerts for high error rates, high latency, or instances failing health checks.

	Dashboard & Public Metrics
	--------------------------
	- Provide an externally-facing dashboard (configurable URL) that exposes exported metrics and operational views for stakeholders and auditors.
		- Purpose: give read-only visibility into service health, ingestion, model performance, and drift without exposing raw input text or sensitive identifiers.

	- Minimal dashboard features
		- Time-series charts for: request_count (per-source and total), error_count/error_rate, latency distribution (P50/P90/P99), model_version_inferences, ingestion_rate (per-source), dedup_rate, backlog/lag for polling sources, and data_drift indicators.
		- Filters: time-range (1h/24h/7d/30d), source selector, model_version selector, and severity/metric selector.
		- Drilldowns: link from alerts/metrics to recent aggregated logs or to the corresponding source configuration for troubleshooting.
		- Export: allow CSV/JSON export of queried metric slices and scheduled report generation (daily/weekly summaries).
		- Update frequency: near-real-time where feasible (default polling/update interval ≤ 30s for critical charts) and configurable per-deployment.

	- Privacy and content rules
		- Do NOT display full raw text from published items on the external dashboard by default. Text snippets or redacted previews require explicit approval and must be stored/encrypted under a documented policy.
		- Do not expose identifiers or PII that could identify individuals; apply masking or omit fields that risk re-identification.

	- Access control & public access model
		- Default: dashboard requires authentication (SSO or read-only API tokens / cloud IAM). Optionally support a publicly accessible, rate-limited, read-only view for non-sensitive summary metrics if explicitly approved by governance.
		- Role-based access: admins (full access), operators (alerts + drilldowns), auditors/execs (read-only dashboards and exports).
		- Rate-limit dashboard API/export endpoints to avoid abuse.

	- Instrumentation & implementation notes
		- Dashboard reads from the metrics backend (Prometheus/Cloud Monitoring/Time-series DB) and from aggregated health events; do not query raw logs for live display of content.
		- Metrics shown must map to exported metric names: request_count, error_count, latency_histogram, model_version_inferences, data_drift, per-source ingestion_rate.
		- Provide embeddable widgets or a simple read-only REST endpoint that returns pre-aggregated metric snapshots for partners to embed.

	- Acceptance criteria for the dashboard (minimal)
		- Dashboard deployed to a configurable URL and accessible per the access control policy.
		- The required metrics (see list above) are visible and filterable by time, source, and model_version.
		- Export (CSV/JSON) of metric slices works and does not include raw text or unredacted PII.
		- Access controls prevent unauthorized access; public view (if enabled) is explicitly approved and rate-limited.

	Admin Controls: Feed Switch & Watch Filters
	------------------------------------------
	- The dashboard must provide an admin-only control panel that allows authorized admins to:
		- Select/switch the active feed/source the dashboard displays (supported feeds configured via `/v1/sources`). This is a read-only switch for end-users but an admin can change which source is the focus for the dashboard's live view.
		- Define up to five (5) watch keywords or hashtags per admin session or per-source (whichever governance requires). These are simple token or hashtag matches (no free-form large regexes by default) used to highlight or surface matching items in the dashboard.

	- Behavior and UX requirements
		- Immediate update: changes to the active feed or the watch filters must be reflected in the dashboard UI immediately (near-real-time). Implementation may use WebSockets, Server-Sent Events, or short-polling (recommended update interval ≤ 5s for watch highlights) to ensure responsiveness.
		- Highlighting: the dashboard should visually surface items matching the watch filters (e.g., badge, color, or dedicated "Watch" stream). Matches should show count and recent matches per-filter.
		- Scope: watch filters apply only to the selected/active feed unless the admin chooses global watch scope (explicit option).
		- Limits & validation: the UI and API must enforce a maximum of 5 watch terms per scope and validate inputs (no > 200 char tokens, forbid control characters). Any attempted exceedance returns a clear validation error.

	- Privacy, security & operational constraints
		- Watch filters and selected feed metadata are sensitive configuration and must be stored encrypted (or referenced via a secrets/config store) and be visible only to authorized admin roles.
		- When a watch filter triggers an item highlight, the dashboard must not reveal full raw text or PII unless explicit, auditable approval exists for that source and the admin role has permission to view redacted/unredacted content.
		- Watch functionality must respect third-party API rate-limits — e.g., enabling many rapid per-filter actions that trigger additional fetches must be debounced and rate-limited to avoid violating publisher TOS.

	- Metrics and export integration
		- Watch-related metrics must be emitted: watch_filter_count, watch_match_count (per-filter), watch_match_rate, and watch_highlight_latency (time between item ingestion and highlight display).
		- Exports should be able to include watch-match aggregates (counts and timestamps) but must never include raw unredacted text unless explicitly permitted per governance and access control.

	- Acceptance criteria (admin feed & watch filters)
		- Authorized admin can switch the dashboard focus between any configured, active feed and the UI updates accordingly.
		- Admin can add/remove up to 5 watch keywords/hashtags; attempts to add a 6th are rejected with a clear error.
		- Filter changes are applied immediately in the live UI (demonstrated by a short integration test that asserts a change appears within ≤5s under normal conditions).
		- Watch metrics are reported and exportable; exports do not include raw text or unredacted PII.
		- Access controls prevent non-admins from modifying feed selection or watch filters.


7) Testing & Validation

	Environment & Stage Testing Matrix
	-----------------------------------
	The testing strategy follows a strict environment mirroring pattern with clear rules for mocking:

	| Environment | Mirrors | Test Type | Mocking Strategy |
	|-------------|---------|-----------|------------------|
	| LOCAL       | DEV     | Unit tests only | ALL mocks (AWS, external APIs) |
	| DEV         | LOCAL   | Unit tests only | ALL mocks (AWS, external APIs) |
	| PREPROD     | PROD    | E2E tests only  | Mock external APIs, real AWS |
	| PROD        | PREPROD | Canary/Smoke only | Mock external APIs, real AWS |

	CRITICAL RULES:
	a) LOCAL and DEV environments run ONLY unit tests with mocks (moto for AWS, responses/httpx for APIs)
	b) PREPROD and PROD environments run ONLY E2E tests without AWS mocks (real infrastructure)
	c) ALWAYS mock external 3rd-party dependencies (ticker APIs, email services) in ALL environments
	d) EXCEPTION: Canary/smoke tests post-deployment MAY use real external services for validation

	External Dependency Mocking (Mandatory)
	----------------------------------------
	External dependencies (Tiingo API, Finnhub API, SendGrid, etc.) MUST be mocked in ALL test environments:
	- Unit tests: Use responses, httpx-mock, or similar to mock HTTP calls
	- Integration tests: Use mock adapters or fixtures for external API responses
	- E2E tests in preprod: Use synthetic data generators for external API behavior
	- Exception: Post-deployment canary/smoke tests MAY hit real external APIs for true end-to-end validation

	Rationale: External APIs have rate limits, costs, non-deterministic data, and can cause flaky tests.
	The smoke/canary exception validates production connectivity without risking test suite stability.

	Synthetic Test Data (E2E Requirement)
	--------------------------------------
	All E2E tests in preprod MUST use synthetic test data:
	1. Before each E2E test suite run, generate deterministic synthetic data (tickers, prices, sentiment)
	2. Configure mock external API adapters to return this synthetic data
	3. Test assertions MUST compute expected outcomes from the same synthetic data
	4. The test framework includes a "test oracle" that calculates correct answers from input data

	Pattern:
	```python
	# E2E test setup
	synthetic_data = generate_synthetic_ticker_data(seed=12345)
	mock_tiingo.configure(synthetic_data)
	mock_finnhub.configure(synthetic_data)

	# Execute test
	response = dashboard_api.get_sentiment(config_id)

	# Assert against computed expectations (not hardcoded)
	expected = compute_expected_sentiment(synthetic_data)
	assert response.sentiment == expected
	```

	Implementation Accompaniment Rule
	----------------------------------
	ALL implementation code MUST be accompanied by unit tests:
	- Every new function/module requires corresponding unit tests
	- Tests must cover happy path AND at least one error path
	- Coverage threshold: 80% minimum for new code
	- No PR merges without passing tests for new/modified code

	Functional Integrity Principle
	-------------------------------
	The functional integrity of the entire system depends on the integrity of each component which MUST be verified with comprehensive unit tests. Unit tests serve as the first line of defense against both:
	- Human bugs: Logic errors, edge cases, incorrect implementations introduced by developers
	- Non-human bugs: Breaking changes in dependent packages, incompatible library updates, security vulnerabilities

	CRITICAL RULE: Never push code that causes local unit tests to fail. When tests fail:
	1. DO NOT "make tests pass" by modifying test fixtures to match broken code (anti-pattern)
	2. DO root-cause the failure: is the bug in the source code or in the test fixture?
	3. DO fix the actual bug (source code if logic is wrong, test if expectations are wrong)
	4. DO verify the fix makes semantic sense, not just satisfies the test assertion
	5. DO run full test suite locally before pushing to ensure no regressions

	Unit Tests vs Integration Tests — Critical Distinction
	-------------------------------------------------------
	PRINCIPLE: Unit tests mock externals; integration tests MUST use real dev infrastructure.

	Unit Tests (tests/unit/)
		- Mock ALL external dependencies (AWS services, APIs, databases)
		- Use moto for AWS service mocking, unittest.mock for functions
		- Run everywhere: local development, CI, pre-commit hooks
		- Fast execution (milliseconds to seconds)
		- Goal: Validate code logic in isolation without external dependencies

	Integration Tests (tests/integration/)
		- MUST use REAL dev environment Terraform-deployed resources
		- NO mocking of infrastructure (DynamoDB tables, Lambda functions, SNS topics, SQS queues, S3 buckets)
		- Run ONLY in CI with AWS credentials for dev environment
		- Slower execution (seconds to minutes) due to real AWS calls
		- Goal: Verify end-to-end data flow through ACTUAL production-like infrastructure

	CRITICAL RULE: Integration test failures indicate dev environment or code problems, NOT test configuration problems.

	When Integration Tests Fail:
		1. DO NOT assume tests are using mocks incorrectly
		2. DO NOT change Terraform to "match test mocks"
		3. DO verify dev environment is deployed and matches Terraform (run `terraform plan`)
		4. DO check deployed AWS resources match Terraform definitions (aws describe-table, aws lambda get-function, etc.)
		5. DO identify whether Terraform, deployed resources, or code expectations are misaligned
		6. DO fix root cause (Terraform config, deployment, or code) then re-test against dev

	Rationale:
		- Dev environment exists as a production-like testing ground
		- Integration tests verify code works with ACTUAL AWS infrastructure behavior
		- Mocking infrastructure defeats the purpose of integration testing
		- "Works in CI with mocks" ≠ "Works in production with real AWS"
		- GSI projection types, IAM permissions, capacity limits, and service quotas only surface in real AWS

	What to Mock in Integration Tests:
		- MOCK: External dependencies OUTSIDE this service (Twitter API, NewsAPI, third-party publishers)
		  Reason: We don't control these; they have rate limits, costs, and changing data

		- MOCK: Prohibitively expensive or non-deterministic internal services (ML inference endpoints)
		  Reason: Specific exception when cost or non-determinism prevents reliable testing
		  Requirement: Must be explicitly documented in test with rationale

		- NO MOCK: Any AWS resource THIS SERVICE creates and maintains via Terraform
		  Examples: DynamoDB tables, Lambda functions, SNS topics, SQS queues, S3 buckets, IAM roles
		  Reason: Integration tests verify these work correctly end-to-end with real AWS behavior

	Test Data Flow Pattern:
		1. Start: Mock external input (simulated NewsAPI response with test articles)
		2. Ingestion: Real Lambda, real DynamoDB, real SNS (our Terraform resources)
		3. Analysis: Mock ML inference (expensive/non-deterministic exception)
		4. Dashboard: Real DynamoDB queries, real aggregations
		5. Verify: Assert on real data in real DynamoDB table

	Enforcement:
		- Integration test directory (tests/integration/) uses real dev resources configured via environment variables
		- CI workflow MUST have AWS credentials and point to dev environment (DYNAMODB_TABLE=dev-*, ENVIRONMENT=dev)
		- Terraform MUST have dev workspace deployed before integration tests run
		- NO @mock_aws decorators in integration tests EXCEPT for mocking external publishers or ML (with documented rationale)
		- Code review MUST verify integration tests are not mocking our own Terraform-managed infrastructure
		- Any mock of our own resources requires explicit approval and documentation of prohibitive cost

	Standard Tests
	--------------
	- Unit tests for core logic and schema validations.
	- Integration test verifying end-to-end inference against a deterministic test fixture and asserting schema + performance (latency under a small synthetic load).
	- Model evaluation: report precision/recall/F1 (or other chosen metrics) on a held-out test set and include baseline numbers in repo.



Interfaces (Minimal Contract)
-----------------------------
- Source configuration (admin/API): POST /v1/sources
	- Input (example):
		{ "id": "source-1", "type": "rss"|"twitter", "endpoint": "https://...", "auth": { /* reference to secret */ }, "poll_interval_seconds": 60 }
	- Behavior: creates a subscription/polling configuration; service will begin ingesting items from that source according to adapter semantics.

- Ingested item record (output/persisted shape):
	- { id: string, source: { type: string, source_id: string, url?: string }, received_at: ISO8601, sentiment: "positive"|"neutral"|"negative", score: number, model_version: string }

- Optional push/forward endpoint (downstream): POST /v1/outputs or webhook configured per-source to forward analyzed items to another system.
	- Input to downstream: same as ingested item record.

- Note: A direct POST /v1/analyze public inference endpoint is optional and can be supported as an administrative debug feature only (must follow same auth and logging/privacy rules).

Acceptance Criteria (Minimal)
-----------------------------
- Service ingests items from configured RSS and Twitter-style sources and produces analyzed records according to the output schema.
- Deduplication prevents re-processing of the same published item.
- Adapter respects rate-limits and backoff; simulated rate-limit condition triggers backoff behavior in integration test.
- End-to-end test passes using a pinned model_version and a test feed fixture (deterministic items).
- Operational test demonstrates that pause/resume of a source works and that the service can recover after transient external API failures.
- Secrets are not present in source control; TLS enforced; auth required for admin endpoints.

Operational Notes
-----------------
- Rollback: Every deployment must support quick rollback to previous model_version and container image.
- Backups & Logs: Retain logs and metrics per the retention policy; rotate and archive as required.

8) Git Workflow & CI/CD Rules

	Pre-Push Requirements
	---------------------
	ALL git pushes MUST meet these requirements before pushing:
	a) Code MUST be linted (ruff check)
	b) Code MUST be formatted (black/ruff format)
	c) Commits MUST be GPG-signed (git commit -S)
	d) Push MUST target a feature branch (never push directly to main)

	Pre-push checklist:
	```bash
	ruff check src/ tests/        # Lint
	ruff format src/ tests/       # Format (or black)
	git commit -S -m "message"    # Sign commit
	git push origin feature-branch # Push to feature branch
	```

	Pipeline Monitoring (Background Process)
	-----------------------------------------
	After pushing to a feature branch, monitor pipeline promotion as a background process:
	- Check pipeline status every 30 seconds
	- Continue implementation work in parallel while monitoring
	- Respond to pipeline failures promptly but don't block on green status

	Pattern:
	```bash
	# Push and monitor in background
	git push origin feature-branch
	gh run watch --interval 30 &  # Monitor in background
	# Continue working on next task
	```

	Branch Lifecycle
	----------------
	a) Feature branches are created for all work
	b) Pipeline merges feature branch into main after all checks pass
	c) Remote feature branch is automatically deleted after merge
	d) Developer MUST clean up local feature branches after merge:
	   ```bash
	   git checkout main
	   git pull origin main
	   git branch -d feature-branch  # Delete local branch
	   ```

	Pipeline Check Bypass (NEVER ALLOWED)
	--------------------------------------
	**ABSOLUTE RULE: NEVER BYPASS PIPELINE. NO EXCEPTIONS. NO EXCUSES.**

	This is a non-negotiable requirement. Pipeline checks exist to protect code quality,
	security, and production stability. Bypassing them undermines the entire CI/CD system.

	PROHIBITED ACTIONS (will result in immediate rollback):
	- Do NOT use --no-verify on commits or pushes
	- Do NOT use --admin flag to bypass required checks on merge
	- Do NOT force-push to main or protected branches
	- Do NOT merge without required approvals and passing checks
	- Do NOT skip, dismiss, or override required status checks
	- Do NOT use GitHub admin privileges to bypass branch protection
	- Do NOT disable branch protection rules, even temporarily
	- Do NOT mark failing checks as "expected to fail" to proceed

	If pipeline fails:
	1. STOP - Do not attempt to bypass
	2. Investigate the failure thoroughly
	3. Fix the root cause in the code or tests
	4. Push the fix to the same feature branch
	5. Wait for ALL pipeline checks to pass
	6. Only then proceed with merge through normal PR process

	Rationale: Every pipeline bypass introduces risk that compounds over time.
	A "quick fix" bypass today becomes tomorrow's production incident.
	The pipeline is the last line of defense before code reaches production.

Design & Diagrams (Canva preferred)
----------------------------------
- Preferred tool: use Canva for system and design diagrams (architecture diagrams, data flow, sequence diagrams, and stakeholder visuals). Canva is the standard for design assets to keep visual style consistent and editable by non-engineering stakeholders.

- What to store in the repo
	- Do NOT store Canva source files (proprietary format) in the main code tree. Instead store:
		- A small `diagrams/` directory containing exported, versioned artifacts: PNG (high-res) and SVG (editable vector) for each diagram, plus a lightweight PDF export where appropriate.
		- A `diagrams/README.md` that lists the Canva design link, the exported filenames, the diagram purpose, and the last-updated date.
		- For each diagram, include a short text summary describing the diagram, the key components, and any assumptions.

- Collaboration & permissions
	- Store a canonical Canva design link in `diagrams/README.md` and keep the design ownership under the project's design/account group. Use Canva team sharing settings and restrict editing rights to designers and architects; allow view/comment for wider stakeholders.
	- When a non-designer needs to request a change, open an issue with the requested change and tag the diagram owner; maintain an edit log in the README.

- Export guidelines
	- Export both PNG (for documentation and quick previews) and SVG (for high-quality embeds and accessibility). Prefer 2x or 3x PNG sizes for retina screens where images are used in docs.
	- File names should include a short slug and ISO date: e.g., `architecture-event-driven-2025-11-14.svg`.

- Versioning & provenance
	- Each exported artifact must include the diagram's Canva URL and the last editor and edit timestamp in the `diagrams/README.md`.
	- When a diagram changes materially (architecture, data flow, security boundaries), add a short changelog entry in the README with who approved the change.

- Accessibility & archival
	- Provide alt text for each exported image in docs where the image is embedded. Keep an archived PDF snapshot for major releases.

- Acceptance criteria
	- `diagrams/README.md` exists and contains Canva link(s), export file names, and ownership.
	- At least one canonical architecture diagram is present as SVG and PNG in `diagrams/` and documents the event-driven, serverless stack.
	- Diagram exports include provenance metadata (Canva link, last editor, date) and a brief changelog for material edits.

Sensitive Security Documentation
---------------------------------
Detailed security documentation including penetration test results, vulnerability assessments, incident response playbooks with internal contact info, and secret rotation schedules are stored in a PRIVATE companion repository:

**Repository**: `../sentiment-analyzer-gsk-security/` (relative to this repo)
**Access**: Restricted to security team and on-call engineers
**Contents**:
- Penetration test reports and remediation tracking
- Vulnerability disclosure procedures
- Incident response playbooks with internal escalation contacts
- Secret rotation schedules and key custodian assignments
- Security audit logs and compliance evidence
- Threat models and attack surface analysis

Public-facing security documentation (SECURITY.md, SECURITY_REVIEW.md) remains in this repository.

9) Tech Debt Tracking

	Registry & GitHub Issues Workflow
	----------------------------------
	All technical debt MUST be tracked using a dual-system approach:

	a) Registry File (`docs/TECH_DEBT_REGISTRY.md`)
		- Single source of truth for detailed tech debt documentation
		- Contains: root cause analysis, proposed fixes, effort estimates, risk assessments
		- Organized by priority: Critical, High, Medium, Low, Future Work
		- Tracks commit history that introduced shortcuts or workarounds
		- Updated whenever tech debt is discovered, resolved, or deferred

	b) GitHub Issues
		- All actionable tech debt items SHOULD have corresponding GitHub Issues
		- Issues enable: assignability, milestone tracking, and cross-referencing in PRs
		- Label with `tech-debt` and appropriate priority label
		- Link to specific registry section in issue description

	Required Fields for Registry Entries
	-------------------------------------
	Each tech debt item MUST include:
	- **ID**: Unique identifier (TD-XXX format)
	- **Location**: File path and line number(s)
	- **Status**: Open | Resolved | Deferred | Blocked | Acceptable
	- **Root Cause**: Why this debt was introduced
	- **Proposed Fix**: How to properly resolve it
	- **Effort**: Estimated time to fix
	- **Risk**: Impact of leaving unfixed vs. fixing

	When to Create Tech Debt Entries
	---------------------------------
	Create entries for:
	- Workarounds (e.g., noqa comments, suppressed warnings)
	- Test expectation changes without fixing root cause
	- Security shortcuts with documented acceptance criteria
	- Deferred features or incomplete implementations
	- Known limitations or edge cases not handled
	- Dependency issues requiring future attention

	Review Requirements
	-------------------
	- Tech debt registry MUST be reviewed before production deployments
	- Items marked "Critical" or "High" with status "Open" MUST be addressed or explicitly accepted
	- Acceptance of deferred items requires documented rationale

	Acceptance Criteria
	-------------------
	- `docs/TECH_DEBT_REGISTRY.md` exists and follows the documented format
	- New shortcuts/workarounds result in registry entries before PR merge
	- GitHub Issues exist for actionable items with `tech-debt` label
	- Registry is reviewed in production deployment checklist

10) Canonical Source Verification & Cognitive Discipline

	Cognitive Anti-Patterns (ABSOLUTE RULES)
	-----------------------------------------
	When troubleshooting external system behaviors (AWS IAM, APIs, libraries),
	developers MUST avoid these cognitive traps:

	a) Do Not Succumb under Time Pressure
		- Accuracy, precision, and consistency take priority over speed
		- A failing pipeline is NOT an excuse to skip verification
		- "Make it work" is NOT acceptable without "make it right"

	b) Methodology over Heuristics
		- This repository's methodology is the final word
		- Pattern matching ("list operations need wildcard") is NOT verification
		- Familiar patterns require the same verification as unfamiliar ones

	c) Question ALL Confirmation Bias Results
		- "some A → some B" does NOT mean "all B ← A"
		- Finding evidence that supports your assumption is NOT verification
		- Actively seek evidence that REFUTES your assumption

	d) Gatekeeper Seals Verification
		- Defense in depth: reviewers catch violations that slipped past
		- PR template requires canonical source citations
		- Reviewers MUST verify citations support the proposed change

	Canonical Source Requirements
	-----------------------------
	Before proposing ANY change to external system configurations:

	1. IDENTIFY the specific action/behavior being modified
	2. CONSULT the canonical source for that external system:
		- AWS: Service Authorization Reference (docs.aws.amazon.com/service-authorization/)
		- GCP: IAM permissions reference
		- Azure: RBAC documentation
		- Libraries: Official documentation or source code
		- APIs: OpenAPI specs or official API documentation
	3. VERIFY the source supports your proposed change
	4. CITE the source in your PR description
	5. DOCUMENT any wildcards as "verified required per [source link]"

	Verification Gate (PR Template)
	-------------------------------
	All PRs modifying external system configurations MUST include:
	- [ ] Cited canonical source for external system behavior claims
	- Canonical Sources Cited section with links and verification notes

Amendments & Governance
-----------------------
This constitution is intentionally minimal. Amendments may be added with a short rationale and must include any new acceptance criteria. Maintain a Version and Last Amended date at the bottom.

Amendment 1.1 (2025-11-26): Added Environment & Stage Testing Matrix, External Dependency Mocking rules, Synthetic Test Data requirements for E2E, Implementation Accompaniment Rule, and Git Workflow & CI/CD Rules including pre-push requirements, pipeline monitoring, branch lifecycle, and bypass prohibition.

Amendment 1.2 (2025-11-27): Strengthened Pipeline Check Bypass section to ABSOLUTE RULE status. Added explicit prohibition of --admin flag bypass, GitHub admin privilege abuse, and branch protection disabling. Clarified that all bypasses result in immediate rollback.

Amendment 1.3 (2025-11-27): Added Sensitive Security Documentation section directing to private `../sentiment-analyzer-gsk-security/` repository for confidential security artifacts.

Amendment 1.4 (2025-11-28): Added Tech Debt Tracking section formalizing the dual-system approach using `docs/TECH_DEBT_REGISTRY.md` as detailed documentation and GitHub Issues for actionability. Defines required fields, entry criteria, and review requirements.

Amendment 1.5 (2025-12-03): Added Canonical Source Verification & Cognitive Discipline section establishing four cognitive anti-patterns as absolute rules for troubleshooting external system behaviors. Requires canonical source citation for IAM, API, and library changes. Adds PR template verification gate.

**Version**: 1.5 | **Ratified**: 2025-11-14 | **Last Amended**: 2025-12-03
