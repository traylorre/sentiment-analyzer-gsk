# Target Repo Deferred/Future/Debt Status

**Generated**: 2025-12-11
**Last Updated**: 2025-12-11 (Post 086/087 merge)
**Source**: Analysis of docs/FUTURE_WORK.md, docs/TECH_DEBT_REGISTRY.md, docs/TEST-DEBT.md, docs/TEST_LOG_ASSERTIONS_TODO.md, docs/DASHBOARD_TESTING_BACKLOG.md, GitHub Issues

## Summary

| Category | Items | Status |
|----------|-------|--------|
| **Tech Debt (TECH_DEBT_REGISTRY.md)** | 21 items | 13 resolved, 8 deferred |
| **Test Debt (TEST-DEBT.md)** | 7 items | **6 resolved**, 1 deferred |
| **Log Assertions (TEST_LOG_ASSERTIONS_TODO.md)** | 21 error patterns | **68 assertions added** (086/087) |
| **Dashboard Testing Backlog** | 6 categories | Backlogged (post-production) |
| **Open GitHub Issues** | 7 issues | Deferred cloud portability + testing |
| **Future Work** | 1 item | Project name parameterization |

---

## Critical/High Priority Items

| ID | Item | Status | Location |
|----|------|--------|----------|
| TD-005 | Dashboard handler coverage (71% → **88%**) | **RESOLVED** | PR #340 (087) |
| TD-006 | Sentiment model S3 loading (51% → **59%**) | **PARTIAL** | PR #340 (087) |
| TD-007 | ERROR log assertion validation | **RESOLVED** | PR #339 (086) |
| TD-001 | Observability tests skip on missing metrics | **RESOLVED** | PR #112 |
| TD-021 | Lambda FIS chaos testing | **BLOCKED** | Waiting for terraform-provider-aws#41208 |

---

## Cloud Portability (Deferred)

All deferred to future - 6-14 weeks total effort if pursued:

| Issue | Item | Effort |
|-------|------|--------|
| #129 | TD-016: Repository pattern (database) | 2-3 weeks |
| #130 | TD-017: Metrics interface abstraction | 1-2 weeks |
| #131 | TD-018: Secrets management abstraction | 1 week |
| #132 | TD-019: Event source abstraction | 2-3 weeks |
| #133 | TD-020: IaC abstraction (Pulumi) | 4-6 weeks |

Current portability score: **25/100** (heavily AWS-coupled)

---

## Testing Debt

**Test Debt Burndown (Updated 2025-12-11):**
- **Resolved**: TD-001, TD-002, TD-003, TD-004, TD-005, TD-007
- **Partial**: TD-006 (S3 model loading 51% → 59%, still below 85% target)
- **Blocked**: TD-021 (Lambda FIS chaos testing - upstream provider issue)

**Log Assertions (COMPLETED via 086/087):**
- ~~21 unique error patterns need explicit `caplog` assertions~~
- **68 `assert_error_logged()` calls** now in test suite
- Pre-commit hook validates ERROR logs on push
- Scripts: `scripts/check-error-log-assertions.sh`

**Dashboard NFR Testing Backlog (Deferred):**
- Performance (latency, memory, cold start)
- Resilience (DynamoDB failures, SSE streams)
- Load (concurrent requests, large datasets)
- Security (timing attacks, input validation)
- Chaos testing (quarterly)

---

## Future Work (Deferred)

**Project Name Parameterization:**
- Current: `*-sentiment-*` hardcoded throughout
- Proposed: `local.project_slug` in Terraform
- Blocked by: `iam_resource_alignment.py` validator can't resolve Terraform locals
- Impact: Low (pattern matches correctly, no mismatch exists)

---

# Burndown Strategy Analysis

## Evaluation Criteria

### Drift Risk Assessment

**Drift Risk** = likelihood that deferred work becomes harder/more expensive over time due to:
1. Codebase evolution making changes more complex
2. Dependencies becoming outdated
3. Knowledge loss as context fades
4. Accumulating technical interest

### Ordering Benefit Assessment

**Ordering Benefit** = value gained by doing items in a specific sequence:
1. Unlocks other work (dependency)
2. Reduces future effort (foundation)
3. Improves velocity for subsequent items
4. Provides immediate feedback/validation

---

## Item-by-Item Analysis

### High Drift Risk Items (UPDATED 2025-12-11)

| Item | Drift Risk | Status |
|------|------------|--------|
| **TD-005: Dashboard coverage** | ~~HIGH~~ **RESOLVED** | 71% → 88% via PR #340 |
| **TD-006: S3 model loading** | MEDIUM | 51% → 59% via PR #340, still needs work |
| **Log Assertions TODO** | ~~MEDIUM~~ **RESOLVED** | 68 assertions added via 086/087 |
| **TD-001: Observability tests** | ~~MEDIUM~~ **RESOLVED** | PR #112 merged |

### Low Drift Risk Items

| Item | Drift Risk | Reason |
|------|------------|--------|
| Cloud portability (TD-016-020) | LOW | AWS-specific code is stable; no immediate multi-cloud pressure |
| TD-021: Lambda FIS chaos | LOW | Blocked on upstream; no drift until unblocked |
| Project name parameterization | LOW | Pattern works; cosmetic improvement |
| Dashboard NFR backlog | LOW | NFRs are additive; don't block functional development |

### Ordering Dependencies

