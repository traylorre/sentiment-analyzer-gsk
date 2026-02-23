# Tasks: OHLC Cache Reconciliation

**Input**: Design documents from `/specs/1218-ohlc-cache-reconciliation/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/cache-headers.md

**Tests**: Tests ARE included — the spec requires unit and integration test updates for error propagation, retry, TTL, and degradation headers.

**Organization**: Tasks grouped by user story (P1–P5) to enable independent implementation and testing.

**CRITICAL**: Do NOT introduce any banned terms (see `scripts/check-banned-terms.sh` for the full list).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Verify clean baseline before making changes

- [x] T001 Run `make test-local` on branch `1218-ohlc-cache-reconciliation` to confirm baseline passes
- [x] T002 Run `make validate` to confirm lint + security + banned-term scanner baseline

**Checkpoint**: Baseline is green — all existing tests pass, no lint violations

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Remove silent error suppression in the cache module so exceptions propagate to the handler. This MUST be complete before any user story can add error-handling or header logic in the handler.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Remove try/except ClientError wrapper around `get_cached_candles()` in `src/lambdas/shared/cache/ohlc_cache.py` — let ClientError propagate to caller
- [x] T004 Remove try/except ClientError wrapper around `put_cached_candles()` in `src/lambdas/shared/cache/ohlc_cache.py` — let ClientError propagate to caller
- [x] T005 Update tests in `tests/unit/shared/cache/test_ohlc_persistent_cache.py` that assert the old silent-catch behavior — change to assert exceptions propagate (ClientError raised, not None returned)
- [x] T006 Run `make test-local` to confirm cache module tests pass with new error propagation behavior

**Checkpoint**: Cache module raises exceptions instead of swallowing them. Existing handler tests may now fail (expected — US1 will fix the handler).

---

## Phase 3: User Story 1 — Transparent Cache Failures (Priority: P1) MVP

**Goal**: When persistent cache storage is broken, the handler catches the exception, logs ERROR, fetches from external API, and returns data with degradation headers. Silent degradation is eliminated.

**Independent Test**: Misconfigure DynamoDB permissions in a moto test → confirm ERROR log + `X-Cache-Source: live-api-degraded` + `X-Cache-Error` header on response.

### Tests for User Story 1

- [x] T007 [P] [US1] Add unit test in `tests/unit/dashboard/test_ohlc.py`: when `get_cached_candles()` raises ClientError, handler returns 200 with `X-Cache-Source: live-api-degraded` and `X-Cache-Error` headers
- [x] T008 [P] [US1] Add unit test in `tests/unit/dashboard/test_ohlc.py`: when `put_cached_candles()` raises ClientError, handler returns 200 with `X-Cache-Write-Error: true` header
- [x] T009 [P] [US1] Add unit test in `tests/unit/dashboard/test_ohlc.py`: when cache read raises, response still contains valid OHLC data from external API (explicit degradation returns data)

### Implementation for User Story 1

- [x] T010 [US1] In `src/lambdas/dashboard/ohlc.py`, remove the try/except wrapper in `_read_from_dynamodb()` — let exceptions from `get_cached_candles()` propagate up to `get_ohlc_data()`
- [x] T011 [US1] In `src/lambdas/dashboard/ohlc.py`, remove the try/except wrapper in `_write_through_to_dynamodb()` — let exceptions from `put_cached_candles()` propagate up to `get_ohlc_data()`
- [x] T012 [US1] In `src/lambdas/dashboard/ohlc.py`, add explicit try/except around the DynamoDB read call in `get_ohlc_data()` — on ClientError: log ERROR with error category, set `cache_source = "live-api-degraded"`, set `cache_error` to error description string, continue to external API fetch
- [x] T013 [US1] In `src/lambdas/dashboard/ohlc.py`, add explicit try/except around the DynamoDB write calls in `get_ohlc_data()` — on ClientError: log ERROR with error category, set `cache_write_error = True`, continue (data already fetched)
- [x] T014 [US1] Run `make test-local` to confirm US1 tests pass and no regressions

**Checkpoint**: Cache failures produce ERROR logs and degradation context variables. Silent degradation eliminated.

---

## Phase 4: User Story 2 — Cache Observability Headers (Priority: P2)

**Goal**: Every OHLC price data response includes `X-Cache-Source`, `X-Cache-Age`, and conditionally `X-Cache-Error` and `X-Cache-Write-Error` headers per the contract in `contracts/cache-headers.md`.

**Independent Test**: Make two sequential identical requests → first returns `X-Cache-Source: live-api`, second returns `X-Cache-Source: persistent-cache` or `X-Cache-Source: in-memory` with `X-Cache-Age > 0`.

### Tests for User Story 2

- [x] T015 [P] [US2] Add unit test in `tests/unit/dashboard/test_ohlc.py`: in-memory cache hit response has `X-Cache-Source: in-memory` and `X-Cache-Age` >= 0
- [x] T016 [P] [US2] Add unit test in `tests/unit/dashboard/test_ohlc.py`: persistent cache hit response has `X-Cache-Source: persistent-cache` and `X-Cache-Age` >= 0
- [x] T017 [P] [US2] Add unit test in `tests/unit/dashboard/test_ohlc.py`: live API fetch response has `X-Cache-Source: live-api` and `X-Cache-Age: 0`
- [x] T018 [P] [US2] Add unit test in `tests/unit/dashboard/test_ohlc.py`: degraded response has `X-Cache-Source: live-api-degraded`, `X-Cache-Error`, and `X-Cache-Age: 0`

### Implementation for User Story 2

- [x] T019 [US2] In `src/lambdas/dashboard/ohlc.py`, add cache header dict construction in `get_ohlc_data()` — populate `X-Cache-Source` and `X-Cache-Age` based on which cache tier served the data (in-memory hit, persistent hit, live-api, or degraded)
- [x] T020 [US2] In `src/lambdas/dashboard/ohlc.py`, add `X-Cache-Error` header when `cache_source == "live-api-degraded"` and `X-Cache-Write-Error: true` header when cache write failed
- [x] T021 [US2] In `src/lambdas/dashboard/ohlc.py`, pass the cache headers dict to ALL Response objects returned from the OHLC endpoint (success, in-memory hit, persistent hit, live-api, degraded) using `headers=` parameter
- [x] T022 [US2] Run `make test-local` to confirm US2 tests pass and no regressions

**Checkpoint**: All OHLC responses include observability headers per contract.

---

## Phase 5: User Story 3 — Cached Data Expiration (Priority: P3)

**Goal**: Every cached item written to DynamoDB includes a `ttl` attribute (epoch seconds). DynamoDB auto-deletes expired items. Historical/daily data: 90 days. Current-day intraday: 5 minutes. Past intraday: 90 days.

**Independent Test**: Write a cached item with short TTL → confirm `ttl` attribute is present and within expected range.

### Tests for User Story 3

- [x] T023 [P] [US3] Add unit test in `tests/unit/shared/cache/test_ohlc_persistent_cache.py`: `put_cached_candles()` with daily resolution writes `ttl` = fetched_at + 90 days (±1 day tolerance)
- [x] T024 [P] [US3] Add unit test in `tests/unit/shared/cache/test_ohlc_persistent_cache.py`: `put_cached_candles()` with current-day intraday resolution writes `ttl` = fetched_at + 5 minutes (±1 minute tolerance)
- [x] T025 [P] [US3] Add unit test in `tests/unit/shared/cache/test_ohlc_persistent_cache.py`: `put_cached_candles()` with past-day intraday resolution writes `ttl` = fetched_at + 90 days

### Implementation for User Story 3

- [x] T026 [US3] In `src/lambdas/shared/cache/ohlc_cache.py`, add TTL calculation in `put_cached_candles()` — compute `ttl` epoch seconds based on resolution and whether data is current-day intraday vs. historical per research.md R1 decision
- [x] T027 [US3] In `src/lambdas/shared/cache/ohlc_cache.py`, include `ttl` attribute in the DynamoDB PutItem/BatchWrite requests
- [x] T028 [US3] Add `ttl { attribute_name = "ttl" enabled = true }` block to the `aws_dynamodb_table.ohlc_cache` resource in `infrastructure/terraform/modules/dynamodb/main.tf`
- [x] T029 [US3] Run `make test-local` to confirm US3 tests pass and no regressions

**Checkpoint**: All new cached items include TTL. Terraform config enables DynamoDB TTL on the table.

---

## Phase 6: User Story 4 — Specification and Documentation Hygiene (Priority: P4)

**Goal**: Purge all removed-framework references from spec docs, cache docs, and code docstrings. Remove banned-term scanner exclusion for `docs/cache/`. Update BENCHED status.

**Independent Test**: Run `bash scripts/check-banned-terms.sh` WITHOUT the `docs/cache/` exclusion → zero violations.

### Implementation for User Story 4

- [x] T030 [P] [US4] Purge banned terms from `.specify/specs/ohlc-cache-remediation.md` — replace removed-framework imports (lines ~1000, ~1124) with `from aws_lambda_powertools.event_handler import Response`, replace removed-framework parameter patterns (lines ~1004, ~1130, ~1229) with Lambda Powertools equivalent
- [x] T031 [P] [US4] Purge banned terms from `.specify/specs/ohlc-cache-remediation-clarifications.md` — update BENCHED status (lines ~312, ~322, ~328-329) to reflect the architectural blocker is resolved and work has resumed
- [x] T032 [P] [US4] Review `.specify/specs/ohlc-cache-remediation-tests.md` for banned terms and purge any found
- [x] T033 [P] [US4] Purge banned terms from `docs/cache/fix-cache-tests.md` — replace removed-framework test client reference (line ~371) with Lambda Powertools test pattern (`lambda_handler(event, context)`)
- [x] T034 [P] [US4] Scan and purge banned terms from remaining `docs/cache/` files: `fix-cache-key.md`, `fix-cache-writing.md`, `fix-cache-reading.md`, `fix-local-api-tables.md`
- [x] T035 [P] [US4] Update `docs/cache/HL-cache-remediation-checklist.md` — mark all 5 checklist items as DONE with code location references
- [x] T036 [US4] Fix resolution docstring in `src/lambdas/shared/cache/ohlc_cache.py` — change "5m" to "5" (or equivalent accurate description) per FR-009
- [x] T037 [US4] Remove the `docs/cache/` exclusion from `scripts/check-banned-terms.sh` per FR-011
- [x] T038 [US4] Run `bash scripts/check-banned-terms.sh` to confirm zero violations without the `docs/cache/` exclusion
- [x] T039 [US4] Run `make validate` to confirm lint + security + banned-term scanner all pass

**Checkpoint**: All docs purged. Scanner passes without exclusions. BENCHED status updated.

---

## Phase 7: User Story 5 — Latent Bug Remediation (Priority: P5)

**Goal**: Fix `#o`/`#c` parsing bug (primary path should work directly), add batch write retry with exponential backoff, remove dead Python <3.9 import fallback.

