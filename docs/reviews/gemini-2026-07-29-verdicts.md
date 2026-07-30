# Gemini external review (2026-07-29) — claim-by-claim verdicts

Source: `GEMINI-FEEDBACK-2026-07-29.md` (verbatim owner dump). Every claim was
verified against the repo by independent agents before a verdict was recorded;
the reviewer worked from a partial snapshot, so several claims describe an
architecture this repo does not have. Verdict vocabulary: **APPLIES** (real
gap, carded), **PARTIALLY** (kernel of truth, corrected facts), **DOES NOT
APPLY** (premise false), **ALREADY COVERED** (repo already handles it).

Cards created from this review carry `source: gemini-review-2026-07-29` on
CLEANUP-BOARD.html.

## Scorecard

| # | Claim | Verdict | Card |
|---|-------|---------|------|
| 1 | No container image scan in deploy.yml | PARTIALLY (real gap; facts corrected) | yes |
| 2 | Dependabot/npm audit gap for Node lockfiles | APPLIES (understated) | yes |
| 3 | Dependabot labels may not exist | DOES NOT APPLY | no |
| 4 | mypy `stages: [manual]` never runs in CI | APPLIES | yes |
| 5 | terraform validate / tflint missing | PARTIALLY | yes |
| 6 | Suppression files accumulate debt with no expiry | PARTIALLY (1 of 3 refuted) | yes |
| 7 | `needs: [build, deploy-preprod]` redundant | DOES NOT APPLY — **acting on it would break the pipeline** | no |
| 8 | Base-image-only scanning misses app packages | PARTIALLY | folded into 1+2 |
| 9 | Drop the `by_sentiment` GSI | DOES NOT APPLY — **dropping it would break prod code** | narrow-projection card only |
| 10 | GSI list by_status/by_tag; PENDING hot partition | PARTIALLY | drift card |
| 11 | SQS batch + missing ReportBatchItemFailures | DOES NOT APPLY (no SQS in data path) | no |
| 12 | ConditionalCheckFailedException unhandled | ALREADY COVERED | minor recursion card |
| 13 | SSE on Next.js Lambda exhausts 1,000 concurrency | DOES NOT APPLY (route real but dead; SSE capped at 25) | no (SSE deferred) |
| 14 | No SSE client-disconnect tests | ALREADY COVERED (Python side) | no (SSE deferred) |
| 15 | Governance yaml files are dead text | APPLIES | yes |
| 16 | Adjacency-list DDB design for SSE subscriptions | DOES NOT APPLY (connections are in-memory) | no |

Refuted-and-dangerous: #7 (removing `build` from `needs:` would blank
`needs.build.outputs.*` — artifact SHAs and `MODEL_VERSION` — at
deploy.yml:1570,1636,1711,1729) and #9 (the GSI hash key is already the binned
string label, and `polling.py:415` + `dashboard/metrics.py:278` query it in the
hot path).

## Detail

### 1. Container image scanning — PARTIALLY APPLIES
- Confirmed: zero `trivy image`/grype/scout in `.github/workflows/`; only
  `trivy config` (IaC) at `.pre-commit-config.yaml:113-118`.
- Corrections: **5** image builds, not 3 (deploy.yml:543, 626, 704 preprod;
  1779, 1853 prod). ECR scan-on-push IS enabled for all three repos
  (infrastructure/terraform/main.tf:653-655, 695-697, 738-740) — but nothing
  ever reads the findings, and `push: true` precedes the smoke test.
