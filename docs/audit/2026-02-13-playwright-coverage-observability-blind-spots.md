# Playwright Coverage & Observability Blind Spot Report

**Service:** sentiment-analyzer-gsk
**Date:** 2026-02-13
**Scope:** Functional requirements, non-functional requirements, custom metrics, alarming, end-to-end tracing
**Type:** Point-in-time snapshot

---

## 1. Executive Summary

The service has **63 Playwright tests** (5 spec files) and **~20 Python E2E tests** covering backend observability. Of those, only **26 Playwright tests** (sanity + auth) and **~10 Python E2E tests** run in CI post-deployment. The infrastructure defines **30+ CloudWatch alarms** across 5 custom namespaces and **6 Lambda functions** all with Active X-Ray tracing.

**Critical findings:**
- **2 Lambda functions have ZERO error alarms** (SSE Streaming, Metrics)
- **3 custom metrics are emitted but have NO alarms** (StuckItems, ConnectionAcquireFailures, EventLatencyMs)
- **7 silent failure paths** where errors are caught, logged, but emit no metric
- **Frontend does NOT propagate X-Ray trace headers**, breaking client-to-server correlation
- **No Playwright tests verify ANY backend observability** (metrics, alarms, traces)
- **Mobile browser testing disabled in CI** (only Desktop Chrome runs)

---

## 2. Playwright Test Coverage — Functional Requirements

### 2.1 What IS Covered

| Requirement | Test File | CI? | Tests |
|---|---|---|---|
| Ticker search + selection | `sanity.spec.ts` | YES | 3 tests (AAPL, GOOG, search) |
| Chart data loading (candles + sentiment) | `sanity.spec.ts` | YES | aria-label assertions on candle/sentiment counts |
| Time range switching (1W–1Y) | `sanity.spec.ts` | YES | 5 range buttons tested |
| Layer toggles (price, sentiment) | `sanity.spec.ts` | YES | aria-pressed assertions |
| Auth: OAuth buttons (Google, GitHub) | `auth.spec.ts` | YES | Button visibility |
| Auth: Magic link form | `auth.spec.ts` | YES | Email input + submit flow |
| Auth: Anonymous dashboard access | `auth.spec.ts` | YES | Dashboard loads without auth |
| Settings: Dark mode, haptics, reduced motion | `settings.spec.ts` | NO | 18 tests |
| Navigation: Tab switching | `navigation.spec.ts` | NO | 8 tests |
| First impression: Empty state, responsive | `first-impression.spec.ts` | NO | 8 tests |

### 2.2 What IS NOT Covered (Functional Gaps)

| Missing Requirement | Spec Source | Severity |
|---|---|---|
| OHLC chart pan/zoom interactions | `specs/1082-pan-numeric-xaxis`, `specs/1070-price-chart-vertical-zoom` | **HIGH** |
| Pan-to-load (fetch data on pan edge) | `specs/1101-ohlc-pan-to-load` | **HIGH** |
| Market gap visualization (weekends/holidays) | `specs/1102-ohlc-market-gap-viz` | **MEDIUM** |
| Multi-resolution switching (1m–1day) | `specs/1009-realtime-multi-resolution` | **HIGH** — tested in Python but not Playwright |
| Mobile swipe gestures (section navigation) | `specs/013-interview-swipe-gestures` | **HIGH** — "must look polished" per spec |
| Cache observability headers (X-Cache-Source, X-Cache-Age) | `specs/1218-ohlc-cache-reconciliation` FR-003/FR-004 | **MEDIUM** |
| Cache degradation mode (X-Cache-Error headers) | `specs/1218-ohlc-cache-reconciliation` FR-001/FR-002 | **MEDIUM** |
| Session state persistence across reload | `specs/1122-zustand-hydration-fix` | **MEDIUM** |
| Configuration CRUD (watch lists, alert rules) | `specs/010-dynamic-dashboard-link` | **LOW** — Python E2E covers this |
| Keyboard shortcuts (Ctrl+1-9, arrows) | `specs/117-keyboard-shortcuts-fix` | **LOW** |

---

## 3. Playwright Test Coverage — Non-Functional Requirements

### 3.1 Performance SLOs

| SLO | Target | Tested? | How | Gap |
|---|---|---|---|---|
| Resolution switching | p95 < 100ms | YES (Python) | `test_resolution_switch_perf.py` | Not in Playwright; **not confirmed running in CI** |
| Live update latency | p95 < 3000ms | YES (Python) | `test_live_update_latency.py` | Not in Playwright; **not confirmed running in CI** |
| Dashboard Lambda latency | p95 < 1s | YES (Alarm) | Terraform alarm | No E2E assertion |
| Analysis Lambda latency | p95 < 25s | YES (Alarm) | Terraform alarm | No E2E assertion |
| API response time | p99 < 5s | NO | — | **NO TEST EXISTS** |
| Chart pan frame rate | Smooth | NO | — | **NO TEST EXISTS** |

