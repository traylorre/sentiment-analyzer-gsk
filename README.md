# sentiment-analyzer-gsk

[![CI](https://img.shields.io/badge/ci-GitHub%20Actions-blue.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions)
[![Security](https://img.shields.io/badge/security-hardened-green.svg)](./SECURITY.md)

A cloud-hosted Sentiment Analyzer service built with serverless AWS architecture (Lambda, DynamoDB, EventBridge, SNS/SQS). Developed using [GitHub Spec-Kit](https://github.com/github/spec-kit) methodology for specification-driven development.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Project Overview](#project-overview)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development Setup](#local-development-setup)
  - [Verify Your Setup](#verify-your-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
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

# Install development dependencies (when available)
# pip install -r requirements-dev.txt

# Install pre-commit hooks (when configured)
# pre-commit install
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

**Current Phase:** Specification Complete (GitHub Spec-Kit Stage 1 ✅)

**Next Steps:**
1. ✅ Stage 1: Specify - **COMPLETE**
2. 🔄 Stage 2: Plan - In progress (implementation planning)
3. ⏳ Stage 3: Tasks - Pending (task breakdown)
4. ⏳ Stage 4: Implement - Pending (development)

**Tracking:** See GitHub Issues and Projects

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
