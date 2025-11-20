# sentiment-analyzer-gsk

[![Tests](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/test.yml/badge.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/test.yml)
[![Lint](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/lint.yml/badge.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/lint.yml)
[![Deploy Dev](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/deploy-dev.yml/badge.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/deploy-dev.yml)
[![Deploy Prod](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/deploy-prod.yml/badge.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/deploy-prod.yml)
[![Security](https://img.shields.io/badge/security-hardened-green.svg)](./SECURITY.md)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-%3E80%25-brightgreen.svg)](./pyproject.toml)

A cloud-hosted Sentiment Analyzer service built with serverless AWS architecture (Lambda, DynamoDB, EventBridge, SNS/SQS). Developed using [GitHub Spec-Kit](https://github.com/github/spec-kit) methodology for specification-driven development.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Project Overview](#project-overview)
- [Demo 1: Interactive Dashboard](#demo-1-interactive-dashboard)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development Setup](#local-development-setup)
  - [Verify Your Setup](#verify-your-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [On-Call & Operations](#on-call--operations)
- [Contributing](#contributing)
- [Security](#security)
- [Documentation](#documentation)

---

## Quick Start

**For new contributors - complete setup in 10 minutes:**

```bash
# 1. Clone repository
git clone https://github.com/traylorre/sentiment-analyzer-gsk.git
cd sentiment-analyzer-gsk

# 2. Install prerequisites (see Prerequisites section)
# Verify: aws --version, terraform --version, python --version

# 3. Configure AWS access (Contributor role only - see CONTRIBUTING.md)
aws configure --profile sentiment-analyzer-contributor
# Use IAM credentials provided by project admin

# 4. Verify access (read-only CloudWatch)
aws cloudwatch list-dashboards --profile sentiment-analyzer-contributor

# 5. Read project specification
cat SPEC.md  # or open in your editor

# 6. Review contribution guidelines
cat CONTRIBUTING.md

# 7. Create feature branch
git checkout -b feature/your-feature-name
```

**You're ready to contribute!** See [Development Workflow](#development-workflow) for next steps.

---

## Project Overview

### What This Service Does

Ingests text from external sources (Twitter, RSS feeds) and returns sentiment analysis:
- **Sentiment labels**: positive/neutral/negative
- **Confidence scores**: 0.0-1.0 range
- **Real-time & batch processing**: EventBridge scheduler + Lambda processors
- **Deduplication**: Avoids reprocessing duplicate items
- **Admin API**: Manage source subscriptions, pause/resume ingestion

### Architecture

- **Compute**: AWS Lambda (Python 3.11)
- **Orchestration**: EventBridge, SNS, SQS
- **Storage**: DynamoDB (on-demand capacity)
- **Sentiment Model**: VADER (lightweight, social media optimized)
- **Infrastructure**: Terraform + Terraform Cloud
- **CI/CD**: GitHub Actions → Terraform Cloud

### Key Features

✅ **Serverless & auto-scaling** - No manual capacity management
✅ **Cost-optimized** - Pay-per-use, ~$15-30/month for 10-50 sources
✅ **Security-first** - Least-privilege IAM, secrets in AWS Secrets Manager
✅ **Observable** - CloudWatch dashboards, alarms, DLQ monitoring
✅ **Tier-aware** - Twitter API tier configuration (Free → Basic → Pro)

---

## Demo 1: Interactive Dashboard

**Current Feature**: Real-time sentiment analysis with live dashboard

### Quick Links

| Document | Purpose |
|----------|---------|
| [Quickstart Guide](./specs/001-interactive-dashboard-demo/quickstart.md) | Step-by-step deployment |
| [Implementation Plan](./specs/001-interactive-dashboard-demo/plan.md) | Architecture & design decisions |
| [Feature Spec](./specs/001-interactive-dashboard-demo/spec.md) | Requirements & acceptance criteria |
| [On-Call SOP](./specs/001-interactive-dashboard-demo/ON_CALL_SOP.md) | Incident response runbooks |
| [Tasks](./specs/001-interactive-dashboard-demo/tasks.md) | Implementation checklist |

### Architecture Overview

![Architecture Diagram](docs/architecture.png)

**Data Flow**: NewsAPI → Ingestion → DynamoDB → SNS → Analysis → Dashboard

**Components**:
- **Ingestion Lambda**: EventBridge-triggered (5 min), fetches NewsAPI articles
- **Analysis Lambda**: SNS-triggered, runs DistilBERT sentiment inference
- **Dashboard Lambda**: Function URL, serves FastAPI + SSE real-time updates
- **DynamoDB**: Single table with 3 GSIs (by_sentiment, by_tag, by_status)

### Running Locally

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Run tests
pytest

# 4. Run linting
black --check src/ tests/
ruff check src/ tests/
```

### Deployment

See [Quickstart Guide](./specs/001-interactive-dashboard-demo/quickstart.md) for full deployment instructions.

```bash
# Dev deployment (automatic on merge to main)
# Or manually trigger via GitHub Actions

# Prod deployment (requires approval)
# Go to Actions → Deploy Prod → Run workflow
```

---

## On-Call & Operations

### For On-Call Engineers

**Start here during incidents**: [ON_CALL_SOP.md](./specs/001-interactive-dashboard-demo/ON_CALL_SOP.md)

12 documented scenarios with step-by-step CLI commands:
- SC-01: Service Degradation
- SC-03: Ingestion Failures
- SC-04: Analysis Failures
- SC-05: Dashboard Failures
- SC-07: NewsAPI Rate Limiting
- SC-08: Budget Alerts
- SC-09: DLQ Accumulation
- And more...

### Monitoring

11 CloudWatch alarms configured in `infrastructure/terraform/modules/monitoring/`:
- Lambda error rates
- Latency thresholds
- SNS delivery failures
- DLQ depth
- Budget alerts

### Quick Diagnostics

```bash
# Check Lambda errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-ingestion \
  --filter-pattern "ERROR" \
  --start-time $(date -d '30 minutes ago' +%s)000

# Check DynamoDB item count
aws dynamodb scan \
  --table-name dev-sentiment-items \
  --select COUNT

# Check active alarms
aws cloudwatch describe-alarms \
  --state-value ALARM \
  --alarm-name-prefix "dev-"
```

---

## Getting Started

### Prerequisites

**Required tools** (install before proceeding):

| Tool | Version | Purpose | Install Link |
|------|---------|---------|--------------|
| **AWS CLI** | v2.x | AWS resource management | [Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| **Terraform** | ≥1.5.0 | Infrastructure as code | [Install Guide](https://developer.hashicorp.com/terraform/downloads) |
| **Python** | 3.11+ | Lambda function development | [Download](https://www.python.org/downloads/) |
| **Git** | ≥2.30 | Version control | [Download](https://git-scm.com/downloads) |
| **jq** | Latest | JSON processing (optional) | [Download](https://jqlang.github.io/jq/download/) |

**Access requirements:**

- ✅ GitHub account with contributor access to this repository
- ✅ AWS IAM credentials (Contributor role - request from @traylorre)
- ❌ **NO production AWS admin access** (principle of least privilege)
- ❌ **NO Terraform Cloud write access** (read-only for contributors)

**Verify installations:**

```bash
aws --version          # Should show: aws-cli/2.x.x
terraform --version    # Should show: Terraform v1.5.x+
python --version       # Should show: Python 3.11.x
git --version          # Should show: git version 2.30+
```

---

### Local Development Setup

**Step 1: Clone and navigate**

```bash
git clone https://github.com/traylorre/sentiment-analyzer-gsk.git
cd sentiment-analyzer-gsk
```

**Step 2: Configure AWS profile (Contributor role)**

```bash
# Create dedicated profile for this project
aws configure --profile sentiment-analyzer-contributor

# Enter credentials provided by project admin:
# AWS Access Key ID: [PROVIDED_BY_ADMIN]
# AWS Secret Access Key: [PROVIDED_BY_ADMIN]
# Default region: us-west-2
# Default output format: json
```

**⚠️ IMPORTANT:** Contributor credentials are **read-only** for:
- CloudWatch dashboards and non-sensitive metrics
- Lambda function logs (sanitized - no secrets)
- DynamoDB table schemas (not data)
- EventBridge rule status

Contributors **CANNOT**:
- Deploy infrastructure changes
- Access Secrets Manager
- Modify IAM roles/policies
- View sensitive CloudWatch metrics (DDoS, quota exhaustion, detailed failure rates)

**Step 3: Verify AWS access**

```bash
# Test read access to CloudWatch
aws cloudwatch list-dashboards \
  --profile sentiment-analyzer-contributor \
  --region us-west-2

# Expected output: List of dashboard names (no error)

# Test Lambda list access (read-only)
aws lambda list-functions \
  --profile sentiment-analyzer-contributor \
  --region us-west-2 \
  --query 'Functions[*].FunctionName'

# Expected output: List of Lambda function names
```

**Step 4: Review project documentation**

```bash
# Read in this order:
1. SPEC.md              # Complete technical specification
2. CONTRIBUTING.md      # Collaboration guidelines
3. SECURITY.md          # Security policy
4. .specify/memory/constitution.md  # High-level requirements
```

**Step 5: Set up Python environment (for Lambda development)**

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -r requirements-dev.txt

# Install git hooks (runs tests before push, formatting before commit)
pre-commit install
pre-commit install --hook-type pre-push
```

---

### Verify Your Setup

Run this verification checklist:

```bash
# ✅ AWS CLI configured
aws sts get-caller-identity --profile sentiment-analyzer-contributor
# Should show: UserId, Account, Arn (contributor role)

# ✅ Can access CloudWatch
aws cloudwatch describe-alarms \
  --profile sentiment-analyzer-contributor \
  --region us-west-2 \
  --max-records 5
# Should list some alarms (or empty list if none exist yet)

# ✅ Terraform works
terraform version
# Should show version ≥1.5.0

# ✅ Git configured
git config user.name && git config user.email
# Should show your name and email
```

**All checks passed?** You're ready to contribute! 🎉

---

## Project Structure

```
sentiment-analyzer-gsk/
├── README.md                    # This file - start here
├── SPEC.md                      # Complete technical specification
├── CONTRIBUTING.md              # Contribution guidelines (MUST READ)
├── SECURITY.md                  # Security policy and vulnerability reporting
├── LICENSE                      # MIT License
│
├── .specify/                    # GitHub Spec-Kit configuration
│   ├── memory/
│   │   └── constitution.md      # High-level project requirements
│   ├── templates/               # Spec-Kit templates
│   └── scripts/                 # Automation scripts
│
├── terraform/                   # Infrastructure as code (when created)
│   ├── modules/                 # Reusable Terraform modules
│   ├── environments/            # Environment-specific configs
│   └── *.tf                     # Root Terraform configuration
│
├── src/                         # Lambda function source code (when created)
│   ├── scheduler/               # EventBridge scheduler Lambda
│   ├── ingestion/               # Source ingestion Lambdas
│   ├── inference/               # Sentiment analysis Lambda
│   └── common/                  # Shared utilities
│
├── tests/                       # Test suites (when created)
│   ├── unit/
│   ├── integration/
│   └── contract/
│
└── .github/                     # GitHub configuration
    ├── workflows/               # CI/CD workflows
    └── CODEOWNERS              # Review assignments
```

**Current stage:** Specification complete, implementation pending

---

## Development Workflow

### Git Hooks (Pre-commit Framework)

This project uses the [pre-commit](https://pre-commit.com/) framework for git hooks.

**One-time setup after cloning:**

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

**What happens automatically:**

- **On commit**: Formatting (black), linting (ruff), Terraform fmt, security checks
- **On push**: Full test suite runs before code is pushed

**Manual commands:**

```bash
# Run all hooks on all files
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate

# Skip hooks (NOT recommended)
git commit --no-verify
```

This ensures code quality before it reaches CI/CD, saving time and preventing failures.

### Standard Workflow for Contributors

**1. Always work on a feature branch:**

```bash
# Create branch from main
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# Branch naming convention:
# - feature/add-rss-parser
# - fix/scheduler-timeout
# - docs/update-readme
```

**2. Make your changes:**

```bash
# Edit files
# Run local tests (when test suite exists)
# Ensure code follows project conventions
```

**3. Commit with clear messages:**

```bash
git add <changed-files>
git commit -m "feat: Add RSS feed parser with XML validation

- Implement feedparser-based RSS ingestion
- Add XXE attack prevention
- Add unit tests for malformed feeds

Addresses: #123"
```

**Commit message format:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `test:` Adding/updating tests
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

**4. Push and create Pull Request:**

```bash
# Push to your branch
git push origin feature/your-feature-name

# GitHub will show link to create PR
# Or go to: https://github.com/traylorre/sentiment-analyzer-gsk/pulls
```

**5. PR Review Process:**

⚠️ **CRITICAL:** All PRs require approval from @traylorre before merge

- ✅ Automated checks run (linting, tests, security scans)
- ✅ CODEOWNERS automatically assigns @traylorre as reviewer
- ✅ GitHub Actions enforces: "Require approval from @traylorre"
- ✅ Branch protection prevents direct push to `main`
- ❌ **Contributors CANNOT merge their own PRs**
- ❌ **Contributors CANNOT bypass review requirements**

**6. After approval:**

```bash
# @traylorre merges the PR (contributors cannot merge)
# Delete your feature branch
git checkout main
git pull origin main
git branch -d feature/your-feature-name
```

---

## Contributing

**Before contributing, you MUST read:**

📖 **[CONTRIBUTING.md](./CONTRIBUTING.md)** - Complete contribution guidelines including:
- Code of conduct
- Collaboration security model
- AWS access policies (Admin vs Contributor roles)
- Secret handling procedures
- Credential rotation process
- Audit trail requirements
- What contributors CAN and CANNOT do

**Quick summary:**
- ✅ Contributors can: View logs, dashboards, create PRs, run read-only AWS commands
- ❌ Contributors cannot: Deploy infra, access secrets, merge PRs, modify IAM

**All contributors are assumed to be potential bad-faith actors** - this is not personal, it's defense-in-depth security.

---

## Security

🔒 **Security is paramount.** This project follows zero-trust principles.

### Reporting Vulnerabilities

**DO NOT create public issues for security vulnerabilities.**

Report privately to: [Configure security contact]

Response time: 48 hours

See [SECURITY.md](./SECURITY.md) for full security policy.

### Security Posture

⚠️ **Service is NOT production-ready** - requires security hardening (see SPEC.md lines 720-881)

**Key security features:**
- Least-privilege IAM roles
- Secrets in AWS Secrets Manager (never in code)
- TLS 1.2+ enforcement
- Input validation on all external data
- NoSQL injection prevention (parameterized DynamoDB queries)
- XXE attack prevention (feedparser secure config)
- Rate limiting and quota management
- Comprehensive audit logging (CloudTrail)

---

## Documentation

### Primary Documents

| Document | Purpose | Audience |
|----------|---------|----------|
| **[README.md](./README.md)** | Getting started, onboarding | All contributors |
| **[SPEC.md](./SPEC.md)** | Complete technical specification | Developers, architects |
| **[CONTRIBUTING.md](./CONTRIBUTING.md)** | Collaboration guidelines | All contributors |
| **[SECURITY.md](./SECURITY.md)** | Security policy | Security researchers, contributors |
| **[constitution.md](./.specify/memory/constitution.md)** | High-level requirements | Product owners, architects |

### Architecture Decision Records (ADRs)

_Coming soon - will document key architectural decisions_

### API Documentation

_Coming soon - OpenAPI/Swagger specs for Admin API_

### Monitoring & Alerts

**CloudWatch Dashboard Access** (Contributors: read-only):
- Service health metrics (request count, success rate)
- Lambda execution metrics (duration, errors)
- DynamoDB metrics (read/write capacity)
- ❌ **NOT accessible:** DDoS metrics, quota exhaustion rates, detailed failure analysis

**Alarm Access** (Contributors: read-only):
- Can view alarm states (OK, ALARM, INSUFFICIENT_DATA)
- Can view alarm history
- ❌ **CANNOT:** Modify alarms, silence alarms, change thresholds

---

## Project Status

**Current Phase:** Implementation (GitHub Spec-Kit Stage 4 🔄)

**Demo 1 Progress:**
1. ✅ Stage 1: Specify - **COMPLETE**
2. ✅ Stage 2: Plan - **COMPLETE**
3. ✅ Stage 3: Tasks - **COMPLETE** (72 tasks defined)
4. 🔄 Stage 4: Implement - **IN PROGRESS**

**Implementation Status:**
- ✅ Phase 1: Project Setup & CI/CD (T001-T011)
- ✅ Phase 2: Shared Libraries (T012-T023)
- ✅ Phase 3: Ingestion Lambda (T024-T031)
- ✅ Phase 4: Analysis Lambda (T032-T038)
- ✅ Phase 5: Dashboard Lambda (T039-T047)
- ✅ Phase 6: Lambda Terraform (T048-T053)
- ✅ Phase 7: Integration (T054-T058)
- ✅ Phase 8: Deployment (T059-T064)
- ✅ Phase 9: Documentation (T065-T072)

**Additional Documentation:**
- [Deployment Guide](docs/DEPLOYMENT.md) - Zero-downtime deployment and rollback
- [Demo Checklist](docs/DEMO_CHECKLIST.md) - Demo day preparation
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

**Tracking:** See [tasks.md](./specs/001-interactive-dashboard-demo/tasks.md)

---

## License

MIT License - See [LICENSE](./LICENSE) file for details.

---

## Maintainers

**Project Owner & Security Admin:**
- @traylorre - All PR approvals, infrastructure deployments, credential management

**Contributors:**
_See [Contributors](https://github.com/traylorre/sentiment-analyzer-gsk/graphs/contributors)_

---

## Questions?

1. Check [SPEC.md](./SPEC.md) for technical details
2. Review [CONTRIBUTING.md](./CONTRIBUTING.md) for collaboration guidelines
3. Search [existing issues](https://github.com/traylorre/sentiment-analyzer-gsk/issues)
4. Ask in PR comments or create a new issue

**Welcome to the project!** 🚀
