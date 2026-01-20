# Documentation Index

This directory contains all project documentation organized by category.

## Quick Navigation

| Category | Description | Key Files |
|----------|-------------|-----------|
| [Architecture](./architecture/) | System design, data flows, decisions | [ARCHITECTURE_DECISIONS.md](./architecture/ARCHITECTURE_DECISIONS.md), [USE-CASE-DIAGRAMS.md](./architecture/USE-CASE-DIAGRAMS.md) |
| [Deployment](./deployment/) | CI/CD, environments, Terraform | [DEPLOYMENT.md](./deployment/DEPLOYMENT.md), [CI_CD_WORKFLOWS.md](./deployment/CI_CD_WORKFLOWS.md) |
| [Operations](./operations/) | Runbooks, troubleshooting, monitoring | [TROUBLESHOOTING.md](./operations/TROUBLESHOOTING.md), [FAILURE_RECOVERY_RUNBOOK.md](./operations/FAILURE_RECOVERY_RUNBOOK.md) |
| [Security](./security/) | IAM, security analysis, audits | [DASHBOARD_SECURITY_ANALYSIS.md](./security/DASHBOARD_SECURITY_ANALYSIS.md), [IAM_TERRAFORM_TROUBLESHOOTING.md](./security/IAM_TERRAFORM_TROUBLESHOOTING.md) |
| [Setup](./setup/) | Development environment setup | [WORKSPACE_SETUP.md](./setup/WORKSPACE_SETUP.md), [GIT_WORKFLOW.md](./setup/GIT_WORKFLOW.md) |
| [Testing](./testing/) | Test strategies, chaos engineering | [TESTING_LESSONS_LEARNED.md](./testing/TESTING_LESSONS_LEARNED.md), [CHAOS_TESTING_OPERATOR_GUIDE.md](./testing/CHAOS_TESTING_OPERATOR_GUIDE.md) |
| [Reference](./reference/) | Specifications, tech debt, costs | [DASHBOARD_SPEC.md](./reference/DASHBOARD_SPEC.md), [TECH_DEBT_REGISTRY.md](./reference/TECH_DEBT_REGISTRY.md) |
| [Diagrams](./diagrams/) | Mermaid architecture diagrams | [high-level-overview.mmd](./diagrams/high-level-overview.mmd), [dataflow-all-flows.mmd](./diagrams/dataflow-all-flows.mmd) |
| [Archive](./archive/) | Historical docs and research | Model selection, audit reports, sessions |

---

## For New Contributors

Start here:
1. [WORKSPACE_SETUP.md](./setup/WORKSPACE_SETUP.md) - Development environment
2. [GIT_WORKFLOW.md](./setup/GIT_WORKFLOW.md) - Git conventions
3. [GPG_SIGNING_SETUP.md](./setup/GPG_SIGNING_SETUP.md) - Required commit signing

## For Developers

- [ARCHITECTURE_DECISIONS.md](./architecture/ARCHITECTURE_DECISIONS.md) - Key design decisions
- [TESTING_LESSONS_LEARNED.md](./testing/TESTING_LESSONS_LEARNED.md) - Testing patterns
- [TECH_DEBT_REGISTRY.md](./reference/TECH_DEBT_REGISTRY.md) - Known issues

## For On-Call Engineers

- [FAILURE_RECOVERY_RUNBOOK.md](./operations/FAILURE_RECOVERY_RUNBOOK.md) - Incident response
- [TROUBLESHOOTING.md](./operations/TROUBLESHOOTING.md) - Common issues
- [OPERATIONAL_FLOWS.md](./operations/OPERATIONAL_FLOWS.md) - System flows

## For DevOps

- [DEPLOYMENT.md](./deployment/DEPLOYMENT.md) - Deployment procedures
- [CI_CD_WORKFLOWS.md](./deployment/CI_CD_WORKFLOWS.md) - GitHub Actions
- [IAM_TERRAFORM_TROUBLESHOOTING.md](./security/IAM_TERRAFORM_TROUBLESHOOTING.md) - Permission issues

