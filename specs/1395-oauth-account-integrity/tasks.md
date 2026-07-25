# Tasks: OAuth Account Integrity (1395)

**Plan:** `specs/1395-oauth-account-integrity/plan.md`
**Test runner:** `PYTHONPATH=. pytest tests/unit/... -v` (moto for DynamoDB, Python 3.13 venv).
All tests are unit-level with moto; no preprod, no live AWS.

**Amended 2026-07-24:** Phases 0–3 were partially executed as WIP 71cb143 (KNOWN
DEFECTS, DO NOT MERGE). Phase 4 below is the dependency-ordered defect-remediation plan
(K-1/K-2/K-3/R-4/R-8 → fail-closed + raising cap, plan §4/§5). Phase 3's T-301 gate is
SUPERSEDED by T-407/T-408. **During all Phase-4 test runs, wrap every pytest invocation
in a per-file timeout (plan §5.4) — the defect being fixed is a hang.**

Legend: `[P]` = parallelizable with siblings once deps met. Each task lists the FR(s) it
satisfies.

## Phase 0 — Verification (no code change)

- **T-000** — Re-confirm `created_at` on `User` and the three helper signatures/line ranges
  are still current before editing (guards against drift). Confirm `sanitize_for_log`,
  `get_safe_error_info` imports already present in `auth.py`.
  _Maps: FR-004, FR-010._ _Deps: none._

## Phase 1 — Tests first (red)

Write failing tests that reproduce the verified footgun and the reuse gap. These MUST fail
against current code.

- **T-101 [P]** — `tests/unit/dashboard/test_auth_email_gsi_footgun.py`: seed one `USER`,
  one `NOTIFICATION`, and one `MAGIC_LINK_TOKEN` all under the **same email** in a moto
  table with the `by_email` GSI; assert `get_user_by_email_gsi` returns the `USER`. To force
  the footgun deterministically, also add a test that stubs/uses a table where a non-USER
  item is returned first under `Limit`, proving the old `Limit=1` path returned `None`.
  _Maps: FR-001, SC-2._ _Deps: T-000._

- **T-102 [P]** — `tests/unit/dashboard/test_auth_provider_sub_dupes.py`: seed **10** `USER`
  records sharing one `provider_sub`, distinct `created_at`; assert
  `get_user_by_provider_sub` returns the **earliest `created_at`** record on every call
  (loop 5×, assert same `user_id`). Repeat for `get_user_by_cognito_sub` with 10 records
  sharing one `cognito_sub`.
  _Maps: FR-002, FR-003, FR-004, SC-3._ _Deps: T-000._

- **T-103 [P]** — `test_auth_multi_user_warn_log.py`: assert a WARN is logged (sanitized,
  includes count, no raw email/sub) when >1 USER is found under a key. Use `caplog`.
  _Maps: FR-005._ _Deps: T-000._

- **T-104 [P]** — `test_oauth_callback_reuse.py`: run `handle_oauth_callback` twice for the
  same Google identity (same `sub`/email) against a moto table; assert exactly **one**
  `USER` record exists after the second call and both calls returned the **same** resolved
  user (reuse). Include a variant where a `MAGIC_LINK_TOKEN` exists under the email before
  the second login (exercises the email-index pollution path end-to-end).
  _Maps: FR-006, FR-009, SC-1._ _Deps: T-000._

- **T-105 [P]** — `test_oauth_callback_reuse.py` (same file): variant where the email lookup
  and the sub lookup resolve to **different** users; assert the callback returns `AUTH_023`
  (not a third record).
  _Maps: FR-007._ _Deps: T-000._

- **T-106 [P]** — Regression guard: run the existing 1181/1182/1183/1381 callback tests to
  capture the current green baseline for AUTH_022, AUTH_023, Flow 3, Flow 5, manual-link
  conflict, and OAuth session restore.
  _Maps: FR-008, SC-4._ _Deps: T-000._

## Phase 2 — Implementation (green)

- **T-201** — Add private `_query_users_by_index(table, index_name, key_expr, attr_values,
  *, max_pages=10)` in `auth.py`: query without `Limit`, keep
  `FilterExpression="entity_type = :type"` (`:type="USER"`), page via `LastEvaluatedKey`
  until USER items are collected or `max_pages` reached; return `list[User]`. Preserve the
  existing `try/except` + `get_safe_error_info` logging on failure (~~return `[]` on error,
  same observable behavior as before~~ **SUPERSEDED by the fail-closed amendment: errors
  RAISE `IdentityLookupError` after logging — see T-404 / plan §4.2. The struck text was
  the K-3 defect.**).
  _Maps: FR-001, FR-010, T-4._ _Deps: T-101._

