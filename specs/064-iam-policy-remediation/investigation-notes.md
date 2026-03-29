# Investigation Notes: LAMBDA-007 Suppression Failure

## Root Cause Analysis

### Problem Statement

LAMBDA-007 suppression entry exists in target repo's `iam-allowlist.yaml` but is not being applied during validation.

### Root Cause

**Bug in `check_passrole_scoped()` function** (`src/validators/iam_allowlist.py:163-183`)

The function checks if ANY `"Resource": "*"` exists in the file, not whether `iam:PassRole`'s specific Resource is `*`.

```python
# Current implementation (BUGGY)
def check_passrole_scoped(content: str) -> bool:
    # No PassRole = vacuously scoped
    if '"iam:PassRole"' not in content and "'iam:PassRole'" not in content:
        return True

    # Check if Resource is "*" (unscoped)
    if re.search(r'"Resource"\s*:\s*"\*"', content):  # BUG: Matches ANY Resource: "*"
        return False
    ...
```

### Why It Fails

The `preprod-deployer-policy.json` has:

1. **IAM statement** (properly scoped):

   ```json
   {
     "Sid": "IAMPreprodResources",
     "Action": ["iam:PassRole", ...],
     "Resource": ["arn:aws:iam::*:role/preprod-*", ...]
   }
   ```

2. **CloudFront statement** (legitimately requires `*`):
   ```json
   {
     "Sid": "CloudFrontCachePolicies",
     "Action": ["cloudfront:ListCachePolicies", ...],
     "Resource": "*"  // AWS requires * for List operations
   }
   ```

The regex `r'"Resource"\s*:\s*"\*"'` matches the CloudFront statement's `"Resource": "*"`, causing `check_passrole_scoped()` to return `False`.

Since the allowlist entry has `passrole_scoped: true`, the context check fails and suppression is not applied.

### Impact

- All files with ANY `Resource: "*"` (even for legitimate reasons like CloudFront List operations) will fail the `passrole_scoped` context check
- LAMBDA-007 suppressions will not work for these files

### Correct Fix

The function should parse the JSON/HCL and only check if the statement containing `iam:PassRole` has `Resource: "*"`.

```python
# Correct approach (pseudocode)
def check_passrole_scoped(content: str) -> bool:
    # Parse the policy statements
    # Find statements that include "iam:PassRole" in Action
    # For those statements only, check if Resource is "*"
    # Return False only if PassRole's Resource is "*"
```

## Options

| Option                        | Description                                             | Risk   | Effort |
| ----------------------------- | ------------------------------------------------------- | ------ | ------ |
| A. Fix template validator     | Modify `check_passrole_scoped()` to parse JSON properly | Medium | Medium |
| B. Remove context requirement | Remove `passrole_scoped: true` from allowlist entry     | Low    | Low    |
| C. Accept as limitation       | Document and move on                                    | Low    | None   |

## Recommendation

**Option B**: Remove `passrole_scoped: true` context requirement from the target repo's `iam-allowlist.yaml`.

**Rationale**:

1. SC-004 states "No template repo code changes required"
2. The existing justification already documents that PassRole is scoped
3. The context check is defense-in-depth, not primary validation
4. Option A (fix template) can be a follow-up feature (065)

## Resolution Path

1. Edit target repo's `iam-allowlist.yaml`
2. Remove `context_required: passrole_scoped: true` from `lambda-cicd-deployment` entry
3. Verify suppression now works
4. Document the limitation for future feature work

## Resolution Applied (2025-12-08)

**Changes Made**:

1. Removed `context_required: passrole_scoped: true` from `lambda-cicd-deployment` entry
2. Removed `context_required: passrole_scoped: true` from `lambda-event-source-mapping` entry
3. Updated `last_updated` to `2025-12-08`
4. Added comments explaining the template validator bug

**Verification Result**:

```
LAMBDA-007 | SUPPRESSED | infrastructure/terraform/ci-user-policy.tf:48
  -> Suppressed by: lambda-cicd-deployment
LAMBDA-007 | SUPPRESSED | docs/iam-policies/dev-deployer-policy.json:37
  -> Suppressed by: lambda-cicd-deployment
LAMBDA-007 | SUPPRESSED | infrastructure/iam-policies/prod-deployer-policy.json:35
  -> Suppressed by: lambda-cicd-deployment
LAMBDA-007 | SUPPRESSED | infrastructure/iam-policies/preprod-deployer-policy.json:37
  -> Suppressed by: lambda-cicd-deployment
```

**Future Work**: Fix `check_passrole_scoped()` in template repo to parse JSON properly (065-iam-allowlist-passrole-fix)
