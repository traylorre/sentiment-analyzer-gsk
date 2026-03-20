# Implementation Plan: Real Sentiment Pipeline

**Branch**: `1227-real-sentiment-pipeline` | **Date**: 2026-03-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1227-real-sentiment-pipeline/spec.md`

## Summary

The sentiment pipeline has two stages: ingestion (fetches articles, publishes to SNS) and analysis (runs DistilBERT inference, writes to timeseries table). The ingestion Lambda has been silently crashing since ~2025-12-22 due to a missing `aws_lambda_powertools` dependency in the ZIP package. The analysis Lambda (Docker-based) is functional but starved of input. The `/sentiment/history` endpoint was never wired to read from the existing timeseries table — it still generates synthetic data. This plan fixes the packaging bug, validates the full pipeline end-to-end (including the ML model artifact and API keys), wires the endpoint, and adds observability.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: aws_lambda_powertools 3.7.0 (missing from ingestion ZIP), boto3 (existing), pydantic (existing)
**Storage**: DynamoDB `{env}-sentiment-timeseries` table (existing, 678 records, PK=`{ticker}#{resolution}`, SK=ISO timestamp)
**Testing**: pytest 8.0+ with moto (unit), E2E via trace inspection diagnostic scripts
**Target Platform**: AWS Lambda (ZIP package for ingestion, Docker for dashboard)
**Project Type**: Single project (Python monorepo with multiple Lambda entry points)
**Performance Goals**: P90 < 500ms for sentiment history endpoint (constitution requirement)
**Constraints**: Finnhub API rate limit 60 calls/min, ingestion must complete within 5-min cycle for 22 tickers
**Scale/Scope**: ~4 files modified, 1 line added to deploy.yml, 1 endpoint rewritten, observability instrumentation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Implementation accompaniment (unit tests) | PASS | New endpoint query logic and cache layer get unit tests |
| GPG-signed commits | PASS | Standard workflow |
| No pipeline bypass | PASS | Standard PR flow |
| External dependency mocking | PASS | Finnhub/Tiingo mocked in unit tests, real DynamoDB in E2E |
| Deterministic time handling | PASS | No time-dependent test logic — queries use fixed date ranges |
| Pre-push checklist | PASS | `make validate` + `make test-local` before push |

No constitution violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/1227-real-sentiment-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code

```text
.github/workflows/
└── deploy.yml                          # MODIFIED: add aws-lambda-powertools to ingestion pip install

src/lambdas/dashboard/
└── ohlc.py                             # MODIFIED: replace synthetic generator (lines 920-1093) with DynamoDB query

src/lambdas/shared/cache/
└── sentiment_cache.py                  # NEW: sentiment history cache (mirrors ohlc_cache.py pattern)

tests/unit/
└── test_sentiment_history.py           # NEW: unit tests for DynamoDB query + cache logic
```

**Structure Decision**: Minimal changes to existing structure. The packaging fix is one line in deploy.yml. The endpoint rewrite replaces ~70 lines of synthetic generator with DynamoDB query logic. New cache module follows the established `shared/cache/` pattern.
