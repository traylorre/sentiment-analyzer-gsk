# Plan: OAuth Account Integrity (1395)

**Spec:** `specs/1395-oauth-account-integrity/spec.md`
**Scope:** Code-only. Fix the `Limit=1 + FilterExpression` footgun in three identity
helpers and rewire `handle_oauth_callback` to reuse by stable identity. No infra, no data
deletion, no JWT minting.
**Amended 2026-07-24:** §4 (fail-closed redesign) supersedes the error-handling and
pagination-bound language in §2 and in the WIP implementation (commit 71cb143, labeled
KNOWN DEFECTS / DO NOT MERGE). §5 is the Phase-3 test-remediation plan. The WIP's "O-1"
partial-result rationale is explicitly REVERSED — see §4.3.

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

*(Amended: the return/error contract of this helper is superseded by §4.2 — it returns a
COMPLETE `list[User]` or raises `IdentityLookupError`; it never returns `[]`-on-error or
a partial list. The `max_pages=10` keyword shown here IS the contract — the WIP's removal
of it was the R-4 drift.)*

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

### 4. Fail-closed redesign (amendment — fixes K-1/K-2/K-3/R-4/R-8)

The first implementation attempt (WIP 71cb143) got the pagination right and the failure
semantics wrong. Refuter-confirmed defects and their fixes:

#### 4.1 K-1 — unbounded loop, unguarded cursor (CRITICAL)

WIP `_query_users_by_index` (auth.py:497-581) loops on
`response.get("LastEvaluatedKey")` with no type check and no page cap (only a WARN at
page 25, `_IDENTITY_QUERY_PAGE_WARN_THRESHOLD`). A bare `MagicMock` table returns a
truthy MagicMock for `.get(...)` forever → infinite loop (reproduced, rc=124; hangs 4
existing tests, see §5.3). Fix:

```python
lek = response.get("LastEvaluatedKey")
if lek is None or lek == {}:
    break                                   # clean exhaustion
if not isinstance(lek, dict):
    raise IdentityLookupError(...)          # FR-014: uninterpretable cursor = fail closed
if page_count >= max_pages:
    logger.warning(...)                     # FR-013 WARN: index name + page count, sanitized
    raise IdentityLookupError(...)          # cap trip is an ERROR, not truncation
exclusive_start_key = lek
```

The WIP's comment block documenting the refusal to cap (auth.py:474-479) and the
`_IDENTITY_QUERY_PAGE_WARN_THRESHOLD` constant are DELETED — that refusal is the R-4
drift. The spec's fear that a cap "re-opens the false-None footgun" was only true of a
*silently truncating* cap; a *raising* cap cannot produce a false None by construction.

#### 4.2 K-3 + R-8 — error contract: raise, never partial, never []-on-error

New module-level exception in `auth.py` (kept local; no shared-module move this feature):

```python
class IdentityLookupError(Exception):
    """Identity GSI lookup could not prove completeness (page failure, cap trip,
    or malformed cursor). Callers MUST fail closed — never treat as 'no user'."""
```

Amended signature/contract (supersedes §2):

```python
def _query_users_by_index(
    table, index_name, key_expr, attr_values, *, max_pages: int = 10
) -> list[User]:
    # Returns the COMPLETE list of USER items under the key (may be []).
    # Raises IdentityLookupError on ANY page failure (incl. page 1), cap trip,
    # or malformed cursor — after logging via get_safe_error_info (FR-010/012).
```

- The WIP's try-inside-the-loop / return-partial-results design ("O-1") is **reversed**.
  Rationale: R-8 — a partial result feeds `_select_canonical_user` a truncated set, so
  the "canonical" pick depends on which pages happened to succeed → identity flaps
  across refreshes, which is the bug this feature exists to kill. And returning `[]` on
  a page-1 failure is K-3: the callback reads `None` as "no account" and mints a
  duplicate (CWE-636 — the exact mechanism behind the 10 prod duplicates 1397 cleans
  up).
- **R-8 mechanism decision: raise, not a `(users, complete)` tuple.** A tuple pushes the
  fail-closed decision to every caller; one forgotten `complete` check silently re-opens
  CWE-636. An exception cannot be ignored silently, keeps the public helpers'
  `User | None` signatures unchanged, and matches the verified precedent (Auth.js core
  `handle-login.ts` and django-allauth `socialaccount` auto-provision only on a clean
  not-found; lookup errors propagate).
- Public helper contract: `None` ⇔ full key range scanned, zero USER items (FR-012).
  Unparseable USER items are still skip+WARN (not raise): a permanently malformed record
  would otherwise hard-lock the account with no retry escape, and the skip is
  deterministic (same item fails parsing every time), so canonical selection stays
  stable. This is the one deliberate deviation from raise-on-anything, documented here.

