# Feature 118: Fix Dashboard Connection Status

## Problem Statement

The ONE URL dashboard (https://d2z9uvoj5xlbd2.cloudfront.net) shows "Connecting..." with a disconnected (red) status indicator. The dashboard never connects to the SSE stream.

## Root Cause Analysis

The dashboard's `config.js` has:
- `API_BASE_URL: ''` (empty, meaning same origin)
- `SSE_BASE_URL: ''` (empty, meaning same origin)
- `ENDPOINTS.STREAM: '/api/v2/stream'`

The dashboard tries to connect to `/api/v2/stream` for SSE streaming, but:

1. CloudFront routes `/api/*` to API Gateway
2. API Gateway routes to Dashboard Lambda (BUFFERED mode)
3. SSE requires RESPONSE_STREAM mode (SSE Lambda)
4. The SSE Lambda has a different Function URL

## Solution Options

### Option A: Route /api/v2/stream to SSE Lambda via CloudFront
Add another CloudFront cache behavior for `/api/v2/stream*` that routes to the SSE Lambda Function URL.

### Option B: Configure SSE_BASE_URL in config.js
Set `SSE_BASE_URL` to the SSE Lambda Function URL directly.

### Option C: Show graceful degradation
If SSE fails, fall back to polling mode and update status to "Polling" instead of "Disconnected".

## Recommended: Option A + Option C

1. Add CloudFront behavior for SSE endpoint to proper Lambda
2. Improve UX with fallback status indication

## Changes

### Option A: infrastructure/terraform/modules/cloudfront/main.tf
- Add cache behavior for `/api/v2/stream*` to SSE Lambda origin

### Option C: src/dashboard/app.js
- Update `updateConnectionStatus()` to show "Polling" when using fallback
- Change indicator color for polling mode (yellow/amber)

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | Dashboard connects to SSE or falls back gracefully | Visual check |
| SC-002 | Status shows "Connected" or "Polling", not "Disconnected" | Visual check |
| SC-003 | Metrics update in real-time (SSE) or via polling | Observe changes |
