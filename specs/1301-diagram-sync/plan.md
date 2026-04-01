# Feature 1301: Implementation Plan

## Current Architecture (what diagrams must show)

```
DASHBOARD PATH:
  Browser → Amplify → API Gateway REST (Cognito + WAF + Rate Limiting)
    → lambda:InvokeFunction → Dashboard Lambda (APIGatewayRestResolver, v1 events)
    → DynamoDB

SSE PATH:
  Browser → Amplify → CloudFront (WAF + Shield + OAC SigV4)
    → lambda:InvokeFunctionUrl → SSE Lambda Function URL (RESPONSE_STREAM, v2 events)
    → DynamoDB

NO DASHBOARD FUNCTION URL (removed in Feature 1300)
```

## Files Modified

| File | Changes |
|------|---------|
| `docs/diagrams/architecture.mmd` | Dashboard: "API Gateway REST + Auth". Add CloudFront→SSE. Remove Dashboard Function URL. |
| `docs/diagrams/high-level-overview.mmd` | Add CloudFront between Browser and SSE. |
| `docs/diagrams/security-flow.mmd` | Zone 0: "API Gateway + WAF + Amplify". Remove Dashboard LambdaURL. Add CloudFront for SSE. |
| `docs/security/DASHBOARD_SECURITY_ANALYSIS.md` | Add "Current Architecture (Post-1253)" section. Label old diagram as deprecated. |
| `docs/operations/OPERATIONAL_FLOWS.md` | Troubleshooting: API Gateway first. Fix curl commands. |
| `README.md` | Sync inline diagram with high-level-overview.mmd. Regenerate mermaid.live badge URL. |

## Diagram Consistency Tooling

1. `make validate-mermaid` — validates syntax of architecture.mmd
2. `make regenerate-mermaid-url` — generates mermaid.live URL for README badge
3. Manual: verify GitHub renders inline mermaid blocks (push to branch, check PR preview)

## Adversarial Review #2

No drift. Plan matches spec (including AR#1 corrections: keep SSE Function URL in security diagram, preserve deprecated section in security analysis).

### Gate Statement
**0 CRITICAL, 0 HIGH. No drift.**
