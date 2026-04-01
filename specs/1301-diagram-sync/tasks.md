# Feature 1301: Tasks

## Task Dependency Graph

```
T1 (architecture.mmd) ─┐
T2 (overview.mmd)      ├── T6 (README sync) → T7 (validate + regenerate URL)
T3 (security-flow.mmd) ┤
T4 (security analysis) ┤
T5 (operational flows) ─┘
```

T1-T5 are independent (different files). T6 depends on T2 (README duplicates overview). T7 depends on T1+T6.

### T1: Update architecture.mmd
**File:** `docs/diagrams/architecture.mmd`
**Requirements:** FR-001

1. Dashboard Lambda node: change "Function URL + Auth" to "API Gateway REST + Auth"
2. Remove Dashboard Function URL reference
3. Add CloudFront node between Browser and SSE Lambda
4. Update edge: `Browser -->|"/api/v2/stream*"| CloudFront -->| SSE`

---

### T2: Update high-level-overview.mmd
**File:** `docs/diagrams/high-level-overview.mmd`
**Requirements:** FR-002

1. Add CloudFront node: `CloudFront[CloudFront<br/>WAF + Shield<br/>SSE Streaming]`
2. Change: `Browser ==>|/api/v2/stream*| SSE` to `Browser ==>|/api/v2/stream*| CloudFront`
3. Add: `CloudFront ==>|OAC SigV4| SSE`

---

### T3: Update security-flow.mmd
**File:** `docs/diagrams/security-flow.mmd`
**Requirements:** FR-003

1. Zone 0 title: "API Gateway + WAF + Amplify" (remove "Lambda Function URL")
2. Remove Dashboard `LambdaURL` node
3. Add `APIGateway` node to Zone 0 as API entry point
4. Add `CloudFront` node for SSE path with OAC note
5. Keep SSE Function URL reference (under CloudFront)
6. Fix edge: `BrowserReq -->|API calls| APIGateway`

---

### T4: Update DASHBOARD_SECURITY_ANALYSIS.md
**File:** `docs/security/DASHBOARD_SECURITY_ANALYSIS.md`
**Requirements:** FR-004

1. Label existing "Current Architecture" as "Previous Architecture (Pre-Feature 1253)" with DEPRECATED note
2. Add new "Current Architecture (Post-Feature 1253)" section with accurate diagram showing API Gateway → Lambda
3. Note in "Recommended Architecture" section that these recommendations are NOW implemented

---

### T5: Update OPERATIONAL_FLOWS.md
**File:** `docs/operations/OPERATIONAL_FLOWS.md`
**Requirements:** FR-005

1. Rewrite troubleshooting flowchart: start with "API Gateway accessible?"
2. Remove "Verify auth_type=NONE" node
3. Add "Check Lambda permission qualifier" and "Check API Gateway deployment" nodes
4. Fix quick-fix commands: `terraform output dashboard_api_url` instead of `dashboard_function_url`
5. Fix curl commands to use API Gateway endpoint

---

### T6: Sync README.md inline diagram
**File:** `README.md`
**Requirements:** FR-006
**Depends on:** T2

1. Copy updated diagram from high-level-overview.mmd to README.md (lines 191-320)
2. Ensure init theme config matches

---

### T7: Validate and regenerate mermaid.live URL
**Requirements:** FR-007, FR-008
**Depends on:** T1, T6

1. Run `make validate-mermaid`
2. Run `make regenerate-mermaid-url`
3. Update README badge link with new URL

## Requirements Coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 | T1 |
| FR-002 | T2 |
| FR-003 | T3 |
| FR-004 | T4 |
| FR-005 | T5 |
| FR-006 | T6 |
| FR-007 | T7 |
| FR-008 | T7 |

## Adversarial Review #3

**Highest-risk task:** T3 (security-flow.mmd). This is the most complex diagram (132 lines, 6 zones, many edges). Restructuring Zone 0 could break node references throughout the diagram.

**Most likely rework:** T6 (README sync). If README has diverged from high-level-overview.mmd beyond the diagram (different theme config, extra annotations), a straight copy may introduce rendering issues.

### Gate Statement
**READY FOR IMPLEMENTATION.** 0 CRITICAL, 0 HIGH remaining.
