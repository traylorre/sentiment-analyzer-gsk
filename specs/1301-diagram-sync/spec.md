# Feature 1301: Update Mermaid Diagrams to Current Architecture

## Problem Statement

8 deviations identified between Mermaid diagrams and the actual architecture after Features 1253 (API Gateway), 1255 (CloudFront for SSE), 1256 (IAM auth on Function URLs), 1297 (resolver switch), and 1300 (Dashboard Function URL removal). Diagrams show a pre-API-Gateway architecture that no longer exists.

## Requirements

### FR-001: architecture.mmd
- Change Dashboard label from "Function URL + Auth" to "API Gateway REST + Auth"
- Add CloudFront node between Browser and SSE: `Browser → CloudFront → SSE`
- Remove Dashboard Function URL reference (deleted in Feature 1300)

### FR-002: high-level-overview.mmd
- Add CloudFront node between Browser and SSE
- Change `Browser ==>|/api/v2/stream*| SSE` to `Browser ==>|/api/v2/stream*| CloudFront ==> SSE`
- Add WAF association note on CloudFront

### FR-003: security-flow.mmd
- Change Zone 0 title from "Lambda Function URL + Amplify" to "API Gateway + WAF + Amplify"
- Remove `LambdaURL` node from Zone 0 (Dashboard Function URL no longer exists)
- Move API Gateway from Zone 5 to Zone 0 as browser entry point for API calls
- Change `BrowserReq -->|API calls| LambdaURL` to `BrowserReq -->|API calls| APIGateway`
- Add CloudFront node for SSE path
- Keep SSE Function URL reference (it still exists, accessed via CloudFront)

### FR-004: DASHBOARD_SECURITY_ANALYSIS.md
- "Current Architecture" diagram: change `auth_type = NONE` to show current reality (API Gateway → Lambda, no direct Function URL). Remove red "vulnerable" styling.
- "Recommended Architecture" section: note that CloudFront+WAF+APIGateway IS the current architecture (no longer "recommended future"). The recommendation has been implemented.

### FR-005: OPERATIONAL_FLOWS.md
- Troubleshooting diagram: change starting point from "Function URL accessible?" to "API Gateway accessible?"
- Remove "Verify auth_type=NONE" decision node
- Add "Check API Gateway deployment" and "Check Lambda permission qualifier" nodes
- Quick fix commands: change `terraform output dashboard_function_url` to `terraform output dashboard_api_url`
- Update curl commands to use API Gateway endpoint

### FR-006: README.md system architecture diagram
- Must match high-level-overview.mmd changes (FR-002)
- Add CloudFront for SSE path
- Remove Dashboard Function URL references

### FR-007: Regenerate mermaid.live URL
- Run `make regenerate-mermaid-url` after updating architecture.mmd
- Update the badge link in README.md with the new encoded URL

### FR-008: Validate diagram syntax
- Run `make validate-mermaid` on all updated .mmd files
- Ensure GitHub renders all inline mermaid blocks correctly

## Success Criteria

1. All 5 .mmd files reflect current architecture (API Gateway for Dashboard, CloudFront for SSE)
2. No references to Dashboard Function URL in any diagram
3. SSE path shows CloudFront in all diagrams
4. `make validate-mermaid` passes
5. README mermaid.live badge URL regenerated
6. DASHBOARD_SECURITY_ANALYSIS.md reflects current (not proposed) architecture
7. OPERATIONAL_FLOWS.md troubleshooting starts with API Gateway, not Function URL

## Adversarial Review #1

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| MEDIUM | FR-003 says "Remove LambdaURL node from Zone 0" but SSE Lambda still has a Function URL (accessed via CloudFront). The security diagram should still show the SSE Function URL in the appropriate zone — just not the Dashboard one. | **Clarified:** Remove DASHBOARD LambdaURL only. Add SSE Function URL under CloudFront in Zone 0, with note "(OAC SigV4, RESPONSE_STREAM)". |
| MEDIUM | FR-004 says DASHBOARD_SECURITY_ANALYSIS.md "Current Architecture" should show current reality. But this file was written as a security AUDIT — changing "Current Architecture" to show the fixed state erases the historical record of what was vulnerable. | **Resolved:** Add a new "Current Architecture (Post-Feature 1253)" section. Keep the old "Previous Architecture" section as historical record with a clear "(DEPRECATED — prior to Feature 1253)" label. |
| LOW | FR-007 regenerates mermaid.live URL only for architecture.mmd. Other .mmd files may also need external viewer links. | **Accepted:** Only architecture.mmd has a README badge link. Other .mmd files are viewed via GitHub's native mermaid renderer. |
| LOW | `dataflow-all-flows.mmd` and `sse-lambda-streaming.mmd` were not in the deviation list but may have stale references. | **Checked:** `dataflow-all-flows.mmd` focuses on data pipelines (no ingress path references). `sse-lambda-streaming.mmd` correctly shows Function URL + RESPONSE_STREAM for SSE. Neither needs changes for this feature. |

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** Proceeding to Stage 3.

## Clarifications

### Q1: Does the README inline diagram duplicate high-level-overview.mmd?
**Answer:** Yes, lines 191-320 of README.md contain the same diagram. Both must be updated in sync.
**Evidence:** Prior audit confirmed identical content.

### Q2: Does `make regenerate-mermaid-url` handle all .mmd files?
**Answer:** No, only `docs/diagrams/architecture.mmd`. The script encodes the .mmd content as a mermaid.live URL for the README badge.
**Evidence:** Makefile lines 222-223.

All questions self-answered.