#### 4.3 Callback + call-site behavior (FR-015)

`handle_oauth_callback`: **no** try/except around the three lookups — the exception must
make the create path unreachable by construction, not by a branch someone can invert.
Recommended surface (OQ-3): register a router-level handler in `router_v2.py` mapping
`IdentityLookupError` → `error_response(503, "Temporary sign-in failure — please retry.")`
(sanitized, no key material). Fallback if the handler is judged too broad: let it
propagate to the Powertools resolver's generic 500. Either satisfies FR-015; a bare
propagate-to-500 must still be verified to not leak exception internals in the body.

Call-site audit (all non-test callers of the three helpers; default = propagate, fail
closed):

| Call site | Flow | Behavior under IdentityLookupError |
|---|---|---|
| `auth.py:2370/2373/2375` | OAuth callback resolution | Propagate → 503 handler. NEVER create. |
| `auth.py:814` | Registration email-uniqueness check | Propagate → 500. (Swallowing would let a duplicate email register.) |
| `auth.py:913`, `auth.py:940` | Magic-link request/verify | Propagate → 500. (Swallowing could mint/mismatch an account.) |
| `auth.py:2030` | Magic-link token consume | Propagate → 500. |
| `auth.py:2649` | Manual provider link (`existing_owner`) | Propagate → 500. (Swallowing could double-link a provider.) |
| `auth.py:3123` | Token refresh (`get_user_by_cognito_sub`) | Propagate → 500; client retries refresh. (Swallowing = session flap, R-8.) |
| `auth.py:3256` | Password-reset request | Propagate → 500. |
| `router_v2.py:1036` | Email lookup via `auth_service` | Propagate → resolver 500 (or the same 503 handler). |

No call site may catch `IdentityLookupError` and continue as "not found". Phase 3 adds a
grep-gate: `except IdentityLookupError` may appear only in `router_v2.py`'s handler (if
OQ-3 chooses it) and in tests.

#### 4.4 K-2 — stale test assertion

`tests/unit/lambdas/shared/auth/test_email_uniqueness.py:338`
(`test_gsi_query_uses_limit_one`) asserts `Limit == 1` — it now asserts the OLD bug and
fails against any correct implementation. Replace with `test_gsi_query_does_not_use_limit`
asserting `"Limit" not in call_kwargs` (keep the sibling index-name and lowercase-
normalization tests as-is).

### 5. Phase-3 test remediation (amendment)

#### 5.1 Rewrite `tests/unit/dashboard/test_auth_gsi_partial_page_failure.py` (K-3 enshrined)

The WIP file asserts the defect as the contract: page-1 failure → `result is None`
(duplicate-minting path), later-page failure → partial result returned, partial canonical
selection. Rewrite to the FR-012/013/014 contract, keeping the useful `_FailOnPageTable`
fake:

- page-1 failure → `pytest.raises(IdentityLookupError)` (all three helpers,
  parametrized as today);
- later-page failure → `pytest.raises(IdentityLookupError)` (no partial survivors);
- cap trip: 11 pages of advertised `LastEvaluatedKey` → raises + FR-013 WARN in `caplog`;
- malformed cursor: `LastEvaluatedKey` = truthy non-dict (e.g. `MagicMock()`) → raises
  immediately (test completes in ms; guards the K-1 regression);
- DELETE `test_partial_failure_prefers_the_earliest_created_at_among_what_was_resolved`
  (partial selection is now forbidden) and the module docstring's O-1/FR-010 rationale.

#### 5.2 New callback fail-closed test (SC-6)

In `tests/unit/dashboard/test_oauth_callback_reuse.py`: a table whose identity-GSI query
raises on page 1 → `handle_oauth_callback` surfaces `IdentityLookupError` (or the 503 via
the router handler, per OQ-3 choice) and **zero** USER records are written. This is the
CWE-636 regression pin.

#### 5.3 Un-hang the 4 existing tests (K-1 fallout)

`tests/unit/dashboard/test_oauth_auto_link.py`, `test_oauth_callback_federation.py`, and
2 tests in `test_oauth_to_oauth_link.py` build bare `MagicMock` tables and don't patch
`get_user_by_cognito_sub`, which the callback now calls. With the FR-014 guard they stop
hanging and instead fail fast — still broken. Fix each by preference order: (a) patch
`get_user_by_cognito_sub` alongside the existing helper patches (smallest diff), or
(b) replace the bare `MagicMock` with a finite fake returning
`{"Items": [...]}`-shaped dicts and no `LastEvaluatedKey`. Do NOT weaken assertions.

