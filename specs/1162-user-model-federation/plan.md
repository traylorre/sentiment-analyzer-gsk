# Implementation Plan: User Model Federation Fields

**Branch**: `1162-user-model-federation` | **Date**: 2026-01-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1162-user-model-federation/spec.md`

## Summary

Add 9 federation fields to the User model to support multi-provider authentication, role-based access control, and email verification workflows. Also implement ProviderMetadata class for per-provider OAuth data storage. This is an additive change with backward compatibility for existing user records.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: pydantic (existing), boto3/DynamoDB (existing)
**Storage**: DynamoDB (NoSQL - schema-flexible, no migration required)
**Testing**: pytest with moto mocks
**Target Platform**: AWS Lambda
**Project Type**: Web application (backend Lambda + frontend Next.js)
**Performance Goals**: N/A (data model change, no performance impact)
**Constraints**: Backward compatibility with existing user records
**Scale/Scope**: ~1000 existing user records

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security & Access Control | ✅ PASS | No new secrets, roles stored encrypted in DynamoDB |
| NoSQL/Expression safety | ✅ PASS | Using pydantic models, boto3 param binding |
| Implementation Accompaniment | ✅ PASS | Unit tests required for new fields |
| Deterministic Time Handling | ✅ PASS | `datetime` fields use existing patterns |
| Pre-Push Requirements | ✅ PASS | Standard workflow applies |

## Project Structure

### Documentation (this feature)

```text
specs/1162-user-model-federation/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/lambdas/shared/models/
└── user.py              # User model + ProviderMetadata class (MODIFY)

tests/unit/lambdas/shared/models/
└── test_user.py         # Unit tests for new fields (CREATE/MODIFY)
```

**Structure Decision**: Single file modification (`user.py`) with new class definition (`ProviderMetadata`). Follows existing project structure.

## Complexity Tracking

No constitution violations. This is a straightforward additive data model change.

---

## Phase 0: Research

No research needed - this feature derives from spec-v2.md which already contains:
- Complete field definitions with types
- Backward compatibility requirements
- State machine constraints (deferred to Feature 1163)

**Decision**: Proceed directly to Phase 1 (Design & Contracts).

---

## Phase 1: Design & Contracts

### Data Model

See [data-model.md](./data-model.md) for complete entity definitions.

**Summary of Changes to User Model:**

| Field | Type | Default | Source |
|-------|------|---------|--------|
| `role` | `Literal["anonymous", "free", "paid", "operator"]` | `"anonymous"` | NEW |
| `verification` | `Literal["none", "pending", "verified"]` | `"none"` | NEW |
| `pending_email` | `str \| None` | `None` | NEW |
| `primary_email` | `str \| None` | `None` | RENAME from `email` (keep alias) |
| `linked_providers` | `list[Literal["email", "google", "github"]]` | `[]` | NEW |
| `provider_metadata` | `dict[str, ProviderMetadata]` | `{}` | NEW |
| `last_provider_used` | `Literal["email", "google", "github"] \| None` | `None` | NEW |
| `role_assigned_at` | `datetime \| None` | `None` | NEW |
| `role_assigned_by` | `str \| None` | `None` | NEW |

**New Class: ProviderMetadata**

| Field | Type | Required |
|-------|------|----------|
| `sub` | `str \| None` | No |
| `email` | `str \| None` | No |
| `avatar` | `str \| None` | No |
| `linked_at` | `datetime` | Yes |
| `verified_at` | `datetime \| None` | No |

### Backward Compatibility Strategy

1. **Field Alias**: `email` → `primary_email` with pydantic `Field(alias="email")` for serialization compatibility
2. **Optional New Fields**: All new fields have defaults, existing records load without errors
3. **Deprecated Fields**: `auth_type` and `is_operator` retained but marked deprecated
4. **Computed Property**: `is_operator` can be computed from `role == "operator"`

### API Contracts

No new API endpoints required. Existing endpoints return User model which will include new fields when populated.

---

## Implementation Approach

1. **Add ProviderMetadata class** to `user.py` (pydantic BaseModel)
2. **Add new fields** to User class with appropriate defaults
3. **Add field alias** for `primary_email` ↔ `email` compatibility
4. **Add deprecation markers** for `auth_type` and `is_operator`
5. **Write unit tests** covering:
   - New field serialization/deserialization
   - Default values
   - Backward compatibility with existing records
   - ProviderMetadata nested model

---

## Artifacts Generated

- [x] plan.md (this file)
- [ ] research.md (not needed - well-specified feature)
- [ ] data-model.md (create next)
- [ ] tasks.md (created by /speckit.tasks)
