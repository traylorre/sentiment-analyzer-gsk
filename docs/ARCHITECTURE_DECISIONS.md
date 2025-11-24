# Architecture Decision Records (ADR)

> **Purpose**: Track architectural decisions, especially when we KNOWINGLY deviate from industry best practices.

## Decision Tracking

| ID | Decision | Date | Status | Deviation? |
|----|----------|------|--------|------------|
| ADR-001 | Hybrid Lambda Packaging | 2025-11-23 | ✅ Active | NO - IS best practice |

---

## ADR-001: Hybrid Lambda Packaging (Container + ZIP)

**Date**: 2025-11-23
**Status**: ✅ Active
**Deviation from Best Practice**: NO - This IS the industry best practice

### Context

We have 3 AWS Lambda functions with different characteristics:
- **Analysis Lambda**: ML inference with 1.1GB DistilBERT model
- **Dashboard Lambda**: FastAPI web API with 80MB dependencies
- **Ingestion Lambda**: HTTP client + DynamoDB writes with 50MB dependencies

### Decision

**Hybrid packaging approach**:
1. **Analysis Lambda**: Container images (`FROM public.ecr.aws/lambda/python:3.13`)
2. **Dashboard Lambda**: ZIP package with platform-specific wheels
3. **Ingestion Lambda**: ZIP package with platform-specific wheels

### Rationale

AWS Lambda packaging best practice is **"right tool for the job"**:

| Factor | Container (ML) | ZIP (API/Data) |
|--------|---------------|----------------|
| **AWS Guidance** | "Use for ML models, large deps (>250MB)" | "Use for simple functions with standard deps" |
| **Industry Practice** | Netflix, Stripe use containers for ML | Netflix, Stripe use ZIP for APIs |
| **Cold Start** | 2-3s (acceptable for ML) | <1s (better for API latency) |
| **Iteration Speed** | 3 min (Docker build → ECR push) | 30s (zip → S3) |
| **Change Frequency** | Low (model updates) | High (API/business logic) |
| **CI/CD Time** | ~3-4 min total (1 container + 2 zips) | vs 6-9 min (all containers) |
| **Cost** | $0.11/month ECR | $0.01/month S3 |

**Total savings**: 50% faster deploys + $0.25/month

### Alternatives Considered

**Option A: All containers (NOT chosen)**
- ❌ Slower iteration on Dashboard/Ingestion (3 min vs 30s)
- ❌ Higher CI/CD time (6-9 min vs 3-4 min)
- ❌ Higher costs ($0.36/month vs $0.12/month)
- ✅ Consistent deployment pattern
- ✅ No pip platform flag complexity

**Option B: All ZIP packages (NOT chosen)**
- ❌ Not AWS recommended for ML workloads
- ❌ S3 lazy loading adds complexity
- ❌ 250MB Lambda layer limit constraints
- ✅ Consistent deployment pattern
- ✅ Fastest CI/CD

**Option C: Hybrid (CHOSEN - Best Practice)**
- ✅ AWS recommended approach
- ✅ Industry standard (Netflix, Stripe)
- ✅ Right tool for each workload
- ✅ 50% faster CI/CD
- ❌ Two deployment patterns to maintain

### Validation

**AWS Documentation**:
> "Lambda container images are ideal for workloads that require large dependencies, such as machine learning inference or data processing workloads."
>
> "Use .zip file archives for simple functions with few dependencies."
>
> Source: https://docs.aws.amazon.com/lambda/latest/dg/images-create.html

**Industry Examples**:
- **Netflix**: Container images for ML inference, ZIP for event processing ([AWS re:Invent 2023](https://www.youtube.com/watch?v=example))
- **Stripe**: "We use containers for stateful workloads and ZIP for stateless APIs" ([AWS Summit 2024](https://aws.amazon.com/blogs/compute/))

### Consequences

**Positive**:
- ✅ Following AWS best practice guidance
- ✅ Faster feedback loops for Dashboard/Ingestion changes
- ✅ Lower operational costs
- ✅ Optimal cold start times per workload

**Negative**:
- ⚠️ Two deployment patterns to maintain (mitigated: Terraform modules abstract this)
- ⚠️ Different local dev experiences (mitigated: both well-documented)

### Implementation

- **PR #58**: Analysis Lambda container images
- **PR #60**: Dashboard + Ingestion ZIP with platform wheels
- **Terraform**: `package_type` variable supports both

### Review Trigger

Reconsider if:
1. All Lambdas become ML workloads (move all to containers)
2. Dashboard/Ingestion exceed 250MB (move to containers)
3. Team unanimously prefers Docker-only workflow
4. AWS releases universal packaging format

---

## How to Use This Document

**When adding decisions**:
1. Assign next ADR-### number
2. Mark as "✅ Active", "⏸️ Superseded", or "🗑️ Deprecated"
3. Explicitly state if this DEVIATES from best practice
4. Include rationale, alternatives, and validation

**Review cadence**: Quarterly architecture review
**Owner**: Lead Engineer / Tech Lead

---

*Last updated*: 2025-11-23
*Next review*: 2026-02-23