- Bonus finding (new, not Gemini's): **no `build-analysis-image-prod` job
  exists** — the prod analysis Lambda consumes a `:latest` tag this pipeline
  never builds (main.tf:376). Carded separately at high severity.

### 2. npm/Node SCA — APPLIES, understated
- `.github/dependabot.yml` covers pip (:33), github-actions (:87), terraform
  (:103); no `npm`. TWO uncovered lockfiles: `frontend/package-lock.json` AND
  root `package-lock.json` (which carries a `basic-ftp` override that exists
  precisely because of a past advisory — nothing watches it now).
- No `npm audit`/audit-ci/osv-scanner anywhere; `npm ci` runs unaudited at
  pr-checks.yml:386 and nightly-e2e.yml:55. CodeQL is Python-only
  (pr-checks.yml:267), so JS has no SAST either.

### 3. Dependabot labels — DOES NOT APPLY
`gh label list` confirms all four assigned labels exist (dependencies, python,
github-actions, terraform).

### 4. mypy — APPLIES
- `.pre-commit-config.yaml:149` `stages: [manual]`; the CI pre-commit job
  (pr-checks.yml:242) therefore never runs it, and no other CI step or
  Makefile target does. mypy is pinned (requirements-ci.txt:62) and configured
  (pyproject.toml:129) but never executed anywhere.
- Correction: not "silent" — pr-checks.yml:236-240 documents the skip.
  `check-false-pass-patterns` no-ops in CI by the same mechanism.
- Interaction: Dependabot PR #894 (mypy 1.19→2.1) is stalled; wiring mypy in
  will surface whatever the bump changes.

### 5. terraform validate / tflint — PARTIALLY APPLIES
- tflint: zero occurrences repo-wide (claim holds).
- `terraform validate` exists at Makefile:65 (`lint` target) but **no workflow
  invokes make**, so it is developer-discretion only. `terraform plan` runs
  only in deploy.yml (:944, :2045), which triggers on push to main — PRs get
  zero Terraform semantic validation.
- Side drift: Makefile:70 still gates on deprecated tfsec (removed from
  pre-commit for not supporting TF 1.5 check blocks).

### 6. Suppression expiry — PARTIALLY APPLIES
- `.pip-audit-ignore`: REFUTED — every entry has a dated expiry + justification
  enforced by a blocking gate (`scripts/pip-audit-gate.sh:34-48`, wired at
  pr-checks.yml:167-168). Only residual: the documented 90-day cap is not
  mechanically enforced (a 5-year expiry would pass).
- `.checkov.baseline`: CONFIRMED — 503 lines of findings, no dates/expiry.
- `.gitleaks.toml`: CONFIRMED — no expiry; also the bare 12-digit allowlist
  regex (:14) over-suppresses, and `tests/.*` is blanket-excluded (:21).

### 7. needs: redundancy — DOES NOT APPLY (dangerous advice)
`needs` also scopes `needs.<job>.outputs`. `test-preprod` reads
`needs.build.outputs.artifact-sha` (deploy.yml:1570, 1636, 1711, 1729); GitHub
Actions does not expose outputs transitively. Removing `build` would silently
blank artifact names and the MODEL_VERSION assertion. Same pattern at :1743,
:1831, :1898, :2103, :2145.

### 8. Scan-layer coverage — PARTIALLY APPLIES
- `pyproject.toml` is a red herring (`dependencies = []`); real pins live in
  requirements files and pip-audit gates them — but with `--no-deps`
  (pip-audit-gate.sh:63), so **transitive Python deps shipped in images are
  audited by nothing**. Node surface: nothing at all (see #2).

### 9. by_sentiment GSI — DOES NOT APPLY
- The premise (continuous float as partition key) is false: hash key is the
  binned string `sentiment` (`positive|neutral|negative`),
  modules/dynamodb/main.tf:29-32, 46-51. The float lives in non-indexed
  `score`/`sentiment_score` attributes.
- It is queried in the hot path: `sse_streaming/polling.py:415,424` and
  `dashboard/metrics.py:278` (asserted by tests). Dropping it breaks both.
- Real residual: 3-value cardinality + `projection_type = "ALL"` concentrates
  the full replicated write stream into 3 GSI partitions. Card: narrow to
  `INCLUDE`, low priority. Gemini's hot-partition mechanics were right in the
  abstract; the drop recommendation was wrong for this repo.

### 10. GSI inventory / by_status — PARTIALLY APPLIES
- `by_tag` exists (main.tf:59-64) and is the index actually deserving the
  "drop or fix" treatment — dead (readers at api_v2.py:95,106,265; no writer
  sets scalar `tag`). Already board card Q6.
- `by_status` values are lowercase `pending|analyzed` (2-way split, not an
  unbounded PENDING backlog); concentration concern real but bounded.
- Reviewer missed 6 other GSIs (by_email, by_entity_status, by_provider_sub,
  by_cognito_sub, chaos indexes).
- NEW drift found while verifying: `by_status` was migrated KEYS_ONLY→ALL
  (main.tf:72; acknowledged at dashboard/metrics.py:556) but
  `ingestion/self_healing.py:34,42,97,174` still asserts KEYS_ONLY and does a
  now-redundant `get_full_items()` batch-GetItem; specs/1003 docs also stale.
  Carded.

### 11. SQS / ReportBatchItemFailures — DOES NOT APPLY
- Real pipeline: EventBridge rate(5 min) → Ingestion → SNS publish_batch
  (`${env}-sentiment-analysis-requests`) → SNS→Lambda async subscription
  (main.tf:1065) → Analysis (one record per invoke,
  analysis/handler.py:121-122). Zero `aws_lambda_event_source_mapping` in the
  repo; the only SQS queue is an unconsumed DLQ (modules/sns/main.tf:5).
- The only real batch (producer-side `publish_batch`, ingestion
  handler.py:1131) already handles per-entry partial failure
  (:1136-1163). Duplicate re-analysis is guarded by the conditional update
  `#status = :pending` (analysis/handler.py:340) with CCFE → metric.
- Verified by-product: **the notification Lambda has no trigger of any kind**
  — no SNS subscription, no API route, and the digest EventBridge rule is
  gated by `create_digest_schedule` which defaults false
  (modules/eventbridge/variables.tf:47-51) and is never set (main.tf:
  1116-1136). This is the root cause behind feature-001 Card D.

### 12. ConditionalCheckFailedException — ALREADY COVERED
Caught and treated as duplicate-success in every dedup path:
`ingestion/storage.py:270-278` (primary), `ingestion/dedup.py:225,267-274`
(upsert race → recursed to update), `shared/dynamodb.py:267-270`. Minor real
side-find: dedup.py:272-274 retries via unbounded recursion (no depth cap) —
low-priority card.

### 13. SSE concurrency trap — DOES NOT APPLY (SSE owner-deferred)
- The cited file `frontend/src/app/api/sse/[...path]/route.ts` is REAL (not
  hallucinated) but dead three ways: edge runtime (not Node Lambda), reads a
  cookie nothing sets (self-documented, lines 23-29, died with Feature 1145),
  requires `SSE_LAMBDA_URL` which Amplify never provides (route 503s), and the
  client flag `NEXT_PUBLIC_USE_SSE_PROXY` is never emitted (use-sse.ts:106) —
  already tracked by existing proxy-route cards.
- Deployment is Terraform-managed Amplify (WEB_COMPUTE), not SST/OpenNext.
- Real SSE: browser EventSource → CloudFront (1255) → OAC SigV4 → IAM Function
  URL RESPONSE_STREAM → dedicated Python Lambda with
  `reserved_concurrency = 25` (main.tf:791) and `SSE_MAX_CONNECTIONS = 100`
  (connection.py:110,205). Blast radius capped; the account is
  concurrency-partitioned per function (main.tf:325,383,442,546,595,791,1156).

### 14. SSE disconnect tests — ALREADY COVERED
24+ tests in `tests/unit/sse_streaming/test_connection_cleanup.py` /
`test_connection_limit.py` plus e2e reconnection suites;
`stream.py:529-540` handles BrokenPipeError/OSError as client-disconnect
(FR-085/SC-039). The Node `req.signal` concern targets the dead edge route,
which streams via `Response(upstream.body)` and does no manual writes.

### 15. Orphaned governance configs — APPLIES
`bidirectional-allowlist.yaml`, `iam-allowlist.yaml`, `naming-config.yaml`
(repo root) have ZERO consumers — the validators that read them migrated to
the external template repo (specs/045-iam-allowlist-v2/plan.md:8 admits it).
Worse, `scripts/check-iam-patterns.sh:26-27` hardcodes an overlapping naming
rule instead of reading `naming-config.yaml` (drift-by-duplication) and is
itself manual-only (Makefile:95, absent from the `validate` chain and CI).
Carded: wire or delete.

### 16. Adjacency-list subscription design — DOES NOT APPLY
SSE connections are in-memory per Lambda instance
(`connection.py:103,380`), never stored in DynamoDB; no CONN#/TOPIC#/GSI1
surface exists. The proposal solves a problem this architecture doesn't have.
If cross-instance connection state is ever needed (e.g. an API Gateway
WebSockets migration), this pattern is the right starting point — noted for
the deferred SSE master card, nothing more.

## Bottom line for prioritization

Genuinely new, confirmed gaps (carded): no npm/Node SCA anywhere (highest
value), no image-scan gate + nothing reads ECR scan findings, prod analysis
image never built by the pipeline (found during verification), mypy wired to
nothing, no Terraform semantic validation on PRs, checkov/gitleaks suppression
files lack the expiry discipline pip-audit already has, three governance yamls
are dead text.

Claims to ignore: drop-by_sentiment (would break prod), needs: cleanup (would
break deploys), SQS batching (no SQS), DDB adjacency redesign (no problem to
solve), dependabot labels (exist), SSE concurrency doom (capped at 25).
