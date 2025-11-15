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

Amendments & Governance
-----------------------
This constitution is intentionally minimal. Amendments may be added with a short rationale and must include any new acceptance criteria. Maintain a Version and Last Amended date at the bottom.

**Version**: 1.0 | **Ratified**: [2025-11-14] | **Last Amended**: [2025-11-14]
