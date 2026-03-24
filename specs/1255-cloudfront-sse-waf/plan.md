# Implementation Plan: CloudFront + WAF for SSE Streaming

**Branch**: `1255-cloudfront-sse-waf` | **Date**: 2026-03-24 | **Spec**: `specs/1255-cloudfront-sse-waf/spec.md`

## Summary

Create CloudFront distribution with SSE Lambda Function URL as origin. No caching (SSE real-time). 180s origin timeout. WAF CLOUDFRONT scope (reusing Feature 1254 module). Update Amplify SSE URL. PriceClass_100. Shield Standard automatic.

## Technical Context

**Language/Version**: HCL (Terraform 1.5+, AWS Provider ~> 5.0)
**Primary Dependencies**: AWS CloudFront, AWS WAF v2, existing SSE Lambda
**Scale/Scope**: ~20 new resources (CloudFront + WAF CLOUDFRONT + association)

## Constitution Check

All gates PASS. Same pattern as Features 1253/1254.

## Project Structure

```text
infrastructure/terraform/
├── modules/cloudfront_sse/         # NEW: CloudFront distribution
│   ├── main.tf                     # Distribution, origin, cache/ORP
│   ├── variables.tf
│   └── outputs.tf                  # distribution_url, arn
├── modules/waf/                    # REUSE with scope=CLOUDFRONT
├── modules/amplify/main.tf         # MODIFY: SSE URL → CloudFront
└── main.tf                         # Wire CloudFront + WAF CLOUDFRONT

tests/e2e/
└── test_cloudfront_sse.py          # NEW: SSE via CloudFront tests
```

## Architecture

```
Frontend → CloudFront (no-cache, 180s timeout, PriceClass_100)
  → WAF CLOUDFRONT (rate limit 2000/5min, SQLi, XSS, bots)
  → SSE Lambda Function URL (RESPONSE_STREAM, 25 concurrency)
```

CloudFront config: CachingDisabled policy, custom Origin Request Policy (forward auth headers), 180s origin read timeout, HTTP/2.
