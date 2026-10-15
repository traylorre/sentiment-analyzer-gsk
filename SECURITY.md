# Security Policy

## Supported Versions

There is no production release, and the production deploy job is disabled. Fixes land only on `main`; there are no release branches.

## Reporting a Vulnerability

Report vulnerabilities privately through GitHub private vulnerability reporting:
https://github.com/traylorre/sentiment-analyzer-gsk/security/advisories/new

Do not open a public issue for a security concern.

**Response Time:** We aim to acknowledge reports within 48 hours.

## Controls in Place

Edge and transport
- API Gateway stage throttling: 100 requests per second steady state, burst 200.
- The dashboard Lambda has no Function URL and is reached only through API Gateway.
- The SSE Lambda's Function URL requires AWS_IAM auth and is served through CloudFront.
- CloudFront connects to the SSE origin over TLS 1.2.

Authentication and sessions
- Sign-in uses Amazon Cognito hosted OAuth (Google) or email magic links. A magic link is a single-use random token, consumed atomically in DynamoDB.
- API requests carry an application-issued HS256 JWT. The Lambda validates its signature, issuer and audience, and requires the sub, exp, iat and nbf claims.
- The dashboard API applies CSRF token middleware.
- CORS origins come from an explicit per-environment allow-list. Terraform rejects `*`, and prod requires a non-empty list.

Secrets
- Third-party API keys and OAuth client secrets are stored in AWS Secrets Manager under a customer-managed KMS key, and the Lambdas cache them for 24 hours. No secret rotates.
- The JWT signing secret reaches the Lambdas as an environment variable, set at deploy from a GitHub Actions secret.

Resilience and observability
- Circuit breakers and per-provider quota tracking guard Tiingo and Finnhub calls during ingestion.
- X-Ray active tracing runs on six of the seven Lambdas; the canary uses PassThrough.

Repository and CI
- GitHub secret scanning with push protection is enabled. gitleaks is a required status check on `main`, and detect-secrets runs in pre-commit and CI.
- Commits to `main` must be signed.
- Semgrep gates `make validate`. CodeQL and a pip-audit job run on pull requests; neither is a required status check.
- Dependabot alerts are enabled, and Dependabot opens weekly version-update PRs. Dependabot security updates are disabled.
- trivy and checkov scan the Terraform in pre-commit and CI.

## Known Gaps

- There are no CloudWatch alarms. Monitoring is metrics and logs only, by decision.
- No per-IP rate limit is enforced. The WAF rate rule exists in Terraform but is disabled in preprod, the only deployed environment.
- The SSE connection cap is 100 per Lambda execution environment, with no per-client limit.
- The API Gateway Cognito authorizer is disabled.
- hCaptcha bot protection is not enforced.
- Authentication failures are logged without the client IP.
- SendGrid calls have no circuit breaker.
- CloudFront applies no geo-restriction and sets no minimum viewer TLS version.

## Contributing

- Never commit credentials. The secret scanners listed above block known formats.
- Build DynamoDB expressions with expression attribute values. Never concatenate request input into them.
