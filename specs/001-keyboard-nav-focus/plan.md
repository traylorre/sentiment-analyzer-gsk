# Implementation Plan: Fix Keyboard Navigation Test to Use .focus()

**Branch**: `001-keyboard-nav-focus` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-keyboard-nav-focus/spec.md`

## Summary

Replace Tab-key-based keyboard navigation tests in the chaos dashboard Playwright suite with programmatic `.focus()` calls. Add focus indicator visibility assertions, modal focus trap verification, Chart.js canvas focus-through testing, and Alpine.js view transition focus safety checks. All tests must produce identical results in headed and headless Chromium.

## Technical Context

**Language/Version**: TypeScript (Playwright tests)
**Primary Dependencies**: `@playwright/test ^1.40.0` (existing)
**Storage**: N/A
**Testing**: Playwright Test (`npx playwright test`)
**Target Platform**: Chromium headless (CI), Chromium headed (local dev)
**Project Type**: Test infrastructure addition
**Performance Goals**: Full keyboard navigation suite completes in under 10 seconds (SC-003)
**Constraints**: Tab key banned for navigation; single-Tab assertions only (FR-007). Headed/headless parity required (FR-006).
**Scale/Scope**: ~20 interactive elements across 6 dashboard views, 1 modal (Andon cord confirmation), Chart.js canvas elements

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.6 (No Quick Fixes) | PASS | Full speckit workflow in progress |
| Amendment 1.7 (Target Repo Independence) | PASS | Tests are in template's e2e/playwright dir |
| Amendment 1.12 (Mandatory Speckit Workflow) | PASS | Following specify->plan->tasks->implement |
| Amendment 1.14 (Validator Usage) | PASS | Will run validators before commit |
| Amendment 1.15 (No Fallback Config) | PASS | BASE_URL already has no fallback (playwright.config.ts) |

## Project Structure

### Documentation (this feature)

```text
specs/001-keyboard-nav-focus/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code (repository root)

```text
e2e/playwright/
├── tests/
│   └── keyboard-nav.spec.ts     # New: keyboard navigation tests
└── helpers/
    └── keyboard.ts              # New: focus management helpers
```

**Structure Decision**: Extends existing Playwright test infrastructure. New test file + helper alongside existing smoke.spec.ts, api.spec.ts, and utils.ts helper.

## Phase 0: Research

See [research.md](research.md) for design decisions.

Key decisions:
1. Use `.focus()` for all focus placement (no Tab navigation)
2. Use `toBeFocused()` for focus assertions
3. Use computed style checks (`outline`, `box-shadow`) for focus indicator visibility
4. Use HTML5 `<dialog>` with `showModal()` API to trigger modal open/close for focus trap tests (native focus trapping)
5. Single-Tab assertion pattern: `.focus()` on element A, `Tab` once, `toBeFocused()` on element B

## Phase 1: Design

### Helper Module (keyboard.ts)

Provides reusable focus management utilities:

- `focusAndAssert(locator)` — call `.focus()` on a locator and assert it received focus
- `assertFocusIndicatorVisible(locator)` — check computed CSS for visible outline/ring/shadow
- `assertFocusOrder(page, selectorA, selectorB)` — focus A, Tab once, assert B has focus
- `assertNotFocusTrapped(page, selector)` — focus element, Tab once, assert focus moved away
- `assertModalFocusTrap(page, openTrigger, modalSelector, closeTrigger)` — open modal, verify focus enters modal, close modal, verify focus returns to trigger

### Test File (keyboard-nav.spec.ts)

Test groups mapped to functional requirements:

| Test Group | FRs Covered | Description |
|------------|-------------|-------------|
| Programmatic focus | FR-001, FR-002, FR-006 | Each interactive element receives focus via `.focus()` and passes `toBeFocused()` |
| Keyboard interaction | FR-003 | Focused elements respond to Enter/Space/Escape |
| Focus indicators | FR-004 | Focused elements have visible CSS focus treatment |
| Canvas focus-through | FR-005, FR-010 | Chart.js canvas has `tabindex="-1"` or focus passes through |
| Tab ban compliance | FR-007 | Only single-Tab assertions used; no chained Tab presses |
| View transition safety | FR-008 | After `x-show` view change, focus is not on a hidden element |
| Modal focus trap | FR-009 | Andon cord modal traps focus on open, returns on close |

### No Database / API Changes

This feature is test-infrastructure-only. No changes to the chaos dashboard source code, Terraform configuration, or API endpoints.

## Phase 2: Implementation Approach

1. **Create `helpers/keyboard.ts`** with focus management utilities
2. **Create `tests/keyboard-nav.spec.ts`** with test groups ordered by priority (P1 first)
3. **Verify headed/headless parity** by running tests in both modes locally

## Dependencies

- Existing Playwright infrastructure (`e2e/playwright/`)
- Chaos dashboard running at `BASE_URL` (same as smoke.spec.ts and api.spec.ts)
- No new npm packages required — all APIs are built into `@playwright/test`

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `.focus()` fails on DaisyUI components that use Shadow DOM | Low | Medium | DaisyUI uses plain CSS classes, not Web Components — no Shadow DOM |
| Alpine.js re-render during test causes focus loss | Medium | Low | Use `page.waitForFunction()` to wait for Alpine hydration before focus assertions |
| Chart.js canvas missing `tabindex="-1"` | Medium | Medium | FR-010 tests will catch this; fix in dashboard markup if needed |
| Modal focus trap not implemented in DaisyUI | Low | High | DaisyUI dialog component handles focus trap natively; verify in research phase |

## Adversarial Review #2

**Reviewed**: 2026-03-29 | **Focus**: Spec drift from clarifications, cross-artifact consistency

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | Plan referenced "DaisyUI modal-toggle" but should be `<dialog>` with `showModal()` | Fixed: plan line 69 updated to `<dialog>` with `showModal()` |
| HIGH | Spec said WCAG keyboard audit "covered by" Feature 1271 — misleading (static vs behavioral) | Fixed: spec updated to clarify 1271 is static analysis, this is behavioral testing |
| MEDIUM | Arrow key navigation for ARIA tablist not covered by any FR | Accepted: arrow key patterns are implementation-specific; can be added if dashboard uses `role="tablist"` |
| MEDIUM | Plan says "no dashboard source changes" but FR-010 may require `tabindex="-1"` on canvas | Acknowledged in risks table row 3; fix would be a dashboard markup change |
| MEDIUM | Plan "~20 interactive elements" is unverified estimate | Accepted: qualified as estimate pending 1242/1245 |
| MEDIUM | FR-008 view transition has no implementation guidance in plan | Accepted: view transitions triggered by clicking tab buttons (Alpine.js x-on:click) |
| LOW | `assertNotFocusTrapped` helper name confusing | Accepted: minor naming issue for implementation |

**Gate**: 0 CRITICAL, 0 HIGH remaining.