### 3.2 Accessibility

| Requirement | Tested? | File |
|---|---|---|
| aria-labels on chart | YES | `sanity.spec.ts` |
| Skip link | YES | `first-impression.spec.ts` (NOT in CI) |
| Keyboard navigation | YES | `navigation.spec.ts` (NOT in CI) |
| Touch targets >= 24x24px | YES | `settings.spec.ts` (NOT in CI) |
| Screen reader flow | NO | — |

### 3.3 Mobile Responsiveness

| Viewport | Tested? | CI? |
|---|---|---|
| Desktop Chrome (1280x800) | YES | YES |
| Mobile Chrome (Pixel 5) | YES | **NO** — `--project="Desktop Chrome"` excludes it |
| Mobile Safari (iPhone 13) | YES | **NO** — excluded in CI |
| Tablet (768x1024) | YES | **NO** — only in `first-impression.spec.ts` |

**Blind spot:** Mobile viewports are tested locally but **never in CI**. Mobile regressions can ship undetected.

---

## 4. Custom Metrics — ERROR and DEGRADED Coverage

### 4.1 Metrics Emitted WITH Alarms (Healthy)

| Metric | Namespace | Alarm | Threshold | Fires? |
|---|---|---|---|---|
| Lambda `Errors` (Ingestion) | `AWS/Lambda` | `ingestion_errors` | > 3 in 5min | YES |
| Lambda `Errors` (Analysis) | `AWS/Lambda` | `analysis_errors` | > 3 in 5min | YES |
| Lambda `Errors` (Dashboard) | `AWS/Lambda` | `dashboard_errors` | > 5 in 5min | YES |
| Lambda `Errors` (Notification) | `AWS/Lambda` | `notification_lambda_errors` | > 3 in 5min | YES |
| Lambda `Duration` (Analysis) | `AWS/Lambda` | `analysis_latency_high` | p95 > 25s | YES |
| Lambda `Duration` (Dashboard) | `AWS/Lambda` | `dashboard_latency_high` | p95 > 1s | YES |
| `NewItemsIngested` | `SentimentAnalyzer` | `no_new_items` | <= 0 for 1hr | YES |
| `DashboardImportErrors` | `SentimentAnalyzer/Packaging` | `dashboard_import_errors` | > 0 | YES |
| `TiingoApiErrors/TiingoApiCalls` | `SentimentAnalyzer/Ingestion` | `tiingo_error_rate` | > 5% | YES |
| `FinnhubApiErrors/FinnhubApiCalls` | `SentimentAnalyzer/Ingestion` | `finnhub_error_rate` | > 5% | YES |
| `CircuitBreakerOpen` | `SentimentAnalyzer/Ingestion` | `circuit_breaker_open` | > 0 | YES |
| `CollisionRate` | `SentimentAnalyzer/Ingestion` | `collision_rate_high/low` | > 40% or < 5% | YES |
| `EmailQuotaUsed` | `SentimentAnalyzer/Notifications` | `sendgrid_quota_*` | 50% / 80% | YES |
| Notification delivery rate | `SentimentAnalyzer/Notifications` | `notification_delivery_rate` | < 95% | YES |
| `AlertsTriggered` | `SentimentAnalyzer/Alerts` | `alert_trigger_rate_high` | > 50/hr | YES |

### 4.2 Metrics Emitted WITHOUT Alarms (BLIND SPOTS)

| Metric | Namespace | Emitter | Impact |
|---|---|---|---|
| **`StuckItems`** | `SentimentAnalyzer` | Metrics Lambda (`handler.py:58`) | Items stuck in "pending" > 5min accumulate silently. Dashboard shows stale data. |
| **`ConnectionAcquireFailures`** | `SentimentAnalyzer/SSE` | SSE Lambda (`metrics.py:123`) | Connection pool exhaustion = users can't receive live updates. No alarm. |
| **`EventLatencyMs`** | `SentimentAnalyzer/SSE` | SSE Lambda (`metrics.py:119`) | Live update latency breaches p95 SLO silently. No alarm. |
| **`MetricsLambdaErrors`** | `SentimentAnalyzer` | Metrics Lambda (`handler.py:128`) | The monitoring system itself can fail without alerting. |
| **`HighLatencyAlert`** | `SentimentAnalyzer/Ingestion` | Ingestion metrics (`metrics.py`) | Latency > 30s (3x SLA) logged but not alarmed. |
| **`PollDurationMs`** | `SentimentAnalyzer/SSE` | SSE Lambda | DynamoDB poll taking too long = stale data, no alarm. |
| **`AnalysisErrors`** | `SentimentAnalyzer` | Analysis handler | Custom metric emitted but alarm only on AWS/Lambda Errors, not this. |