---

## Directory Contents

### architecture/
System architecture and design decisions.

| File | Description |
|------|-------------|
| [ARCHITECTURE_DECISIONS.md](./architecture/ARCHITECTURE_DECISIONS.md) | ADRs and rationale |
| [USE-CASE-DIAGRAMS.md](./architecture/USE-CASE-DIAGRAMS.md) | User flow diagrams |
| [DATA_FLOW_AUDIT.md](./architecture/DATA_FLOW_AUDIT.md) | Data flow analysis |
| [real-time-multi-resolution-architecture.md](./architecture/real-time-multi-resolution-architecture.md) | Real-time system design |
| [INTERFACE-ANALYSIS-SUMMARY.md](./architecture/INTERFACE-ANALYSIS-SUMMARY.md) | Component interfaces |
| [CLOUD_PROVIDER_PORTABILITY_AUDIT.md](./architecture/CLOUD_PROVIDER_PORTABILITY_AUDIT.md) | Multi-cloud analysis |
| [LAMBDA_DEPENDENCY_ANALYSIS.md](./architecture/LAMBDA_DEPENDENCY_ANALYSIS.md) | Lambda dependencies |
| [AUTH_SESSION_LIFECYCLE.md](./architecture/AUTH_SESSION_LIFECYCLE.md) | Authentication flow |

### deployment/
CI/CD pipelines and deployment procedures.

| File | Description |
|------|-------------|
| [DEPLOYMENT.md](./deployment/DEPLOYMENT.md) | Main deployment guide |
| [CI_CD_WORKFLOWS.md](./deployment/CI_CD_WORKFLOWS.md) | GitHub Actions workflows |
| [TERRAFORM_DEPLOYMENT_FLOW.md](./deployment/TERRAFORM_DEPLOYMENT_FLOW.md) | Terraform automation |
| [ENVIRONMENT_STRATEGY.md](./deployment/ENVIRONMENT_STRATEGY.md) | Dev/preprod/prod strategy |
| [GITHUB_ENVIRONMENTS_SETUP.md](./deployment/GITHUB_ENVIRONMENTS_SETUP.md) | Environment protection |
| [GITHUB_SECRETS_SETUP.md](./deployment/GITHUB_SECRETS_SETUP.md) | Secrets configuration |
| [PROMOTION_WORKFLOW_DESIGN.md](./deployment/PROMOTION_WORKFLOW_DESIGN.md) | Environment promotion |
| [PRODUCTION_PREFLIGHT_CHECKLIST.md](./deployment/PRODUCTION_PREFLIGHT_CHECKLIST.md) | Pre-deploy checks |

### operations/
Runbooks and operational procedures.

| File | Description |
|------|-------------|
| [TROUBLESHOOTING.md](./operations/TROUBLESHOOTING.md) | Common issues and fixes |
| [FAILURE_RECOVERY_RUNBOOK.md](./operations/FAILURE_RECOVERY_RUNBOOK.md) | Incident response |
| [OPERATIONAL_FLOWS.md](./operations/OPERATIONAL_FLOWS.md) | System operation flows |
| [DEMO_CHECKLIST.md](./operations/DEMO_CHECKLIST.md) | Demo preparation |
| [CACHE_PERFORMANCE.md](./operations/CACHE_PERFORMANCE.md) | Cache analysis |
| [PERFORMANCE_VALIDATION.md](./operations/PERFORMANCE_VALIDATION.md) | Performance metrics |

### security/
Security analysis and IAM configuration.

