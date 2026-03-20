# Tasks: Real Sentiment Pipeline

**Input**: Design documents from `/specs/1227-real-sentiment-pipeline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Unit tests included per constitution (Implementation Accompaniment Rule).

**Organization**: Tasks grouped by user story. US1 and US2 are both P1 but US1 unblocks US2 (ingestion must work before we can verify the endpoint reads real data).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Fix the root cause — the missing dependency that killed ingestion 3 months ago

- [x] T001 Add `aws-lambda-powertools==3.7.0` to the ingestion Lambda pip install in `.github/workflows/deploy.yml` — find the ingestion dependencies section (around line 145, after `aws-xray-sdk==2.14.0`) and add the missing package. Match the version used by the canary Lambda (line 334).
- [x] T002 Verify the fix locally by checking that all ingestion source files import successfully — run `python -c "import sys; sys.path.insert(0, 'src'); from lambdas.ingestion.handler import lambda_handler"` after installing aws-lambda-powertools in the dev environment.

**Checkpoint**: The packaging bug is fixed in CI config. Next deploy will produce a working ZIP.

---

## Phase 2: Foundational — Sentiment Cache Module

**Purpose**: Create the cache layer that US2 (endpoint) and US3 (observability) both depend on

- [x] T003 Create sentiment history cache module in `src/lambdas/shared/cache/sentiment_cache.py` — follow the `ohlc_cache.py` pattern. In-memory dict cache with jittered TTL (5 min ± 10%). Cache key: `{ticker}:{source}:{start_date}:{end_date}`. Register `CacheStats` instance named `sentiment_history` with the global `CacheMetricEmitter`. Provide `get_cached_history()` and `cache_history()` functions.
- [x] T004 [P] Write unit test for sentiment cache in `tests/unit/test_sentiment_cache.py` — test: cache miss returns None, cache hit returns stored data, TTL expiration clears entry, CacheStats records hits/misses, jittered TTL is within ±10% of 5 minutes.

**Checkpoint**: Cache layer ready. Both US2 and US3 can use it.

---

## Phase 3: User Story 1 — Restore Sentiment Data Pipeline (Priority: P1)

**Goal**: The full pipeline runs: ingestion fetches articles → analysis computes sentiment → timeseries records appear.

**Independent Test**: Invoke ingestion Lambda (no FunctionError), verify analysis Lambda processes messages, check DynamoDB for new timeseries records.

### Pre-flight checks (verify pipeline dependencies before deploying)

- [x] T005 [US1] Verify ML model artifact exists in S3 — run `aws s3 head-object --bucket sentiment-analyzer-models-$(aws sts get-caller-identity --query Account --output text) --key distilbert/v1.0.0/model.tar.gz`. If missing, the analysis Lambda cannot compute sentiment and the pipeline silently produces zero records. Also note the LastModified date — if the model hasn't been updated since deployment, it's the same version that worked in December.
- [x] T005b [US1] Verify analysis Lambda can process a message — invoke `aws lambda invoke --function-name preprod-sentiment-analysis --payload '{"Records":[{"Sns":{"Message":"{\"source_type\":\"test\",\"body\":{\"source_id\":\"test-preflight\",\"text_for_analysis\":\"Test positive sentiment\",\"matched_tickers\":[\"AAPL\"],\"timestamp\":\"2026-03-20T00:00:00Z\",\"model_version\":\"v1.0.0\"}}"}}]}'`. Verify no `FunctionError`. If invocation exceeds 60s (cold start timeout), increase the analysis Lambda timeout before proceeding. NOTE: This test payload is hand-crafted. After T007 (real ingestion), capture a REAL SNS message from CloudWatch logs and compare its format to validate this payload was representative.

### Packaging fix and deployment

- [x] T006 [US1] Push the deploy.yml fix (T001) and trigger a deploy to rebuild the ingestion Lambda ZIP with the missing dependency. Verify the deploy pipeline succeeds.
- [x] T007 [US1] Invoke the ingestion Lambda directly via `aws lambda invoke --function-name preprod-sentiment-ingestion` and verify: (a) no `FunctionError`, (b) response body shows `articles_processed > 0` (confirms API keys are valid — if keys expired during the 3-month outage, this returns 0 articles with no FunctionError), (c) no API authentication errors in the response. If `articles_processed == 0`, check Secrets Manager for key expiration and rotate if needed.
- [x] T007b [US1] Query the timeseries table for records with today's date — `aws dynamodb query --table-name preprod-sentiment-timeseries --key-condition-expression "PK = :pk AND SK >= :today"`. Verify new records exist. This confirms the FULL pipeline (ingestion → SNS → analysis → timeseries) is working.
- [x] T007c [US1] Validate SNS message format — after T007 succeeds, check CloudWatch logs for the analysis Lambda to confirm it received and processed the real ingestion message without format errors. If the message format changed since Feature 1010 (merged Dec 21), the analysis Lambda may reject real messages even though the preflight test (T005b) passed with a hand-crafted payload.
- [x] T007d [US1] Wait 10 minutes after deploy and verify the EventBridge schedule is triggering the ingestion Lambda automatically — check CloudWatch metrics for `preprod-sentiment-ingestion` invocation count > 0 in the last 10 minutes.
- [x] T008 [P] [US1] Write unit test for ingestion handler import in `tests/unit/test_ingestion_import.py` — test that `from lambdas.ingestion.handler import lambda_handler` succeeds without ImportError. This prevents the regression from recurring.

**Checkpoint**: US1 complete. Full pipeline verified: ingestion runs, API keys valid, analysis processes real messages, timeseries populated, schedule firing.

---

## Phase 4: User Story 2 — Wire History Endpoint to Real Data (Priority: P1)

**Goal**: `/sentiment/history` returns real data from DynamoDB instead of synthetic RNG

**Independent Test**: Query the endpoint for a ticker with known timeseries records. Verify the response matches stored data. Verify X-Ray trace shows DynamoDB Query subsegment.

### Implementation for User Story 2

- [x] T009 [US2] Replace the synthetic generator in `src/lambdas/dashboard/ohlc.py` (lines ~1020-1093) with a function that queries the `{env}-sentiment-timeseries` DynamoDB table. NOTE: The sentiment history route handler lives in ohlc.py because routes are organized by URL path (`/tickers/{ticker}/sentiment/history`), not by domain. Ensure OHLC endpoints (earlier in the file) are NOT affected by this change — run OHLC-specific tests after modification. Query pattern: PK=`{ticker}#24h`, SK range between start and end dates. Map DynamoDB records to `SentimentPoint` objects: avg→score, sources→source (IMPORTANT: `sources` field stores `{provider}:{article_id}` format e.g. `tiingo:91120376` — extract the provider prefix before the colon for source attribution), count→use for article count, confidence derived from model output or default 0.8. Use the sentiment cache module (T003) for in-memory caching. Include `x-cache-source` header in the response (`in-memory` or `persistent-cache`).
- [x] T010 [US2] Remove the synthetic data generation code — delete the `hashlib.sha256(ticker.encode())` pattern, the `random.seed(ticker_hash)` logic, and the `base_score` accumulation loop. Verify with `grep -r "hashlib.sha256.*ticker" src/` that no synthetic code remains.
- [x] T011 [US2] Handle edge cases in the query function: empty results return `SentimentHistoryResponse` with `count: 0` and empty `history` array (FR-005). Support the existing query parameters: `source` filter (use PREFIX matching on the `sources` list — e.g. filter `tiingo` matches `tiingo:91120376`), `range` presets (1W/1M/3M/6M/1Y → compute start/end dates), custom `start_date`/`end_date` (FR-004). For `aggregated` source: return all records regardless of source prefix (current data is Tiingo-only; multi-source aggregation becomes meaningful when Finnhub data flows).
- [x] T012 [P] [US2] Write unit test for sentiment history query in `tests/unit/test_sentiment_history.py` — mock DynamoDB with moto. Test: returns real records when they exist, returns empty array when no records, respects date range filtering, respects source filter, maps DynamoDB fields correctly (avg→score, sources→source). Verify synthetic RNG pattern is absent.
- [x] T013 [US2] Run the trace inspection diagnostic (`scripts/trace_inspection_v3.py`) against the sentiment endpoint. Verify X-Ray trace shows DynamoDB Query subsegment (not 1ms flat trace). Verify response data matches timeseries table records.

