# Tasks: Documentation Reorganization

## Task 1: Create Directory Structure
**Status:** pending
**Dependencies:** none

Create all new directories under docs/:
- docs/architecture/
- docs/deployment/
- docs/operations/
- docs/security/
- docs/setup/
- docs/testing/
- docs/reference/
- docs/archive/model-selection/
- docs/archive/audit-dec-2025/
- docs/archive/sessions/
- docs/archive/lessons-learned/
- docs/archive/phase-summaries/

## Task 2: Move Orphan Files (Architecture)
**Status:** pending
**Dependencies:** Task 1

Move to docs/architecture/:
- ARCHITECTURE_DECISIONS.md
- real-time-multi-resolution-architecture.md
- USE-CASE-DIAGRAMS.md
- DATA_FLOW_AUDIT.md
- INTERFACE-ANALYSIS-SUMMARY.md
- CLOUD_PROVIDER_PORTABILITY_AUDIT.md
- LAMBDA_DEPENDENCY_ANALYSIS.md
- AUTH_SESSION_LIFECYCLE.md

## Task 3: Move Orphan Files (Operations)
**Status:** pending
**Dependencies:** Task 1

Move to docs/operations/:
- TROUBLESHOOTING.md
- DEMO_CHECKLIST.md
- PIPELINE_VISIBILITY_IMPLEMENTATION.md
- CACHE_PERFORMANCE.md
- PERFORMANCE_VALIDATION.md
- LOG_VALIDATION_STATUS.md

## Task 4: Move Orphan Files (Security)
**Status:** pending
**Dependencies:** Task 1

Move to docs/security/:
- DASHBOARD_SECURITY_ANALYSIS.md
- DASHBOARD_SECURITY_TEST_COVERAGE.md
- IAM_CI_USER_POLICY.md
- IAM_JUSTIFICATIONS.md

## Task 5: Move Orphan Files (Testing)
**Status:** pending
**Dependencies:** Task 1

Move to docs/testing/:
- TESTING_LESSONS_LEARNED.md
- CRITICAL_TESTING_MISTAKE.md
- DASHBOARD_TESTING_BACKLOG.md
- TEST-DEBT.md
- TEST_LOG_ASSERTIONS_TODO.md
- INTEGRATION_TEST_REFACTOR_PLAN.md

## Task 6: Move Orphan Files (Reference)
**Status:** pending
**Dependencies:** Task 1

Move to docs/reference/:
- API_GATEWAY_GAP_ANALYSIS.md
- COST_BREAKDOWN.md
- FRONTEND_DEPENDENCY_MANAGEMENT.md
- TECH_DEBT_REGISTRY.md
- SPECIFICATION-GAPS.md

## Task 7: Move Archive Files (Lessons Learned)
**Status:** pending
**Dependencies:** Task 1

Move to docs/archive/lessons-learned/:
- CI_CD_LESSONS_LEARNED.md
- TERRAFORM_LESSONS_LEARNED.md
- TEST_QUALITY_LESSONS_LEARNED.md

## Task 8: Move Archive Files (Phase Summaries)
**Status:** pending
**Dependencies:** Task 1

Move to docs/archive/phase-summaries/:
- PHASE_1_2_SUMMARY.md
- PHASE_3_SUMMARY.md

## Task 9: Move Setup Cluster
**Status:** pending
**Dependencies:** Task 1

Move to docs/setup/ (preserving internal links):
- GIT_WORKFLOW.md
- GPG_SIGNING_SETUP.md
- PYTHON_VERSION_PARITY.md
- CODEQL-PRE-PUSH-HOOK.md
- GET_DASHBOARD_RUNNING.md
- WORKSPACE_SETUP.md

## Task 10: Move Deployment Cluster
**Status:** pending
**Dependencies:** Task 1

Move to docs/deployment/:
- TERRAFORM_DEPLOYMENT_FLOW.md
- ENVIRONMENT_STRATEGY.md
- GITHUB_ENVIRONMENTS_SETUP.md
- GITHUB_SECRETS_SETUP.md
- DEPLOYMENT_CONCURRENCY.md
- PRODUCTION_PREFLIGHT_CHECKLIST.md
- FIRST_PROD_DEPLOY_READY.md
- PROMOTION_WORKFLOW_DESIGN.md
- PROMOTION_PIPELINE_MASTER_SUMMARY.md
- PREPROD_DEPLOYMENT_ANALYSIS.md
- CI_CD_WORKFLOWS.md
- DEPLOYMENT.md

## Task 11: Move Remaining Operations Files
**Status:** pending
**Dependencies:** Task 3

Move to docs/operations/:
- FAILURE_RECOVERY_RUNBOOK.md
- OPERATIONAL_FLOWS.md

## Task 12: Move Remaining Security Files
**Status:** pending
**Dependencies:** Task 4

Move to docs/security/:
- IAM_TERRAFORM_TROUBLESHOOTING.md

## Task 13: Move Remaining Reference Files
**Status:** pending
**Dependencies:** Task 6

Move to docs/reference/:
- DASHBOARD_SPEC.md

## Task 14: Move Root Files to Archive (Model Selection)
**Status:** pending
**Dependencies:** Task 1

