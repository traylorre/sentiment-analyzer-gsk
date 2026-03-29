# Implementation Plan: Scope axe-core to Error Boundary Element

**Branch**: `1271-axe-scope-error-boundary` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1271-axe-scope-error-boundary/spec.md`

## Summary

Add scoped axe-core accessibility auditing to the chaos dashboard Playwright tests. The audit targets the main content container (`data-testid="chaos-dashboard-content"`) to avoid false positives from CDN-injected elements. Includes hydration readiness gate, modal scanning, WCAG 2.1 AA rule filtering, and pinned dependency version.

## Technical Context

**Language/Version**: TypeScript (Playwright tests), HTML (dashboard markup)
**Primary Dependencies**: `@playwright/test ^1.40.0` (existing), `@axe-core/playwright ^4.10.0` (new, pinned to major.minor per FR-010)
**Storage**: N/A
**Testing**: Playwright Test (`npx playwright test`)
**Target Platform**: Chromium headless (CI), Chromium headed (local dev)
**Project Type**: Test infrastructure addition
**Performance Goals**: Accessibility audit adds <5 seconds to suite execution
**Constraints**: Must not introduce false positives from CDN elements, must detect real violations
**Scale/Scope**: 5 dashboard views (experiments, reports, detail, diff, trends), ~20 interactive elements, 1 modal

## Dependencies

- **Hard**: Feature 1242 (chaos-report-viewer) — creates chaos.html and all dashboard views
- **Soft**: Feature 1245 (gate-toggle) — adds Andon cord confirmation modal

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.6 (No Quick Fixes) | PASS | Full speckit workflow in progress |
| Amendment 1.7 (Target Repo Independence) | PASS | Tests are in template's e2e/playwright dir |
| Amendment 1.12 (Mandatory Speckit Workflow) | PASS | Following specify→plan→tasks→implement |
| Amendment 1.14 (Validator Usage) | PASS | Will run validators before commit |
| Amendment 1.15 (No Fallback Config) | N/A | No configuration fallbacks in test code |

## Project Structure

### Documentation (this feature)

```text
specs/1271-axe-scope-error-boundary/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart
├── checklists/
│   └── requirements.md  # Quality checklist
└── contracts/
    └── accessibility-audit.md  # Audit result contract
```

### Source Code (repository root)

```text
e2e/playwright/
├── package.json                  # Add @axe-core/playwright dependency
├── tests/
│   └── accessibility.spec.ts     # New: scoped accessibility tests
└── helpers/
    └── accessibility.ts          # New: axe-core helper utilities

# Target repo (chaos dashboard):
src/dashboard/chaos.html          # Modified: add data-testid attribute
```

**Structure Decision**: Extends existing Playwright test infrastructure. New test file + helper alongside existing smoke.spec.ts and api.spec.ts.

## Adversarial Review #2

**Reviewed**: 2026-03-29 | **Focus**: Spec drift from clarifications, cross-artifact consistency

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | Plan said `^4.x` but research says `^4.10.0` — version pin inconsistency | Fixed: plan updated to `^4.10.0` |
| HIGH | Plan said "~6 views" but clarification Q2 confirms exactly 5 | Fixed: plan updated to "5 dashboard views" |
| MEDIUM | Contract merged AuditResult has ambiguous `scope` field | Accepted: primary scope used, modal violations annotated |
| MEDIUM | Readiness gate terminology inconsistent (button vs interactive element) | Accepted: implementation aligns on "visible button or [role=button]" |
| MEDIUM | `withTags()` vs `runOnly` terminology mismatch | Accepted: they map to same API |
| LOW | Modal selector `[role="dialog"]` vs `dialog[open]` undocumented | Accepted: `[role="dialog"]` catches non-native dialogs too |
| LOW | Dependency on 1242/1245 not in plan | Fixed: Dependencies section added |

**Gate**: 0 CRITICAL, 0 HIGH remaining.
