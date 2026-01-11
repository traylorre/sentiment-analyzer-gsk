# Feature Specification: Mid-Session Tier Upgrade

**Feature Branch**: `1191-mid-session-tier-upgrade`
**Created**: 2026-01-11
**Status**: Draft
**Input**: User description: "A19: Mid-Session Tier Upgrade Flow - Implement immediate premium access after payment during active session"
**Parent Spec**: `specs/1126-auth-httponly-migration/spec-v2.md` (Acceptance Criteria A19/B9)

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Immediate Premium Access After Payment (Priority: P1)

A user currently logged in with a free account makes a subscription payment. They expect premium features to be available immediately after payment confirmation, without needing to log out, refresh the page, or wait for token expiration (up to 15 minutes).

**Why this priority**: Core user value proposition - users who pay expect instant gratification. Delayed access creates frustration and support tickets.

**Independent Test**: Can be fully tested by simulating a payment webhook and verifying premium features unlock within the polling window.

**Acceptance Scenarios**:

1. **Given** a logged-in free user completes payment, **When** the payment is confirmed, **Then** premium features become accessible within 60 seconds without manual refresh
2. **Given** a logged-in free user completes payment, **When** the backend processes the upgrade, **Then** all active sessions for that user reflect the new subscription tier
3. **Given** a logged-in free user completes payment, **When** polling detects the upgrade, **Then** the user sees a success confirmation message

---

### User Story 2 - Multi-Tab Consistency (Priority: P2)

A user has multiple browser tabs open with the application. When they upgrade their subscription in one tab, all other tabs should reflect the new subscription tier without requiring manual refresh.

**Why this priority**: Users expect consistent experience across tabs. Stale state in other tabs creates confusion and bugs.

**Independent Test**: Can be tested by opening two tabs, upgrading in one, and verifying the other tab reflects the new tier on next interaction.

**Acceptance Scenarios**:

1. **Given** a user has multiple tabs open, **When** they upgrade in one tab, **Then** all tabs reflect the new tier within 60 seconds
2. **Given** a user has multiple tabs open, **When** upgrade notification is broadcast, **Then** each tab refreshes its authentication state automatically

---

### User Story 3 - Graceful Degradation on Delays (Priority: P3)

If the payment processing system experiences delays beyond the normal polling window, the user receives helpful guidance rather than being left in an uncertain state.

**Why this priority**: Edge case handling that prevents user confusion during system stress.

**Independent Test**: Can be tested by simulating webhook delay beyond polling window and verifying user receives appropriate message.

**Acceptance Scenarios**:

1. **Given** payment processing is delayed beyond 60 seconds, **When** polling times out, **Then** user sees a message suggesting manual page refresh
2. **Given** network errors occur during polling, **When** individual poll requests fail, **Then** polling continues with remaining attempts

---

### Edge Cases

- What happens when the user closes the payment tab before upgrade confirmation?
- How does the system handle concurrent upgrade requests for the same user?
- What happens if the webhook fails and is retried by the payment provider?
- How does the system behave if the user's session expires during the upgrade process?

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST upgrade user subscription tier atomically with session invalidation (both succeed or both fail)
- **FR-002**: System MUST poll for tier changes using exponential backoff (1s, 2s, 4s, 8s, 16s, 29s)
- **FR-003**: System MUST complete upgrade detection within 60 seconds of payment confirmation
- **FR-004**: System MUST broadcast tier changes to all active browser tabs for the user
- **FR-005**: System MUST display success notification when upgrade is detected
- **FR-006**: System MUST display timeout guidance if upgrade is not detected within polling window
- **FR-007**: System MUST ensure old sessions cannot access premium features after upgrade (no stale state)
- **FR-008**: System MUST handle webhook retries idempotently (duplicate webhooks don't cause errors)
- **FR-009**: System MUST log upgrade events for audit trail

### Key Entities

- **User**: Account holder with subscription tier (free, paid, operator)
- **Session**: Active authentication state tied to a browser/device
- **Subscription**: Payment relationship with tier and validity period
- **Upgrade Event**: Record of tier change with timestamp and source

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 95% of users see premium features unlock within 10 seconds of payment confirmation
- **SC-002**: 99.9% of upgrades complete within 60-second polling window
- **SC-003**: Zero incidents of stale tier state (old tokens accessing wrong tier)
- **SC-004**: Multi-tab consistency achieved within 60 seconds of upgrade
- **SC-005**: Webhook processing handles 100 concurrent upgrade events without errors
- **SC-006**: No duplicate upgrade events logged for single payments

## Assumptions

- Payment provider delivers webhooks within 60 seconds under normal load
- Users have stable network connections during upgrade process
- Browser supports cross-tab communication mechanisms
- Existing session management infrastructure can be extended (not replaced)

## Dependencies

- Existing authentication/session infrastructure (from 1126-auth-httponly-migration)
- Payment provider webhook integration
- Cross-tab synchronization mechanism
