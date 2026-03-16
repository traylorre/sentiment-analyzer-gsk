# Feature Specification: Auth Security Hardening

**Feature Branch**: `1222-auth-security-hardening`
**Created**: 2026-03-16
**Status**: Draft
**Input**: Fix critical authentication vulnerabilities: provider linking uniqueness, account linking authorization, email verification state machine bypass, and PKCE support

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prevent Provider Identity Theft (Priority: P1)

A malicious user (User A) must not be able to link their account to an OAuth provider identity (e.g., Google sub) that already belongs to another user (User B). If User A attempts to link a provider sub that User B has already linked, the system must reject the request and leave both accounts unmodified.

**Why this priority**: This is an account takeover vulnerability. If exploited, an attacker could authenticate as another user via their OAuth provider, gaining full access to the victim's data, sessions, and configurations.

**Independent Test**: Can be tested by creating two users, linking User B to a Google sub, then attempting to link User A to the same Google sub — expecting rejection.

**Acceptance Scenarios**:

1. **Given** User B has linked their account to Google OAuth sub `google:12345`, **When** User A attempts to link to Google sub `google:12345`, **Then** the system rejects the request with an error and neither account is modified.
2. **Given** User A has no provider links, **When** User A links to an unlinked Google sub `google:99999`, **Then** the link succeeds and the sub is recorded exclusively for User A.
3. **Given** User B has linked to GitHub sub `github:abc`, **When** User A links to Google sub `google:xyz` (different provider, different sub), **Then** both links coexist without conflict.
4. **Given** a race condition where two users simultaneously attempt to link the same provider sub, **When** both requests process concurrently, **Then** exactly one succeeds and the other is rejected (no partial states).

---

### User Story 2 - Prevent Unauthorized Account Merging (Priority: P1)

When a user requests to link or merge accounts, the system must verify that the authenticated user is the owner of the source account. An attacker must not be able to merge a victim's account into their own by specifying an arbitrary target user ID.

**Why this priority**: Account merging without authorization verification could allow data hijacking — an attacker merges a victim's configurations, alerts, and session history into their own account.

**Independent Test**: Can be tested by authenticating as User A and attempting to merge User B's account — expecting authorization failure.

**Acceptance Scenarios**:

1. **Given** User A is authenticated, **When** User A calls the account linking endpoint with a target pointing to User B, **Then** the system verifies User A's identity matches the source account and rejects if mismatched.
2. **Given** User A is authenticated and owns both the source and target accounts (anonymous-to-authenticated migration), **When** User A merges their anonymous session into their authenticated account, **Then** the merge succeeds with full data transfer.
3. **Given** an unauthenticated request, **When** the account linking endpoint is called, **Then** the system returns 401 Unauthorized.

---

### User Story 3 - Enforce Email Verification State Machine (Priority: P2)

The system must enforce the role-verification state machine at the data layer, not just at the application model layer. A user must not achieve an elevated role (e.g., "free" or "paid") without completing actual email verification. Direct database modifications must not bypass the state machine.

**Why this priority**: If the state machine only runs in application-layer validation, any process that writes directly to the database (migration scripts, admin tools, race conditions) could bypass verification requirements and elevate privileges.

**Independent Test**: Can be tested by attempting a direct database update to set `verification=verified` on an anonymous user — expecting the conditional write to enforce the state machine.

**Acceptance Scenarios**:

1. **Given** an anonymous user with `verification=none`, **When** a database update attempts to set `verification=verified` without a valid verification token, **Then** the conditional write fails and the user remains `anonymous:none`.
2. **Given** an anonymous user who completes magic link verification, **When** the verification process sets `verification=verified`, **Then** the role auto-upgrades to `free:verified` via the established state machine.
3. **Given** a user with `role=free, verification=verified`, **When** an attempt is made to downgrade `verification` to `none`, **Then** the conditional write prevents the downgrade.

---

### User Story 4 - Add PKCE to OAuth Authorization Flow (Priority: P2)

The OAuth authorization flow must include PKCE (Proof Key for Code Exchange) to prevent authorization code interception attacks. The system must generate a code_verifier, derive a code_challenge, include it in the authorization request, and validate it during token exchange.

**Why this priority**: Without PKCE, if the client is public (JavaScript-based), an attacker who intercepts the authorization code can exchange it for tokens. PKCE makes intercepted codes useless without the original code_verifier.

**Independent Test**: Can be tested by initiating an OAuth flow, verifying the authorization URL contains `code_challenge` and `code_challenge_method`, then verifying the token exchange includes the `code_verifier`.

**Acceptance Scenarios**:

1. **Given** a user initiates OAuth login, **When** the authorization URL is generated, **Then** it includes `code_challenge` (S256) and `code_challenge_method=S256` parameters.
2. **Given** a valid authorization code and code_verifier, **When** the token exchange is performed, **Then** the exchange succeeds and returns valid tokens.
3. **Given** a valid authorization code but wrong code_verifier, **When** the token exchange is attempted, **Then** the exchange fails with an error.
4. **Given** the code_verifier is stored in the OAuth state record, **When** the callback processes the code, **Then** the code_verifier is retrieved from the state record and included in the token exchange.

