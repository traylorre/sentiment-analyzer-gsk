# Spec: Documentation Reorganization

## Problem Statement

The documentation in sentiment-analyzer-gsk is scattered and difficult to consume:
- **87 documentation files** across root and /docs/
- **21 root-level markdown files** (many are historical artifacts)
- **61 flat files in /docs/** with no categorical organization
- Model selection research spread across 5 files
- Lessons learned scattered across 4 separate files
- Session summaries mixed with operational docs

For an interviewer or new contributor, the current structure is overwhelming and communicates disorganization despite containing valuable content.

## Goals

1. **Reduce root clutter** from 21 files to 6 (standard OSS files only)
2. **Organize /docs/** into categorical subdirectories
3. **Consolidate overlapping content** without losing important granularity
4. **Maintain all internal links** (48 identified cross-references)
5. **Create documentation index** for easy navigation
6. **Archive historical artifacts** while keeping them accessible

## Non-Goals

- Rewriting documentation content
- Changing the specs/ directory structure
- Modifying code or tests
- Creating new documentation beyond the index

## Design

### Root Directory Structure (After)

```
README.md           # Entry point (keep)
SPEC.md             # Authoritative source (keep)
CONTRIBUTING.md     # Standard OSS file (keep)
SECURITY.md         # Standard OSS file (keep)
CHANGELOG.md        # Standard OSS file (keep)
CLAUDE.md           # Auto-generated (keep)
```

### Files to Move from Root to /docs/archive/

| File | Reason | Destination |
|------|--------|-------------|
| DECISION_SUMMARY.md | Historical decision | docs/archive/model-selection/ |
| SENTIMENT_MODEL_COMPARISON.md | Research artifact | docs/archive/model-selection/ |
| SENTIMENT_ANALYSIS_INDEX.md | Research artifact | docs/archive/model-selection/ |
| METRICS_COMPARISON.md | Research artifact | docs/archive/model-selection/ |
| RECOMMENDATION.md | Research artifact | docs/archive/model-selection/ |
| RESULT1-validation-gaps.md | Dec 2025 audit | docs/archive/audit-dec-2025/ |
| RESULT2-tech-debt.md | Dec 2025 audit | docs/archive/audit-dec-2025/ |
| RESULT3-deferred-debt-status.md | Dec 2025 audit | docs/archive/audit-dec-2025/ |
| RESULT4-drift-audit.md | Dec 2025 audit | docs/archive/audit-dec-2025/ |
| SESSION_SUMMARY_WSL_DEPLOYMENT.md | Session artifact | docs/archive/sessions/ |
| VALIDATE3.md | Session artifact | docs/archive/sessions/ |
| IMPLEMENTATION_GUIDE.md | Reference doc | docs/reference/ |

### Files to Delete from Root

| File | Reason |
|------|--------|
| DEMO_URLS.local.md | Should be gitignored template |
| BACKLOG.md | Empty 769 bytes, use GitHub issues |
| INSTRUCTIONS setup sentiment analyzer.txt | Redundant with docs/setup/WORKSPACE_SETUP.md |

### New /docs/ Directory Structure

```
docs/
├── README.md                    # Documentation index (NEW)
├── architecture/                # 8 files
│   ├── ARCHITECTURE_DECISIONS.md
│   ├── real-time-multi-resolution-architecture.md
│   ├── USE-CASE-DIAGRAMS.md
│   ├── DATA_FLOW_AUDIT.md
│   ├── INTERFACE-ANALYSIS-SUMMARY.md
│   ├── CLOUD_PROVIDER_PORTABILITY_AUDIT.md
│   ├── LAMBDA_DEPENDENCY_ANALYSIS.md
│   └── AUTH_SESSION_LIFECYCLE.md
├── deployment/                  # 12 files
│   ├── DEPLOYMENT.md
│   ├── TERRAFORM_DEPLOYMENT_FLOW.md
│   ├── ENVIRONMENT_STRATEGY.md
│   ├── GITHUB_ENVIRONMENTS_SETUP.md
│   ├── GITHUB_SECRETS_SETUP.md
│   ├── DEPLOYMENT_CONCURRENCY.md
│   ├── PRODUCTION_PREFLIGHT_CHECKLIST.md
│   ├── FIRST_PROD_DEPLOY_READY.md
│   ├── PROMOTION_WORKFLOW_DESIGN.md
│   ├── PROMOTION_PIPELINE_MASTER_SUMMARY.md
│   ├── PREPROD_DEPLOYMENT_ANALYSIS.md
│   └── CI_CD_WORKFLOWS.md
├── operations/                  # 8 files
│   ├── TROUBLESHOOTING.md
│   ├── FAILURE_RECOVERY_RUNBOOK.md
│   ├── OPERATIONAL_FLOWS.md
│   ├── DEMO_CHECKLIST.md
│   ├── PIPELINE_VISIBILITY_IMPLEMENTATION.md
│   ├── CACHE_PERFORMANCE.md
│   ├── PERFORMANCE_VALIDATION.md
│   └── LOG_VALIDATION_STATUS.md
├── security/                    # 5 files
│   ├── DASHBOARD_SECURITY_ANALYSIS.md
│   ├── DASHBOARD_SECURITY_TEST_COVERAGE.md
│   ├── IAM_TERRAFORM_TROUBLESHOOTING.md
│   ├── IAM_CI_USER_POLICY.md
│   └── IAM_JUSTIFICATIONS.md
├── setup/                       # 6 files
│   ├── WORKSPACE_SETUP.md
│   ├── GET_DASHBOARD_RUNNING.md
│   ├── GIT_WORKFLOW.md
│   ├── GPG_SIGNING_SETUP.md
│   ├── PYTHON_VERSION_PARITY.md
│   └── CODEQL-PRE-PUSH-HOOK.md
├── testing/                     # 7 files
│   ├── TESTING_LESSONS_LEARNED.md
│   ├── CRITICAL_TESTING_MISTAKE.md
│   ├── DASHBOARD_TESTING_BACKLOG.md
│   ├── TEST-DEBT.md
│   ├── TEST_LOG_ASSERTIONS_TODO.md
│   ├── INTEGRATION_TEST_REFACTOR_PLAN.md
│   └── chaos-testing/           # Preserve existing subfolder
├── reference/                   # 6 files
│   ├── DASHBOARD_SPEC.md
│   ├── API_GATEWAY_GAP_ANALYSIS.md
│   ├── COST_BREAKDOWN.md
│   ├── FRONTEND_DEPENDENCY_MANAGEMENT.md
│   ├── TECH_DEBT_REGISTRY.md
│   └── SPECIFICATION-GAPS.md
├── diagrams/                    # Preserve existing (4 .mmd files)
├── runbooks/                    # Preserve existing if any
└── archive/                     # Historical artifacts
    ├── model-selection/         # Consolidated from 5 root files
    ├── audit-dec-2025/          # 4 RESULT*.md files
    ├── phase-summaries/         # PHASE_*.md files
    ├── sessions/                # Session notes
    └── archived-specs/          # Preserve existing
```

### Consolidation Strategy

#### Lessons Learned (4 → 1 with sections)

Merge into `docs/LESSONS_LEARNED.md`:
- Section: CI/CD (from CI_CD_LESSONS_LEARNED.md)
- Section: Terraform (from TERRAFORM_LESSONS_LEARNED.md)
- Section: Testing (from TESTING_LESSONS_LEARNED.md + TEST_QUALITY_LESSONS_LEARNED.md)

Keep originals in docs/archive/lessons-learned/ for reference.

### Link Migration Strategy

Based on dependency analysis:
- **94 files (69%)** have zero links - safe to move immediately
- **20 files** are link targets only - update incoming refs after move
- **5 files** have outgoing links only - update after targets move
- **18 files** are bidirectionally linked - move clusters together

Critical clusters to move as units:
1. Setup cluster: WORKSPACE_SETUP.md + 4 targets
2. Dashboard cluster: DASHBOARD_SPEC.md + 3 targets
3. Chaos testing: entire subfolder (already organized)

### Link Update Rules

1. **Root → docs/**: `docs/X.md` → `docs/category/X.md`
2. **docs/ flat → subdirectory**: `./X.md` → `./category/X.md`
3. **docs/ → root**: `../X.md` → unchanged
4. **Cross-subdirectory**: `./X.md` → `../other-category/X.md`

### Broken Link Fixes

| Source | Broken Link | Fix |
|--------|-------------|-----|
| SECURITY.md | specs/001-interactive-dashboard-demo/SECURITY_REVIEW.md | Remove link or create file |
| docs/LESSONS_LEARNED.md | `![](badge-url)` (7 instances) | Replace with actual badge URLs or remove table |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Broken links post-reorganization | HIGH | Run link validator before/after |
| Lost git history for moved files | MEDIUM | Use `git mv` for all moves |
| Outdated README references | HIGH | Update README.md links last |
| CI/CD doc references | MEDIUM | Search workflows for .md refs |

## Validation

1. Pre-flight: `make validate` passes
2. Link check: `grep -r "docs/" --include="*.md"` shows valid paths
3. Git history: `git log --follow docs/category/FILE.md` preserves history
4. No orphans: All docs accessible via docs/README.md index

## Out of Scope

- Merging content between files (only organizing)
- Updating CLAUDE.md (auto-generated)
- Modifying code documentation in src/ or tests/
- Changing specs/ structure

## Acceptance Criteria

- [ ] Root directory has exactly 6 markdown files
- [ ] All docs organized into categorical subdirectories
- [ ] docs/README.md index exists and covers all files
- [ ] All internal links resolve (no 404s)
- [ ] Git history preserved for moved files
- [ ] CI pipeline passes (make validate)
