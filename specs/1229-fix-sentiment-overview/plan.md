# Implementation Plan: Fix Sentiment Overview & History Endpoints

**Branch**: `1229-fix-sentiment-overview` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1229-fix-sentiment-overview/spec.md`

## Summary

Both sentiment endpoints (`/configurations/{id}/sentiment` and `/configurations/{id}/sentiment/{ticker}/history`) return empty/stub data because they try to call dead external adapters or return hardcoded mock data. Fix: rewire both to query the `sentiment-timeseries` DynamoDB table via the existing `TimeseriesQueryService`, following the same pattern already working in `ohlc.py`. Additionally, align sentiment resolutions from 8 (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h) to 6 (1m, 5m, 15m, 30m, 1h, 24h) matching OHLC 1:1 for dashboard overlay.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: boto3 (DynamoDB), pydantic (response models), existing `TimeseriesQueryService`
**Storage**: DynamoDB `{env}-sentiment-timeseries` table (existing, already populated by analysis pipeline)
**Testing**: pytest with moto (unit), LocalStack (integration)
**Target Platform**: AWS Lambda (existing dashboard Lambda)
**Project Type**: Web application (Python backend + React frontend)
**Performance Goals**: <2s response for overview with 20 tickers; reuse existing `TimeseriesQueryService` caching
**Constraints**: API response model structure preserved; sentiment dict key changes from dead "tiingo"/"finnhub" to "aggregated"
**Scale/Scope**: ~20 tickers per configuration max; 6 resolution levels; 2 endpoints to rewire; frontend resolution config update

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Parameterized queries / no SQL injection | PASS | DynamoDB KeyConditionExpression with ExpressionAttributeValues (existing pattern) |
| Implementation accompaniment (unit tests) | PASS | New query logic will have unit tests with moto mocks |
| Deterministic time handling in tests | PASS | Will use fixed dates and freezegun per constitution |
| External dependency mocking | PASS | No new external dependencies; DynamoDB mocked in unit tests |
| GPG-signed commits | PASS | Standard workflow |
| Feature branch workflow | PASS | Branch `1229-fix-sentiment-overview` already created |
| SAST/lint pre-push | PASS | `make validate` before push |
| Secrets management | PASS | No new secrets; TIMESERIES_TABLE env var already wired |
| Least-privilege IAM | PASS | Dashboard Lambda already has read access to timeseries table |

No violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/1229-fix-sentiment-overview/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: research findings
├── data-model.md        # Phase 1: entity/data model
├── quickstart.md        # Phase 1: implementation quickstart
├── contracts/           # Phase 1: API contracts
│   └── sentiment-api.yaml
└── tasks.md             # Phase 2: task breakdown (created by /speckit.tasks)
```

### Source Code (files to modify)

```text
src/
├── lambdas/
│   └── dashboard/
│       ├── sentiment.py          # MODIFY: Rewrite get_sentiment_by_configuration() + get_ticker_sentiment_history()
│       ├── router_v2.py          # MODIFY: Pass resolution param, fix error messages (lines 1551, 1621)
│       └── timeseries.py         # MODIFY: Update DEFAULT_LIMITS dict (line 227-236)
├── lib/
│   └── timeseries/
│       ├── models.py             # MODIFY: Resolution enum 8→6 (add 15m/30m, remove 10m/3h/6h/12h)
│       ├── preload.py            # MODIFY: Update RESOLUTION_ORDER (line 24-33)
│       └── fanout.py             # MODIFY: Update docstring only (iterates Resolution enum automatically)
└── lambdas/
    └── sse_streaming/
        └── handler.py            # MODIFY: Update valid_resolutions set (line 215)

src/dashboard/
└── config.js                     # MODIFY: Update RESOLUTIONS, RESOLUTION_ORDER, UNIFIED_RESOLUTIONS

frontend/
└── src/
    ├── types/sentiment.ts        # MODIFY: Change TickerSentiment.sentiment to use "aggregated" key
    └── components/heatmap/
        └── heat-map-view.tsx     # MODIFY: Remove hardcoded source key access (tiingo/finnhub/ourModel)

tests/
├── unit/
│   ├── test_sentiment_overview.py        # NEW: Unit tests for rewired overview
│   ├── test_sentiment_history.py         # NEW: Unit tests for rewired history
│   ├── dashboard/test_sentiment.py       # MODIFY: Remove adapter parameter tests (lines 81, 98, 116, 130)
│   ├── test_preload_strategy.py          # MODIFY: Update assertions for 6 resolutions
│   ├── test_sse_resolution_filter.py     # MODIFY: Remove references to removed resolutions
│   ├── test_resolution_cache.py          # MODIFY: Update expected TTLs
│   ├── test_timeseries_key_design.py     # MODIFY: Update hardcoded resolution list
│   ├── test_timeseries_bucket.py         # MODIFY: Update alignment test cases
│   └── dashboard/test_config_resolution.py # MODIFY: Update expected resolution set
└── integration/
    └── test_sentiment_endpoints.py       # NEW: Integration tests against LocalStack
```

**Structure Decision**: Existing web application structure. Both backend AND frontend changes required. The frontend heatmap hardcodes source key access that must be updated to work with aggregated timeseries data.

## Adversarial Review Findings (2026-03-21)

### Finding 1: Resolution change blast radius (CRITICAL — addressed in plan)

The Resolution enum change affects 17+ files beyond `models.py`. The plan now includes ALL files requiring modification: SSE handler validation set, router error messages, frontend config.js, preload adjacency logic, DEFAULT_LIMITS dict, and 7+ test files.

### Finding 2: Frontend model compatibility (CRITICAL — addressed in plan)

The plan originally claimed "frontend requires zero changes." This was false:
- `heat-map-view.tsx` hardcodes `ticker.sentiment.tiingo`, `ticker.sentiment.finnhub`, `ticker.sentiment.ourModel`
- TypeScript types use camelCase (`ourModel`) vs backend snake_case (`our_model`)
- `confidence` is required in frontend but optional in backend

Resolution: Frontend changes are now included in the plan. The heatmap must render aggregated data instead of per-source breakdowns. Note: the existing per-source access was already dead code (always empty), so the heatmap was never functional for sentiment — this fix makes it work for the first time.

### Finding 3: Dead code removal safe, tests need updating (MODERATE — addressed in plan)

`_get_tiingo_sentiment()`, `_get_finnhub_sentiment()`, `_compute_our_model_sentiment()` are only called within `get_sentiment_by_configuration()`. Safe to remove. 4 unit tests in `test_sentiment.py:81,98,116,130` test the adapter parameters and will need rewriting.