#### 5.4 Chunked, timeout-guarded regression run

All auth-suite runs during Phase 3 go through a per-file timeout wrapper (e.g.
`timeout 120 pytest <file> -x -q` per file, or `pytest-timeout` if already a dep — do not
add a new dependency without checking) so a reintroduced pagination hang burns 2 minutes,
not a session. The final gate is the full chunked sweep green, then the independent
refuter re-run (verification-refuter standard: implementer never grades own work).

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
  non-USER key collisions. **Raises `IdentityLookupError`** on page failure / cap trip /
  malformed cursor (§4.2); `None` only on clean exhaustive zero.
- `get_user_by_provider_sub(table, provider, sub) -> User | None` — deterministic among
  duplicates; same raise contract.
- `get_user_by_cognito_sub(table, cognito_sub) -> User | None` — deterministic among
  duplicates; same raise contract.
- `handle_oauth_callback(...) -> OAuthCallbackResponse` — same signature and response
  fields; behavior: reuse-by-stable-identity, one record per identity. Lets
  `IdentityLookupError` propagate (surfaces as 5xx per §4.3); no error path reaches
  user creation.

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

## Adversarial Review #2 — Second Pass (Fail-Closed Amendment)

Cross-artifact drift check between the amended spec (FR-012..016, rewritten T-4/FR-004/
FR-010, EC-7, SC-6/7) and this amended plan (§4/§5), plus attack on the amendment itself.

| ID | Severity | Check / finding | Resolution |
|---|---|---|---|
| C-1 | CRITICAL | Does any plan path still allow error→None→create? Swept §4.2 (helper raises on all three incompleteness classes), §4.3 (no try/except in callback resolution; create unreachable on error), §4.4/§5.1 (both defect-enshrining tests removed/rewritten). The one deliberate non-raise (unparseable USER item skip) cannot produce a false None when a parseable USER exists, and a key whose ONLY user record is unparseable was already unresolvable pre-amendment. | Justified + documented in §4.2. No error→create path remains. Resolved. |
| C-2 | CRITICAL | Contract-widening blast radius: 9 non-test call sites now face a new exception; an unaudited one could 500 with a leaking body or catch-and-continue. | §4.3 call-site table enumerates all 9 with per-site fail-closed behavior + a grep-gate confining `except IdentityLookupError` to the router handler and tests. Tracked as tasks T-405a/b. Resolved at plan level. |
| H-1 | HIGH | Spec FR-013 says WARN **then raise** on cap trip; a sloppy read of §4.1 pseudocode could reorder or drop the WARN (losing EC-7 alertability). | §4.1 pseudocode shows WARN before raise; §5.1 pins it with a `caplog` assertion. Consistent. Resolved. |
| H-2 | HIGH | The 4 hanging tests (§5.3): fixing via option (b) finite fakes could accidentally change what the tests assert (auto-link/federation semantics), masking a real regression behind the callback reorder. | §5.3 orders (a) patch-first (smallest diff, assertions untouched) and explicitly forbids weakening assertions; AR#3 names this in the highest-risk discussion. Resolved. |
| M-1 | MEDIUM | `max_pages=10` appears in §2 (pre-amendment helper sketch) and §4.2 — drift risk if one changes. | §2 sketch now carries a supersession note pointing at §4.2 as the contract; single source. OQ-2 tracks the value with the owner. Resolved. |
| M-2 | MEDIUM | §5.4 proposes `pytest-timeout` without knowing if it's a dependency (would violate no-new-deps discipline). | §5.4 already conditions on "if already a dep — do not add a new dependency without checking"; the `timeout 120` wrapper needs nothing. Resolved. |
| L-1 | LOW | OQ-3 (503 handler vs bare 500) is unresolved and could stall Phase 3. | Non-blocking by design: FR-015 is satisfied by either; §4.3 records the recommendation and the leak-check requirement for the bare-500 fallback. Resolved. |

Cross-checks: every amended FR has a plan mechanism (FR-012→§4.2; FR-013/014→§4.1;
FR-015→§4.3; FR-016→§4.4+§5.1; amended FR-004→exhaust-then-select in §4.1/§4.2; amended
FR-010→log-then-raise in §4.2). Plan introduces nothing beyond spec scope (one exception
class, one optional router handler — both in existing files; no infra, no schema, no new
deps). EC-7 tradeoff appears in both artifacts with the same resolution (accepted, not
defeated).

**Gate: 0 CRITICAL, 0 HIGH cross-artifact drift remaining. Amended plan is consistent
with the amended spec. Proceed to tasks amendment.**
