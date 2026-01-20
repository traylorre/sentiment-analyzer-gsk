# Implementation Plan: Documentation Reorganization

## Phase 1: Create Directory Structure

Create new directories before any file moves:

```bash
mkdir -p docs/architecture
mkdir -p docs/deployment
mkdir -p docs/operations
mkdir -p docs/security
mkdir -p docs/setup
mkdir -p docs/testing
mkdir -p docs/reference
mkdir -p docs/archive/model-selection
mkdir -p docs/archive/audit-dec-2025
mkdir -p docs/archive/sessions
mkdir -p docs/archive/lessons-learned
mkdir -p docs/archive/phase-summaries
```

## Phase 2: Move Orphan Files (Zero Dependencies)

These 94 files have no incoming or outgoing links. Safe to move without link updates.

### Architecture Category
```bash
git mv docs/ARCHITECTURE_DECISIONS.md docs/architecture/
git mv docs/real-time-multi-resolution-architecture.md docs/architecture/
git mv docs/USE-CASE-DIAGRAMS.md docs/architecture/
git mv docs/DATA_FLOW_AUDIT.md docs/architecture/
git mv docs/INTERFACE-ANALYSIS-SUMMARY.md docs/architecture/
git mv docs/CLOUD_PROVIDER_PORTABILITY_AUDIT.md docs/architecture/
git mv docs/LAMBDA_DEPENDENCY_ANALYSIS.md docs/architecture/
git mv docs/AUTH_SESSION_LIFECYCLE.md docs/architecture/
```

### Operations Category
```bash
git mv docs/TROUBLESHOOTING.md docs/operations/
git mv docs/DEMO_CHECKLIST.md docs/operations/
git mv docs/PIPELINE_VISIBILITY_IMPLEMENTATION.md docs/operations/
git mv docs/CACHE_PERFORMANCE.md docs/operations/
git mv docs/PERFORMANCE_VALIDATION.md docs/operations/
git mv docs/LOG_VALIDATION_STATUS.md docs/operations/
```

### Security Category
```bash
git mv docs/DASHBOARD_SECURITY_ANALYSIS.md docs/security/
git mv docs/DASHBOARD_SECURITY_TEST_COVERAGE.md docs/security/
git mv docs/IAM_CI_USER_POLICY.md docs/security/
git mv docs/IAM_JUSTIFICATIONS.md docs/security/
```

### Testing Category
```bash
git mv docs/TESTING_LESSONS_LEARNED.md docs/testing/
git mv docs/CRITICAL_TESTING_MISTAKE.md docs/testing/
git mv docs/DASHBOARD_TESTING_BACKLOG.md docs/testing/
git mv docs/TEST-DEBT.md docs/testing/
git mv docs/TEST_LOG_ASSERTIONS_TODO.md docs/testing/
git mv docs/INTEGRATION_TEST_REFACTOR_PLAN.md docs/testing/
```

### Reference Category
```bash
git mv docs/API_GATEWAY_GAP_ANALYSIS.md docs/reference/
git mv docs/COST_BREAKDOWN.md docs/reference/
git mv docs/FRONTEND_DEPENDENCY_MANAGEMENT.md docs/reference/
git mv docs/TECH_DEBT_REGISTRY.md docs/reference/
git mv docs/SPECIFICATION-GAPS.md docs/reference/
```

### Archive - Lessons Learned
```bash
git mv docs/CI_CD_LESSONS_LEARNED.md docs/archive/lessons-learned/
git mv docs/TERRAFORM_LESSONS_LEARNED.md docs/archive/lessons-learned/
git mv docs/TEST_QUALITY_LESSONS_LEARNED.md docs/archive/lessons-learned/
```

### Archive - Phase Summaries
```bash
git mv docs/PHASE_1_2_SUMMARY.md docs/archive/phase-summaries/
git mv docs/PHASE_3_SUMMARY.md docs/archive/phase-summaries/
```

## Phase 3: Move Linked Clusters (Together)

