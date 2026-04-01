# Feature 1295: Tasks

## T-001: Add qualifier to Lambda permission
File: `infrastructure/terraform/modules/api_gateway/main.tf` line 722
Add `qualifier = "live"` to `aws_lambda_permission.api_gateway`.

## AR#3
Highest risk: Terraform may try to recreate the permission (destroy + create) which briefly removes API Gateway → Lambda access. This is during `terraform apply` only — no user traffic during deploy.
**READY FOR IMPLEMENTATION.**
