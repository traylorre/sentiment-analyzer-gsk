# Authorization

> **CANON**: verified against code.

How a request gets authorized, who issues the tokens, and how deployment credentials stay
separated between environments.

## Request authorization

Every `/api/*` request carries a bearer token. The Lambda auth middleware is the authorization
layer (`src/lambdas/shared/middleware/auth_middleware.py`). API Gateway does not validate
tokens: it provides rate limiting and WAF, and its Cognito authorizer is disabled because the
frontend bearer is a first-party app JWT that a Cognito authorizer cannot validate
(`infrastructure/terraform/main.tf:879`).

The middleware classifies the token by validating it, never by trusting request headers
(`auth_middleware.py:27`):

- **Authenticated**: an HS256 app JWT (issuer `sentiment-analyzer`). `validate_jwt` checks
  signature, expiry, audience, and not-before (`auth_middleware.py:133`). Access tokens live
  15 minutes with 60 seconds of clock-skew leeway (`auth_middleware.py:103-104`). The token's
  `rev` claim is compared against the user record's `revocation_id`; a stale claim means the
  session was force-revoked and the token is rejected (`auth_middleware.py:223`).
- **Anonymous**: the bearer is the session's user_id UUID (`src/lambdas/dashboard/auth.py:3396`).

Cognito backs the OAuth flows (Google, GitHub) and verifies those identities server-side
against Cognito's public keys (`src/lambdas/shared/auth/cognito.py`). The bearer the frontend
presents afterwards is the app JWT above, not a Cognito token.

Roles ride in the JWT `roles` claim, derived from user state by `get_roles_for_user`
(`src/lambdas/shared/auth/roles.py:24`). Role progression is
`anonymous -> free -> paid -> operator` (`src/lambdas/shared/models/user.py:16`).

## Authentication methods

Passwordless by design. Three methods (`src/lambdas/shared/models/user.py:47`):

| Method | Mechanism |
|---|---|
| Anonymous | Session auto-created on first visit, no email required |
| Magic link | Emailed one-time link |
| OAuth | Google or GitHub via Cognito |

### Magic link

Links expire after 1 hour and are one-time: the token is 256-bit random
(`secrets.token_urlsafe`) and consumed atomically with a DynamoDB `ConditionExpression`, so a
replay finds it already spent (`src/lambdas/dashboard/auth.py:1827-1837`). While a link is
pending, the user keeps using the site anonymously. Verification upgrades the account
`anonymous -> free`.

## Sessions

Sessions last 30 days (`src/lambdas/dashboard/auth.py:139`). Each device creates its own
session against the same account. Sessions expire independently: a refresh resets only the
used session's expiry to a fresh 30 days and leaves the others untouched (`auth.py:1013`).

A user holds at most 5 concurrent sessions (`auth.py:140`). A sixth login evicts the oldest in
one DynamoDB transaction: condition-check that it still exists, delete it, blocklist its
refresh token, create the new session (`evict_oldest_session_atomic`, `auth.py:1275`). The
evicted device gets `AUTH_014` (`src/lambdas/shared/errors/auth_errors.py:28`).

## Refresh tokens

Refresh tokens travel only as an httpOnly cookie set by the router and are excluded from
response bodies (`auth.py:1654-1655`). They are single-use: each refresh rotates the token
under a conditional write, so concurrent refreshes cannot fork a session (`auth.py:3363`).

## CORS

The origin allowlist is deliberately broad because the frontend is served cross-origin
(Amplify, the GitHub Pages demo, localhost in preprod;
`infrastructure/terraform/preprod.tfvars:25-29`), and the httpOnly refresh cookie must cross
those origins, so responses send `Access-Control-Allow-Credentials: true`
(`src/lambdas/dashboard/handler.py:328`; the SSE Function URL CORS config enables credentials
too, `main.tf:829`).

What keeps that posture safe is that origins stay an explicit list. Terraform validation bans
the wildcard (`variables.tf:73`), prod refuses an empty or non-HTTPS list (`main.tf:42-75`),
and the Lambda post-processor echoes an origin only when it appears in `CORS_ORIGINS`
(`handler.py:324`). API Gateway answers CORS for preflight and gateway errors, which never
reach the Lambda; the Lambda post-processor handles everything else (`handler.py:19-27`).

## Credential separation between environments

Preprod credentials cannot modify prod resources, and prod credentials cannot modify preprod.

- Every AWS resource name carries its environment prefix
  (`infrastructure/terraform/main.tf:242-251`), which is what lets IAM scope access by prefix.
- Each environment deploys as its own IAM user whose policy allows only that environment's
  prefixed resources and explicitly denies the other environment's. The users and policies
  live in AWS, not in this repo.
- GitHub Environments hold the keys. Deploy jobs declare `environment: preprod` or
  `environment: production`, and both read the same secret name `AWS_ACCESS_KEY_ID`; the
  environment scoping selects which key the job receives (`.github/workflows/deploy.yml:508`,
  `deploy.yml:1742`). JWT signing secrets are also per environment (`PREPROD_JWT_SECRET`,
  `PROD_JWT_SECRET`).
- `production` requires reviewer approval. `production-auto` carries the same secrets without
  the approval gate and is selected only when the actor is Dependabot (`deploy.yml:1903`).