| File | Description |
|------|-------------|
| [DASHBOARD_SECURITY_ANALYSIS.md](./security/DASHBOARD_SECURITY_ANALYSIS.md) | Security audit |
| [DASHBOARD_SECURITY_TEST_COVERAGE.md](./security/DASHBOARD_SECURITY_TEST_COVERAGE.md) | Security test coverage |
| [IAM_TERRAFORM_TROUBLESHOOTING.md](./security/IAM_TERRAFORM_TROUBLESHOOTING.md) | IAM debugging |
| [IAM_CI_USER_POLICY.md](./security/IAM_CI_USER_POLICY.md) | CI user permissions |
| [IAM_JUSTIFICATIONS.md](./security/IAM_JUSTIFICATIONS.md) | Permission rationale |

### setup/
Development environment setup guides.

| File | Description |
|------|-------------|
| [WORKSPACE_SETUP.md](./setup/WORKSPACE_SETUP.md) | Complete setup guide |
| [GET_DASHBOARD_RUNNING.md](./setup/GET_DASHBOARD_RUNNING.md) | Dashboard quickstart |
| [GIT_WORKFLOW.md](./setup/GIT_WORKFLOW.md) | Git conventions |
| [GPG_SIGNING_SETUP.md](./setup/GPG_SIGNING_SETUP.md) | Commit signing |
| [PYTHON_VERSION_PARITY.md](./setup/PYTHON_VERSION_PARITY.md) | Python version requirements |
| [CODEQL-PRE-PUSH-HOOK.md](./setup/CODEQL-PRE-PUSH-HOOK.md) | Security scanning |

### testing/
Testing strategies and chaos engineering.

| File | Description |
|------|-------------|
| [TESTING_LESSONS_LEARNED.md](./testing/TESTING_LESSONS_LEARNED.md) | Testing patterns |
| [CHAOS_TESTING_OPERATOR_GUIDE.md](./testing/CHAOS_TESTING_OPERATOR_GUIDE.md) | Chaos engineering guide |
| [CRITICAL_TESTING_MISTAKE.md](./testing/CRITICAL_TESTING_MISTAKE.md) | Anti-patterns to avoid |
| [DASHBOARD_TESTING_BACKLOG.md](./testing/DASHBOARD_TESTING_BACKLOG.md) | Test backlog |
| [TEST-DEBT.md](./testing/TEST-DEBT.md) | Test tech debt |
| [INTEGRATION_TEST_REFACTOR_PLAN.md](./testing/INTEGRATION_TEST_REFACTOR_PLAN.md) | Refactoring plan |

### reference/
Specifications and technical references.

| File | Description |
|------|-------------|
| [DASHBOARD_SPEC.md](./reference/DASHBOARD_SPEC.md) | Dashboard specification |
| [IMPLEMENTATION_GUIDE.md](./reference/IMPLEMENTATION_GUIDE.md) | Implementation patterns |
| [TECH_DEBT_REGISTRY.md](./reference/TECH_DEBT_REGISTRY.md) | Technical debt tracking |
| [SPECIFICATION-GAPS.md](./reference/SPECIFICATION-GAPS.md) | Spec gap analysis |
| [API_GATEWAY_GAP_ANALYSIS.md](./reference/API_GATEWAY_GAP_ANALYSIS.md) | API analysis |
| [COST_BREAKDOWN.md](./reference/COST_BREAKDOWN.md) | Infrastructure costs |
| [FRONTEND_DEPENDENCY_MANAGEMENT.md](./reference/FRONTEND_DEPENDENCY_MANAGEMENT.md) | Frontend packages |

### archive/
Historical documents and research artifacts.

| Directory | Contents |
|-----------|----------|
| [model-selection/](./archive/model-selection/) | ML model comparison research |
| [audit-dec-2025/](./archive/audit-dec-2025/) | December 2025 validation audit |
| [lessons-learned/](./archive/lessons-learned/) | Historical lessons learned |
| [phase-summaries/](./archive/phase-summaries/) | Project phase summaries |
| [sessions/](./archive/sessions/) | Session notes and summaries |

---

*Last updated: 2026-01-19*
