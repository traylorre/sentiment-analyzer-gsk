# Specification: Security-First Drift Burndown

**Feature**: 090-security-first-burndown
**Date**: 2025-12-11
**Priority**: P1 (Critical - Security & Compliance)
**Status**: Draft
**Input**: RESULT4-drift-audit.md findings

## Overview

Address P1 security findings from the drift audit (RESULT4):
1. Migrate 4 legacy IAM ARN patterns to `*-sentiment-*` format
2. Create new deployer users with correct naming convention
3. Add SRI (Subresource Integrity) attributes to CDN scripts
4. Configure CSP (Content Security Policy) headers in CloudFront
5. Add Dockerfile USER directive to SSE Lambda image
6. Create `/sri-validate` methodology for ongoing SRI compliance

## Context

### RESULT4 Findings (Security-Related)

| Finding | File | Severity | Category |
|---------|------|----------|----------|
| 4 legacy IAM ARN patterns | `ci-user-policy.tf` | HIGH | IAM |
| Missing SRI integrity | `chaos.html:15-16`, `index.html:8` | MEDIUM | Supply Chain |
| Wildcard CORS | `handler.py:48` | HIGH | Acknowledged |
| tarfile traversal | `sentiment.py:117` | HIGH | Acknowledged |
| Missing Dockerfile USER | `Dockerfile:45` | MEDIUM | Container Security |

### Legacy IAM Patterns to Migrate

```
Current (Legacy):
- arn:aws:iam::*:user/sentiment-analyzer-*-deployer
- arn:aws:s3:::sentiment-analyzer-terraform-state-*
- arn:aws:s3:::sentiment-analyzer-terraform-state-*/*
- arn:aws:kms:*:*:alias/sentiment-analyzer-*

Target (New):
- arn:aws:iam::*:user/*-sentiment-deployer
- arn:aws:s3:::*-sentiment-tfstate
- arn:aws:s3:::*-sentiment-tfstate/*
- arn:aws:kms:*:*:alias/*-sentiment-*
```

### CDN Scripts Requiring SRI

| Script | URL | Hash Required |
|--------|-----|---------------|
| Tailwind CSS | `https://cdn.tailwindcss.com` | sha384-... |
| DaisyUI | `https://cdn.jsdelivr.net/npm/daisyui@4.12.14/dist/full.min.css` | sha384-... |
| Chart.js | `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js` | sha384-... |

## User Stories

### US1: IAM Migration (P1)

**As a** DevSecOps engineer
**I want** deployer users named with `{env}-sentiment-deployer` pattern
**So that** IAM policy ARN patterns match resource names consistently

**Acceptance Criteria**:
- [ ] New deployer users created: `preprod-sentiment-deployer`, `prod-sentiment-deployer`
- [ ] IAM policy ARN patterns updated to `*-sentiment-*`
- [ ] Legacy patterns removed from `ci-user-policy.tf`
- [ ] Old deployer users deprecated (not deleted until migration verified)
- [ ] `make check-iam-patterns` passes with 0 errors

### US2: SRI Implementation (P1)

**As a** security engineer
**I want** all CDN scripts protected by SRI integrity attributes
**So that** supply chain attacks via CDN compromise are mitigated

**Acceptance Criteria**:
- [ ] All `<script>` tags with CDN URLs have `integrity` and `crossorigin` attributes
- [ ] All `<link>` tags with CDN URLs have `integrity` and `crossorigin` attributes
- [ ] SHA384 hashes used (stronger than SHA256)
- [ ] `/sri-validate` methodology created via `/add-methodology`
- [ ] Validator detects missing SRI on CDN scripts

### US3: CSP Headers (P2)

**As a** security engineer
**I want** Content Security Policy headers on CloudFront responses
**So that** XSS attacks are mitigated through browser enforcement

**Acceptance Criteria**:
- [ ] CloudFront response headers policy created with CSP
- [ ] CSP includes `script-src` with CDN domains and 'self'
- [ ] CSP includes `style-src` with CDN domains and 'self'
- [ ] `default-src 'self'` as baseline
- [ ] Policy attached to CloudFront distribution behavior

### US4: Dockerfile Security (P2)

**As a** security engineer
**I want** SSE Lambda container to run as non-root user
**So that** container escape attacks have reduced impact

**Acceptance Criteria**:
- [ ] `lambda` user created with UID 1000
- [ ] `USER lambda` directive added before CMD
- [ ] Container builds successfully
- [ ] Lambda function URL still works

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | `make check-iam-patterns` passes with 0 legacy errors | `make check-iam-patterns \| grep -c "LEGACY" == 0` |
| SC-002 | All 3 CDN scripts have SRI integrity attributes | `grep -c integrity src/dashboard/*.html == 3` |
| SC-003 | `/sri-validate` command exists and detects missing SRI | `ls .claude/commands/sri-validate.md` |
| SC-004 | CloudFront CSP header configured | Terraform plan shows `content_security_policy` |
| SC-005 | Dockerfile runs as non-root | `grep -c "USER lambda" Dockerfile == 1` |
| SC-006 | Lambda function URL responds (smoke test) | `curl -s $SSE_URL/health \| jq .status` |

## Non-Functional Requirements