### 4.3 Lambda Functions WITHOUT Error Alarms

| Lambda | Error Alarm | Latency Alarm | In Dashboard? |
|---|---|---|---|
| Ingestion | YES | **NO** | YES |
| Analysis | YES | YES | YES |
| Dashboard | YES | YES | YES |
| Notification | YES | **NO** | YES |
| **Metrics** | **NO** | **NO** | YES (widget only) |
| **SSE Streaming** | **NO** | **NO** | YES (widget only) |

**The Metrics Lambda and SSE Streaming Lambda have dashboard widgets showing errors but NO alarms to wake an operator.** An operator would have to be staring at the dashboard to notice.

---

## 5. Customer Experience Verification

### Can customers access stock prices overlaid with sentiment inference?

**Playwright verification:** PARTIAL

| Customer Journey Step | Verified? | How |
|---|---|---|
| Dashboard loads | YES | `sanity.spec.ts` — heading visible |
| Search for ticker (AAPL) | YES | `sanity.spec.ts` — search + select |
| Price candles display | YES | aria-label asserts `[1-9]\d* price candles` |
| Sentiment line displays | YES | aria-label asserts `[1-9]\d* sentiment points` |
| Toggle layers on/off | YES | aria-pressed assertions |
| Switch time ranges | YES | 1W/1M/3M/6M/1Y tested |
| Live sentiment updates (SSE) | **NO** | Not in Playwright. Python `test_live_update_latency.py` tests SSE but from Python, not browser |
| OHLC candle rendering accuracy | **NO** | No assertion that candle OHLC values match API response |
| Sentiment score accuracy | **NO** | No assertion that displayed sentiment matches backend data |
| Multi-resolution (1m–1day) | **NO** | Only time ranges (1W–1Y) tested, not resolutions |

**Critical gap:** Playwright tests verify that "some number of candles" render but never verify the **data accuracy** — a customer could see wrong prices and tests would pass.

---

## 6. Operator Alarming for Error/Degraded Situations

### 6.1 Alarm Configuration Issues

| Alarm | Issue | Severity |
|---|---|---|
| `analysis_latency_high` | Threshold 25s is extremely generous for a 60s timeout Lambda. A p95 of 20s would pass but leave only 40s headroom. | **MEDIUM** — consider tightening to 15s |
| `no_new_items` | `treat_missing_data = breaching` — CORRECT. Absence means pipeline is broken. | OK |
| `dashboard_errors` | Threshold > 5 errors/5min is permissive for a customer-facing service. At 100 req/s that's a 0.02% error rate before alarm. | **LOW** |
| `collision_rate_low` | `< 5%` alarm with 6 evaluation periods (30min). Takes 30 minutes to detect if cross-source dedup stops working. | **MEDIUM** |
| All cost alarms | `treat_missing_data = notBreaching` — Correct for cost metrics. | OK |
| Budget | 6 thresholds (25%–100%) — Well-configured. | OK |

### 6.2 Missing Operator Alarms (Would Cause Silent Outages)

