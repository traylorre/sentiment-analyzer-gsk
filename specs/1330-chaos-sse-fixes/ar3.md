# AR#3: Final Readiness Check

## Cross-Artifact Consistency

### AR3-001: Task coverage matches spec requirements
| Spec Requirement | Task(s) | Status |
|-----------------|---------|--------|
| FR-001: Delete chaos-sse-recovery.spec.ts | T1 | COVERED |
| FR-002: Delete chaos-sse-lifecycle.spec.ts | T2 | COVERED |
| FR-003: Fix mock auth response format | T3 | COVERED |
| FR-004: Fix/document a11y violations | T5 | COVERED |
| FR-005: Fix error boundary degradation | T6 | COVERED |
| NFR-001: No production code (unless a11y) | T5 may modify components | COVERED |
| NFR-002: Deletion documented | spec.md, plan.md | COVERED |

**Status**: All requirements have corresponding tasks.

### AR3-002: Task dependency ordering is correct
- T1, T2 (deletions) have no dependencies — correct
- T3 (mock fix) has no dependencies — correct
- T4 (validation) depends on T3 — correct
- T5, T6 (investigations) have no dependencies — correct
- T7 (full validation) depends on T1, T2, T4, T5, T6 — correct

**Status**: Dependency graph is acyclic and complete.

### AR3-003: T3 edit target uniqueness
The auth mock in `mockTickerDataApis()` is on lines 182-194 of `mock-api-data.ts`.
The edit replaces the body of the route handler. The string `access_token` appears
only once in this file (in the auth mock). The edit target is unique.

**Status**: Verified.

### AR3-004: T3 doesn't break the cleanup function
`mockTickerDataApis()` returns a cleanup function that calls `page.unroute('**/api/v2/auth/anonymous')`.
The route pattern doesn't change — only the response body changes. Cleanup is unaffected.

**Status**: Verified.

### AR3-005: Deleted test IDs vs remaining chaos tests
After deleting T032-T040 (SSE tests), the remaining chaos test IDs are:
- T013, T014 (cached-data)
- T022, T023, T024 (error-boundary)
- T025, T026, T027 (accessibility)
- Plus: chaos-scenarios (T001-T005), chaos-degradation, chaos-cross-browser

No test ID conflicts or gaps that would cause confusion.

**Status**: No issues.

### AR3-006: T5 and T6 are investigation tasks — could they fail?
T5 and T6 require running tests locally to identify specific failures. The tasks
provide decision trees for different failure modes. If the investigation reveals an
unexpected root cause, the tasks have enough context to adapt.

**Risk**: If axe finds a complex a11y violation that requires significant component
refactoring, T5 could expand beyond the estimated 15 minutes.

**Mitigation**: The spec's decision framework (fix real violations, exclude scanner
noise) bounds the scope. Component-level a11y fixes are typically small (add ARIA
attribute, adjust color).

**Status**: Acceptable risk.

### AR3-007: Feature 1329 conflict
Feature 1329 (chart-auth-mock) plans to create `mockAnonymousAuth()` with the SAME
wrong response format. If 1329 is implemented before 1330, its `mockAnonymousAuth()`
will have the wrong format. If 1330 is implemented first, the clarify.md documents
the issue for 1329.

**Resolution**: The tasks note this in T3's cross-feature comment. The `mockTickerDataApis()`
in mock-api-data.ts does NOT call a shared auth helper — it has its own inline mock.
So fixing T3 is independent of 1329.

**Status**: No blocking conflict. Cross-feature note documented.

### AR3-008: Deletion permanence
Deleting test files is permanent (git tracks them, but they leave the working tree).
The tests were written for Feature 1265 which specified SSE chaos testing. Deleting
them means 1265's SSE test coverage goes from "broken E2E" to "zero" rather than
"unit tests."

The spec acknowledges this (R1) and explicitly defers unit test creation to a
follow-up feature. This is acceptable because broken tests provide zero value
and negative value (CI time waste, false sense of coverage).

**Status**: Accepted. Follow-up feature needed for SSE unit tests.

## Implementation Readiness Checklist

| Criterion | Status |
|-----------|--------|
| All spec requirements have tasks | YES |
| All tasks have clear actions | YES |
| All tasks have verification commands | YES |
| Dependency graph is valid | YES |
| Edit targets are unique/unambiguous | YES |
| No blocking cross-feature conflicts | YES |
| Risk mitigations documented | YES |
| Estimated effort is realistic | YES |

## Disposition: READY FOR IMPLEMENTATION.

Zero blocking issues. Implementation can proceed with T1+T2+T3 in parallel (all
independent), then T4+T5+T6 in parallel, then T7.