Move from root to docs/archive/model-selection/:
- DECISION_SUMMARY.md
- SENTIMENT_MODEL_COMPARISON.md
- SENTIMENT_ANALYSIS_INDEX.md
- METRICS_COMPARISON.md
- RECOMMENDATION.md

## Task 15: Move Root Files to Archive (Audit)
**Status:** pending
**Dependencies:** Task 1

Move from root to docs/archive/audit-dec-2025/:
- RESULT1-validation-gaps.md
- RESULT2-tech-debt.md
- RESULT3-deferred-debt-status.md
- RESULT4-drift-audit.md

## Task 16: Move Root Files to Archive (Sessions)
**Status:** pending
**Dependencies:** Task 1

Move from root to docs/archive/sessions/:
- SESSION_SUMMARY_WSL_DEPLOYMENT.md
- VALIDATE3.md

## Task 17: Move IMPLEMENTATION_GUIDE.md
**Status:** pending
**Dependencies:** Task 1

Move from root to docs/reference/:
- IMPLEMENTATION_GUIDE.md

## Task 18: Delete Redundant Root Files
**Status:** pending
**Dependencies:** Tasks 14-17

After verification, delete:
- BACKLOG.md (empty/minimal)
- INSTRUCTIONS setup sentiment analyzer.txt (redundant)

Handle DEMO_URLS.local.md:
- Create .DEMO_URLS.local.md.template
- Add to .gitignore

## Task 19: Update Internal Links in docs/setup/WORKSPACE_SETUP.md
**Status:** pending
**Dependencies:** Tasks 9, 10

Update links:
- `./DEPLOYMENT.md` → `../deployment/DEPLOYMENT.md`
- Other links within setup/ stay relative

## Task 20: Update Internal Links in docs/security/IAM_TERRAFORM_TROUBLESHOOTING.md
**Status:** pending
**Dependencies:** Tasks 10, 11

Update links:
- `./DEPLOYMENT_CONCURRENCY.md` → `../deployment/DEPLOYMENT_CONCURRENCY.md`
- `./FAILURE_RECOVERY_RUNBOOK.md` → `../operations/FAILURE_RECOVERY_RUNBOOK.md`
- `./GITHUB_ENVIRONMENTS_SETUP.md` → `../deployment/GITHUB_ENVIRONMENTS_SETUP.md`

## Task 21: Update Internal Links in docs/reference/DASHBOARD_SPEC.md
**Status:** pending
**Dependencies:** Task 13

Scan and update any cross-directory links.

## Task 22: Update Internal Links in docs/operations/OPERATIONAL_FLOWS.md
**Status:** pending
**Dependencies:** Task 11

Update links:
- Security analysis refs → `../security/`
- Deployment refs → `../deployment/`

## Task 23: Update Internal Links in docs/deployment/GITHUB_SECRETS_SETUP.md
**Status:** pending
**Dependencies:** Task 10

Update links:
- IAM refs → `../security/`

## Task 24: Update README.md Links
**Status:** pending
**Dependencies:** Tasks 2-13

Update all docs/ references:
- `docs/WORKSPACE_SETUP.md` → `docs/setup/WORKSPACE_SETUP.md`
- `docs/DEPLOYMENT.md` → `docs/deployment/DEPLOYMENT.md`
- `docs/TROUBLESHOOTING.md` → `docs/operations/TROUBLESHOOTING.md`
- `docs/IAM_TERRAFORM_TROUBLESHOOTING.md` → `docs/security/IAM_TERRAFORM_TROUBLESHOOTING.md`

## Task 25: Fix Broken Link in SECURITY.md
**Status:** pending
**Dependencies:** none

Fix or remove broken reference to:
- specs/001-interactive-dashboard-demo/SECURITY_REVIEW.md

## Task 26: Fix Placeholder Badges in docs/LESSONS_LEARNED.md
**Status:** pending
**Dependencies:** Task 7

Replace 7 `![](badge-url)` placeholders with actual URLs or remove table.

## Task 27: Create docs/README.md Index
**Status:** pending
**Dependencies:** Tasks 2-17

Create documentation index with:
- Category overview
- Links to all major documents
- Quick navigation guide

## Task 28: Handle Remaining docs/ Files
**Status:** pending
**Dependencies:** Task 1

Categorize and move any remaining flat files:
- FUTURE_WORK.md → delete (empty) or archive
- sri-methodology.md → archive
- formatter-migration.md → archive
- ui-improvement-report-unusualwhales.md → archive
- PREPROD_DASHBOARD_INVESTIGATION_SUMMARY.md → archive/sessions

## Task 29: Validate All Links
**Status:** pending
**Dependencies:** Tasks 19-26

Run link validation:
- Scan all .md files for relative links
- Verify each target exists
- Fix any remaining broken links

## Task 30: Run make validate
**Status:** pending
**Dependencies:** Task 29

Ensure CI passes:
- make validate
- make test-local (if applicable)

## Task 31: Verify Git History Preservation
**Status:** pending
**Dependencies:** Task 30

Spot-check git history:
- `git log --follow docs/architecture/ARCHITECTURE_DECISIONS.md`
- Ensure history follows renames
