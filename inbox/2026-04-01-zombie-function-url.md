---
date: 2026-04-01
source: sentiment-analyzer-gsk
branch: main
type: near-miss
---

## What happened

SSE streaming required Lambda Function URL (API Gateway can't do RESPONSE_STREAM). Dashboard Lambda also got a Function URL — originally the sole entry point. When API Gateway was added for Cognito/WAF/rate-limiting, the Dashboard Function URL became zombie infrastructure. Feature 1256 locked it to AWS_IAM (returns 403 to everyone), but the Amplify frontend had a ternary fallback that would silently point users at the dead URL if API Gateway was ever empty. A control plane bug hiding behind a security hardening feature.

## Why it's interesting

When you add a new ingress path alongside an old one, the old path doesn't die — it becomes a zombie. IAM auth made it safe but not clean. The fallback chain made it dangerous. The fix wasn't "add compatibility" — it was "delete the zombie and make the fallback fail loudly at terraform plan." Fallbacks that fail silently are control plane bugs.

## Context

- Branch: main
- Recent commits: df245be Switch Dashboard Lambda to APIGatewayRestResolver, 568e5e9 Fix API Gateway 502 + CORS, 42dbab7 Expose api_url in deploy-preprod
- Working on: Unblocking deploy pipeline — 11 failing preprod E2E tests from v1/v2 event format mismatch