### NFR-001: Backward Compatibility
- Legacy deployer users must remain functional during migration
- Rollback plan if new users fail

### NFR-002: No Service Disruption
- CloudFront CSP must not break existing functionality
- SRI hashes must be correct (verified locally first)

### NFR-003: Methodology Consistency
- `/sri-validate` must follow template repo methodology structure
- Validator file: `src/validators/sri.py`
- Tests file: `tests/unit/test_sri_validator.py`
- Command file: `.claude/commands/sri-validate.md`

## Technical Approach

### IAM Migration Strategy

1. **Phase 1: Create new users** (no impact to existing)
   - Create `preprod-sentiment-deployer` IAM user
   - Create `prod-sentiment-deployer` IAM user
   - Attach same policies as legacy users

2. **Phase 2: Update IAM policy patterns**
   - Update ARN patterns in `ci-user-policy.tf`
   - Remove legacy `sentiment-analyzer-*` patterns
   - Keep both old and new patterns temporarily

3. **Phase 3: Update CI/CD credentials**
   - Generate new access keys for new users
   - Update GitHub secrets
   - Test deployment pipeline

4. **Phase 4: Deprecate legacy users**
   - Remove legacy patterns from policy
   - Disable (not delete) old users
   - Monitor for any access attempts

### SRI Implementation Strategy

1. **Generate SRI hashes** using `openssl` or online tools
2. **Update HTML files** with integrity and crossorigin attributes
3. **Create validator** to detect missing SRI on CDN scripts
4. **Add methodology** via `/add-methodology` command

### CSP Implementation Strategy

1. **Define CSP policy** starting with restrictive baseline
2. **Create CloudFront response headers policy** in Terraform
3. **Attach policy** to CloudFront distribution behavior
4. **Test** that CDN scripts still load correctly

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| IAM migration breaks CI/CD | Medium | High | Test with both credentials before switching |
| SRI hash mismatch | Low | Medium | Verify hashes locally before commit |
| CSP breaks functionality | Medium | Medium | Start with report-only mode if needed |
| Dockerfile change breaks Lambda | Low | Medium | Test container locally first |

## Dependencies

- AWS Console/CLI access for IAM user creation
- GitHub Admin access for secrets update
- CloudFront distribution access for response headers
- ECR access for container image rebuild

## Clarification Answers (Pass 1)

### Q1: CI/CD Secrets Update
**Answer**: Automate with `gh CLI`
- Use `gh secret set` to update AWS credentials programmatically
- Requires `repo` scope token (available in Claude Code environment)

### Q2: CDN Versioning Strategy
**Answer**: Use latest with CI hash check
- Don't pin to exact versions (allows security patches)
- Add CI job to detect SRI hash changes and alert
- `/sri-validate` will check hashes match

### Q3: Methodology Index
**Answer**: Create `index.yaml`
- Create `.specify/methodologies/index.yaml` matching template structure
- Add SRI methodology entry
- Enable future methodology additions

### Q4: Container Permissions
**Answer**: Verify /tmp access works
- Lambda provides writable /tmp by default for all users
- Test that `lambda` user can write to /tmp during build verification
- No explicit chmod needed

## Clarification Answers (Pass 2)

### Q5: AWS Permissions for IAM Creation
**Answer**: Document prerequisite
- Admin manually creates IAM users via AWS Console/CLI
- Follows AWS Well-Architected principle: separation of concerns
- CI/CD consumes credentials, never creates them
- Avoids chicken-egg bootstrap problem

### Q6: CloudFront Policy Approach
**Answer**: Check and extend
- Read existing policy first to preserve HSTS, X-Frame-Options, etc.
- Only add CSP if missing
- Never remove existing security headers
- Safe incremental approach

### Q7: SRI Validator Scope
**Answer**: All HTML files
- Scan all `*.html` files in repository
- Include configurable excludes for test fixtures
- Default excludes: `tests/fixtures/`, `node_modules/`

## Out of Scope

- Wildcard CORS fix (environment-specific, documented)
- tarfile traversal fix (false positive, uses nosec)
- Full CSP report-uri implementation (future work)

## Canonical Sources

### SRI
- [MDN: Subresource Integrity](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity)
- [OWASP: Subresource Integrity](https://owasp.org/www-community/controls/SubresourceIntegrity)
- [MDN: SRI Implementation Guide](https://developer.mozilla.org/en-US/docs/Web/Security/Practical_implementation_guides/SRI)

### CSP
- [AWS: CloudFront Response Headers Policy](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/understanding-response-headers-policies.html)
- [MDN: Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy)
- [AWS: Add HTTP Security Headers to CloudFront](https://repost.aws/knowledge-center/cloudfront-http-security-headers)

### IAM
- [AWS: IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [AWS: IAM Naming Conventions Blog](https://aws.amazon.com/blogs/security/working-backward-from-iam-policies-and-principal-tags-to-standardized-names-and-tags-for-your-aws-resources/)
- [AWS: Rename IAM User](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users_rename.html)

### Container Security
- [AWS: Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Docker: Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

## Related

- RESULT4-drift-audit.md (input)
- RESULT3-deferred-debt-status.md (context)
- Template: `.specify/methodologies/index.yaml` (methodology structure)
