# Implementation Plan: Mid-Session Tier Upgrade

**Branch**: `1191-mid-session-tier-upgrade` | **Date**: 2026-01-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1191-mid-session-tier-upgrade/spec.md`
**Parent Spec**: `specs/1126-auth-httponly-migration/spec-v2.md` (A19/B9)

## Summary

Implement immediate premium access after payment during active session. Backend receives Stripe webhook and atomically updates user role + revocation_id (forcing token refresh). Frontend polls with exponential backoff (1s, 2s, 4s, 8s, 16s, 29s) to detect role change. Cross-tab sync broadcasts role updates to all tabs.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, boto3 (DynamoDB), Zustand (state), BroadcastChannel API
**Storage**: DynamoDB (existing tables: Users, Sessions)
**Testing**: pytest (backend), vitest (frontend)
**Target Platform**: AWS Lambda (backend), Browser (frontend)
**Project Type**: web (frontend + backend)
**Performance Goals**: 95% of upgrades detected within 10s, 99.9% within 60s
**Constraints**: Atomic transactions (no partial state), idempotent webhook handling
**Scale/Scope**: Extends existing auth infrastructure, no new DynamoDB tables

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.6 (No Quick Fixes) | PASS | Following full speckit workflow |
| Amendment 1.8 (IAM Managed Policy) | N/A | No new IAM policies needed |
| Amendment 1.12 (Mandatory Speckit) | PASS | specify → plan → tasks → implement |
| Amendment 1.15 (No Fallback Config) | CHECK | Stripe webhook secret must use `os.environ["KEY"]` |
| Cost Sensitivity | PASS | No new infrastructure, uses existing Lambda/DynamoDB |

## Project Structure

### Documentation (this feature)

```text
specs/1191-mid-session-tier-upgrade/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
# Backend (Python - AWS Lambda)
src/lambdas/
├── dashboard/
│   └── auth.py              # EXTEND: Add handle_stripe_webhook()
├── shared/
│   ├── models/user.py       # EXISTS: Has subscription fields
│   └── auth/roles.py        # EXISTS: Has role resolution

# Frontend (TypeScript - Next.js)
frontend/src/
├── stores/
│   └── auth-store.ts        # EXTEND: Add subscription selectors
├── lib/
│   └── sync/
│       └── broadcast-channel.ts  # NEW: Cross-tab sync utility
├── hooks/
│   └── use-tier-upgrade.ts  # NEW: Polling hook with exponential backoff
└── types/
    └── auth.ts              # EXTEND: Add subscription fields to User

# Tests
tests/
├── unit/
│   └── dashboard/
│       └── test_stripe_webhook.py  # NEW: Webhook handler tests
└── integration/
    └── test_tier_upgrade.py        # NEW: End-to-end upgrade flow

frontend/tests/unit/
├── hooks/
│   └── test-use-tier-upgrade.ts    # NEW: Polling hook tests
└── lib/
    └── test-broadcast-channel.ts   # NEW: Cross-tab sync tests
```

**Structure Decision**: Extends existing web application structure. Backend changes to `src/lambdas/dashboard/auth.py` (where TransactWriteItems pattern exists). Frontend adds new utility + hook files.
