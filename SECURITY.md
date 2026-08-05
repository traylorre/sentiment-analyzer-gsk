# Security Policy

## Supported Versions

This service is in pre-production development. Security support will be provided for the latest version only once production releases begin.

## Reporting Vulnerabilities

Please report security vulnerabilities privately to the project maintainers. Do not create public issues for security concerns.

**Contact:** [Configure your security contact email]

**Response Time:** We aim to acknowledge reports within 48 hours.

## Security Status

✅ **Feature 006 Security Enhancements Implemented**


### Critical Issues Status

**Dashboard Lambda Security**:
- **P0-1**: ✅ FIXED - IP-based rate limiting with DynamoDB tracking
- **P0-2**: ✅ FIXED - SSE connection limits implemented (max 2 per IP)
- **P0-3**: ✅ FIXED - Cognito authentication replaces static API key
- **P0-4**: ✅ FIXED - Cognito JWT validation at Lambda level
- **P0-5**: ✅ FIXED - CORS environment-based origins enforced

### High Priority Issues

- **P1-1**: ✅ FIXED - CloudWatch alarms for error rates, cost burn, notification delivery
- **P1-2**: ✅ FIXED - IP logging added to authentication failures

### Feature 006 Security Additions

- **Circuit Breaker**: Per-service protection (Tiingo, Finnhub, SendGrid)
- **Quota Tracking**: External API rate limit management
- **X-Ray Tracing**: Day 1 mandatory on all 6 Lambdas
- **hCaptcha**: Bot protection for sensitive endpoints
- **Magic Links**: HMAC-signed passwordless authentication

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
- ✅ Rate limiting and quota management (FIXED - IP-based with DynamoDB)
- ✅ Cognito authentication replaces static API keys (FIXED)
- ✅ CloudWatch security monitoring alarms (FIXED - error rate, cost, delivery alarms)

## Architecture Overview

- Serverless AWS infrastructure (Lambda, DynamoDB, EventBridge, SNS, CloudFront, Cognito)
- All secrets managed via AWS Secrets Manager with 5-minute TTL caching
- Authentication via AWS Cognito (JWT tokens, OAuth providers, magic links)
- External APIs: Tiingo (primary), Finnhub (secondary), SendGrid (notifications)
- X-Ray distributed tracing on all 6 Lambdas
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

## Claims vs controls

Each claim above checked against live code and terraform: whether a live control backs it, and where.

Backed by a live control:

- IP-based rate limiting (P0-1): per-IP, per-action limits tracked in DynamoDB with TTL cleanup. `src/lambdas/shared/middleware/rate_limit.py`.
- Cognito authentication (P0-3, P0-4): backing infrastructure exists. `infrastructure/terraform/modules/cognito/`.
- hCaptcha bot protection: `src/lambdas/shared/middleware/hcaptcha.py`.
- Magic links (HMAC-signed passwordless authentication): `src/lambdas/dashboard/auth.py`.
- Secrets Manager 5-minute TTL caching: `DEFAULT_CACHE_TTL_SECONDS = 300` at `src/lambdas/shared/secrets.py:45`.

Not backed, or wrong in detail:

- SSE connection limits "max 2 per IP" (P0-2): the code enforces a global cap of 100 connections (`MAX_CONNECTIONS` at `src/lambdas/dashboard/sse.py:60`). No per-IP limit of 2 exists anywhere in the codebase.
- X-Ray "on all 6 Lambdas" (stated twice above): terraform declares 7 Lambda modules in `infrastructure/terraform/main.tf` (ingestion, analysis, dashboard, metrics, notification, sse_streaming, canary), of which 6 carry `tracing_mode = "Active"`.
- Recommended Deployment Architecture: stale as a recommendation because the migration already happened. API Gateway at `infrastructure/terraform/main.tf:859`, WAF at `infrastructure/terraform/main.tf:932`, CloudFront for SSE at `infrastructure/terraform/main.tf:966`, dashboard `create_function_url = false` at `infrastructure/terraform/main.tf:508`. One detail remains open: the sse_streaming Lambda keeps a Function URL (`infrastructure/terraform/main.tf:824`, AWS_IAM auth with response streaming).
- Security contact: the value on line 11 is the unconfigured placeholder text, in a public-facing policy.
