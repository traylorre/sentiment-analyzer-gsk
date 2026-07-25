# Feature 1395: OAuth Account Integrity

**Status:** Draft — Amended 2026-07-24 (fail-closed + bounded-cap-that-raises; supersedes
the T-4 "stop at first USER" language and the WIP's documented cap refusal; see FR-012
through FR-016 and Adversarial Review #1 Second Pass)
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
  the user's data), with `user_id` ascending as a stable tiebreaker. Because the identity
  GSIs are hash-only (no range key, no ordering), earliest-`created_at` selection
  **requires examining every `USER` item under the key** — the lookup MUST paginate the
  key range to full exhaustion (or hit the raising cap, FR-013) *before* selecting.
  Early-exit ("stop at the first USER found") is **forbidden**: it makes the selection
  page-order-dependent, i.e. nondeterministic, which is the exact defect FR-004 exists to
  remove.
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
- **FR-010** *(amended — was "log the swallowed error"; now fail-closed)* — No lookup may
  swallow an error and return `None`/partial data, logged or not. Every exception path
  MUST log via the existing `get_safe_error_info` / `sanitize_for_log` helpers **and then
  raise** per FR-012. Logging alone is insufficient: a logged-but-swallowed error still
  reaches the caller as "no such user" and mints a duplicate (CWE-636).
- **FR-011** — The fix MUST NOT change the `by_email`, `by_provider_sub`, or
  `by_cognito_sub` GSI schema or projection. If a schema change is later judged necessary,
  it MUST be escalated to the owner (per the standing "no new AWS resources" constraint) —
  it is out of scope here.
- **FR-012 — Fail-closed lookup contract.** For all three helpers, a `None` return means
  **exactly one thing**: the full key range was scanned to exhaustion and zero `USER`
  items exist. Nothing else may produce `None`. Any DynamoDB error on **any** page
  (including page 1), any cap trip (FR-013), and any malformed pagination cursor (FR-014)
  MUST raise a dedicated exception (`IdentityLookupError`). Partial results MUST NOT be
  returned: selecting a "canonical" user over a truncated set makes the resolved identity
  depend on which pages happened to succeed, flapping across refreshes (refuter finding
  R-8). Precedent: Auth.js core `handle-login` and django-allauth auto-provision only on
  a clean successful not-found; a lookup error propagates and never falls through to
  account creation (OWASP Fail-Securely; CWE-636; OWASP API4:2023 for the bounded read).
- **FR-013 — Bounded cap that raises.** `_query_users_by_index` MUST enforce
  `max_pages=10`. Hitting the cap with pagination unfinished (a `LastEvaluatedKey` still
  present) MUST emit a sanitized WARN (index name, page count) and **raise
  `IdentityLookupError`** — never silent truncation, never an empty/partial result.
  Precedent: bounds surface incompleteness rather than fabricating completeness (DynamoDB
  1MB page returns `LastEvaluatedKey`; Elasticsearch `max_result_window` errors; boto3
  `MaxItems` returns `NextToken`). At ~1MB/page, 10 pages ≈ 10MB under a single identity
  key — orders of magnitude beyond any legitimate user's notifications/tokens/duplicates.
- **FR-014 — Pagination-cursor type guard.** The loop MUST treat
  `response.get("LastEvaluatedKey")` as a continuation token **only** if it is a non-empty
  `dict` (`isinstance` check). `None`/empty-dict terminates normally; any other truthy
  value (e.g. a `MagicMock` attribute, whose `.get()` is truthy forever — refuter K-1,
  reproduced as an infinite loop) MUST raise `IdentityLookupError`. A cursor we cannot
  interpret means completeness cannot be proven, so fail closed — and a bad test fake now
  fails fast instead of hanging the suite.
- **FR-015 — Callback fails closed; no call site may mint on error.**
  `handle_oauth_callback` MUST surface `IdentityLookupError` as a **5xx** response (user
  retries) and MUST NOT contain any code path from a lookup exception to
  `_create_authenticated_user`. There is no catch-and-continue inside the callback's
  resolution block. All other call sites of the three helpers (registration, magic link,
  password reset, manual provider link, token refresh, `router_v2` email lookup) MUST
  also fail closed: propagate (default → resolver 500) or return an explicit 5xx — never
  translate the exception back into "user not found".
- **FR-016 — Test remediation.** The WIP test
  `tests/unit/dashboard/test_auth_gsi_partial_page_failure.py` currently **enshrines the
  K-3 defect** (asserts `result is None` on a page-1 failure, and asserts partial results
  are returned on later-page failures). It MUST be rewritten in Phase 3 to assert
  `pytest.raises(IdentityLookupError)` for page failures (any page), cap trips, and
  malformed cursors, and its partial-result-selection test MUST be deleted.
  `tests/unit/lambdas/shared/auth/test_email_uniqueness.py:338`
  (`test_gsi_query_uses_limit_one`) asserts the **old bug** (`Limit==1`) and MUST be
  replaced with an assertion that no `Limit` is passed.

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
- **SC-4** — All existing OAuth-callback tests (1181/1182/1183/1381) still pass. (Four of
  them currently hang against the WIP because they use bare `MagicMock` tables and don't
  patch the newly-called `get_user_by_cognito_sub`; they are remediated per FR-016/plan —
  patched or given finite fakes — not weakened.)
- **SC-5** — No new IAM/GSI/AWS resources introduced; `terraform plan` shows no infra diff.
- **SC-6** — A DynamoDB failure on ANY page during the OAuth callback's identity
  resolution yields a 5xx and **zero** new `USER` records. (Unit test: fake table raises
  on page 1 → assert `IdentityLookupError` surfaces / 5xx path, assert no
  `_create_authenticated_user` write occurred.)
- **SC-7** — A key range that still has a `LastEvaluatedKey` after 10 pages raises
  `IdentityLookupError` and emits the FR-013 WARN; a non-dict truthy `LastEvaluatedKey`
  raises immediately (no hang — test completes in milliseconds where the WIP looped
  forever, refuter rc=124).

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
- **EC-7 — Cap-hit → 5xx → targeted-lockout tradeoff (accepted).** An attacker who can
  write enough items under a victim's `email` hash key to exceed 10 pages (~10MB — on the
  order of 10,000 NOTIFICATION/MAGIC_LINK_TOKEN items) forces the victim's login to a
  retryable 5xx (FR-013) instead of resolving. This is the **correct** trade and is
  accepted, not defeated: the fail-open alternative is that the same pollution silently
  masks the victim's `USER` record and every login mints a fresh duplicate — permanent,
  invisible account corruption (the mechanism behind the 10 live prod duplicates that
  1397 cleans up). A 5xx is transient, user-visible, and the FR-013 WARN makes the
  pollution alertable so an operator can investigate the key. Do not add complexity
  trying to "win" this scenario inside the lookup; rate limiting and write-path controls
  own it.

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
- **T-4 — Denial via unbounded pagination** *(amended — the original wording contained a
  contradiction: "stop at the first USER" is incompatible with FR-004's earliest-
  `created_at` rule, which requires seeing ALL USER items under a hash-only key. The
  early-exit language is removed.)* Dropping `Limit` and paginating a polluted key could
  read many items, or (refuter K-1) spin forever on a malformed cursor. Mitigation:
  **exhaust the key range (or trip the raising cap), then select.** The scan is bounded
  by `max_pages=10` whose trip is an ERROR (WARN + raise, FR-013), the cursor is
  type-guarded (FR-014), and realistic key cardinality is tiny (one human's
  notifications/tokens/duplicates), so the bound is never reached legitimately. The cap
  converts a resource-exhaustion attack into an observable, alertable 5xx (see EC-7)
  instead of either an unbounded read or a silent false-"no user".

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

