# Feature Specification: 104-interview-dashboard-one-url

**Branch**: `104-interview-dashboard-one-url` | **Date**: 2025-12-12

## Problem Statement

The Interview Dashboard's "View Live Dashboard" link points to the Lambda Function URL
(`https://ee2a3fxtkxmpwp2bhul3uylmb40hfknf.lambda-url.us-east-1.on.aws`) instead of the
CloudFront "ONE URL" (`https://d2z9uvoj5xlbd2.cloudfront.net`).

This causes:
1. SSE streaming failures (Lambda URL only routes to Dashboard Lambda, not SSE Lambda)
2. Missing CloudFront caching benefits
3. Inconsistent architecture demonstration during interviews

## Root Cause

Line 1647 of `interview/index.html` hardcodes the Lambda Function URL:
```javascript
const ENVIRONMENTS = {
    preprod: 'https://ee2a3fxtkxmpwp2bhul3uylmb40hfknf.lambda-url.us-east-1.on.aws',
    prod: 'https://prod-sentiment-dashboard.lambda-url.us-east-1.on.aws'
};
```

## Solution

Update the `ENVIRONMENTS` configuration to use CloudFront URLs:
```javascript
const ENVIRONMENTS = {
    preprod: 'https://d2z9uvoj5xlbd2.cloudfront.net',
    prod: 'https://prod.sentiment-analyzer.example.com'  // Update when available
};
```

## Scope

| In Scope | Out of Scope |
|----------|--------------|
| Update ENVIRONMENTS.preprod URL | CloudFront routing changes (separate feature) |
| Update ENVIRONMENTS.prod placeholder | SSE Lambda integration |

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | View Live Dashboard opens CloudFront URL | Manual test |
| SC-002 | API demos work through CloudFront | Manual test |
| SC-003 | No JavaScript errors in console | Browser DevTools |

## Technical Details

**File**: `interview/index.html`
**Line**: 1647
**Change**: Single line URL update

## References

- CloudFront domain: `d2z9uvoj5xlbd2.cloudfront.net`
- Previous Lambda URL: `ee2a3fxtkxmpwp2bhul3uylmb40hfknf.lambda-url.us-east-1.on.aws`
