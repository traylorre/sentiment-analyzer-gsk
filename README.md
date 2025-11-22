# sentiment-analyzer-gsk

[![Security](https://img.shields.io/badge/security-hardened-green.svg)](./SECURITY.md)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Coverage](https://img.shields.io/badge/coverage-%3E80%25-brightgreen.svg)](./pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Terraform](https://img.shields.io/badge/terraform-%3E%3D1.5-623CE4.svg?logo=terraform)](https://www.terraform.io/)
[![AWS](https://img.shields.io/badge/AWS-Lambda%20%7C%20DynamoDB-FF9900.svg?logo=amazon-aws)](https://aws.amazon.com/)

A cloud-hosted Sentiment Analyzer service built with serverless AWS architecture (Lambda, DynamoDB, EventBridge, SNS/SQS). Features dev/preprod/prod promotion pipeline with automated testing and deployment gates.

## CI/CD Pipeline Status

### PR Checks
[![Code Quality](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-lint.yml/badge.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-lint.yml)
[![Unit Tests](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-test.yml/badge.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-test.yml)
[![Security Scan](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-security.yml/badge.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-security.yml)
[![CodeQL](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-codeql.yml/badge.svg)](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pr-check-codeql.yml)

### Deployment Pipeline
| Stage | Workflow | Status |
|-------|----------|--------|
| **[1/4]** Build Artifacts | [pipeline-1-build.yml](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-1-build.yml) | ![Build](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-1-build.yml/badge.svg) |
| **[2/4]** Deploy to Preprod | [pipeline-2-deploy-preprod.yml](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-2-deploy-preprod.yml) | ![Deploy Preprod](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-2-deploy-preprod.yml/badge.svg) |
| **[3/4]** Preprod Integration Tests | [pipeline-3-test-preprod.yml](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-3-test-preprod.yml) | ![Test Preprod](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-3-test-preprod.yml/badge.svg) |
| **[4/4]** Deploy to Production | [pipeline-4-deploy-prod.yml](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-4-deploy-prod.yml) | ![Deploy Prod](https://github.com/traylorre/sentiment-analyzer-gsk/actions/workflows/pipeline-4-deploy-prod.yml/badge.svg) |

---

## Table of Contents

- [Quick Start](#quick-start)
- [Project Overview](#project-overview)
  - [What This Service Does](#what-this-service-does)
  - [Architecture](#architecture)
  - [Key Features](#key-features)
- [Architecture Diagrams](#architecture-diagrams)
- [Demo: Interactive Dashboard](#demo-interactive-dashboard)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development Setup](#local-development-setup)
  - [Verify Your Setup](#verify-your-setup)
- [Development Workflow](#development-workflow)
  - [Git Hooks](#git-hooks-pre-commit-framework)
  - [Standard Workflow](#standard-workflow-for-contributors)
- [Deployment](#deployment)
  - [Environment Promotion Flow](#environment-promotion-flow)
  - [Deployment Commands](#deployment-commands)
- [On-Call & Operations](#on-call--operations)
  - [For On-Call Engineers](#for-on-call-engineers)
  - [Monitoring](#monitoring)
  - [Quick Diagnostics](#quick-diagnostics)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [Security](#security)
- [Documentation](#documentation)
- [Project Status](#project-status)
- [License](#license)

---

## Quick Start

**For new contributors - complete setup in 10 minutes:**

```bash
# 1. Clone repository
git clone https://github.com/traylorre/sentiment-analyzer-gsk.git
cd sentiment-analyzer-gsk

# 2. Install prerequisites (see Prerequisites section)
# Verify: aws --version, terraform --version, python --version

# 3. Set up Python environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 4. Install git hooks
pre-commit install
pre-commit install --hook-type pre-push

# 5. Run tests locally
pytest

# 6. Read project specification
cat SPEC.md  # or open in your editor

# 7. Review contribution guidelines
cat CONTRIBUTING.md

# 8. Create feature branch
git checkout -b feature/your-feature-name
```

**You're ready to contribute!** See [Development Workflow](#development-workflow) for next steps.

---

## Project Overview

### What This Service Does

Ingests text from external sources (NewsAPI, RSS feeds) and returns sentiment analysis:
- **Sentiment labels**: positive/neutral/negative
- **Confidence scores**: 0.0-1.0 range
- **Real-time & batch processing**: EventBridge scheduler + Lambda processors
- **Deduplication**: Avoids reprocessing duplicate items
- **Live dashboard**: FastAPI + SSE for real-time sentiment streaming

### Architecture

- **Compute**: AWS Lambda (Python 3.11)
- **Orchestration**: EventBridge, SNS, SQS
- **Storage**: DynamoDB (on-demand capacity)
- **Sentiment Model**: DistilBERT (fine-tuned for social media)
- **Infrastructure**: Terraform with S3 backend and DynamoDB locking
- **CI/CD**: GitHub Actions → Dev → Preprod → Prod promotion pipeline

### Key Features

✅ **Serverless & auto-scaling** - No manual capacity management
✅ **Cost-optimized** - Pay-per-use with budget alerts
✅ **Security-first** - Least-privilege IAM, secrets in AWS Secrets Manager
✅ **Observable** - CloudWatch dashboards, alarms, DLQ monitoring
✅ **Multi-environment** - Isolated dev/preprod/prod environments
✅ **Promotion pipeline** - Automated artifact promotion with validation gates

---

## Architecture Diagrams

### High-Level System Architecture

```mermaid
graph TB
    subgraph "External Sources"
        NewsAPI[NewsAPI]
        RSS[RSS Feeds]
    end

    subgraph "AWS Cloud"
        subgraph "Ingestion Layer"
            EB[EventBridge<br/>Scheduler<br/>5 min]
            Ingestion[Ingestion Lambda<br/>Python 3.11]
        end

        subgraph "Processing Layer"
            SNS[SNS Topic<br/>sentiment-events]
            Analysis[Analysis Lambda<br/>DistilBERT]
        end

        subgraph "API Layer"
            Dashboard[Dashboard Lambda<br/>FastAPI + SSE]
            FnURL[Function URL]
        end

        subgraph "Storage Layer"
            DDB[(DynamoDB<br/>sentiment-items)]
            DLQ[DLQ<br/>Failed Messages]
        end

        subgraph "Monitoring"
            CW[CloudWatch<br/>Logs & Alarms]
            Budget[Budget Alerts]
        end
    end

    subgraph "Users"
        Browser[Web Browser]
    end

    EB -->|Trigger| Ingestion
    NewsAPI -->|Fetch Articles| Ingestion
    RSS -->|Fetch Feeds| Ingestion

    Ingestion -->|Publish| SNS
    Ingestion -->|Store| DDB

    SNS -->|Subscribe| Analysis
    Analysis -->|Store Results| DDB
    Analysis -->|Failed| DLQ

    Browser <-->|HTTPS| FnURL
    FnURL <-->|Invoke| Dashboard
    Dashboard -->|Query| DDB
    Dashboard -->|SSE Stream| Browser

    Ingestion -.->|Logs| CW
    Analysis -.->|Logs| CW
    Dashboard -.->|Logs| CW

    CW -.->|Cost Alerts| Budget

    style Ingestion fill:#FF6B6B
    style Analysis fill:#4ECDC4
    style Dashboard fill:#45B7D1
    style DDB fill:#FFA07A
    style SNS fill:#98D8C8
```

### Environment Promotion Pipeline

```mermaid
graph LR
    subgraph "Source"
        Code[Feature Branch]
    end

    subgraph "Build"
        GHA[GitHub Actions<br/>Build & Test]
        Artifact[Lambda Packages<br/>SHA-versioned]
    end

    subgraph "Dev Environment"
        DevDeploy[Deploy Dev]
        DevTest[Integration Tests]
        DevApprove{Tests Pass?}
    end

    subgraph "Preprod Environment"
        PreprodDeploy[Deploy Preprod]
        PreprodTest[Smoke Tests]
        PreprodApprove{Validation<br/>Gate}
    end

    subgraph "Prod Environment"
        ProdApprove{Manual<br/>Approval}
        ProdDeploy[Deploy Prod]
        ProdMonitor[Production<br/>Monitoring]
    end

    Code --> GHA
    GHA --> Artifact
    Artifact --> DevDeploy
    DevDeploy --> DevTest
    DevTest --> DevApprove

    DevApprove -->|✅ Pass| PreprodDeploy
    DevApprove -->|❌ Fail| Code

    PreprodDeploy --> PreprodTest
    PreprodTest --> PreprodApprove

    PreprodApprove -->|✅ Pass| ProdApprove
    PreprodApprove -->|❌ Fail| Code

    ProdApprove -->|✅ Approved| ProdDeploy
    ProdApprove -->|❌ Rejected| Code

    ProdDeploy --> ProdMonitor

    style DevApprove fill:#FFD93D
    style PreprodApprove fill:#FFD93D
    style ProdApprove fill:#FF6B6B
    style Artifact fill:#6BCF7F
```

### Data Flow: Real-Time Sentiment Processing

```mermaid
sequenceDiagram
    participant EB as EventBridge
    participant Ing as Ingestion Lambda
    participant NA as NewsAPI
    participant SNS as SNS Topic
    participant Ana as Analysis Lambda
    participant DDB as DynamoDB
    participant Dash as Dashboard Lambda
    participant User as Browser (SSE)

    EB->>Ing: Trigger (every 5 min)
    Ing->>NA: Fetch latest articles
    NA-->>Ing: Articles JSON

    Ing->>DDB: Check for duplicates
    DDB-->>Ing: Dedup results

    Ing->>DDB: Store raw article
    Ing->>SNS: Publish event

    SNS->>Ana: Trigger analysis
    Ana->>Ana: Run DistilBERT inference
    Ana->>DDB: Store sentiment results

    User->>Dash: Connect SSE stream
    Dash->>DDB: Query sentiment_index
    DDB-->>Dash: Stream results
    Dash-->>User: SSE events (JSON)

    Note over Dash,User: Real-time updates<br/>via Server-Sent Events
```

### DynamoDB Table Design

```mermaid
erDiagram
    SENTIMENT_ITEMS {
        string item_id PK
        string source_type
        string source_id
        string title
        string content
        timestamp ingested_at
        string status
        float sentiment_score
        string sentiment_label
        timestamp analyzed_at
        json tags
    }

    GSI_BY_SENTIMENT {
        string sentiment_label PK
        timestamp analyzed_at SK
        float sentiment_score
    }

    GSI_BY_TAG {
        string tag PK
        timestamp ingested_at SK
    }

    GSI_BY_STATUS {
        string status PK
        timestamp ingested_at SK
    }

    SENTIMENT_ITEMS ||--o{ GSI_BY_SENTIMENT : "indexed by"
    SENTIMENT_ITEMS ||--o{ GSI_BY_TAG : "indexed by"
    SENTIMENT_ITEMS ||--o{ GSI_BY_STATUS : "indexed by"
```

---

## Demo: Interactive Dashboard

**Current Feature**: Real-time sentiment analysis with live dashboard

### Quick Links

| Document | Purpose |
|----------|---------|
| [Quickstart Guide](./specs/001-interactive-dashboard-demo/quickstart.md) | Step-by-step deployment |
| [Implementation Plan](./specs/001-interactive-dashboard-demo/plan.md) | Architecture & design decisions |
| [Feature Spec](./specs/001-interactive-dashboard-demo/spec.md) | Requirements & acceptance criteria |
| [On-Call SOP](./specs/001-interactive-dashboard-demo/ON_CALL_SOP.md) | Incident response runbooks |

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

**Step 2: Set up Python environment**

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

**Step 3: Review project documentation**

```bash
# Read in this order:
1. SPEC.md              # Complete technical specification
2. CONTRIBUTING.md      # Collaboration guidelines
3. SECURITY.md          # Security policy
4. docs/DEPLOYMENT.md   # Deployment procedures
```

---

### Verify Your Setup

Run this verification checklist:

```bash
# ✅ Python environment
python --version
# Should show Python 3.11+

# ✅ Dependencies installed
pytest --version
black --version
ruff --version

# ✅ Git configured
git config user.name && git config user.email
# Should show your name and email

# ✅ Pre-commit hooks installed
pre-commit --version
# Should show pre-commit version
```

**All checks passed?** You're ready to contribute! 🎉

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
# Run local tests
pytest

# Ensure code follows project conventions
black src/ tests/
ruff check src/ tests/
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

---

## Deployment

### Environment Promotion Flow

This project uses a three-stage promotion pipeline:

1. **Dev** - Deploys automatically on merge to `main`
2. **Preprod** - Artifact promotion via `build-and-promote.yml` workflow
3. **Prod** - Manual deployment after preprod validation

### Deployment Commands

**Dev Deployment (Automatic):**
```bash
# Automatically triggers on merge to main
# Or manually trigger via:
gh workflow run deploy-dev.yml --repo traylorre/sentiment-analyzer-gsk
```

**Preprod Deployment (Artifact Promotion):**
```bash
# Build and promote to preprod
gh workflow run build-and-promote.yml \
  --repo traylorre/sentiment-analyzer-gsk \
  --ref feat/promotion-pipeline-setup

# Check preprod deployment status
gh run list --workflow=build-and-promote.yml --limit 1
```

**Prod Deployment (Manual Approval Required):**
```bash
# Only after preprod validation passes
gh workflow run deploy-prod.yml --repo traylorre/sentiment-analyzer-gsk
```

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment procedures and rollback strategies.

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

## Project Structure

```
sentiment-analyzer-gsk/
├── README.md                    # This file - start here
├── SPEC.md                      # Complete technical specification
├── CONTRIBUTING.md              # Contribution guidelines
├── SECURITY.md                  # Security policy and vulnerability reporting
├── LICENSE                      # MIT License
│
├── .specify/                    # GitHub Spec-Kit configuration
│   ├── memory/
│   │   └── constitution.md      # High-level project requirements
│   └── templates/               # Spec-Kit templates
│
├── infrastructure/              # Infrastructure as code
│   ├── terraform/               # Terraform root module
│   │   ├── modules/             # Reusable Terraform modules
│   │   │   ├── lambda/          # Lambda function module
│   │   │   ├── dynamodb/        # DynamoDB table module
│   │   │   ├── secrets/         # Secrets Manager module
│   │   │   ├── iam/             # IAM roles and policies
│   │   │   └── monitoring/      # CloudWatch alarms
│   │   ├── main.tf              # Root configuration
│   │   ├── variables.tf         # Input variables
│   │   └── outputs.tf           # Output values
│   └── scripts/                 # Helper scripts
│
├── src/                         # Lambda function source code
│   ├── ingestion/               # Ingestion Lambda
│   ├── analysis/                # Analysis Lambda
│   ├── dashboard/               # Dashboard Lambda (FastAPI)
│   └── common/                  # Shared utilities
│
├── tests/                       # Test suites
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── contract/                # Contract tests
│
├── docs/                        # Project documentation
│   ├── DEPLOYMENT.md            # Deployment guide
│   ├── DEMO_CHECKLIST.md        # Demo preparation
│   ├── TROUBLESHOOTING.md       # Common issues
│   └── IAM_TERRAFORM_TROUBLESHOOTING.md  # IAM debugging guide
│
├── specs/                       # Feature specifications
│   └── 001-interactive-dashboard-demo/
│       ├── spec.md              # Feature requirements
│       ├── plan.md              # Implementation plan
│       ├── tasks.md             # Task breakdown
│       ├── quickstart.md        # Getting started
│       └── ON_CALL_SOP.md       # Operations runbook
│
└── .github/                     # GitHub configuration
    ├── workflows/               # CI/CD workflows
    │   ├── test.yml             # Run tests
    │   ├── lint.yml             # Code quality checks
    │   ├── deploy-dev.yml       # Dev deployment
    │   ├── build-and-promote.yml # Preprod promotion
    │   └── deploy-prod.yml      # Prod deployment
    └── CODEOWNERS               # Review assignments
```

---

## Contributing

**Before contributing, you MUST read:**

📖 **[CONTRIBUTING.md](./CONTRIBUTING.md)** - Complete contribution guidelines including:
- Code of conduct
- Development workflow
- Testing requirements
- PR review process
- Security best practices

**Quick summary:**
- ✅ Contributors can: Create PRs, run tests, view documentation
- ❌ Contributors cannot: Merge PRs without approval, modify IAM directly

**All contributions require:**
- Passing tests (`pytest`)
- Code formatting (`black`, `ruff`)
- Security scans (automated via pre-commit)
- Review approval from @traylorre

---

## Security

🔒 **Security is paramount.** This project follows zero-trust principles.

### Reporting Vulnerabilities

**DO NOT create public issues for security vulnerabilities.**

Report privately to: @traylorre

Response time: 48 hours

See [SECURITY.md](./SECURITY.md) for full security policy.

### Security Posture

**Key security features:**
- Least-privilege IAM roles
- Secrets in AWS Secrets Manager (never in code)
- TLS 1.2+ enforcement
- Input validation on all external data
- NoSQL injection prevention (parameterized DynamoDB queries)
- Rate limiting and quota management
- Comprehensive audit logging (CloudTrail)
- Automated security scanning (pre-commit hooks)

---

## Documentation

### Primary Documents

| Document | Purpose | Audience |
|----------|---------|----------|
| **[README.md](./README.md)** | Getting started, onboarding | All contributors |
| **[SPEC.md](./SPEC.md)** | Complete technical specification | Developers, architects |
| **[CONTRIBUTING.md](./CONTRIBUTING.md)** | Collaboration guidelines | All contributors |
| **[SECURITY.md](./SECURITY.md)** | Security policy | Security researchers, contributors |
| **[DEPLOYMENT.md](./docs/DEPLOYMENT.md)** | Deployment procedures | DevOps, on-call |
| **[IAM_TERRAFORM_TROUBLESHOOTING.md](./docs/IAM_TERRAFORM_TROUBLESHOOTING.md)** | IAM debugging guide | DevOps, on-call |

### Operations Documentation

| Document | Purpose |
|----------|---------|
| [ON_CALL_SOP.md](./specs/001-interactive-dashboard-demo/ON_CALL_SOP.md) | Incident response runbooks |
| [TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [DEMO_CHECKLIST.md](./docs/DEMO_CHECKLIST.md) | Demo day preparation |

---

## Project Status

**Current Phase:** Promotion Pipeline Setup 🔄

**Recent Milestones:**
1. ✅ Demo 1: Interactive Dashboard - **COMPLETE**
2. ✅ Dev Environment - **DEPLOYED**
3. 🔄 Preprod Environment - **IN PROGRESS**
4. ⏳ Prod Environment - **PENDING**

**Deployment Pipeline Status:**
- ✅ Build & Test - Automated
- ✅ Dev Deploy - Automated on merge to `main`
- 🔄 Preprod Deploy - Artifact promotion via workflow
- ⏳ Prod Deploy - Manual approval required

**Tracking:** See [GitHub Actions](https://github.com/traylorre/sentiment-analyzer-gsk/actions)

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
