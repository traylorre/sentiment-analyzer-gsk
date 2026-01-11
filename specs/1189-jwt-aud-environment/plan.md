# Feature 1189: Implementation Plan

## Overview

Configuration-only change to add environment-specific JWT audience values.

## Implementation Steps

### Step 1: Update dev.tfvars

Add `jwt_audience` variable with dev-specific value.

**File**: `infrastructure/terraform/dev.tfvars`

```hcl
# Feature 1189: Environment-specific JWT audience (A16)
jwt_audience = "sentiment-api-dev"
```

### Step 2: Update preprod.tfvars

Add `jwt_audience` variable with preprod-specific value.

**File**: `infrastructure/terraform/preprod.tfvars`

```hcl
# Feature 1189: Environment-specific JWT audience (A16)
jwt_audience = "sentiment-api-preprod"
```

### Step 3: Update prod.tfvars

Add `jwt_audience` variable with prod-specific value.

**File**: `infrastructure/terraform/prod.tfvars`

```hcl
# Feature 1189: Environment-specific JWT audience (A16)
jwt_audience = "sentiment-api-prod"
```

## Verification

1. Run `terraform plan` for each environment to verify the JWT_AUDIENCE env var change
2. Existing unit tests continue to pass (no code changes)
3. After deployment, verify JWT validation logs show correct audience

## Rollback

Revert tfvars changes to use default `"sentiment-analyzer-api"` value.

## Dependencies

- Feature 1147 (COMPLETE): JWT audience validation infrastructure
- Feature 1054 (COMPLETE): JWT secret management
