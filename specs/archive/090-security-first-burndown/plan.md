# Implementation Plan: Security-First Drift Burndown

**Branch**: `090-security-first-burndown` | **Date**: 2025-12-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/090-security-first-burndown/spec.md`

## Summary

Address P1 security findings from RESULT4 drift audit by migrating 4 legacy IAM patterns, creating new deployer users, adding SRI to CDN scripts, configuring CSP headers, fixing Dockerfile security, and creating `/sri-validate` methodology.

## Technical Context

**Language/Version**: Python 3.13, Terraform 1.5+, HTML5
**Primary Dependencies**: boto3, gh CLI, openssl
**Target Platform**: AWS (IAM, CloudFront, ECR, Lambda)
**Project Type**: Security hardening + methodology creation
**Constraints**: Must not break existing deployments during migration

## Constitution Check

| Constitution Requirement | Status | Notes |
|--------------------------|--------|-------|
| **7) Testing & Validation** | ✅ PASS | Validator tests for SRI methodology |
| **8) Git Workflow** | ✅ PASS | Feature branch, GPG signing |
| **10) Local SAST** | ✅ PASS | SRI validator is SAST tool |
| IAM Best Practices | ✅ PASS | Follows AWS naming conventions |

**Gate Result**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/090-security-first-burndown/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── tasks.md             # Phase 2 output
└── quickstart.md        # Setup guide
```

### Code Changes

```text
infrastructure/terraform/
├── ci-user-policy.tf    # Update IAM ARN patterns
└── modules/cloudfront/
    └── main.tf          # Add CSP response headers policy

src/dashboard/
├── index.html           # Add SRI attributes
└── chaos.html           # Add SRI attributes

src/lambdas/sse_streaming/
└── Dockerfile           # Add USER directive

.specify/methodologies/
└── index.yaml           # NEW: Methodology registry

src/validators/
└── sri.py               # NEW: SRI validator

tests/unit/
└── test_sri_validator.py # NEW: Validator tests

.claude/commands/
└── sri-validate.md      # NEW: Slash command

.github/workflows/
└── pr-checks.yml        # Add SRI hash verification job
```

## Phase 0: Research

### Research Tasks

1. **SRI Hash Generation**: Identify method to generate SHA384 hashes for CDN URLs
2. **CloudFront CSP**: Review Terraform `aws_cloudfront_response_headers_policy` resource
3. **IAM User Creation**: Verify AWS CLI/Terraform approach for new users
4. **Template Methodology**: Review template repo methodology structure

### Research Findings

**SRI Hash Generation**:
```bash
# For remote URLs
curl -s https://cdn.tailwindcss.com | openssl dgst -sha384 -binary | openssl base64 -A
```

**CloudFront CSP** (Terraform):
```hcl
resource "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "${var.environment}-sentiment-security-headers"

  security_headers_config {
    content_security_policy {
      content_security_policy = "default-src 'self'; script-src 'self' cdn.tailwindcss.com cdn.jsdelivr.net; style-src 'self' cdn.jsdelivr.net 'unsafe-inline'"
      override = true
    }
  }
}
```

**IAM User Creation** (AWS CLI):
```bash
aws iam create-user --user-name preprod-sentiment-deployer
aws iam create-access-key --user-name preprod-sentiment-deployer
```

See [research.md](./research.md) for detailed findings.

## Phase 1: Design

### Component 1: IAM Migration

```
Current State:
- Users: sentiment-analyzer-preprod-deployer, sentiment-analyzer-prod-deployer
- Patterns: sentiment-analyzer-* (legacy)

Target State:
- Users: preprod-sentiment-deployer, prod-sentiment-deployer
- Patterns: *-sentiment-* (consistent with resources)
```

**Migration Steps**:
1. Create new IAM users via AWS CLI
2. Generate access keys
3. Update GitHub secrets via `gh secret set`
4. Update Terraform IAM policy patterns
5. Test deployment with new credentials
6. Disable legacy users (keep for rollback)

### Component 2: SRI Implementation

**Files to Update**:
| File | CDN Resources | Action |
|------|--------------|--------|
| `src/dashboard/index.html` | chart.js | Add integrity + crossorigin |
| `src/dashboard/chaos.html` | tailwind, daisyui | Add integrity + crossorigin |

**SRI Validator Detection Patterns**:
```python
# Detect CDN script/link without integrity
r'<script[^>]+src=["\']https?://[^"\']+["\'][^>]*(?!integrity)'
r'<link[^>]+href=["\']https?://[^"\']+["\'][^>]*(?!integrity)'
```

### Component 3: CSP Headers

**Policy Definition**:
```
default-src 'self';
script-src 'self' cdn.tailwindcss.com cdn.jsdelivr.net 'unsafe-inline';
style-src 'self' cdn.jsdelivr.net 'unsafe-inline';
img-src 'self' data:;
connect-src 'self' *.amazonaws.com;
frame-ancestors 'none';
```

### Component 4: Dockerfile Security

```dockerfile
# Create non-root user
RUN adduser --disabled-password --gecos '' --uid 1000 lambda

# Switch to non-root user before CMD
USER lambda
CMD ["python", "-m", "uvicorn", "handler:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Component 5: SRI Methodology

**Files to Create**:
1. `.specify/methodologies/index.yaml` - Registry (copy structure from template)
2. `src/validators/sri.py` - SRI validator
3. `tests/unit/test_sri_validator.py` - Unit tests
4. `.claude/commands/sri-validate.md` - Slash command
5. `docs/sri-methodology.md` - Documentation

## Decision Log

| Decision | Rationale | Alternative Rejected |
|----------|-----------|---------------------|
| Use AWS CLI for IAM users | Direct control, no Terraform state conflict | Terraform (state management complexity) |
| SHA384 for SRI | Strongest commonly-used algorithm | SHA256 (weaker), SHA512 (overkill) |
| Create methodology index | Template parity, future extensibility | Skip index (drift from template) |
| Lambda user UID 1000 | Standard convention for containerized apps | nobody (less explicit) |

## Blind Spot Detection (Pre-Plan)

### Potential Blind Spots Identified

1. **CDN URL Changes**: What if CDN provider changes URL structure?
   - Mitigation: Pin to specific CDN paths, document update process

2. **SRI Hash Invalidation**: CDN content changes break SRI
   - Mitigation: CI job detects hash changes, alerts for update

3. **CSP Breaking Inline Scripts**: App may use inline scripts
   - Mitigation: Review codebase for inline scripts, add 'unsafe-inline' if needed

4. **IAM Policy Propagation Delay**: AWS IAM changes take time to propagate
   - Mitigation: Wait/retry logic in CI tests

5. **GitHub Secrets Scope**: Secrets may be environment-scoped
   - Mitigation: Set both repository and environment secrets

## Phase 2: Tasks

Tasks will be generated by `/speckit.tasks` command after second clarify pass.

## Verification Checklist

- [ ] `make check-iam-patterns` passes
- [ ] All HTML files have SRI on CDN resources
- [ ] `/sri-validate` command works
- [ ] CloudFront returns CSP header
- [ ] Dockerfile builds with non-root user
- [ ] Lambda function URL responds
- [ ] CI pipeline passes with new credentials
