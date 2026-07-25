# Plan: OAuth Account Integrity (1395)

**Spec:** `specs/1395-oauth-account-integrity/spec.md`
**Scope:** Code-only. Fix the `Limit=1 + FilterExpression` footgun in three identity
helpers and rewire `handle_oauth_callback` to reuse by stable identity. No infra, no data
deletion, no JWT minting.

## Technical Approach

### 1. Chosen footgun fix — drop `Limit`, filter server-side, paginate to exhaustion

The prompt offered three options. Evaluated against the **verified** GSI facts:

- **(b) Restructure the GSI so it only projects USER records — REJECTED.** The `by_email`
  GSI is keyed on the `email` attribute, and `NOTIFICATION`
  (`notification.py:57`) and `MAGIC_LINK_TOKEN` (`magic_link_token.py:50`) legitimately
  write `email`. There is no attribute we can strip from those items without breaking their
  own access patterns, and DynamoDB has no "project only if entity_type=USER" GSI predicate.
  A sparse index would require a dedicated marker attribute written only by USER — a schema
  change, which FR-011 forbids without owner escalation. So (b) is not available for
  `by_email`. (For `by_provider_sub`/`by_cognito_sub` the index is *already* USER-only, so
  the projection is fine there — the problem there is duplicates, not key confusion.)

- **(a)/(c) Drop `Limit`, apply the `entity_type = USER` filter, page with
  `LastEvaluatedKey` until a USER match or key exhaustion — CHOSEN.** This is correct for
  all three helpers and is the least-invasive change that actually fixes the bug: the query
  shape, index, and IAM permissions are unchanged; only the `Limit` and the result-handling
  loop change. It resolves the `by_email` key-confusion (FR-001) and, combined with the
  deterministic selector below, resolves the duplicate-`sub` nondeterminism
  (FR-002/003/004).