**Independent Test**: Confirm primary parsing path (`item["open"]`) succeeds without triggering KeyError fallback. Confirm unprocessed items are retried.

### Tests for User Story 5

- [x] T040 [P] [US5] Add unit test in `tests/unit/shared/cache/test_ohlc_persistent_cache.py`: `get_cached_candles()` parses response using `item["open"]` and `item["close"]` directly (not `item["#o"]`/`item["#c"]`)
- [x] T041 [P] [US5] Add unit test in `tests/unit/shared/cache/test_ohlc_persistent_cache.py`: `put_cached_candles()` retries unprocessed items with exponential backoff (mock batch_write_item to return UnprocessedItems twice, verify 3 calls total)
- [x] T042 [P] [US5] Add unit test in `tests/unit/shared/cache/test_ohlc_persistent_cache.py`: `put_cached_candles()` raises RuntimeError after MAX_RETRIES exhausted with unprocessed items remaining

### Implementation for User Story 5

- [x] T043 [US5] In `src/lambdas/shared/cache/ohlc_cache.py`, fix response parsing (~lines 206-213): remove `item["#o"]` / `item["#c"]` checks, use `item["open"]` / `item["close"]` directly per research.md R4 decision
- [x] T044 [US5] In `src/lambdas/shared/cache/ohlc_cache.py`, add exponential backoff retry for unprocessed batch write items per research.md R3 decision (base 100ms, max 3 retries, raise RuntimeError on exhaustion)
- [x] T045 [US5] In `src/lambdas/shared/cache/ohlc_cache.py`, remove dead `backports.zoneinfo` import fallback (~lines 121-122) — repo targets Python 3.13 exclusively per FR-010
- [x] T046 [US5] Run `make test-local` to confirm US5 tests pass and no regressions

