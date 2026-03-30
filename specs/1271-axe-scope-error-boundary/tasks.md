# Tasks: Scope axe-core to Error Boundary Element

**Input**: Design documents from `/specs/1271-axe-scope-error-boundary/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/accessibility-audit.md

**Tests**: Not explicitly requested — test tasks omitted.

**Organization**: Tasks grouped by user story for independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Add dependency and create file scaffolding

- [ ] T001 Add `@axe-core/playwright` `^4.10.0` to devDependencies in `e2e/playwright/package.json` and run `npm install`
- [ ] T002 [P] Create accessibility helper file at `e2e/playwright/helpers/accessibility.ts` with module scaffolding and imports for `AxeBuilder` from `@axe-core/playwright`
- [ ] T003 [P] Create accessibility test file at `e2e/playwright/tests/accessibility.spec.ts` with test suite scaffolding

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Dashboard markup change and helper implementation that all tests depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Add `data-testid="chaos-dashboard-content"` attribute to the main content container div in `src/dashboard/chaos.html` (the `<div class="container mx-auto p-4 max-w-7xl">` element)
- [ ] T005 Implement `waitForDashboardReady(page, scope)` in `e2e/playwright/helpers/accessibility.ts` — wait for at least 1 visible `button` or `[role=button]` element within the scope container (FR-008 readiness gate)
- [ ] T006 Implement `runScopedAccessibilityAudit(page, options?)` in `e2e/playwright/helpers/accessibility.ts` per contract: scope to `[data-testid="chaos-dashboard-content"]`, configure `withTags(['wcag2a', 'wcag2aa'])` (FR-011), call readiness gate, run audit, optionally scan `[role="dialog"]` modals (FR-009), merge results
- [ ] T007 Implement `assertNoAccessibilityViolations(result, options?)` in `e2e/playwright/helpers/accessibility.ts` per contract: fail on critical/serious violations, log moderate/minor as warnings (FR-005/FR-006)

**Checkpoint**: Helper module complete — audit can be invoked from tests

---

## Phase 3: User Story 1 — Scoped Accessibility Audit on Dashboard Content (Priority: P1) MVP

**Goal**: Accessibility audit scoped to main content container, excluding CDN elements

**Independent Test**: Run `npx playwright test accessibility` and verify violations are only from within `[data-testid="chaos-dashboard-content"]`

### Implementation for User Story 1

- [ ] T008 [US1] Implement test: "main content container has no critical/serious violations" in `e2e/playwright/tests/accessibility.spec.ts` — navigate to dashboard, call `runScopedAccessibilityAudit(page)` with default scope, call `assertNoAccessibilityViolations(result)`
- [ ] T009 [US1] Implement test: "audit fails when scope selector is missing" in `e2e/playwright/tests/accessibility.spec.ts` — verify that if `data-testid` is absent, the helper throws an error (not a silent pass)
- [ ] T010 [US1] Implement test: "audit fails on empty hydration" in `e2e/playwright/tests/accessibility.spec.ts` — mock a page where scope container exists but has no interactive elements, verify readiness gate throws
- [ ] T011 [US1] Implement test: "modal is scanned when visible" in `e2e/playwright/tests/accessibility.spec.ts` — open the Andon cord confirmation modal, run audit with `includeModals: true`, verify modal element violations are included in results

**Checkpoint**: US1 complete — main content audit works with readiness gate and modal scanning

---

## Phase 4: User Story 2 — Per-View Accessibility Audit (Priority: P2)

**Goal**: Optional scoping to individual visible views within the dashboard

**Independent Test**: Navigate to reports view, run view-scoped audit, verify only reports view elements appear in results

### Implementation for User Story 2

- [ ] T012 [US2] Extend `runScopedAccessibilityAudit` options to accept a `viewSelector` parameter in `e2e/playwright/helpers/accessibility.ts` — when provided, scope to `[data-testid="chaos-dashboard-content"] ${viewSelector}:visible` instead of the full container
- [ ] T013 [US2] Implement test: "reports view has no critical/serious violations when active" in `e2e/playwright/tests/accessibility.spec.ts` — navigate to reports view, run view-scoped audit with `viewSelector: '[x-show*="reports"]'`, assert no violations
- [ ] T014 [US2] Implement test: "hidden views are excluded from view-scoped audit" in `e2e/playwright/tests/accessibility.spec.ts` — navigate to experiments view, run view-scoped audit, verify no elements from the hidden reports view appear in results

**Checkpoint**: US2 complete — per-view scoping works independently

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and validation

- [ ] T015 [P] Update `e2e/playwright/package.json` `scripts` section to include an `accessibility` test command if not already present
- [ ] T016 Run quickstart.md validation: execute all commands in `specs/1271-axe-scope-error-boundary/quickstart.md` and verify expected output

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on T001 (dependency installed) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion (T004-T007)
- **User Story 2 (Phase 4)**: Depends on Phase 2 + T008 (base audit must work before per-view extension)
- **Polish (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 — no dependencies on US2
- **User Story 2 (P2)**: Can start after Phase 2 — extends US1's helper but tests independently

### Parallel Opportunities

- T002 and T003 can run in parallel (different files)
- T008-T011 within US1 are sequential (build on each other)
- T012-T014 within US2 are sequential (build on helper extension)
- T015 can run in parallel with T016

---

## Parallel Example: Phase 1

```bash
# Launch setup tasks together:
Task: "Add @axe-core/playwright to e2e/playwright/package.json"

# After T001, launch scaffolding in parallel:
Task: "Create accessibility helper in e2e/playwright/helpers/accessibility.ts"
Task: "Create accessibility test in e2e/playwright/tests/accessibility.spec.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T007)
3. Complete Phase 3: User Story 1 (T008-T011)
4. **STOP and VALIDATE**: Run `npx playwright test accessibility` and verify scoped audit works
5. Deploy if ready — per-view scoping can be added later

### Incremental Delivery

1. Setup + Foundational → Audit infrastructure ready
2. Add User Story 1 → Main content audit works → Deploy (MVP!)
3. Add User Story 2 → Per-view scoping works → Deploy
4. Each story adds value without breaking previous stories

---

## Notes

- Feature depends on Feature 1242 (chaos dashboard) being implemented first
- Feature 1245 (gate toggle) is a soft dependency for modal scanning tests
- If 1245 is not implemented, T011 should be skipped with a TODO note
- All file paths are relative to the `e2e/playwright/` directory

## Adversarial Review #3

**Reviewed**: 2026-03-29

- **Highest-risk task**: T004 — depends on Feature 1242 creating chaos.html. If 1242 is not implemented, T004 is blocked and all downstream tasks fail.
- **Most likely rework**: T006 — complex helper concentrates scope logic, readiness gate, modal scanning, and result merging in one function. Most likely to need iteration.
- **CRITICAL/HIGH remaining**: 0
- **READY FOR IMPLEMENTATION** (conditional on Feature 1242 being implemented first)