| Scenario | Current State | Operator Impact |
|---|---|---|
| SSE streaming dies | No error alarm on SSE Lambda | Customers lose live updates. Operator unaware until customer complaint. |
| Metrics Lambda dies | No error alarm on Metrics Lambda | All custom metric monitoring stops. Alarms on custom metrics fire incorrectly (treat_missing_data=notBreaching means they'll resolve, giving false green). |
| Items stuck in pending | StuckItems metric emitted, no alarm | Dashboard shows stale sentiment data. Customers see outdated analysis. |
| Connection pool exhaustion | ConnectionAcquireFailures emitted, no alarm | New SSE connections rejected. Customers get no streaming. |
| Ingestion takes too long | No latency alarm on Ingestion Lambda | Timeout risk. Articles processed late, customers see delayed sentiment. |

### 6.3 Alarm-to-Dashboard Coverage

The CloudWatch dashboard (`{env}-sentiment-analyzer`) has 13 widgets covering all 6 Lambdas but **the Alarm Status widget (Row 4) only shows 6 alarms** out of 30+. An operator looking at the dashboard gets an incomplete alarm picture.

---

## 7. End-to-End Latency Tracing (X-Ray)

### 7.1 Trace Chain Analysis

```
Browser --> [GAP] --> API Gateway --> Dashboard Lambda --> DynamoDB
                                                       --> SSE Lambda --> DynamoDB
Ingestion Lambda --> Tiingo/Finnhub --> DynamoDB --> SNS --> Analysis Lambda --> DynamoDB
                                                                             --> Timeseries fanout
Notification Lambda --> SendGrid
```

### 7.2 X-Ray Coverage per Component

| Component | X-Ray Active? | Subsegments? | Gap |
|---|---|---|---|
| CloudWatch RUM | YES (`enable_xray=true`) | Automatic | None |
| **Frontend fetch()** | **NO** | **N/A** | **No `X-Amzn-Trace-Id` header propagated from client** |
| API Gateway | YES (`xray_tracing_enabled=true`) | Automatic | None |
| Dashboard Lambda | YES (Powertools Tracer) | 20+ captures | None |
| SSE Streaming Lambda | YES (`patch_all()`) | `stream_status` only | **Only 1 subsegment for entire Lambda** |
| Ingestion Lambda | YES (`patch_all()`) | 6 captures | None |
| Analysis Lambda | YES (`patch_all()`) | 2 captures | None |
| Notification Lambda | YES (`patch_all()`) | 3 captures | None |
| Metrics Lambda | YES (`patch_all()`) | Minimal | Low priority |
| DynamoDB calls | YES (auto-patched) | Automatic | None |
| Tiingo/Finnhub HTTP | YES (httpx auto-patched) | Automatic | None |
| **SendGrid HTTP** | **UNCERTAIN** | **Unknown** | **SendGrid SDK may not expose urllib3 for patching** |
| **SNS cross-Lambda** | **IMPLICIT** | **SDK auto** | **No explicit trace context in MessageAttributes** |
| **SSE events to client** | **NO** | **N/A** | **Trace IDs not included in SSE event payloads** |

### 7.3 Not Exclusively Using X-Ray to Trace

| Instance | What's Used Instead | File |
|---|---|---|
| SSE event latency logging | Custom `log_latency()` via CloudWatch Logs Insights `pctile()` | `src/lambdas/sse_streaming/latency_logger.py` |
| Cache hit rate logging | Custom `log_cache_hit_rate()` via CloudWatch Logs Insights | `src/lambdas/sse_streaming/cache_logger.py` |
| Correlation IDs | Custom `{source_id}-{request_id}` format | `src/lib/metrics.py:get_correlation_id()` |

These are supplementary and not violations per se, but an operator needs to query **both** X-Ray and CloudWatch Logs Insights to get complete latency data. A single-pane tracing experience requires consolidating onto X-Ray.

---

## 8. Blind Spots — Silent Failure Modes

### 8.1 CRITICAL: Metrics Emission Itself Can Fail Silently

**File:** `src/lib/metrics.py:227-232`

```python
except Exception as e:
    logger.error(f"Failed to emit metric: {e}", ...)
    # NO metric about metrics failures. NO alarm possible.
```

If CloudWatch `put_metric_data` fails (IAM permission change, throttling, network partition), **the entire observability system goes dark** and nobody knows. The `no_new_items` alarm would resolve to OK (treat_missing_data=breaching would fire, but other alarms with notBreaching would show green).

**Cascading impact:** This is the single most dangerous blind spot. A CloudWatch regional degradation would make your service appear healthy to operators.

### 8.2 HIGH: Circuit Breaker Persistence Failures

**File:** `src/lambdas/shared/circuit_breaker.py:334-339, 369-374`

DynamoDB save/load of circuit breaker state catches exceptions, logs, and falls back to defaults. No metric emitted. If DynamoDB is throttled, circuit breakers reset to closed on every Lambda invocation, defeating their purpose.

### 8.3 HIGH: Audit Trail Persistence Failures

**File:** `src/lambdas/ingestion/audit.py:64-72`

`save()` catches `ClientError`, logs, returns `False`. No metric. The audit trail can silently stop persisting without any alarm firing. Compliance implications.

### 8.4 HIGH: Downstream Notification Publish Failures

**File:** `src/lambdas/ingestion/notification.py:127-136`

SNS `publish()` failure is caught, logged, returns `None`. No metric emitted. Per FR-004, downstream systems must be notified within 30 seconds. This failure path violates the SLA silently.

### 8.5 MEDIUM: Time-Series Fanout Partial Writes

**File:** `src/lib/timeseries/fanout.py:177-184`

`BatchWriteItem` unprocessed items after retries are logged but no metric emitted. Dashboard could show data at some resolutions (1m, 5m) but not others (1h, 24h), with no alarm.

### 8.6 MEDIUM: Self-Healing Item Fetch Failures

**File:** `src/lambdas/ingestion/self_healing.py:230-238`

Individual item fetch failures during self-healing are logged and skipped with `continue`. No metric. Self-healing can appear successful (emits `SelfHealingItemsRepublished`) while silently dropping items.

### 8.7 MEDIUM: Parallel Fetcher Error Aggregation

**File:** `src/lambdas/ingestion/parallel_fetcher.py:133-147`

Errors collected in `self._errors` list but no aggregate error count metric emitted for the parallel fetch operation as a whole.

---

## 9. Consolidated Callouts

### 9.1 NOT Exclusively Using X-Ray to Trace

| Location | What's Happening | Should Be |
|---|---|---|
| `src/lambdas/sse_streaming/latency_logger.py` | Custom structured log for pctile() queries | X-Ray subsegment with duration annotation |
| `src/lambdas/sse_streaming/cache_logger.py` | Custom structured log for cache hit rate | X-Ray annotation on subsegment |
| `src/lib/metrics.py:get_correlation_id()` | Custom `{source}-{request_id}` correlation | X-Ray trace ID propagation |
| Frontend SSE client | No trace context | X-Amzn-Trace-Id in SSE event payloads |
| Frontend API client | No trace headers | X-Amzn-Trace-Id header on fetch() |

### 9.2 NOT Using CloudWatch to Emit a Metric

| Location | What's Logged | Should Also Emit |
|---|---|---|
| `circuit_breaker.py:334-339` | "Failed to load circuit breaker" | `CircuitBreakerPersistenceFailure` |
| `circuit_breaker.py:369-374` | "Failed to save circuit breaker" | `CircuitBreakerPersistenceFailure` |
| `audit.py:64-72` | "Failed to save collection event" | `AuditEventPersistenceFailure` |
| `notification.py:127-136` | "Failed to publish notification" | `DownstreamNotificationFailure` |
| `metrics.py:227-232` | "Failed to emit metric" | Cannot self-report; needs canary |
| `self_healing.py:230-238` | "Failed to get full item" | `SelfHealingItemFetchFailure` |
| `fanout.py:177-184` | "Failed to write all items" | `TimeseriesFanoutPartialFailure` |

### 9.3 CloudWatch Metrics/Alarms Incorrectly Configured

| Alarm / Metric | Issue | Risk |
|---|---|---|
| **SSE Lambda — no error alarm** | Widget shows errors but no alarm fires | SSE outage undetected |
| **Metrics Lambda — no error alarm** | Monitor-of-monitors gap | All custom monitoring stops silently |
| **StuckItems — metric but no alarm** | Items rot in "pending" | Stale dashboard data |
| **ConnectionAcquireFailures — metric but no alarm** | SSE pool exhausted | Users silently lose live updates |
| **EventLatencyMs — metric but no alarm** | SSE latency SLO violation | p95 < 3s SLO breached undetected |
| **Ingestion Lambda — no latency alarm** | Only error alarm exists | Ingestion approaching timeout goes unnoticed |
| **Notification Lambda — no latency alarm** | Only error alarm exists | Email delivery delays undetected |
| **Dashboard alarm widget** | Shows 6 of 30+ alarms | Operator gets false sense of "all green" |
| **analysis_latency_high threshold = 25s** | Lambda timeout is 60s | Only 35s headroom; should alert earlier (e.g., 15s) |

---

## 10. Summary — What an Operator's Single Dashboard Cannot Show Today

An operator looking at the CloudWatch dashboard today **cannot** see:

1. Whether SSE streaming is healthy (no error alarm, no latency alarm)
2. Whether the monitoring system itself is working (Metrics Lambda has no alarm)
3. Whether items are stuck in the pipeline (StuckItems emitted but not alarmed)
4. Whether SSE connection pool is exhausted (metric exists, no alarm)
5. Whether frontend clients can trace requests end-to-end (no X-Ray header propagation)
6. Whether SendGrid email delivery is being X-Ray traced (uncertain patching)
7. Whether time-series data is partially written across resolutions (no metric)
8. Whether audit trail persistence is working (no metric on failure)

**The system has good observability for the happy path but multiple blind spots on degraded/error paths.** The most dangerous failure mode is CloudWatch `put_metric_data` itself failing — this would make every other metric-based alarm unreliable while showing green on `notBreaching` alarms.