### Setup Cluster (WORKSPACE_SETUP links to these)
```bash
# Move targets first
git mv docs/GIT_WORKFLOW.md docs/setup/
git mv docs/GPG_SIGNING_SETUP.md docs/setup/
git mv docs/PYTHON_VERSION_PARITY.md docs/setup/
git mv docs/CODEQL-PRE-PUSH-HOOK.md docs/setup/
git mv docs/GET_DASHBOARD_RUNNING.md docs/setup/

# Move source last
git mv docs/WORKSPACE_SETUP.md docs/setup/
```

### Deployment Cluster
```bash
git mv docs/TERRAFORM_DEPLOYMENT_FLOW.md docs/deployment/
git mv docs/ENVIRONMENT_STRATEGY.md docs/deployment/
git mv docs/GITHUB_ENVIRONMENTS_SETUP.md docs/deployment/
git mv docs/GITHUB_SECRETS_SETUP.md docs/deployment/
git mv docs/DEPLOYMENT_CONCURRENCY.md docs/deployment/
git mv docs/PRODUCTION_PREFLIGHT_CHECKLIST.md docs/deployment/
git mv docs/FIRST_PROD_DEPLOY_READY.md docs/deployment/
git mv docs/PROMOTION_WORKFLOW_DESIGN.md docs/deployment/
git mv docs/PROMOTION_PIPELINE_MASTER_SUMMARY.md docs/deployment/
git mv docs/PREPROD_DEPLOYMENT_ANALYSIS.md docs/deployment/
git mv docs/CI_CD_WORKFLOWS.md docs/deployment/
git mv docs/DEPLOYMENT.md docs/deployment/
```

### Security Cluster (IAM links)
```bash
git mv docs/IAM_TERRAFORM_TROUBLESHOOTING.md docs/security/
```

### Operations Cluster
```bash
git mv docs/FAILURE_RECOVERY_RUNBOOK.md docs/operations/
git mv docs/OPERATIONAL_FLOWS.md docs/operations/
```

### Reference Cluster
```bash
git mv docs/DASHBOARD_SPEC.md docs/reference/
```

## Phase 4: Move Root Files to Archive

```bash
# Model selection research
git mv DECISION_SUMMARY.md docs/archive/model-selection/
git mv SENTIMENT_MODEL_COMPARISON.md docs/archive/model-selection/
git mv SENTIMENT_ANALYSIS_INDEX.md docs/archive/model-selection/
git mv METRICS_COMPARISON.md docs/archive/model-selection/
git mv RECOMMENDATION.md docs/archive/model-selection/

# Dec 2025 audit
git mv RESULT1-validation-gaps.md docs/archive/audit-dec-2025/
git mv RESULT2-tech-debt.md docs/archive/audit-dec-2025/
git mv RESULT3-tech-debt.md docs/archive/audit-dec-2025/ 2>/dev/null || true
git mv RESULT3-deferred-debt-status.md docs/archive/audit-dec-2025/
git mv RESULT4-drift-audit.md docs/archive/audit-dec-2025/

# Sessions
git mv SESSION_SUMMARY_WSL_DEPLOYMENT.md docs/archive/sessions/
git mv VALIDATE3.md docs/archive/sessions/

# Reference
git mv IMPLEMENTATION_GUIDE.md docs/reference/
```

## Phase 5: Delete Redundant Files

```bash
# Verify before deletion
cat BACKLOG.md  # Should be nearly empty
cat "INSTRUCTIONS setup sentiment analyzer.txt"  # Redundant with WORKSPACE_SETUP

# Delete
rm BACKLOG.md
rm "INSTRUCTIONS setup sentiment analyzer.txt"

# DEMO_URLS.local.md - move to gitignored template
mv DEMO_URLS.local.md .DEMO_URLS.local.md.template
echo "DEMO_URLS.local.md" >> .gitignore
```

## Phase 6: Update Internal Links

### Files Requiring Link Updates

