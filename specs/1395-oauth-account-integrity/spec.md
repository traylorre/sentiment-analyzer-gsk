# Feature 1395: OAuth Account Integrity

**Status:** Draft
**Owner:** Auth / Platform
**Related:** 1180 (provider_sub GSI), 1181/1182/1183 (auto-link flows), 1188 (session eviction), 1381 (OAuth session restore), 1396 (app JWT — downstream), 1397 (dup-record data migration — downstream)

## Summary

A single Google (Cognito) identity is minting a **new internal `user_id` on nearly every
login**, fragmenting one human's account across many duplicate `USER` records in
`preprod-sentiment-users`. This feature stops the fragmentation at its source: it fixes a
DynamoDB `Limit=1 + FilterExpression` query footgun in the three identity-lookup helpers,
and rewires the OAuth callback to reuse an existing account by **stable identity**
(`provider_sub` / `cognito_sub`) rather than relying solely on an email lookup that can
silently return nothing.

This feature is **code-only**. It does not delete the existing duplicate records (that is
feature 1397, a separate owner-gated data migration) and it does not mint the application
JWT (feature 1396). It is a prerequisite for 1396: while duplicates exist, the
`by_cognito_sub` lookup on token refresh resolves to a nondeterministic one of the
duplicates, so identity flaps across reloads.

## Root Cause (verified)

Verified this session against current code (`src/lambdas/dashboard/auth.py`), the model
layer (`src/lambdas/shared/models/*.py`), and the table schema
(`infrastructure/terraform/modules/dynamodb/main.tf`).

### Fact 1 — GSI schema (verified: `infrastructure/terraform/modules/dynamodb/main.tf:310-345`)

All three identity GSIs are **hash-only** (no range key) and project **all** attributes:

| GSI | Hash key | Range key | Projection |
|---|---|---|---|
| `by_email` | `email` | (none) | `ALL` |
| `by_cognito_sub` | `cognito_sub` | (none) | `ALL` |
| `by_provider_sub` | `provider_sub` | (none) | `ALL` |

A DynamoDB item is projected into a GSI **iff it carries the hash-key attribute**. So the
membership of each index is determined entirely by which entity types write that attribute.

### Fact 2 — Non-USER entities collide under `by_email` (verified: model layer)

The `email` attribute is written by **three** entity types, not just `USER`:

- `USER` — `src/lambdas/shared/models/user.py:179` (written when non-None)
- `NOTIFICATION` — `src/lambdas/shared/models/notification.py:57`
- `MAGIC_LINK_TOKEN` — `src/lambdas/shared/models/magic_link_token.py:50`

Therefore, for a given email, the `by_email` GSI can contain a `USER` item **plus**
`NOTIFICATION` and/or `MAGIC_LINK_TOKEN` items under the same hash key.

By contrast, `provider_sub` and `cognito_sub` are written **only** by `USER`
(`src/lambdas/shared/models/user.py:181,316` and the `_link_provider` write at
`auth.py:2571-2575`; grep of `src/lambdas/shared/models/*.py` shows no other writer). So
`by_provider_sub` and `by_cognito_sub` contain **only** `USER` items.

### Fact 3 — The `Limit=1 + FilterExpression` footgun (verified: three helpers)

`get_user_by_email_gsi` (`auth.py:476-523`), `get_user_by_provider_sub`
(`auth.py:527-588`), and `get_user_by_cognito_sub` (`auth.py:2906-2945`) all issue:

```python
table.query(
    IndexName=...,
    KeyConditionExpression="<key> = :v",
    FilterExpression="entity_type = :type",   # :type = "USER"
    ExpressionAttributeValues={...},
    Limit=1,
)
```

DynamoDB applies `Limit` to the items matched by the **key condition**, **before** the
`FilterExpression` runs. The engine reads up to `Limit` key-matched items, then filters. So:

