# Research: Auth Security Hardening (1222)

## R1: Provider Sub Uniqueness Enforcement

**Decision**: Use pre-check GSI query + DynamoDB conditional write for atomicity.

**Rationale**: The `by_provider_sub` GSI already exists (Feature 1180). A GSI query before `_link_provider()` catches 99%+ of duplicates. The remaining race condition window (GSI eventual consistency) is closed by adding a conditional write that checks `provider_sub` doesn't already exist on the target user record. Since each user has exactly one `provider_sub` value, the uniqueness is enforced per-user at the item level.

**Alternatives considered**:
- DynamoDB Transactions (TransactWriteItems) with a separate uniqueness table: Rejected — adds a new table, increases complexity, and the GSI + conditional write approach is sufficient for the write patterns.
- Application-level locking: Rejected — Lambda is stateless, no shared lock available.

**Implementation approach**:
1. In `_link_provider()`, before the update: query `by_provider_sub` GSI for `{provider}:{sub}`
2. If a different user already owns that sub, return error immediately
3. If the same user owns it (re-link), proceed (idempotent)
4. Add audit logging for both success and rejection

## R2: Account Merge Authorization

**Decision**: Compare JWT `sub` claim from the request's auth context against `current_user_id` parameter.

**Rationale**: The `current_user_id` is extracted by `get_user_id_from_event()` in the router, which reads it from the JWT token. The `link_to_user_id` in the request body is the target account. Authorization means verifying the caller owns the source account — which is already true if `current_user_id` comes from the JWT. The vulnerability is that the endpoint doesn't verify this chain is intact (e.g., a malicious client could tamper with the user_id extraction).

**Implementation approach**:
1. In `link_accounts()`, add explicit check: `current_user_id` must equal the authenticated user's JWT `sub`
2. Verify the merge direction: the authenticated user merges FROM their current account TO the target
3. Return 403 with generic message on mismatch

## R3: Verification State Machine at Data Layer

**Decision**: Add ConditionExpression to DynamoDB updates that set `verification=verified`.

**Rationale**: Currently `_mark_email_verified()` (line 2618) and `complete_email_link()` (line 3120) use unconditional SET operations. Adding a ConditionExpression ensures only valid transitions occur at the data layer, regardless of how the write is triggered.

**Implementation approach**:
1. In `_mark_email_verified()`: Add `ConditionExpression="verification <> :verified OR attribute_not_exists(verification)"` — prevents re-verification of already-verified users (idempotent but logged)
2. In `complete_email_link()`: Add `ConditionExpression="attribute_exists(PK)"` + validate that `pending_email` matches the expected email being verified
3. For role transitions: The pydantic validator handles `anonymous:verified → free:verified` auto-upgrade, which is correct. The data layer guard prevents bypassing the `none → verified` transition without going through the proper verification code path.

**Alternatives considered**:
- DynamoDB Streams + Lambda trigger for state machine enforcement: Rejected — adds infrastructure complexity, increases latency, and the conditional write approach is simpler and synchronous.

## R4: PKCE for OAuth Flow

**Decision**: Generate code_verifier (128 bytes URL-safe random), derive code_challenge (SHA-256 + base64url), store verifier in OAuth state record, include in token exchange.

**Rationale**: The Cognito client is public (`generate_secret = false` in cognito/main.tf:118). Without PKCE, authorization codes can be intercepted and exchanged. PKCE is RFC 7636 standard and supported by AWS Cognito.

**Implementation approach**:
1. In `store_oauth_state()`: Generate `code_verifier` (43-128 chars, URL-safe) and store alongside existing fields
2. In `get_authorize_url()`: Accept `code_challenge` parameter, include in URL with `code_challenge_method=S256`
3. In `exchange_code_for_tokens()`: Accept `code_verifier` parameter, include in token exchange POST
4. In `handle_oauth_callback()`: Retrieve `code_verifier` from validated state, pass to token exchange
5. In `validate_oauth_state()`: Return `code_verifier` in the validated state object

**OAuth State Record Changes**:
- New field: `code_verifier` (String, 43-128 chars)
- Stored at creation time, retrieved at validation time
- Not included in any GSI (only accessed via primary key lookup)