- **T-202** — Add private `_select_canonical_user(users, *, key_label, key_prefix) -> User |
  None`: if empty→`None`; if >1→WARN via `logger.warning` with `sanitize_for_log(key_prefix)`
  and `count`; return `min(users, key=lambda u: (u.created_at, u.user_id))`.
  _Maps: FR-004, FR-005._ _Deps: T-102, T-103._

- **T-203** — Rewrite `get_user_by_email_gsi` (`auth.py:476-523`) to use T-201 + T-202
  (drop `Limit=1`). Keep signature and normalized-lowercase email behavior.
  _Maps: FR-001._ _Deps: T-201, T-202._

- **T-204** — Rewrite `get_user_by_provider_sub` (`auth.py:527-588`) to use T-201 + T-202
  (drop `Limit=1`). Keep the `provider`/`sub` guard and `"{provider}:{sub}"` composition.
  _Maps: FR-002, FR-004._ _Deps: T-201, T-202._

- **T-205** — Rewrite `get_user_by_cognito_sub` (`auth.py:2906-2945`) to use T-201 + T-202
  (drop `Limit=1`). Keep the empty-`cognito_sub` guard.
  _Maps: FR-003, FR-004._ _Deps: T-201, T-202._

- **T-206** — Rewrite the resolution block in `handle_oauth_callback` (replace the single
  `existing_user = get_user_by_email_gsi(...)` at `auth.py:2248`): compute
  `existing_by_sub`, `existing_by_cognito`, `existing_by_email`; set
  `stable_user = existing_by_sub or existing_by_cognito` and
  `existing_user = stable_user or existing_by_email`. Re-express the `AUTH_023` condition so
  a sub-vs-email divergence still triggers the conflict (FR-007). Leave AUTH_022 / Flow 3 /
  Flow 5 / manual-conflict / reuse-vs-create branches structurally intact.
  _Maps: FR-006, FR-007, FR-009, FR-008._ _Deps: T-203, T-204, T-205._

## Phase 3 — Verify & gate

- **T-301** — Run all new + existing auth unit tests; T-101–T-105 now pass, T-106 baseline
  still green.
  _Maps: SC-1, SC-2, SC-3, SC-4._ _Deps: T-201..T-206._

- **T-302** — `ruff format` + `ruff check` on `src/lambdas/dashboard/auth.py` and new tests;
  `bandit -c pyproject.toml -r src/ -ll` clean.
  _Deps: T-206._

- **T-303** — `cd infrastructure/terraform && terraform validate` and confirm no schema/IAM
  diff is implied (no `.tf` files touched by this feature).
  _Maps: FR-011, SC-5._ _Deps: none (independent)._

## Phase 4 — Defect remediation (fail-closed amendment; supersedes T-301 as the gate)

Dependency order: T-401 and T-402 first (red — pin the amended contract), then
implementation T-403→T-404→T-405a/b, then test un-hang T-406, then gates T-407/T-408.

- **T-401 [P]** — *(K-2 → FR-016)* Fix
  `tests/unit/lambdas/shared/auth/test_email_uniqueness.py:338`: replace
  `test_gsi_query_uses_limit_one` with `test_gsi_query_does_not_use_limit` asserting
  `"Limit" not in call_kwargs` (plan §4.4). Leave the sibling index-name and
  lowercase-normalization tests untouched.
  _Deps: none._

- **T-402 [P]** — *(K-3/R-8/K-1 red → FR-012, FR-013, FR-014, FR-016)* Rewrite
  `tests/unit/dashboard/test_auth_gsi_partial_page_failure.py` per plan §5.1: page-1 AND
  later-page failures → `pytest.raises(IdentityLookupError)` (all three helpers,
  parametrized); cap trip at page 11 → raises + FR-013 WARN in `caplog`; truthy non-dict
  `LastEvaluatedKey` → raises immediately (K-1 regression pin, must complete in ms);
  DELETE the partial-selection test and the O-1 docstring. Add the SC-6 callback test to
  `tests/unit/dashboard/test_oauth_callback_reuse.py`: page-1 lookup failure →
  `IdentityLookupError` surfaces and ZERO `USER` records written (plan §5.2). These MUST
  fail against WIP 71cb143.
  _Deps: none._