- **`by_email` (multiple entity types under the key):** if a `NOTIFICATION` or
  `MAGIC_LINK_TOKEN` item is the first item read under the email hash, `Limit=1` returns
  exactly that one item, the `entity_type = USER` filter drops it, and the helper returns
  **`None` even though a `USER` exists**. This is the primary fragmentation trigger.
- **`by_provider_sub` / `by_cognito_sub` (only USER under the key):** the filter never
  removes the single returned item, so the footgun does not cause a false `None`. But once
  duplicate `USER` records share a `sub` (which is the current live state), `Limit=1`
  returns a **nondeterministic** one of them, so the resolved `user_id` flaps between
  reloads.

### Fact 4 — The callback reuses by email only (verified: `auth.py:2143-2453`)

`handle_oauth_callback` decides create-vs-reuse solely on the email lookup:

- `existing_user = get_user_by_email_gsi(table, email)` (`auth.py:2248`)
- The create/reuse branch is `if existing_user:` (`auth.py:2361`) vs `else: _create...`
  (`auth.py:2390-2393`).
- `get_user_by_provider_sub` is called at `auth.py:2253` **only** to raise `AUTH_023` when
  the sub belongs to a *different* user — it is **not** used to reuse the matching user.

Consequence: when the email lookup returns a false `None` (Fact 3), `existing_user` is
`None`, and unless the provider_sub lookup happens to catch it, the callback falls into the
`else` branch and **mints a brand-new `user_id`**. Because `provider_sub` is written by
`_link_provider` only *after* the user is created, and GSIs are eventually consistent, a
rapid second login can also miss the provider_sub lookup — producing the observed
same-day cluster of duplicates.

### Observed impact (verified: live `preprod-sentiment-users`)

One Cognito `sub` → **10 duplicate `USER` records**, all `auth_type=google`, created within
a single day. On token refresh, `get_user_by_cognito_sub` resolves to a nondeterministic
one of the 10, so the app-side identity is unstable across reloads.

## User Stories

### US-1 — Returning Google user keeps one account
As a returning Google user, when I log in again (same Google identity), I resolve to my
**existing** `user_id` and no new `USER` record is created, so my configurations, alerts,
and history stay attached to one account.

### US-2 — Stable identity across token refresh
As a signed-in user, when my session refreshes (Cognito refresh flow, feature 1381), the
server resolves the **same** `user_id` every time, so my session is not silently swapped
onto a different duplicate record.

### US-3 — Correct account even when email index is polluted
As a user who has notifications and/or magic-link tokens stored under my email, when I log
in, the email lookup still finds **my `USER` record** (not a `NOTIFICATION`/token item),
so I am recognized rather than treated as new.

### US-4 — Auto-link and conflict flows preserved
As a user with an existing email-auth or OAuth account, when I sign in via a second
provider, the existing Feature 1181/1182/1183 auto-link and `AUTH_022`/`AUTH_023` conflict
behaviors continue to apply unchanged — the integrity fix must not regress them.

### US-5 — Operator observability
As an operator, when a lookup falls back, resolves via a secondary key, or encounters
multiple `USER` records under one identity, I see a structured, sanitized log line, so I
can detect residual fragmentation and confirm the fix is working.

## Functional Requirements

- **FR-001** — `get_user_by_email_gsi` MUST return the `USER` record for an email whenever
  one exists, even if `NOTIFICATION` or `MAGIC_LINK_TOKEN` items share the same `email`
  hash key. It MUST NOT rely on `Limit=1` to do so.
- **FR-002** — `get_user_by_provider_sub` MUST return the correct `USER` record for a
  `provider:sub` and MUST select **deterministically** when more than one `USER` currently
  shares that `provider_sub` (until 1397 removes duplicates).
- **FR-003** — `get_user_by_cognito_sub` MUST return the correct `USER` record for a
  `cognito_sub` and MUST select **deterministically** when more than one `USER` currently
  shares that `cognito_sub`.