```
Log Assertions ─────────────────────────────────────────┐
                                                        │
TD-005 (Dashboard coverage) ────┬──────────────────────▶│ NFR Testing Backlog
                                │                       │ (needs solid functional
TD-006 (S3 model loading) ──────┘                       │  coverage first)
                                                        │
TD-001 (Observability) ─────────────────────────────────┘

Cloud Portability (TD-016 → TD-017 → TD-018 → TD-019 → TD-020)
     Repository → Metrics → Secrets → Events → IaC
     (each layer builds on previous abstraction)
```

---

## Top 3 Burndown Approaches

### Approach 1: "Test Foundation First" (Recommended)

**Strategy**: Eliminate testing debt before it compounds, enabling confident future changes.

**Sequence**:
1. **Log Assertions TODO** (2-3 hours) - Quick win, stops drift
2. **TD-005: Dashboard coverage** (1-2 days) - Highest drift risk
3. **TD-006: S3 model loading** (1 day) - Second highest drift risk
4. **TD-001: Observability** (merge PR #112) - Already done

**Rationale**:
- Test debt compounds fastest (every feature adds untested paths)
- Log assertions are prerequisite for reliable error detection
- Coverage improvements enable NFR testing later
- Quick wins build momentum

**Effort**: ~1 week
**Drift Reduction**: HIGH (stops compounding test debt)
**Ordering Benefit**: HIGH (enables NFR backlog, improves CI feedback)

**Success Metrics**:
- Dashboard coverage ≥85%
- S3 loading coverage ≥85%
- Zero unexpected ERROR logs in test output
- All caplog assertions in place

---

### Approach 2: "Horizontal Slice - Observability Complete"

**Strategy**: Make the system fully observable before adding features.

**Sequence**:
1. **TD-001: Observability tests** (merge PR #112)
2. **Log Assertions TODO** (2-3 hours)
3. **Dashboard NFR: Logging tests** (from backlog)
4. **Dashboard NFR: Metrics tests** (from backlog)

**Rationale**:
- Observability is foundational for production confidence
- Log assertions + observability tests = complete error visibility
- Metrics tests validate CloudWatch integration
- Creates feedback loop for all future work

**Effort**: ~3-4 days
**Drift Reduction**: MEDIUM (observability is stable)
**Ordering Benefit**: HIGH (improves debugging for all future work)

**Success Metrics**:
- Zero pytest.skip in observability tests
- All 21 error patterns have caplog assertions
- Structured logging validated
- CloudWatch metrics emission verified

---

### Approach 3: "Risk-Based Prioritization"

**Strategy**: Address highest-impact items regardless of category.

**Sequence**:
1. **TD-005: Dashboard coverage** - Highest drift risk, actively developed
2. **Log Assertions TODO** - Quick win, foundational
3. **TD-006: S3 model loading** - ML paths are critical
4. **Dashboard NFR: Resilience tests** - DynamoDB failure handling

**Rationale**:
- Dashboard is user-facing; failures are visible
- S3 model loading is on critical path for analysis
- Resilience tests catch production issues early
- Ignores low-value portability work

**Effort**: ~1 week
**Drift Reduction**: HIGH (targets highest-drift items)
**Ordering Benefit**: MEDIUM (mixed dependencies)

**Success Metrics**:
- Dashboard coverage ≥85%
- S3 loading coverage ≥85%
- DynamoDB failure paths tested
- Error logging validated

---

## Recommendation

**Approach 1: "Test Foundation First"** is the best choice because:

1. **Highest ROI**: Test debt compounds; every day delayed = more work later
2. **Enables future work**: NFR backlog requires solid functional coverage
3. **Quick wins**: Log assertions can be done in one session
4. **Measurable progress**: Coverage metrics provide clear feedback
5. **Low risk**: No production changes, pure test improvements

**What to defer**:
- Cloud portability (TD-016-020): No business driver, stable as-is
- Lambda FIS chaos (TD-021): Blocked upstream, can't act
- Project name parameterization: Cosmetic, working correctly
- Dashboard NFR backlog: Phase 2 after coverage improves

---

## Completed Features (086/087)

**Feature 086**: `086-test-debt-burndown` (PR #339, merged 2025-12-11)
- Pre-commit hook for ERROR log assertion validation
- Script: `scripts/check-error-log-assertions.sh`
- Advisory mode (warns but doesn't block push)

**Feature 087**: `087-test-coverage-completion` (PR #340, merged 2025-12-11)
- Dashboard handler coverage: 71% → 88% ✅
- Sentiment model S3 tests: 51% → 59% (partial)
- Log assertions: 42 → 68 (+26 assertions)
- Tests: 6 files updated, 3 new S3 model tests

**Success Criteria Results**:
- SC-001: ✅ 68 `assert_error_logged()` calls in test suite
- SC-002: ✅ Dashboard handler coverage 88% (target: 85%)
- SC-003: ❌ Sentiment model coverage 59% (target: 85% - still needs work)
- SC-004: ✅ All 1992 tests pass

---

## Remaining Work

### TD-006: Sentiment Model Coverage (Deferred)
**Current**: 59%
**Target**: 85%
**Gap**: S3 download paths, error handling edge cases
**Effort**: ~2-3 hours to add integration tests

### TD-021: Lambda FIS Chaos Testing (Blocked)
**Status**: Waiting for terraform-provider-aws#41208
**No action possible until upstream fix**

### Cloud Portability (Low Priority)
TD-016 through TD-020 remain deferred - no business driver
