# Tasks: SPEC.md Full Documentation Audit & Cleanup

**Feature**: 001-spec-doc-cleanup
**Branch**: `001-spec-doc-cleanup`
**Generated**: 2026-01-31
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 14 |
| User Stories | 3 (US1: Developer, US2: Operations, US3: Auditor) |
| Phases | 5 |
| Parallel Opportunities | 3 tasks |
| Estimated Commits | 7 atomic commits |

---

## Phase 1: Setup & Discovery

**Goal**: Prepare working environment and confirm discovery findings before making changes.

- [ ] T001 Run full grep scan to confirm Twitter-related content count in SPEC.md
- [ ] T002 Verify Lambda inventory matches research findings (6 actual vs 7 documented)
- [ ] T003 Create backup reference of current SPEC.md state via git tag `pre-cleanup-001`

---

## Phase 2: Foundational - Full Audit Report (FR-010)

**Goal**: Complete the full audit comparing SPEC.md against codebase before any edits.

- [ ] T004 Generate audit report comparing ALL SPEC.md documented components against Terraform/src in specs/001-spec-doc-cleanup/audit-report.md

---

## Phase 3: User Story 1 - Developer Reads Accurate Documentation (P1)

**Story Goal**: Remove all Twitter references so developers see only Tiingo/Finnhub as data sources.

**Independent Test**: `grep -ci "twitter\|tweets" SPEC.md` returns 0

### Tasks

- [ ] T005 [US1] Remove Twitter API configuration section (lines 45-70) from SPEC.md
- [ ] T006 [US1] Remove tweepy from dependencies list (line 40) in SPEC.md
- [ ] T007 [P] [US1] Remove Twitter from source type schemas (lines 140, 146, 195) in SPEC.md
- [ ] T008 [US1] Update architecture description (line 16) to remove "Twitter-style" reference in SPEC.md
- [ ] T009 [US1] Remove QUOTA_EXHAUSTED Twitter error state (line 178) from SPEC.md

**Verification**: After Phase 3, run `grep -ci "twitter\|tweets" SPEC.md` - must return 0

---

## Phase 4: User Story 2 - Operations Team Understands Actual Infrastructure (P1)

**Story Goal**: Remove phantom Lambda documentation so ops only sees real infrastructure.

**Independent Test**: Count of Lambdas in SPEC.md equals count in src/lambdas/ (6)

### Tasks

- [ ] T010 [US2] Remove Quota Reset Lambda section (lines 245-256) from SPEC.md
- [ ] T011 [P] [US2] Remove quota-reset-lambda-dlq references and Twitter-tier concurrency (lines 240-243) from SPEC.md
- [ ] T012 [US2] Remove Twitter-related CloudWatch metrics and alarms from SPEC.md

**Verification**: After Phase 4, run `grep -c "Quota Reset\|quota_reset" SPEC.md` - must return 0

---

## Phase 5: User Story 3 - Auditor Verifies Documentation Accuracy (P2)

**Story Goal**: Remove/update cost estimates so auditors can verify costs against actual APIs.

**Independent Test**: Cost section references only Tiingo/Finnhub, no Twitter pricing

### Tasks

- [ ] T013 [P] [US3] Remove or revise Twitter-based cost estimates (lines 270-332) in SPEC.md - replace with Tiingo/Finnhub actual costs or remove entirely

---

## Phase 6: Polish & Verification

**Goal**: Final verification and PR creation.

- [ ] T014 Run final verification: all grep checks pass, Lambda count matches, no broken internal links in SPEC.md
- [ ] T015 Create PR with atomic commits and enable auto-merge

---

## Dependencies

```
T001 → T002 → T003 → T004 (Setup must complete first)
T004 → T005-T009 (Audit before US1 edits)
T005-T009 → T010-T012 (US1 before US2, same file)
T010-T012 → T013 (US2 before US3, same file)
T013 → T014 → T015 (Polish after all stories)
```

**Note**: Tasks within a phase are sequential (same file edits), but verification tasks (T001-T003) can be parallelized.

---

## Parallel Execution Opportunities

| Tasks | Reason |
|-------|--------|
| T007 | Schema changes are isolated from config changes |
| T011 | DLQ references can be removed independently |
| T013 | Cost section is isolated from Lambda section |

---

## Verification Checklist (per FR-007)

After all tasks complete, verify:

```bash
# All must return 0
grep -ci "twitter" SPEC.md
grep -ci "tweets" SPEC.md
grep -ci "monthly_tweets" SPEC.md
grep -ci "quota_reset" SPEC.md
grep -ci "twitter_api_tier" SPEC.md
grep -ci "tweepy" SPEC.md

# Must equal 6 (actual Lambdas)
grep -c "Lambda:" SPEC.md | grep -E "^6$"
```

---

## Implementation Strategy

### MVP Scope (User Story 1 only)

If time-constrained, complete only US1 (T005-T009). This removes Twitter references and provides the highest value for developer onboarding.

### Incremental Delivery

1. **Commit 1**: Remove Twitter API configuration (T005, T006)
2. **Commit 2**: Remove Twitter from schemas (T007)
3. **Commit 3**: Update architecture + remove error state (T008, T009)
4. **Commit 4**: Remove Quota Reset Lambda (T010)
5. **Commit 5**: Remove Twitter tier concurrency + DLQ (T011, T012)
6. **Commit 6**: Update cost estimates (T013)
7. **Commit 7**: Final verification (T014)

Each commit should pass its verification check before proceeding.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Accidental removal of valid content | Atomic commits; git tag backup (T003) |
| Missed references | Post-commit grep verification |
| Broken internal links | Manual markdown link check in T014 |
| Cost section becomes empty | Either add Tiingo/Finnhub costs or remove section with note |