**Checkpoint**: US2 complete. Customers see real sentiment data. Synthetic generator removed. DynamoDB reads visible in traces.

---

## Phase 5: User Story 3 — Sentiment Endpoint Observability (Priority: P2)

**Goal**: Sentiment endpoint has cache headers, cache metrics, and trace detail matching OHLC

**Independent Test**: Query sentiment history and check for `x-cache-source` header. Check CloudWatch for `Cache/Hits` and `Cache/Misses` with dimension `Cache=sentiment_history`.

### Implementation for User Story 3

- [x] T014 [US3] Verify `x-cache-source` header is present on sentiment history responses — this should already be implemented in T009 (cache module integration). Run `curl -D - ... | grep x-cache-source` to confirm.
- [x] T015 [US3] Verify CacheStats metrics emit correctly — query CloudWatch for `Cache/Misses` with dimension `Cache=sentiment_history` after making a sentiment history request. If metrics don't appear within the flush interval (60s), check that the cache module registered with the global emitter correctly.
- [x] T016 [US3] Verify X-Ray trace detail — invoke the trace inspection diagnostic. The sentiment trace should now show a DynamoDB Query subsegment with `table=preprod-sentiment-timeseries`, matching the OHLC trace pattern.
- [x] T017 [P] [US3] Write unit test for sentiment cache observability in `tests/unit/test_sentiment_cache_observability.py` — test: CacheStats `sentiment_history` instance emits hits/misses, x-cache-source header is set correctly for in-memory vs persistent-cache responses.

