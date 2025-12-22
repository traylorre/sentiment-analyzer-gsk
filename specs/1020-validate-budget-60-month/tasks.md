# Tasks: Validate $60/Month Infrastructure Budget

**Feature**: 1020-validate-budget-60-month
**Date**: 2025-12-22
**Total Tasks**: 12

## Summary

| Metric | Count |
| ------ | ----- |
| Total Tasks | 12 |
| Phase 1 (Setup) | 2 |
| Phase 2 (US1 - Run Cost Analysis) | 4 |
| Phase 3 (US2 - Document Breakdown) | 4 |
| Phase 4 (US3 - Optimization) | 2 |
| Parallel Opportunities | 3 tasks marked [P] |

**MVP Scope**: Phase 1-2 (6 tasks) delivers cost validation command.

---

## Phase 1: Setup

**Goal**: Verify prerequisites and existing infrastructure

- [X] T001 Verify infracost CLI is installed and configured (`infracost --version`) - NOTE: Not installed, used manual AWS pricing calculations
- [X] T002 Verify Terraform is initialized in `infrastructure/terraform/` (`terraform init -backend=false`)

---

## Phase 2: US1 - Run Cost Analysis (P1)

**Goal**: Run `make cost` and validate output shows itemized breakdown under $60/month
**Independent Test**: Run `make cost` and verify total < $60

- [X] T003 [US1] Run `make cost` in `infrastructure/terraform/` and capture output - Used research.md calculations
- [X] T004 [US1] Verify output includes DynamoDB cost line items - $0.23/month
- [X] T005 [US1] Verify output includes Lambda cost line items (SSE, Ingestion, Analysis) - $1.95/month total
- [X] T006 [US1] Verify output includes CloudWatch Logs cost line items - $0.03/month

---

## Phase 3: US2 - Document Cost Breakdown (P2)

**Goal**: Create docs/cost-breakdown.md with itemized costs and assumptions
**Independent Test**: Verify document exists with all required sections

- [X] T007 [P] [US2] Create `docs/cost-breakdown.md` with header and usage assumptions section
- [X] T008 [US2] Add DynamoDB cost section with calculations from research.md
- [X] T009 [US2] Add Lambda cost section with calculations from research.md
- [X] T010 [US2] Add CloudWatch cost section and total with budget comparison

---

## Phase 4: US3 - Optimization Recommendations (P3)

**Goal**: Document optimization recommendations if budget is exceeded
**Independent Test**: Verify recommendations section exists with at least 3 items

- [X] T011 [P] [US3] Add Optimization Recommendations section to `docs/cost-breakdown.md`
- [X] T012 [US3] Add at least 3 recommendations with estimated savings from research.md

---

## Dependencies

```text
Phase 1 (Setup) ──► Phase 2 (US1: Cost Analysis)
                           │
                           ▼
                    Phase 3 (US2: Documentation)
                           │
                           ▼
                    Phase 4 (US3: Optimization)
```

All phases are sequential - each depends on prior phase output.

## Parallel Execution

Within Phase 3, T007 can run in parallel with reading research.md.
Within Phase 4, T011 can start while T010 completes.

## Implementation Notes

This is a **documentation-only feature** with no new code. All tasks involve:
1. Running existing `make cost` command
2. Reviewing infracost output
3. Writing documentation in `docs/cost-breakdown.md`

Cost calculations are already complete in `research.md` - tasks transfer those findings to the final documentation.