## Adversarial Review #1 — Second Pass (Fail-Closed Amendment)

Attacking the amended spec. Context: the first implementation attempt (WIP 71cb143,
labeled DO NOT MERGE) exposed defects the original spec permitted or even mandated
(the T-4 early-exit language, the unbounded "paginate to exhaustion" reading, the
log-and-return-None error contract). This pass verifies the amendment closes them
without opening new holes.

### Findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| C-3 | CRITICAL | Original FR-010 ("log the error, return None") was itself the K-3 defect: a logged error still reached `handle_oauth_callback` as "no user" and minted a duplicate — CWE-636, the literal mechanism behind the 10 live prod duplicates. The WIP even grew a test enshrining it. | FR-010 rewritten (log **then raise**), FR-012 pins the `None`-means-clean-zero contract, FR-015 forbids any exception→create path, FR-016 mandates the enshrined test be rewritten to assert raise. SC-6 makes it assertable. Resolved. |
| C-4 | CRITICAL | Spec-internal contradiction: T-4 said "stop at the first (deterministically selected) USER" while FR-004 requires earliest-`created_at` — impossible without seeing ALL USER items under a hash-only GSI key. The WIP resolved the ambiguity by refusing the cap (R-4 drift) and paginating unboundedly (K-1 hang). | T-4 rewritten: exhaust-or-raising-cap THEN select; early-exit explicitly forbidden in FR-004. Cap refusal superseded by FR-013. Resolved. |
| H-4 | HIGH | "Paginate to exhaustion" with no cursor validation is an infinite loop under any truthy non-dict `LastEvaluatedKey` (reproduced: bare `MagicMock` `.get()` is truthy forever, rc=124). A production SDK anomaly would hang a Lambda to timeout the same way. | FR-014 type guard: non-empty `dict` continues, `None`/`{}` terminates, anything else raises. SC-7 asserts the fast-fail. Resolved. |
| H-5 | HIGH | Raising cap creates a targeted-lockout vector: pollute a victim's email key past 10 pages → victim gets 5xx. A reviewer could demand the cap be removed again (re-opening R-4/K-1) to "protect availability". | EC-7 documents the tradeoff as ACCEPTED with rationale: fail-open silently corrupts the account permanently; fail-closed 5xx is transient, visible, and alertable via the FR-013 WARN. Spec forbids re-litigating it inside the lookup. Resolved (accepted, documented). |
| H-6 | HIGH | Widening the error contract from `None` to raise touches ~9 call sites beyond the callback; a site that catches broadly and maps back to `None` (or an unhandled path that 500s without sanitized logging) would re-open the hole or leak. | FR-015 extends fail-closed to ALL call sites with propagate-to-500 as the default; the plan carries a per-call-site audit table and the tasks gate on it (T-405b). Resolved at spec level; execution risk tracked in AR#3. |
| M-4 | MEDIUM | `max_pages=10` is asserted, not derived; too low re-opens false-lockout, too high weakens the DoS bound. | FR-013 records the derivation (~1MB/page × 10 ≈ 10MB ≫ any legitimate identity key; live worst case is 10 dup USER items + a handful of tokens ≪ 1 page). Value flagged to owner as OQ-2 (non-blocking, default stands). Resolved. |
| M-5 | MEDIUM | SC-4 ("existing tests pass unchanged") became unsatisfiable — 4 existing tests hang against the new callback because they don't patch `get_user_by_cognito_sub`. Left as-is, implementers might "fix" it by reverting the callback ordering. | SC-4 amended: tests are remediated (patched/finite fakes), not weakened; remediation is FR-016-adjacent and tasked (T-406). Resolved. |
| L-3 | LOW | `IdentityLookupError` name/location unspecified could drift into a shared-module bikeshed. | Plan pins it: module-level exception in `auth.py`, no shared-module move in this feature. Resolved. |

### Edits made
- FR-010 rewritten; FR-012/013/014/015/016 added; FR-004 exhaustion requirement added.
- T-4 rewritten (contradiction removed); EC-7 added; SC-4 amended; SC-6/SC-7 added.
- Status header notes the amendment and supersessions.

### Gate
**0 CRITICAL, 0 HIGH remaining.** (C-3/C-4 resolved by the rewritten FRs; H-4 resolved by
FR-014; H-5 accepted+documented in EC-7; H-6 resolved at spec level, execution tracked in
AR#3.) Spec amendment coherent; proceed to plan amendment.

### Open questions for the owner (amendment)
- **OQ-2 (non-blocking):** `max_pages=10` default. Derivation in FR-013 says 10 pages
  ≈ 10MB per identity key, ~3 orders of magnitude above the live worst case. Confirm or
  adjust; any value ≥2 preserves correctness because the trip RAISES rather than
  truncates.
- **OQ-3 (non-blocking):** exact 5xx surface for the callback — propagate to the
  Powertools resolver's generic 500 vs. a router-level `IdentityLookupError` handler
  returning 503 + retryable message. Plan recommends the 503 handler; either satisfies
  FR-015.