**Checkpoint**: US3 complete. Sentiment has full observability parity with OHLC.

---

## Phase 6: Polish & Validation

**Purpose**: End-to-end verification and regression prevention

- [x] T018 Run the full backend unit test suite (`make test-local`) to verify zero regressions from the endpoint rewrite.
- [x] T019 Run the v3 observability audit (`scripts/trace_inspection_v3.py`) — the sentiment test should now show PASS (not WARN for synthetic data). Update the audit script if needed to reflect the new expected behavior.
- [x] T020 Run quickstart.md validation — execute all 5 verification steps from quickstart.md and confirm each passes.
- [x] T021 Verify the frontend chart renders real sentiment data — run `scripts/screenshot_dashboard.py --ticker AAPL` and confirm the sentiment overlay shows data points (not a flat synthetic curve).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Can start in parallel with Phase 1 (different files)
- **Phase 3 (US1)**: Depends on Phase 1 (deploy.yml fix must be committed and deployed)
- **Phase 4 (US2)**: Depends on Phase 2 (cache module) and Phase 3 (data must exist in table)
- **Phase 5 (US3)**: Depends on Phase 4 (endpoint must be wired before verifying observability)
- **Phase 6 (Polish)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (Packaging Fix)**: Independent — only changes deploy.yml
- **US2 (Endpoint Wiring)**: Depends on US1 (needs data in the table to serve) and Phase 2 (cache module)
- **US3 (Observability)**: Depends on US2 (endpoint must be rewritten before adding observability verification)

### Parallel Opportunities

- T001 and T003 can run in parallel (deploy.yml vs cache module — different files)
- T004 and T008 can run in parallel (different test files)
- T012 and T017 can run in parallel (different test files)

---

## Implementation Strategy

### MVP First (US1 Only)

1. T001: Fix deploy.yml (1 line)
2. T002: Verify import locally
3. T005-T005b: Pre-flight checks (model artifact, analysis Lambda)
4. T006-T007: Deploy and confirm data flowing
5. **STOP and VALIDATE**: Lambda runs, new records appear in DynamoDB
6. This alone restores sentiment data production after 3 months of silence

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready (deploy fix + cache module)
2. US1 → Deploy (ingestion Lambda works, data flows)
3. US2 → Deploy (customers see real data instead of synthetic)
4. US3 → Deploy (operators can monitor the sentiment pipeline)
5. Polish → Full validation with diagnostic scripts

---

## Notes

- Total tasks: **26**
- Setup: 2 tasks (T001-T002)
- Foundation: 2 tasks (T003-T004)
- US1: 9 tasks (T005-T008, T005b, T007b, T007c, T007d) — pre-flight checks + deployment + SNS format validation
- US2: 5 tasks (T009-T013)
- US3: 4 tasks (T014-T017)
- Polish: 4 tasks (T018-T021)
- MVP scope: Phase 1 + Phase 3 pre-flight (verify dependencies before deploying the fix)
- Full scope: 26 tasks across 6 phases
- Adversarial analysis additions: model artifact check, analysis Lambda preflight, SNS format validation, EventBridge confirmation, API key validation merged into T007
- **CRITICAL NOTE**: DynamoDB TTL on the timeseries table was DISABLED on 2026-03-19 to preserve the 678 existing records (were hours from expiration). Re-enabling TTL is a deliberate future decision — must decide on retention policy (90 days may be too short for a sentiment history product).