**Checkpoint**: Primary parsing path works directly. Batch write retries unprocessed items. Dead code removed.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all user stories

- [x] T047 Run `make validate` — confirm fmt + lint + security + banned-term scanner all pass
- [x] T048 Run `make test-local` — confirm ALL unit + integration tests pass
- [x] T049 Verify `X-Cache-*` headers are included in existing integration tests at `tests/integration/ohlc/test_happy_path.py` and `tests/integration/ohlc/test_error_resilience.py` — add assertions if missing
- [x] T050 Run `bash scripts/check-banned-terms.sh` one final time — confirm zero violations without `docs/cache/` exclusion
- [x] T051 Review all changed files for any accidental introduction of banned terms (run `scripts/check-banned-terms.sh`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (cache module must propagate exceptions before handler can catch them)
- **US2 (Phase 4)**: Depends on Phase 3 (headers include degradation variants, so US1 degradation logic must exist first)
- **US3 (Phase 5)**: Depends on Phase 2 only (TTL is independent of header/error work; can run parallel with US1/US2 if desired, but sequential is safer for a single implementer)
- **US4 (Phase 6)**: Independent of US1/US2/US3 — can run in parallel (only doc/spec file changes)
- **US5 (Phase 7)**: Depends on Phase 2 (cache module changes must not conflict with foundational error propagation changes)
- **Polish (Phase 8)**: Depends on ALL user stories being complete

### User Story Dependencies

- **US1 (P1)**: Requires Foundational (Phase 2) complete. No dependency on other stories.
- **US2 (P2)**: Requires US1 complete (degradation headers are part of the header contract).
- **US3 (P3)**: Requires Foundational (Phase 2) complete. Independent of US1/US2.
- **US4 (P4)**: Fully independent — only touches docs/specs, no source code overlap.
- **US5 (P5)**: Requires Foundational (Phase 2) complete. Independent of US1/US2/US3 (different functions in same file, but no logical overlap).

### Critical Path

```
Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2) → Phase 8 (Polish)
                  ↘ Phase 5 (US3) ↗
                  ↘ Phase 6 (US4) ↗
                  ↘ Phase 7 (US5) ↗
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implementation tasks are sequential (same file modifications)
- Validation checkpoint (`make test-local`) after each story

### Parallel Opportunities

- T007, T008, T009 (US1 tests) can run in parallel — different test functions
- T015, T016, T017, T018 (US2 tests) can run in parallel — different test functions
- T023, T024, T025 (US3 tests) can run in parallel — different test functions
- T030, T031, T032, T033, T034, T035 (US4 doc purge) can run in parallel — different files
- T040, T041, T042 (US5 tests) can run in parallel — different test functions
- US3, US4, US5 can run in parallel with each other (after Phase 2)

---

## Parallel Example: User Story 4 (Doc Purge)

```bash
# Launch all doc purge tasks in parallel (different files):
Task: "Purge banned terms from .specify/specs/ohlc-cache-remediation.md"
Task: "Purge banned terms from .specify/specs/ohlc-cache-remediation-clarifications.md"
Task: "Review .specify/specs/ohlc-cache-remediation-tests.md for banned terms"
Task: "Purge banned terms from docs/cache/fix-cache-tests.md"
Task: "Scan remaining docs/cache/ files for banned terms"
Task: "Update HL-cache-remediation-checklist.md items to DONE"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (verify baseline)
2. Complete Phase 2: Foundational (remove silent error suppression in cache module)
3. Complete Phase 3: US1 — Transparent Cache Failures
4. **STOP and VALIDATE**: `make test-local && make validate`
5. Silent degradation eliminated — biggest production risk resolved

### Incremental Delivery

1. Setup + Foundational → Error propagation established
2. Add US1 → Test → Validate (MVP — silent degradation eliminated)
3. Add US2 → Test → Validate (observability headers on all responses)
4. Add US3 → Test → Validate (TTL on cached items)
5. Add US4 → Test → Validate (docs purged, scanner exclusion removed)
6. Add US5 → Test → Validate (parsing bug fixed, retry added, dead code removed)
7. Polish → Final `make validate && make test-local`

### Recommended Execution (Single Implementer)

Follow phases sequentially: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

This ensures each story builds cleanly on the previous work and avoids merge conflicts within `ohlc_cache.py` and `ohlc.py`.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- BANNED TERMS: See `scripts/check-banned-terms.sh` for the canonical list
- Commit after each phase with `git commit -S` (GPG signed)
- Stop at any checkpoint to validate story independently
- All TTL test assertions use fixed dates (`datetime(2024, 1, 2, ...)`) — not `date.today()` per Constitution Amendment 1.5