---

### Edge Cases

- What happens when a provider changes a user's sub (e.g., Google account merge)? The old sub becomes orphaned. The system should handle lookup failures gracefully without crashing.
- *(Out of scope)* Provider unlinking is a separate feature. This spec only hardens linking and merging. Lockout prevention for unlinking is deferred to future work.
- What happens during concurrent OAuth callbacks for the same user from different providers? Each callback should process independently with atomic state updates.
- What happens when the code_verifier expires between authorization request and callback? The OAuth state record has a 5-minute TTL — if callback arrives after expiry, the flow fails gracefully with a "session expired" message.
- What happens when an attacker replays a consumed OAuth state? The conditional update on `used=false` ensures exactly-once consumption. Replays receive a generic error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST reject provider linking when the `provider_sub` is already linked to a different user account. Enforcement applies to new linking operations only; existing data is not retroactively blocked.
- **FR-002**: System MUST use an atomic check-and-set operation to enforce provider sub uniqueness, preventing race conditions between concurrent linking attempts.
- **FR-012**: System MUST provide an audit capability to scan existing user data for duplicate `provider_sub` entries across accounts. Duplicates are flagged for manual review, not auto-resolved.
- **FR-003**: System MUST verify that the authenticated user's identity matches the source account in all account linking and merging requests.
- **FR-004**: System MUST return 403 Forbidden when an authenticated user attempts to link or merge an account they do not own.
- **FR-005**: System MUST enforce the role-verification state machine at the data layer via conditional writes, not solely via application-layer model validation.
- **FR-006**: System MUST prevent database writes from setting `verification=verified` without a corresponding valid verification token consumption in the same transaction.
- **FR-007**: System MUST include PKCE `code_challenge` (S256 method) in all OAuth authorization URLs.
- **FR-008**: System MUST store the `code_verifier` in the OAuth state record alongside CSRF state, provider, and redirect URI.
- **FR-009**: System MUST include the `code_verifier` in the token exchange request to the identity provider.
- **FR-010**: System MUST return consistent, generic error messages for all authentication failures to prevent information leakage about which users have linked which providers.
- **FR-011**: System MUST log all account linking and merging attempts (success and failure) with correlation IDs for security audit purposes.

### Key Entities

- **Provider Link**: A binding between a user account and an OAuth provider identity (provider name + provider sub). Must be globally unique per provider sub.
- **Account Merge**: A one-time operation that transfers data from a source account to a target account, leaving a tombstone on the source. Must be idempotent and authorized.
- **OAuth State Record**: A short-lived (5-minute TTL) record that stores CSRF state, PKCE code_verifier, provider, and redirect URI for an in-flight OAuth authorization flow.
- **Verification State Machine**: The lifecycle of a user's email verification status (`none → pending → verified`) and the corresponding role transitions (`anonymous → free → paid`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero provider sub collisions — no two user accounts can share the same provider identity, verified by automated tests including concurrent race condition scenarios.
- **SC-002**: All account linking requests are authorization-checked — 100% of link/merge calls verify the authenticated user owns the source account.
- **SC-003**: Role elevation requires verified email — no user achieves `free` or `paid` role without completing email verification, enforced at the data layer.
- **SC-004**: All OAuth flows use PKCE — 100% of authorization URLs include `code_challenge` and all token exchanges include `code_verifier`.
- **SC-005**: All security-critical operations are audit-logged with correlation IDs, enabling full reconstruction of any account linking or merge event.
- **SC-006**: Existing unit tests continue to pass — zero regressions from security hardening changes.
- **SC-007**: New security tests cover all 4 vulnerability classes with both positive (valid operation succeeds) and negative (attack rejected) cases.

## Clarifications

### Session 2026-03-16

- Q: Should existing duplicate provider_sub entries be migrated or only new links enforced? → A: Audit existing data for duplicates first, then enforce on new links only. Flag existing violations for manual review, do not auto-resolve.
- Q: Is provider unlinking (with lockout prevention) in scope? → A: No. This feature only hardens linking and merging. Provider unlinking is deferred to future work.
- Q: Is the Cognito client public or confidential? → A: Public (`generate_secret = false` in cognito/main.tf:118). PKCE remains P2 critical.

## Assumptions

- The Cognito client is configured as a public client (`generate_secret = false` in `cognito/main.tf:118`), making PKCE essential rather than optional. Verified from Terraform source.
- The existing `provider_sub` GSI on the users table can be used for uniqueness lookups, but the actual uniqueness enforcement must happen via conditional writes (GSI is eventually consistent).
- The existing tombstone pattern for account merges is architecturally sound — this feature adds authorization checks, not architectural changes.
- Magic link verification is the primary path for the `none → verified` state transition. OAuth provider `email_verified` claims are a secondary path that also triggers the transition.
