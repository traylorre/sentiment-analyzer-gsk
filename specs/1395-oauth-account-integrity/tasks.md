# Tasks: OAuth Account Integrity (1395)

**Plan:** `specs/1395-oauth-account-integrity/plan.md`
**Test runner:** `PYTHONPATH=. pytest tests/unit/... -v` (moto for DynamoDB, Python 3.13 venv).
All tests are unit-level with moto; no preprod, no live AWS.

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
  existing `try/except` + `get_safe_error_info` logging on failure (return `[]` on error,
  same observable behavior as before).
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

## FR coverage matrix

| FR | Tasks |
|---|---|
| FR-001 | T-101, T-201, T-203 |
| FR-002 | T-102, T-204 |
| FR-003 | T-102, T-205 |
| FR-004 | T-102, T-202, T-204, T-205 |
| FR-005 | T-103, T-202 |
| FR-006 | T-104, T-206 |
| FR-007 | T-105, T-206 |
| FR-008 | T-106, T-206 |
| FR-009 | T-104, T-206 |
| FR-010 | T-201 |
| FR-011 | T-303 |

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