- **FR-004** — The deterministic selection rule for FR-002/FR-003 MUST be the record with
  the **earliest `created_at`** (oldest wins → the canonical account most likely to hold
  the user's data), with `user_id` ascending as a stable tiebreaker.
- **FR-005** — When any of the three helpers observes **more than one** `USER` under a
  single identity key, it MUST emit a structured WARN log (sanitized via
  `sanitize_for_log`) recording the identity-key type, a truncated key prefix, and the
  count — never the raw email or full sub.
- **FR-006** — `handle_oauth_callback` MUST resolve an existing account by **stable
  identity first**: try `get_user_by_provider_sub(provider, sub)`, then
  `get_user_by_cognito_sub(sub)`, then fall back to `get_user_by_email_gsi(email)`. If any
  resolves to a `USER`, the callback MUST **reuse** that `user_id` and MUST NOT create a
  new record.
- **FR-007** — When the stable-identity lookup and the email lookup both resolve to a
  `USER`, they MUST refer to the **same** `user_id`; if they diverge, the callback MUST
  treat it as the existing `AUTH_023` cross-account conflict (existing behavior), not
  create a third record.
- **FR-008** — The existing Feature 1181/1182/1183 flows MUST be preserved unchanged:
  `AUTH_022` (email not verified by provider), `AUTH_023` (provider already linked to a
  different user), Flow 3 (email→OAuth auto-link), Flow 5 (OAuth→OAuth auto-link), and the
  manual-link `conflict` response.
- **FR-009** — A new `USER` record MUST be created **only** when none of the three lookups
  resolves to an existing `USER` (i.e., a genuinely first-time identity).
- **FR-010** — No lookup may **silently** swallow an error and return `None` in a way that
  causes account creation without a log. Every exception path MUST log via the existing
  `get_safe_error_info` / `sanitize_for_log` helpers (existing behavior retained).
- **FR-011** — The fix MUST NOT change the `by_email`, `by_provider_sub`, or
  `by_cognito_sub` GSI schema or projection. If a schema change is later judged necessary,
  it MUST be escalated to the owner (per the standing "no new AWS resources" constraint) —
  it is out of scope here.

## Success Criteria

- **SC-1** — A returning Google login (same Cognito `sub`) reuses the existing `user_id`;
  DynamoDB `USER` count for that `sub` does not increase. (Verified by moto unit test:
  two sequential `handle_oauth_callback` calls → one `USER` record.)
- **SC-2** — `get_user_by_email_gsi` returns the `USER` even when a `NOTIFICATION` and a
  `MAGIC_LINK_TOKEN` also exist under the same email. (Verified by moto unit test that
  seeds all three under one email.)
- **SC-3** — `get_user_by_provider_sub` and `get_user_by_cognito_sub` return the
  earliest-`created_at` `USER` deterministically when 10 duplicates share the key.
  (Verified by moto unit test seeding 10 records.)
- **SC-4** — All existing OAuth-callback tests (1181/1182/1183/1381) still pass unchanged.
- **SC-5** — No new IAM/GSI/AWS resources introduced; `terraform plan` shows no infra diff.

## Edge Cases

- **EC-1 — GSI eventual consistency after create.** A brand-new user's `provider_sub` /
  `cognito_sub` write may not yet be visible to the GSI on a rapid second login. The
  callback still creates at most one *additional* record in that window; the durable fix is
  that once the write propagates, subsequent logins reuse it. Documented as accepted
  residual risk, mitigated because `_create_authenticated_user` performs a base-table write
  and the reuse path prefers stable identity going forward. (See Adversarial Review #1,
  H-1.)
- **EC-2 — Returning user whose Google email changed.** The stable identity is `sub`, not
  email; because FR-006 tries `provider_sub`/`cognito_sub` first, a user who changed their
  Google email still resolves to their existing `user_id`. The email lookup alone would
  have missed them.
- **EC-3 — Two different humans, same email (email-auth vs Google).** Handled by the
  existing conflict/auto-link matrix (FR-008); the integrity fix must not collapse two
  distinct `sub`s into one account.
- **EC-4 — Concurrent first logins (race).** Two near-simultaneous first-ever callbacks for
  the same brand-new `sub` can each see "no existing user" and both create. This is
  pre-existing and not fully closed here; see Adversarial Review #1 (H-2) for the decided
  scope boundary and the conditional-write mitigation option deferred to 1396/owner.
- **EC-5 — Multiple `USER`s under one key today.** The live table already has 10. The
  helpers must return deterministically (FR-004) so behavior is stable *before* 1397
  deletes them; the deterministic pick is the oldest record.
- **EC-6 — Legacy users missing `provider_sub`.** Early duplicates created before
  1180/1222 may lack `provider_sub`; they are absent from `by_provider_sub` but present in
  `by_cognito_sub` (Cognito sub is set on OAuth login). FR-006's cognito_sub fallback
  covers them.

## Threat Model

- **T-1 — Account takeover via key confusion.** An attacker who can write a
  `NOTIFICATION`/`MAGIC_LINK_TOKEN` under a victim's email must not be able to steer the
  email lookup. Mitigation: the fix filters to `entity_type = USER` across the full key
  match (not just the first item), so injected non-USER items cannot masquerade as the
  user; and reuse prefers `sub` (server-derived from a validated id_token), not email.
- **T-2 — Identity forgery via client input.** `cognito_sub` and `provider_sub` are derived
  from the validated OAuth id_token (`decode_id_token`, `auth.py:2236-2238`), never from
  client-supplied fields. No change; reaffirmed.
- **T-3 — Log-based info leak.** New multi-record and fallback logs (FR-005) must not emit
  raw email or full sub. Mitigation: use `sanitize_for_log` and truncated prefixes, mirror
  existing patterns in these helpers.
- **T-4 — Denial via unbounded pagination.** Dropping `Limit` and paginating a polluted key
  could read many items. Mitigation: bound the scan with a sane page cap and stop at the
  first (deterministically selected) `USER`; realistic key cardinality is tiny (one user's
  notifications/tokens), so cost is negligible.

## Adversarial Review #1

Attacking the spec for scope creep, testability, missing failure modes, GSI
eventual-consistency, changed-email returning users, concurrent-login races, and the
AUTH_022/023 link flows.

### Findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| C-1 | CRITICAL | Draft FR set fixed only `by_email` and left `by_provider_sub`/`by_cognito_sub` on `Limit=1`, so nondeterministic selection among the 10 live duplicates would persist and 1396 (token refresh) would still flap. | Added FR-002/003/004 (deterministic earliest-`created_at` selection) and SC-3. Resolved. |
| C-2 | CRITICAL | Draft callback rewrite risked bypassing the `AUTH_023`/`AUTH_022` and Flow 3/5 branches by resolving purely on `sub`, silently re-linking a provider already owned by a different user. | FR-007 + FR-008 pin the divergence case to existing `AUTH_023` and require all 1181/1182/1183 branches preserved; SC-4 gates on their tests passing. Resolved. |
| H-1 | HIGH | GSI eventual consistency: a rapid second login before the new user's `provider_sub`/`cognito_sub` propagates could still create one extra record, appearing to defeat the fix. | Documented as EC-1 accepted residual risk. `cognito_sub` is set at create via `_update_cognito_sub` and Cognito sub is present in the id_token immediately, so the `by_cognito_sub` path closes faster than `by_provider_sub`. Full closure (conditional write) deferred with owner sign-off (see H-2). Downgraded to accepted. |
| H-2 | HIGH | Concurrent first-login race (EC-4) can create two records even with correct lookups; spec must not imply the race is closed. | Scope boundary made explicit: this feature stops the *systemic* footgun-driven fragmentation (the actual live cause), not the narrow TOCTOU race. Conditional-write-on-create (`attribute_not_exists` keyed on a deterministic identity SK) flagged as an owner decision, candidate for 1396. Not silently claimed fixed. Resolved (scoped out, documented). |
| H-3 | HIGH | "Deterministic selection" was underspecified — "return a USER" is not testable if the tiebreak is unstated. | FR-004 pins the rule (earliest `created_at`, then `user_id` ascending) and SC-3 makes it assertable. Resolved. |
| M-1 | MEDIUM | Changed-Google-email returning user could be missed if reuse still keyed on email first. | FR-006 orders stable identity (`sub`) before email; EC-2 documents the outcome. Resolved. |
| M-2 | MEDIUM | Dropping `Limit` invites unbounded reads on a polluted key (DoS/cost). | T-4 + a bounded page cap in FR/plan; realistic cardinality is tiny. Resolved. |
| M-3 | MEDIUM | New logs could leak raw email/sub. | FR-005 + T-3 mandate `sanitize_for_log` and truncated prefixes. Resolved. |
| L-1 | LOW | Spec did not state that GSI schema stays fixed, risking scope creep into a migration. | FR-011 + SC-5 forbid schema changes without owner escalation. Resolved. |
| L-2 | LOW | Ambiguity on whether this feature deletes the 10 dupes. | Summary + scope explicitly defer deletion to 1397. Resolved. |

### Edits made
- Added FR-002, FR-003, FR-004 (deterministic multi-record selection) and FR-007.
- Added SC-3 and SC-5; expanded EC-1, EC-4, EC-6.
- Added Threat Model T-4 (bounded pagination).
- Made the "stable identity before email" ordering explicit in FR-006.

### Gate
**0 CRITICAL, 0 HIGH remaining.** (C-1, C-2 resolved via new FRs; H-1 accepted+documented,
H-2 scoped out with owner flag, H-3 resolved.) Proceed to plan.

## Clarifications

Self-answered from the codebase (verified), with any genuinely open items flagged for the
owner.

1. **Which entity types actually pollute `by_email`?** — Answered. Exactly `USER`,
   `NOTIFICATION`, `MAGIC_LINK_TOKEN` write the `email` attribute
   (`user.py:179`, `notification.py:57`, `magic_link_token.py:50`). `by_provider_sub` and
   `by_cognito_sub` are USER-only (no other model writes those attrs). So `by_email` needs
   robust filtering; the other two only need deterministic duplicate handling.

2. **Deterministic tiebreak when multiple USER records share a key?** — Answered.
   `created_at` exists on `User` (`user.py:48`, serialized `user.py:168`), so select the
   **earliest `created_at`**, `user_id` ascending as final tiebreak (FR-004). Oldest record
   is the most likely canonical account holding the user's data, and it stays stable across
   reloads until 1397 deletes the rest.

3. **Does the callback already trust only server-derived identity?** — Answered. `email`
   and `sub` come from `decode_id_token(tokens.id_token)` (`auth.py:2236-2238`), never from
   client input. The reuse rewrite keeps this; no new client-supplied claim is trusted.

4. **Will preferring `sub` over email break the AUTH_022/023 conflict matrix?** — Answered.
   No. The conflict branches (`auth.py:2250-2356`) operate on `existing_user` and the
   provider_sub check; FR-007 pins the sub-vs-email divergence to the existing `AUTH_023`
   path rather than a new record. All 1181/1182/1183 tests gate the change (SC-4).

5. **Is any GSI schema change required?** — Answered. No. Pagination + server-side filter
   fixes the footgun without touching the index; a sparse USER-only index would be a schema
   change and is explicitly out of scope (FR-011).

### Open questions for the owner
- **OQ-1 (deferred, non-blocking):** Should we add a conditional-write guard
  (`attribute_not_exists` on a deterministic identity key) at user-create time to close the
  concurrent-first-login race (EC-4)? This is a stronger guarantee than the lookup fix but
  is a separate design decision; recommended for 1396 or a follow-up, not this feature.