1. **docs/setup/WORKSPACE_SETUP.md** - 4 outgoing links
   - `./DEPLOYMENT.md` → `../deployment/DEPLOYMENT.md`
   - `./GITHUB_SECRETS_SETUP.md` → `./GITHUB_SECRETS_SETUP.md` (same dir)
   - `./GIT_WORKFLOW.md` → `./GIT_WORKFLOW.md` (same dir)
   - `./GPG_SIGNING_SETUP.md` → `./GPG_SIGNING_SETUP.md` (same dir)

2. **docs/security/IAM_TERRAFORM_TROUBLESHOOTING.md** - 4 outgoing links
   - `./DEPLOYMENT_CONCURRENCY.md` → `../deployment/DEPLOYMENT_CONCURRENCY.md`
   - `./FAILURE_RECOVERY_RUNBOOK.md` → `../operations/FAILURE_RECOVERY_RUNBOOK.md`
   - `./GITHUB_ENVIRONMENTS_SETUP.md` → `../deployment/GITHUB_ENVIRONMENTS_SETUP.md`
   - Verify: `./GITHUB_SECRETS_CONFIGURATION.md` → check if exists

3. **docs/reference/DASHBOARD_SPEC.md** - 3 outgoing links
   - Check for links to ON_CALL_SOP, API, MODEL_VERSIONING

4. **docs/operations/OPERATIONAL_FLOWS.md** - 2 outgoing links
   - Check for links to DASHBOARD_SECURITY_ANALYSIS, TERRAFORM_DEPLOYMENT_FLOW

5. **docs/deployment/GITHUB_SECRETS_SETUP.md** - 3 outgoing links
   - Check for links to WORKFLOW_DOCUMENTATION, DEPLOYMENT, IAM_CI_USER_POLICY

6. **README.md** - Update all docs/ references
   - `docs/WORKSPACE_SETUP.md` → `docs/setup/WORKSPACE_SETUP.md`
   - `docs/DEPLOYMENT.md` → `docs/deployment/DEPLOYMENT.md`
   - `docs/TROUBLESHOOTING.md` → `docs/operations/TROUBLESHOOTING.md`
   - `docs/IAM_TERRAFORM_TROUBLESHOOTING.md` → `docs/security/IAM_TERRAFORM_TROUBLESHOOTING.md`

## Phase 7: Fix Broken Links

1. **SECURITY.md line 24** - broken ref to SECURITY_REVIEW.md
   - Option A: Create `specs/001-interactive-dashboard-demo/SECURITY_REVIEW.md`
   - Option B: Remove the link

2. **docs/LESSONS_LEARNED.md** - 7 placeholder badge URLs
   - Replace `![](badge-url)` with actual GitHub Actions badge URLs or remove table

## Phase 8: Create Documentation Index

Create `docs/README.md` with navigation structure.

## Phase 9: Validation

```bash
# Check for broken links
grep -rn "docs/[A-Z]" *.md | grep -v "docs/archive" | grep -v "docs/architecture" | grep -v "docs/deployment" | grep -v "docs/operations" | grep -v "docs/security" | grep -v "docs/setup" | grep -v "docs/testing" | grep -v "docs/reference" | grep -v "docs/diagrams" | grep -v "docs/chaos-testing" | grep -v "docs/runbooks"

# Run project validation
make validate

# Verify git history
git log --follow docs/architecture/ARCHITECTURE_DECISIONS.md
```

## Execution Order

1. Phase 1: Create directories (no risk)
2. Phase 2: Move orphans (no link risk)
3. Phase 3: Move clusters (internal links only)
4. Phase 4: Move root files (external links)
5. Phase 5: Delete redundant (verify first)
6. Phase 6: Update links (critical)
7. Phase 7: Fix broken links (cleanup)
8. Phase 8: Create index (new content)
9. Phase 9: Validation (verify success)

## Rollback Plan

If validation fails:
```bash
git checkout origin/main -- docs/
git checkout origin/main -- *.md
```
