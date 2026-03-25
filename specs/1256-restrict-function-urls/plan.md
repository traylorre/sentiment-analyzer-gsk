# Implementation Plan: Restrict Lambda Function URLs

**Branch**: `1256-restrict-function-urls` | **Date**: 2026-03-24 | **Spec**: `specs/1256-restrict-function-urls/spec.md`

## Summary

Switch both Lambda Function URLs from `authorization_type = NONE` to `AWS_IAM`. Add CloudFront OAC for SSE Lambda so CloudFront can sign requests. No code changes. $0 additional cost.

## Technical Context

**Language/Version**: HCL (Terraform 1.5+, AWS Provider ~> 5.0)
**Scale/Scope**: ~5 resource changes (2 auth type changes, 1 OAC, 1 Lambda permission, 1 CloudFront update)

## Constitution Check

All gates PASS.

## Project Structure

```text
infrastructure/terraform/
├── modules/lambda/                  # MODIFY: support authorization_type variable
│   └── main.tf or variables.tf      # Add function_url_auth_type variable
├── modules/cloudfront_sse/
│   └── main.tf                      # MODIFY: Add OAC for Lambda origin
├── main.tf                          # MODIFY: Set auth_type=AWS_IAM on both Lambdas
│                                    # Add Lambda permission for CloudFront OAC
└── (no new modules needed)

tests/e2e/
└── test_function_url_restricted.py  # NEW: Verify 403 on direct Function URL
```

## Architecture

After Feature 1256:
```
API Gateway → IAM invoke → Dashboard Lambda (auth_type=AWS_IAM) ← Direct URL = 403
CloudFront → OAC (SigV4) → SSE Lambda (auth_type=AWS_IAM)      ← Direct URL = 403
Deploy CI  → aws lambda invoke → Both Lambdas (IAM, not Function URL)
```

### CloudFront OAC for Lambda

CloudFront OAC (`aws_cloudfront_origin_access_control`) signs requests to the Lambda Function URL origin. The Lambda needs a resource-based policy allowing `lambda:InvokeFunctionUrl` from the CloudFront service principal with the distribution as source.

### Changes Required

1. **Lambda module**: Add `function_url_auth_type` variable (default: "NONE" for backward compat, set to "AWS_IAM" for hardened Lambdas)
2. **Dashboard Lambda**: Set `function_url_auth_type = "AWS_IAM"` in main.tf
3. **SSE Lambda**: Set `function_url_auth_type = "AWS_IAM"` in main.tf
4. **CloudFront SSE module**: Add OAC resource + set `origin_access_control_id` on origin
5. **Lambda permission**: Add `aws_lambda_permission` for CloudFront to invoke SSE Lambda via Function URL
