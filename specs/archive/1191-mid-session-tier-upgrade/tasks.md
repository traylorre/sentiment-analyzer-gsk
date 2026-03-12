# Tasks: Mid-Session Tier Upgrade

**Feature**: 1191-mid-session-tier-upgrade
**Generated**: 2026-01-11
**Total Tasks**: 18
**User Stories**: 3 (P1: Immediate Premium Access, P2: Multi-Tab Consistency, P3: Graceful Degradation)

## Phase 1: Setup

- [ ] T001 Add stripe>=10.0.0 to requirements.txt for webhook handling
- [ ] T002 Create webhook event tracking table schema in infrastructure/terraform/modules/dynamodb/main.tf

## Phase 2: Foundational (Backend)

- [ ] T003 Create WebhookEvent model in src/lambdas/shared/models/webhook_event.py
- [ ] T004 Create Stripe signature verification helper in src/lambdas/shared/auth/stripe_utils.py
- [ ] T005 [P] Create map_stripe_plan_to_role() function in src/lambdas/shared/auth/roles.py

## Phase 3: User Story 1 - Immediate Premium Access (P1)

**Goal**: User upgrades to paid and sees premium features within 60s without refresh
**Independent Test**: Trigger webhook → verify role=paid in DynamoDB → verify next /refresh returns paid role

- [ ] T006 [US1] Add handle_stripe_webhook() endpoint to src/lambdas/dashboard/auth.py
- [ ] T007 [US1] Implement atomic role upgrade with TransactWriteItems (role + revocation_id) in src/lambdas/dashboard/auth.py
- [ ] T008 [US1] Add idempotency check (event.id lookup) before processing in src/lambdas/dashboard/auth.py
- [ ] T009 [P] [US1] Add subscription_active and subscription_expires_at to frontend User type in frontend/src/types/auth.ts
- [ ] T010 [US1] Create useTierUpgrade() hook with exponential backoff polling in frontend/src/hooks/use-tier-upgrade.ts
- [ ] T011 [US1] Add upgrade success toast notification in frontend/src/hooks/use-tier-upgrade.ts

## Phase 4: User Story 2 - Multi-Tab Consistency (P2)

**Goal**: Role upgrade broadcasts to all tabs, all tabs refresh state
**Independent Test**: Open 2 tabs → upgrade in tab 1 → verify tab 2 shows paid role within 60s

- [ ] T012 [US2] Create BroadcastChannel sync utility in frontend/src/lib/sync/broadcast-channel.ts
- [ ] T013 [US2] Add ROLE_UPGRADED broadcast on successful upgrade in frontend/src/hooks/use-tier-upgrade.ts
- [ ] T014 [US2] Add BroadcastChannel listener to auth-store.ts to trigger refreshUserProfile() on ROLE_UPGRADED

## Phase 5: User Story 3 - Graceful Degradation (P3)

**Goal**: User sees helpful message if webhook delayed beyond 60s
**Independent Test**: Mock slow webhook → verify timeout message shown → verify retry suggestion

- [ ] T015 [US3] Add timeout fallback message to useTierUpgrade() in frontend/src/hooks/use-tier-upgrade.ts
- [ ] T016 [P] [US3] Add retry button UI that restarts polling in frontend/src/hooks/use-tier-upgrade.ts

## Phase 6: Polish & Cross-Cutting

- [ ] T017 Add unit tests for handle_stripe_webhook() in tests/unit/dashboard/test_stripe_webhook.py
- [ ] T018 Add unit tests for useTierUpgrade hook in frontend/tests/unit/hooks/test-use-tier-upgrade.ts

## Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational)
                       ↓
                Phase 3 (US1: Immediate Premium)
                       ↓
                Phase 4 (US2: Multi-Tab)
                       ↓
                Phase 5 (US3: Graceful Degradation)
                       ↓
                Phase 6 (Polish)
```

**Note**: US2 depends on US1 (needs upgrade flow to broadcast). US3 depends on US1 (needs polling hook to add timeout).

## Parallel Execution Opportunities

### Phase 2 Parallel Group
- T005 (role mapping) can run in parallel with T003, T004

### Phase 3 Parallel Group
- T009 (frontend types) can run in parallel with T006-T008 (backend)

### Phase 5 Parallel Group
- T016 (retry UI) can run in parallel with T015 (timeout message)

## Implementation Strategy

**MVP Scope**: Phase 1-3 (Setup + Foundational + US1)
- Delivers core value: immediate premium access after payment
- Backend webhook handling complete
- Frontend polling with success notification

**Incremental Delivery**:
1. Phase 1-3: Core tier upgrade flow (MVP)
2. Phase 4: Multi-tab sync (nice-to-have)
3. Phase 5: Timeout UX (polish)
4. Phase 6: Tests (quality gate)
