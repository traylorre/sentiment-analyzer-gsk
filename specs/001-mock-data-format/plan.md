# Implementation Plan: Fix Mock OHLC/Sentiment Data Format

**Branch**: `001-mock-data-format` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-mock-data-format/spec.md`

## Summary

Align mock OHLC and sentiment data in Playwright E2E test fixtures with the actual API response contracts defined by the backend Pydantic models. The mock data in `frontend/tests/e2e/helpers/mock-api-data.ts` is missing fields, uses incorrect date formats, and lacks null-value variants for optional fields, causing tests to pass against a shape that diverges from production.

## Technical Context

**Language/Version**: TypeScript (mock data fixtures), Python 3.13 (backend Pydantic models as source of truth)
**Primary Dependencies**: `@playwright/test` (existing), Pydantic v2 (backend reference models)
**Storage**: N/A
**Testing**: Playwright Test (`npx playwright test`)
**Target Platform**: Chromium headless (CI), Chromium headed (local dev)
**Project Type**: Test data correction
**Performance Goals**: N/A (static fixture data, no runtime cost)
**Constraints**: Mock shape must exactly match OHLCResponse and SentimentHistoryResponse Pydantic models
**Scale/Scope**: 2 mock response objects (OHLC, sentiment), ~4 candle entries, ~4 sentiment entries

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.6 (No Quick Fixes) | PASS | Full speckit workflow in progress |
| Amendment 1.7 (Target Repo Independence) | PASS | Mock data is in target repo's test fixtures |
| Amendment 1.12 (Mandatory Speckit Workflow) | PASS | Following specify->plan->tasks->implement |
| Amendment 1.14 (Validator Usage) | PASS | Will run validators before commit |
| Amendment 1.15 (No Fallback Config) | N/A | No configuration fallbacks in test data |

## Project Structure

### Documentation (this feature)

```text
specs/001-mock-data-format/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (target repository)

```text
# Files modified:
frontend/tests/e2e/helpers/mock-api-data.ts    # Updated: OHLC + sentiment mock objects

# Source of truth (read-only reference):
src/lambdas/shared/models/ohlc.py              # OHLCResponse, PriceCandle
src/lambdas/shared/models/sentiment_history.py  # SentimentHistoryResponse, SentimentPoint
frontend/src/types/chart.ts                     # TypeScript mirror types
```

**Structure Decision**: Single file modification in existing test helper. No new files, no new directories. The mock data objects are updated in place to match the backend contract.

## Cross-Repo Workflow

This spec is authored in the template repo (`terraform-gsk-template`) for methodology tracking, but ALL code changes target the target repo (`sentiment-analyzer-gsk`). Implementation workflow:

1. Spec/plan/tasks authored here in template repo
2. Implementation branch created in target repo: `git checkout -b fix/mock-data-format`
3. Code changes applied to `frontend/tests/e2e/helpers/mock-api-data.ts` in target repo
4. Validation run in target repo: `cd frontend && npx playwright test`
5. PR created in target repo referencing this spec

## Dependencies

- **None** — mock data fix is independent of dashboard implementation status

## Adversarial Review #2

**Reviewed**: 2026-03-29 | **Focus**: Spec drift from clarifications, cross-artifact consistency

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | Cross-repo implementation workflow undocumented | Fixed: Cross-Repo Workflow section added to plan |
| HIGH | `resolution_fallback` type conflict — data-model says boolean, clarification Q4 implies nullable | Verified: data-model is correct (boolean). Q4 language was imprecise about `fallback_message` (which IS nullable). No change needed. |
| MEDIUM | No contract artifact for mock data TypeScript interface | Accepted: data-model serves as sufficient reference; TypeScript types in target repo are authoritative |
| MEDIUM | SentimentHistoryResponse.source typed as string in data-model but enum in FR-008 | Accepted: should be enum; implementation will use correct type |
| MEDIUM | Q4 self-contradictory about nullable boolean | Clarification imprecise but data-model correct |
| LOW | `time_range` lacks enum constraint | Accepted: derived from backend model at implementation time per FR-010 |
| LOW | `cache_expires_at` format not in FR-006 | Accepted: covered in research Decision 6 and data-model |

**Gate**: 0 CRITICAL, 0 HIGH remaining.
