# Tasks 1398: cross-source-dedup-fix

Dependency-ordered. Each task maps to an FR. Battleplan stage: authored only — no
implementation performed yet. [P] = parallelizable with siblings at same depth.

## Phase A — Prove the defect (must come FIRST)

- [ ] **T1 (FR-004): Write the regression test file** —
  `tests/unit/ingestion/test_cross_source_tz_merge.py` per plan §2: Test 1 (adapter
  SK string equality), Test 2 (end-to-end merge via `_process_article`, both
  orderings, Key-argument assertions + moto row count), Test 3 (UTC-midnight epoch +
  non-UTC host tz via monkeypatched `TZ`/`tzset`), Test 4 (guard idempotence —
  written xfail/skipped until T4 exists, then enabled). `published_at` MUST be
  produced by the real adapter parse code with mocked HTTP payloads; fixture epoch
  computed from the aware datetime, not hardcoded.
- [ ] **T2 (FR-004, gate): Record FAILS-BEFORE evidence** — run T1's file against
  unmodified code. Tests 1-3 MUST fail with the `+00:00`-vs-bare SK mismatch
  visible in the assertion diff. Capture output for the PR. If Test 2 passes here,
  STOP: the test is vacuous — rewrite before touching production code.

## Phase B — Fix

- [ ] **T3 (FR-001): Normalize Finnhub news timestamp** — `finnhub.py:227` →
  `datetime.fromtimestamp(item["datetime"], tz=UTC)`. One line; `UTC` already
  imported at finnhub.py:8. Explicitly do NOT touch finnhub.py:388 (OHLC path,
  verified out of scope).
- [ ] **T4 (FR-002): Add tz-invariance guard in `_process_article`** —
  `src/lambdas/ingestion/handler.py` before `generate_dedup_key` (:969) and SK
  build (:1005): naive `published_at` → treat as UTC; aware → untouched. Enable
  Test 4.

## Phase C — Verify (all [P] after T3+T4)

- [ ] **T5 (FR-004, gate): Record PASSES-AFTER evidence** — full T1 file green;
  pair with T2 output in the PR description.
- [ ] **T6 [P] (FR-003 / SC-3, SC-4): No-regression sweep** — full
  `pytest tests/unit/ingestion/` and `pytest tests/unit/shared/` (adapter tests);
  assert zero changes needed to existing tests' expectations for Tiingo (any
  existing test that needed a Tiingo expectation change = SC-3 violation, stop).
- [ ] **T7 [P] (spec AR#1 Attack 3): Consumer sweep** — grep consumers of
  `metadata.published_at` and SNS `timestamp`; confirm each parses ISO 8601 with
  offset (news_item.py:158 confirmed already). Document findings in PR.
- [ ] **T8 [P]: Lint/SAST gates** — ruff check/format, bandit, per repo pre-push
  checklist.

## Phase D — Land

- [ ] **T9: PR** — includes T2+T5 fail/pass transcripts, the :388 out-of-scope
  note, and the transition note (old naive-SK Finnhub rows won't merge during the
  lookback window; TTL clears them — no backfill, per plan §3).
- [ ] **T10 (post-merge, preprod): Live spot check** — after one ingestion cycle,
  find a story present in both feeds; expect ONE item, `sources` length 2, and the
  dedup.py:216 "Updated article with new source" log firing for a cross-source pair
  for the first time.

## Dependencies

```
T1 → T2 → (T3, T4) → T5 → T9 → T10
              └────→ (T6, T7, T8) → T9
```

---

## Adversarial Review #3 (tasks)

**Attack 1 — "T1 before T3 is TDD theater if the implementer writes the test with
the fix in mind and it accidentally encodes post-fix behavior."** The T2 gate is the
defense: fails-before is a recorded, mandatory artifact, and the failure mode is
specified (SK string diff must be visible). A test that doesn't fail at T2 is
rejected by instruction, not by judgment.

**Attack 2 — "T4's guard placement (before :969) subtly changes the dedup PK for
naive inputs on non-UTC hosts — is that covered?"** Yes, deliberately: Test 3 runs
under a monkeypatched non-UTC TZ and asserts PK-date and SK equality. On Lambda
(TZ=UTC) the PK never diverged, so no production PK changes.

**Attack 3 — "T6 could mask a real Tiingo SK change if an existing test is loose."**
T6's stop-condition is expectation *edits*, and Test 1/Test 4 assert byte-identical
isoformat for aware inputs directly — belt and braces.

**Attack 4 — "T10 depends on both feeds carrying the same story with the same
second-granular publish time — it may not reproduce on demand."** Acknowledged;
T10 is a spot check, not a gate. The merge correctness gate is T5 (deterministic
unit evidence). If no shared story appears within a few cycles, T10 falls back to
asserting the absence of NEW dual-row pairs (query for items sharing a `dedup_key`
with disjoint single-source `sources` created post-deploy).

**Ordering check:** every task maps to an FR or a spec/plan AR obligation;
fails-before/passes-after are explicit tasks (T2, T5) not footnotes; no task touches
finnhub.py:388.

**Highest-risk task: T1/T2** — writing the merge test at the wrong layer
(hand-constructed datetimes or a mock that ignores Key semantics) would make it pass
before the fix and prove nothing. The T2 stop-condition exists precisely for this.

**Verdict: READY.** No blockers, no owner gates, no infra, no migration. Ready for
implementation whenever the battleplan opens the implementation phase.