- **T-403** — *(K-1/R-4 → FR-013, FR-014)* In `auth.py`: add module-level
  `IdentityLookupError`; in `_query_users_by_index` add the cursor type guard and the
  `max_pages=10` raising cap exactly per plan §4.1 (WARN then raise on trip); DELETE the
  cap-refusal comment block (WIP auth.py:474-479) and
  `_IDENTITY_QUERY_PAGE_WARN_THRESHOLD`.
  _Deps: T-402._

- **T-404** — *(K-3/R-8 → FR-010, FR-012)* In `_query_users_by_index`: remove the
  return-partial / return-`[]`-on-error paths; any page query exception → log via
  `get_safe_error_info` then `raise IdentityLookupError(...) from e`. Keep the
  skip+WARN for unparseable USER items (deliberate deviation, plan §4.2). Public helpers'
  `User | None` signatures unchanged; `None` only on clean exhaustive zero.
  _Deps: T-403._

- **T-405a** — *(FR-015)* Callback surface: confirm `handle_oauth_callback` has no
  try/except around the resolution block (exception makes create unreachable); implement
  the OQ-3 choice — recommended: `router_v2.py` handler mapping `IdentityLookupError` →
  `error_response(503, ...)` with a sanitized generic message; if bare propagate-to-500
  is chosen instead, verify the 500 body leaks no exception internals.
  _Deps: T-404._

- **T-405b** — *(FR-015)* Call-site audit: walk the 8 non-callback call sites (plan §4.3
  table) confirming each propagates (no `except IdentityLookupError` outside the router
  handler and tests — enforce with a grep gate); confirm none converts the exception to
  "not found".
  _Deps: T-404._

- **T-406** — *(K-1 fallout → SC-4)* Un-hang the 4 existing tests
  (`test_oauth_auto_link.py`, `test_oauth_callback_federation.py`, 2 in
  `test_oauth_to_oauth_link.py`) per plan §5.3: prefer patching
  `get_user_by_cognito_sub` alongside existing patches; else finite dict-shaped fakes.
  Assertions MUST NOT be weakened.
  _Deps: T-403 (guard converts hang → fast fail, making iteration feasible)._

- **T-407** — *(gate)* Chunked, timeout-guarded regression sweep (plan §5.4): per-file
  `timeout 120 pytest <file> -x -q` across the auth unit suites (new 1395 files +
  email-uniqueness + oauth auto-link/federation/to-oauth-link + 1181/1182/1183/1381
  baselines), then one full chunked pass. Any timeout = FAIL (hang regression).
  _Maps: SC-1..SC-4, SC-6, SC-7._ _Deps: T-401..T-406._

- **T-408** — *(gate)* Independent refuter re-run: a separate agent (not the
  implementer) re-verifies K-1/K-2/K-3/R-4/R-8 closed against the actual diff, re-runs
  the rc=124 reproduction, and greps for any surviving error→None path. Implementer
  never grades own work (verification-refuter standard).
  _Deps: T-407._

## FR coverage matrix

| FR | Tasks |
|---|---|
| FR-001 | T-101, T-201, T-203 |
| FR-002 | T-102, T-204 |
| FR-003 | T-102, T-205 |
| FR-004 | T-102, T-202, T-204, T-205 (exhaust-then-select enforced by T-403/T-404) |
| FR-005 | T-103, T-202 |
| FR-006 | T-104, T-206 |
| FR-007 | T-105, T-206 |
| FR-008 | T-106, T-206, T-406 |
| FR-009 | T-104, T-206 |
| FR-010 | T-201, T-404 |
| FR-011 | T-303 |
| FR-012 | T-402, T-404 |
| FR-013 | T-402, T-403 |
| FR-014 | T-402, T-403 |
| FR-015 | T-402 (SC-6 test), T-405a, T-405b |
| FR-016 | T-401, T-402 |

## Adversarial Review #3

### Highest-risk task
**T-206 (callback resolution rewrite).** It sits on the critical auth path and must reorder
identity resolution *without* regressing the AUTH_022/023 and Flow 3/5 branches. The prior
code's `AUTH_023` condition compares `existing_by_sub` against `existing_user`; changing how
`existing_user` is computed (now sub-first) can flip that comparison's meaning. If done
carelessly, a legitimate same-user re-login could be misread as a cross-account conflict, or
a real conflict could be swallowed.

Mitigation baked into tasks: T-105 asserts the divergence→`AUTH_023` case explicitly, and
T-106 pins the full existing conflict/auto-link matrix as a regression baseline before any
edit. T-206 is gated behind those tests being written first (Phase 1 red).

