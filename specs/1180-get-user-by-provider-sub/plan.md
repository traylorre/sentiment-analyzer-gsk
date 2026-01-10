# Implementation Plan: Get User by Provider Sub Helper

**Branch**: `1180-get-user-by-provider-sub` | **Date**: 2026-01-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1180-get-user-by-provider-sub/spec.md`

## Summary

Implement a `get_user_by_provider_sub(provider, sub)` helper function that enables account linking flows by looking up users by their OAuth provider's subject claim. This requires:
1. Adding a new GSI (`by_provider_sub`) to DynamoDB via Terraform
2. Updating `_link_provider()` to populate the `provider_sub` attribute
3. Implementing the lookup function in auth.py

## Technical Context

**Language/Version**: Python 3.13, Terraform 1.5+
**Primary Dependencies**: boto3 (DynamoDB), pydantic (User model)
**Storage**: DynamoDB with new GSI
**Testing**: pytest with moto (mocked DynamoDB)
**Target Platform**: AWS Lambda
**Project Type**: Backend service + Infrastructure
**Performance Goals**: Query latency <100ms p99
**Constraints**: GSI must use on-demand capacity, KEYS_ONLY projection
**Scale/Scope**: Foundation for all account linking flows

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| IAM least-privilege | PASS | No new IAM permissions needed (GSI uses table permissions) |
| Infrastructure as Code | PASS | GSI defined in Terraform |
| DynamoDB best practices | PASS | GSI with composite key, KEYS_ONLY projection |
| No table scans | PASS | GSI enables O(1) lookups |

**Gate Status**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/1180-get-user-by-provider-sub/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # GSI design research
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
infrastructure/terraform/modules/dynamodb/
└── main.tf              # Add by_provider_sub GSI

src/lambdas/dashboard/
└── auth.py              # Add get_user_by_provider_sub(), update _link_provider()

tests/unit/dashboard/
└── test_auth_provider_sub.py  # New test file for provider_sub lookup
```

**Structure Decision**: Infrastructure change (Terraform) + Backend code change (Python)

## Design

### GSI Schema

```hcl
global_secondary_index {
  name            = "by_provider_sub"
  hash_key        = "provider_sub"
  projection_type = "KEYS_ONLY"
}
```

**Key Format**: `{provider}:{sub}` (e.g., "google:118368473829470293847")

**Why KEYS_ONLY**:
- Minimizes GSI storage costs
- Query returns PK, then use get_item for full user
- Acceptable latency (~10ms overhead for get_item)

### Function Signature

```python
def get_user_by_provider_sub(
    table: Any,
    provider: Literal["google", "github"],
    sub: str,
) -> User | None:
    """Look up user by OAuth provider subject claim.

    Args:
        table: DynamoDB table resource
        provider: OAuth provider ("google" or "github")
        sub: OAuth subject claim (provider's user ID)

    Returns:
        User if found, None otherwise
    """
```

### _link_provider() Update

When linking a provider, also set the `provider_sub` attribute:

```python
# In _link_provider():
update_expr += ", provider_sub = :provider_sub"
expr_values[":provider_sub"] = f"{provider}:{claims['sub']}"
```

### Query Flow

1. Build composite key: `provider_sub = f"{provider}:{sub}"`
2. Query GSI `by_provider_sub` with hash key
3. If no results: return None
4. If result found: extract PK, call get_item for full user
5. Parse and return User model

## Complexity Tracking

No constitution violations - this is a straightforward GSI addition following existing patterns.

## Testing Strategy

### Unit Tests (moto)

1. `test_get_user_by_provider_sub_found` - User with matching provider_sub
2. `test_get_user_by_provider_sub_not_found` - No matching user
3. `test_get_user_by_provider_sub_different_provider` - Same sub, different provider
4. `test_get_user_by_provider_sub_empty_inputs` - Edge case handling
5. `test_link_provider_populates_provider_sub` - Verify _link_provider() sets attribute

### Integration Tests

- Verify GSI lookup works against real DynamoDB in preprod

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| GSI propagation delay | Low | Medium | Test in preprod before federation flows |
| Existing users without provider_sub | Medium | Low | Function returns None, handled by caller |
| Terraform apply failure | Low | Medium | Test in dev workspace first |

## Out of Scope

- Backfilling provider_sub for existing users
- Caching lookups
- Multi-region GSI replication
