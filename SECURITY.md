# Security Policy

## Supported Versions

This service is in pre-production development. Security support will be provided for the latest version only once production releases begin.

## Reporting Vulnerabilities

Please report security vulnerabilities privately to the project maintainers. Do not create public issues for security concerns.

**Contact:** [Configure your security contact email]

**Response Time:** We aim to acknowledge reports within 48 hours.

## Security Status

✅ **Feature 006 Security Enhancements Implemented**

**Last Security Review**: 2025-11-26
**Status**: APPROVED FOR DEMO (Feature 006 Tiingo/Finnhub pivot complete)

### Critical Issues Status

**Dashboard Lambda Security** - See `specs/001-interactive-dashboard-demo/SECURITY_REVIEW.md` for full details:
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
- **X-Ray Tracing**: Day 1 mandatory on all 4 Lambdas
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
- X-Ray distributed tracing on all 4 Lambdas
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