**Justification for the least-invasive correct option:** keeping `Limit=1` would preserve
the bug (both false-`None` and nondeterminism), so it is not on the table (per the task's
"do NOT silently keep Limit=1 if non-USER items can share the key" — verified they can).
Restructuring the index is a schema change we are forbidden from making unilaterally and is
unnecessary since pagination fully fixes it. Pagination reads at most the handful of items
under one identity key (one human's notifications/tokens/duplicates), so cost is negligible
(T-4), and we still cap pages defensively.

### 2. Shared internal helper

Introduce one private helper to avoid divergence across the three lookups:

```python
def _query_users_by_index(table, index_name, key_expr, attr_values, *, max_pages=10):
    """Return ALL USER items under a GSI key, paginating and filtering entity_type=USER.

    - No Limit: the entity_type=USER FilterExpression is applied across the full key match,
      so non-USER items sharing the hash key (NOTIFICATION, MAGIC_LINK_TOKEN under by_email)
      can never mask a real USER.
    - Bounded by max_pages as a DoS guard (T-4); realistic cardinality is tiny.
    """
```

Each public helper then:
- calls `_query_users_by_index(...)`,
- if zero USER items → return `None` (genuine miss),
- if one → return it,
- if more than one → **FR-005** WARN log (sanitized key prefix + count), then **FR-004**
  select `min(users, key=lambda u: (u.created_at, u.user_id))` and return it.

`get_user_by_email_gsi` keeps its "at most one USER per email" invariant, so >1 there is
itself a fragmentation signal and gets the same WARN + deterministic pick (defensive).

### 3. Callback rewrite — reuse by stable identity first (FR-006/007/009)

In `handle_oauth_callback` (`auth.py:2143-2453`), replace the email-only resolution
(`existing_user = get_user_by_email_gsi(...)` at line 2248) with an ordered resolution that
preserves every downstream branch:

```python
existing_by_sub = get_user_by_provider_sub(table, provider, cognito_sub) if cognito_sub else None
existing_by_cognito = get_user_by_cognito_sub(table, cognito_sub) if cognito_sub else None
existing_by_email = get_user_by_email_gsi(table, email)

# Stable identity wins for REUSE (FR-006): the same human, resolved by server-derived sub.
stable_user = existing_by_sub or existing_by_cognito

# Preserve AUTH_023 (FR-007/008): a sub already owned by a DIFFERENT user than the
# email match is still a cross-account conflict — unchanged semantics, now fed by the
# reliable lookups.
existing_user = stable_user or existing_by_email
```

- The existing `AUTH_023` block (`auth.py:2250-2275`) is retained; its condition
  (`existing_by_sub and (not existing_user or existing_by_sub.user_id != existing_user.user_id)`)
  is re-expressed so that when `stable_user` and `existing_by_email` **diverge**, the
  conflict path fires (FR-007) instead of minting a third record.
- The `AUTH_022` block and Flow 3 / Flow 5 auto-link logic (`auth.py:2277-2356`) are
  unchanged — they operate on `existing_user` which now resolves more reliably.
- The `if existing_user:` reuse branch (`auth.py:2361`) vs `else: _create...`
  (`auth.py:2390`) is unchanged in structure; it now only reaches `else` when all three
  lookups miss (FR-009).

**Note on `cognito_sub` vs `provider_sub`:** the id_token `sub` (`auth.py:2238`) is the
Cognito user-pool sub. `provider_sub` in the table is `"{provider}:{sub}"`
(`auth.py:2571`). The callback already passes `cognito_sub` into
`get_user_by_provider_sub(table, provider, cognito_sub)` at line 2253 (composing the
`"google:{sub}"` key internally), and `_update_cognito_sub` stores the same value as
`cognito_sub`. So both stable-identity lookups key off the one server-validated sub — no
new claim is trusted.

## Data Model Notes (verified)

- Table: `${env}-sentiment-users`, single-table, `PK`/`SK`.
- GSIs (all `projection_type = ALL`, hash-only): `by_email`(email), `by_cognito_sub`(cognito_sub),
  `by_provider_sub`(provider_sub), `by_entity_status`(entity_type/status).
  Verified `infrastructure/terraform/modules/dynamodb/main.tf:310-345`.
- Index membership by writer:
  - `by_email` ← USER, NOTIFICATION, MAGIC_LINK_TOKEN (three writers → key confusion).
  - `by_cognito_sub` ← USER only.
  - `by_provider_sub` ← USER only.
- `created_at` is present on `User` (used for FR-004 ordering; confirmed field on the model
  during task authoring — see tasks T-000 verification step).
- **No schema change.** No attribute added, no projection changed, no new GSI, no IAM
  change. `terraform plan` must be a no-op (SC-5).

## Contracts

Internal Python contracts only (no HTTP contract change; `OAuthCallbackResponse` shape is
unchanged):

- `get_user_by_email_gsi(table, email) -> User | None` — now returns the USER even amid
  non-USER key collisions.
- `get_user_by_provider_sub(table, provider, sub) -> User | None` — deterministic among
  duplicates.
- `get_user_by_cognito_sub(table, cognito_sub) -> User | None` — deterministic among
  duplicates.
- `handle_oauth_callback(...) -> OAuthCallbackResponse` — same signature and response
  fields; behavior: reuse-by-stable-identity, one record per identity.

## Constitution Check

- **Security & access control:** identity derived from validated id_token only (T-2);
  no unauthenticated path added. Compliant.
- **No raw user text in logs:** FR-005/T-3 mandate `sanitize_for_log` + truncated prefixes.
  Compliant.
- **IaC / no ad-hoc infra:** zero infra change; SC-5 asserts no `terraform plan` diff.
  Compliant with the standing "no new AWS resources" constraint.
- **No unjustified fallbacks / no silent failure:** every lookup error path logs
  (FR-010); reuse ordering is explicit and observable. Compliant.
- **Parameterized data access:** all queries use `ExpressionAttributeValues` binding
  (no string interpolation into expressions). Compliant.
- **Testability:** moto-based unit tests reproduce the footgun and the reuse (SC-1/2/3).
  Compliant.

No constitution violations. No complexity-tracking exceptions required.

## Adversarial Review #2

Cross-artifact drift check between `spec.md` (incl. AR#1 + Clarifications) and this plan.

| Check | Result |
|---|---|
| Every FR has a plan mechanism | FR-001→pagination+filter; FR-002/003/004→shared helper + earliest-`created_at` selector; FR-005→WARN log in helper; FR-006/007/009→callback stable-identity ordering; FR-008→existing branches retained; FR-010→error paths log; FR-011→no schema change / SC-5. No orphan FRs. |
| Plan introduces nothing beyond spec scope | Only the shared `_query_users_by_index` helper + callback resolution reorder. No JWT (1396), no dup deletion (1397), no infra. Aligned. |
| Footgun-fix option matches AR#1 C-1/H-3 | Plan chooses (a)/(c) pagination for all three helpers *and* the deterministic selector — exactly what C-1/H-3 required. Consistent. |
| Auto-link preservation (C-2/FR-008) | Plan retains AUTH_022/023 + Flow 3/5 blocks and re-expresses the divergence condition per FR-007. Consistent. |
| `created_at` assumption | Verified present (`user.py:48`); plan and Clarification #2 agree. No drift. |
| Eventual-consistency / race (EC-1/EC-4, H-1/H-2) | Plan documents them as accepted/scoped-out and points OQ-1 at the owner; does not claim the race is closed. Consistent with AR#1. |
| Constitution check vs FRs | Logging, IaC-no-op, no-silent-fallback, parameterized queries all mapped. No violation. |
| Contract stability | `OAuthCallbackResponse` shape unchanged; only helper internals + resolution order change. No API drift. |

**Gate: 0 CRITICAL, 0 HIGH cross-artifact drift. Plan is consistent with the spec.**
Proceed to tasks.