### Most likely rework
**T-202 selection semantics vs. `created_at` type.** `created_at` is a `datetime`
(`user.py:48`), so `min(..., key=(created_at, user_id))` sorts correctly — but if any legacy
duplicate stored `created_at` as a string or is missing it, `from_dynamodb_item` could raise
or sort inconsistently. Likely rework: add a defensive default (treat missing/parse-failed
`created_at` as `datetime.max` so a malformed record never wins the "oldest" pick) and a
test seeding one malformed record among the 10. This is a small, contained change if T-102
surfaces it.

### Second-order risk
The concurrent-first-login race (EC-4) and GSI eventual consistency (EC-1) are **not** closed
by these tasks — correctly, per the scoped decision in AR#1 (H-1/H-2) and OQ-1. Reviewers
must not treat SC-1 (sequential two-login reuse) as proof the race is closed; it is not
claimed to be.

### Gate
All FRs map to at least one implementation task and one test (see coverage matrix). Root
cause is verified against current code and schema. No infra or schema change required. The
highest-risk task is fenced by tests-first and a regression baseline.

**READY FOR IMPLEMENTATION.**

## Adversarial Review #3 — Second Pass (Fail-Closed Amendment)

Attacking Phase 4 for ordering hazards, silent-regression paths, and gate integrity.

### Findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| C-1 | CRITICAL | If T-406 (test un-hang) were done via finite fakes BEFORE T-403's guard lands, an implementer could "fix" the hangs by weakening the fakes and never notice the loop defect survives. | Ordering pinned: T-406 depends on T-403; §5.3/T-406 forbid weakening assertions; T-402's non-dict-cursor test pins the fast-fail independently of any fake. Resolved. |
| C-2 | CRITICAL | T-402 rewrites the very test file that enshrined K-3 — a careless rewrite could keep the old `result is None` assertions alongside new ones and pass both against a half-fixed helper. | T-402 mandates the old partial-selection test and O-1 docstring be DELETED, and requires the new file FAIL against WIP 71cb143 (red-first proof it asserts the new contract, not both). Resolved. |
| H-1 | HIGH | T-405b's grep gate could false-pass if a call site catches broad `Exception` (not `IdentityLookupError` by name) and maps to None — grep won't see it. | T-405b requires walking each of the 8 sites per the plan §4.3 table (semantic audit), with the grep only as a supplementary gate; T-408's refuter independently greps for surviving error→None paths. Resolved. |
| H-2 | HIGH | T-407's per-file timeout could mask a slow-but-not-hung regression (e.g. cap raised to 1000 pages still finishes < 120s in unit tests). | The cap value itself is pinned by T-402's page-11 raising test — a wrong cap fails functionally, not just temporally. Timeout is a hang guard, not the correctness gate. Resolved. |
| M-1 | MEDIUM | T-401 and T-402 are both [P] and touch different files, but both must fail against the WIP before implementation starts; nothing forces the red check. | Red-first is explicit in T-402 ("MUST fail against WIP 71cb143"); T-401's replacement test trivially fails against any Limit-passing implementation and passes after — its direction is unambiguous. Accepted. |
| M-2 | MEDIUM | T-405a's OQ-3 fork (503 handler vs bare 500) could stall implementation waiting on the owner. | Both branches specified and FR-015-compliant; recommended default (503 handler) is actionable without owner input; the fork is surface-shape only, not behavior. Resolved. |

### Highest-risk task

**T-404 (error-contract flip in `_query_users_by_index`).** It inverts the failure
semantics of the single helper feeding 9 call sites across registration, magic link,
password reset, provider link, token refresh, and the OAuth callback. The failure modes
are asymmetric: too little (one surviving `return []`/partial path) silently re-opens
CWE-636 duplicate minting; too much (raising on the unparseable-item skip, or a broad
catch upstream) can hard-lock real logins. It is fenced on both sides — T-402's raises
tests catch fail-open leftovers, T-406/T-407 catch fail-closed overreach breaking the
existing flows, and T-405b audits the blast radius — but it is the one task where a
subtle mistake degrades production auth in either direction.

### Second-order risk

The EC-7 targeted-lockout trade (cap-hit → victim 5xx) is accepted by design; reviewers
must not "fix" a Phase-4 test failure by softening the raise back into truncation. Any
future pressure on `max_pages` goes through OQ-2 (owner), not code.

### Gate

All five defects (K-1/K-2/K-3/R-4/R-8) map to at least one red test task and one
implementation task; all new FRs (FR-012..016) are covered in the matrix; ordering
prevents the two identified silent-regression paths; final verification is independent
(T-408). 0 CRITICAL, 0 HIGH unresolved.

**READY FOR IMPLEMENTATION.**
