# Implementation Plan: Fix Double-Slash URL in API Requests

**Branch**: `1118-fix-api-url-double-slash` | **Date**: 2026-01-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1118-fix-api-url-double-slash/spec.md`

## Summary

Fix the double-slash URL issue in frontend API requests that causes HTTP 422 errors on authentication. The solution implements URL normalization in the API client layer to ensure proper URL construction regardless of trailing/leading slash variations.

## Technical Context

**Language/Version**: TypeScript (Next.js 14+)
**Primary Dependencies**: Next.js, fetch API (native)
**Storage**: N/A (frontend-only fix)
**Testing**: Manual browser verification, unit tests for URL normalization function
**Target Platform**: Web browsers (Chrome, Firefox, Safari, Edge)
**Project Type**: Web application (frontend focus)
**Performance Goals**: No performance impact (string manipulation at request time)
**Constraints**: Must not break existing API calls; greenfield approach (no fallbacks)
**Scale/Scope**: Single utility function + API client modification

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Authentication (Sec 3) | N/A | Fix improves auth, doesn't change auth logic |
| TLS/HTTPS (Sec 3) | PASS | All API calls remain HTTPS |
| Secrets Management (Sec 3) | N/A | No secrets involved |
| Unit Tests (Sec 7) | REQUIRED | URL normalization function should be unit tested |
| GPG Signed Commits (Sec 8) | REQUIRED | Will sign all commits |
| Feature Branch (Sec 8) | PASS | On 1118-fix-api-url-double-slash branch |
| No Pipeline Bypass (Sec 8) | REQUIRED | Will not bypass |
| No Fallbacks (Amendment) | PASS | Greenfield approach, single canonical pattern |

**Gate Result**: PASS - Proceeding with implementation.

## Project Structure

### Documentation (this feature)

```text
specs/1118-fix-api-url-double-slash/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 output (URL normalization patterns)
├── data-model.md        # Phase 1 output (URL construction model)
├── quickstart.md        # Phase 1 output (verification steps)
├── checklists/          # Requirements checklist
└── tasks.md             # Phase 2 output (implementation tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   └── lib/
│       ├── api/
│       │   └── client.ts    # MODIFY - URL construction happens here
│       └── utils/
│           └── url.ts       # CREATE - URL normalization utility
└── tests/                   # If unit tests exist for frontend
```

**Structure Decision**: Web application structure - modifying existing frontend API client in `frontend/src/lib/api/client.ts` and adding a URL normalization utility.

## Complexity Tracking

> No violations - simple utility function addition and single-point modification.

| Aspect | Complexity | Justification |
|--------|------------|---------------|
| Files Changed | 1-2 files | client.ts modification + optional url.ts utility |
| Dependencies | 0 new | Uses native string/URL APIs |
| Testing | Unit test | URL normalization function is easily unit testable |
