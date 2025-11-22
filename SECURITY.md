# Security Policy

## Supported Versions

This service is in pre-production development. Security support will be provided for the latest version only once production releases begin.

## Reporting Vulnerabilities

Please report security vulnerabilities privately to the project maintainers. Do not create public issues for security concerns.

**Contact:** [Configure your security contact email]

**Response Time:** We aim to acknowledge reports within 48 hours.

## Security Status

⚠️ **CRITICAL: Dashboard has P0 vulnerabilities - DO NOT deploy to production without mitigations.**

**Last Security Review**: 2025-11-22
**Status**: BLOCKED FOR PRODUCTION

### Critical Issues (MUST fix before production)

**Dashboard Lambda Function URL** - See `docs/DASHBOARD_SECURITY_ANALYSIS.md` for full details:
- **P0-1**: No rate limiting on Lambda Function URL → Cost drain attack ($100 budget in ~33 hours)
- **P0-2**: ✅ FIXED - SSE connection limits implemented (max 2 per IP)
- **P0-3**: Static API key with no rotation policy → Long-term unauthorized access
- **P0-4**: Lambda Function URL has `auth_type = "NONE"` → No AWS-level authentication
- **P0-5**: ✅ FIXED - CORS wildcard removed, environment-based origins enforced

### High Priority Issues

- **P1-1**: No CloudWatch alarms for anomalous request patterns
- **P1-2**: ✅ FIXED - IP logging added to authentication failures

### Recommended Deployment Architecture

**Before production**, migrate from Lambda Function URL to:
1. **CloudFront CDN** - DDoS protection, geo-blocking
2. **AWS WAF** - IP-based rate limiting, automatic blocking
3. **API Gateway** - Request throttling (100 req/min), custom authorizer
4. **Lambda** (current) - Connection limits, API key rotation

**Estimated Cost**: +$5/month
**Risk Reduction**: 95% (blocks all automated attacks)

Key areas requiring hardening before production deployment:
- ✅ SSE concurrency exhaustion protection (FIXED)
- ✅ CORS wildcard removal (FIXED)
- ✅ IP-based forensic logging (FIXED)
- ⚠️ Rate limiting and quota management (PENDING - requires API Gateway)
- ⚠️ API key rotation policy (PENDING)
- ⚠️ CloudWatch security monitoring alarms (PENDING)

## Architecture Overview

- Serverless AWS infrastructure (Lambda, DynamoDB, EventBridge, API Gateway)
- All secrets managed via AWS Secrets Manager
- API authentication via API Gateway API Keys
- TLS 1.2+ enforced for all external communications

## Known Limitations

This service requires additional security hardening in the following areas:
1. External API integration resilience
2. Cost control mechanisms
3. Operational monitoring and alerting

For implementation requirements, see project specification documentation.

## Security Best Practices

When contributing to this project:
- Never commit credentials, API keys, or secrets
- Use parameterized queries for all database operations
- Validate and sanitize all external inputs
- Follow AWS security best practices for IAM roles and policies
- Enable MFA for all AWS and infrastructure accounts
