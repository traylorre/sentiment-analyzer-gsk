
## Project Name Parameterization (Deferred)

**Context**: The naming pattern `*-sentiment-*` is used throughout IAM policies and resource names. Currently hardcoded.

**Future improvement**:
1. Create a `local.project_slug = "sentiment"` in `infrastructure/terraform/main.tf`
2. Update all resource names to use `${local.project_slug}` instead of hardcoded "sentiment"
3. Update `iam_resource_alignment.py` validator to resolve Terraform locals (separate feature)

**Why deferred**: The `iam_resource_alignment.py` validator does static text analysis and cannot resolve Terraform variables/locals. Would need plan-based parsing or local resolution logic.

**Current state**: Pattern `*-sentiment-*` correctly matches all resources. No mismatch exists.
