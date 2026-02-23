# Fix: Update Terraform Handler Path

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P6
**Status:** [ ] TODO
**Depends On:** [design-native-handler.md](./design-native-handler.md)

---

## Problem Statement

Terraform defines the Lambda handler entrypoint. Currently points to the FastAPI/Mangum wrapper. Must be updated to point to the new native handler.

---

## Change

```hcl
# BEFORE
resource "aws_lambda_function" "dashboard" {
  handler = "main.handler"  # main.py → Mangum(app)
  ...
}

# AFTER
resource "aws_lambda_function" "dashboard" {
  handler = "ohlc.lambda_handler"  # ohlc.py → lambda_handler(event, context)
  ...
}
```

---

## Verification Before Apply

```bash
# 1. Confirm handler path resolves correctly
# The handler format is: <module_path>.<function_name>
# For container-based Lambdas: path is relative to WORKDIR in Dockerfile
# For ZIP-based Lambdas: path is relative to ZIP root

# 2. Check if dashboard is container or ZIP
grep -A5 "dashboard" infrastructure/terraform/main.tf | grep -E "image_uri|filename"
```

---

## Container-Based Lambda Consideration

If dashboard Lambda uses ECR (container), the handler path is relative to the Dockerfile WORKDIR:

```dockerfile
# If WORKDIR is /app and code is at /app/src/lambdas/dashboard/ohlc.py
# Then handler = "src.lambdas.dashboard.ohlc.lambda_handler"
```

---

## Checklist

- [ ] Identify current handler value in Terraform
- [ ] Identify if Lambda is ZIP or container-based
- [ ] Determine correct module path for new handler
- [ ] Update `handler` attribute in Terraform
- [ ] Run `terraform plan` to verify only handler changes
- [ ] Verify no other Terraform resources reference the old handler path

---

## Risk

| Risk | Mitigation |
|------|------------|
| Wrong module path | Test locally with `python -c "from ohlc import lambda_handler"` |
| Container WORKDIR mismatch | Check Dockerfile for exact WORKDIR |
| Other Lambdas affected | Search for all `handler =` in Terraform |

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `infrastructure/terraform/main.tf` | TBD | Update handler path |
| `infrastructure/terraform/modules/lambda/main.tf` | TBD | If using module |

---

## Related

- [fix-requirements-cleanup.md](./fix-requirements-cleanup.md) - Package removal (same deploy)
- [fix-validation-smoketest.md](./fix-validation-smoketest.md) - Verify handler works after deploy
