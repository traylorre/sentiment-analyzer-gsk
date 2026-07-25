# Plan 1398: cross-source-dedup-fix

**Scope:** two-line production change + one defense-in-depth guard + one regression
test. No infra, no migration, no new dependencies.

## 1. The Fix

### Change A (primary, FR-001) — `src/lambdas/shared/adapters/finnhub.py:227`

```python
# before
published_at = datetime.fromtimestamp(item["datetime"])
# after
published_at = datetime.fromtimestamp(item["datetime"], tz=UTC)
```

`UTC` is already imported (finnhub.py:8, `from datetime import UTC, datetime,
timedelta`). No import change needed.

**NOT changed:** `finnhub.py:388` (`OHLCCandle.date` on the `/stock/candle` price
path). Verified this session: it does not feed `published_at`, the dedup key, or the
news SK. Touching it here would be an unverified edit to an unrelated path.
Signposted in spec Open Questions (Q2).

### Change B (defense-in-depth, FR-002) — `src/lambdas/ingestion/handler.py` `_process_article`, adjacent to :1005

Before building the SK (and before `generate_dedup_key`, so the PK date hash gets the
same protection on non-UTC hosts):

```python
if article.published_at.tzinfo is None:
    article = article.model_copy(
        update={"published_at": article.published_at.replace(tzinfo=UTC)}
    )
```

Rationale: adapters are the right place to fix the data, but the key-construction
site is the right place to enforce the invariant. A future adapter that regresses to
naive datetimes must not silently split the keyspace again. `replace(tzinfo=UTC)` is
correct here because every naive datetime in this pipeline is UTC wall clock by
construction (Lambda TZ=UTC); it is a no-op for aware values so Tiingo SKs are
byte-identical before/after. (Exact placement/mechanics may be adjusted at
implementation time — e.g. mutating a local variable instead of `model_copy` — the
invariant is what's specified, guarded by the FR-002 test.)

## 2. Test Design (FR-003, FR-004)

New file: `tests/unit/ingestion/test_cross_source_tz_merge.py`

**Critical property: `published_at` MUST come out of the real adapter parse code.**
The existing `test_cross_source_dedup.py` hands identical timestamp *strings*
straight to the dedup layer, which is exactly why it passes while prod fails. This
test must not repeat that mistake.

Structure:

1. **Fixture — one story, two feeds.** Pick one UTC instant, e.g.
   `2026-01-15T14:30:00Z` → epoch `1768487400`. Build a Tiingo payload
   (`{"publishedDate": "2026-01-15T14:30:00Z", "title": "Apple Reports Q4 Earnings
   Beat", ...}`) and a Finnhub payload (`{"datetime": 1768487400, "headline": "Apple
   reports Q4 earnings beat", ...}` — different casing to exercise headline
   normalization too). Mock the HTTP layer (`respx`/`responses`/monkeypatched
   `client.get`, matching existing adapter-test conventions) and call the real
   `TiingoAdapter.get_news()` / `FinnhubAdapter.get_news()` parse paths to obtain two
   `NewsArticle` objects.
2. **Test 1 — SK equality (unit-level smoking gun):**
   `assert tiingo_article.published_at.isoformat() ==
   finnhub_article.published_at.isoformat()`. Fails today
   (`...+00:00` vs bare). Passes after Change A.
3. **Test 2 — end-to-end merge:** run both articles through `_process_article`
   against a mocked/moto table. Assert the second call takes the `"updated"` path
   and both `update_item`/`put_item` invocations used the SAME
   `{"source_id", "timestamp"}` Key; with moto, additionally assert exactly one item
   exists and `sources == ["tiingo", "finnhub"]`. Fails today (two distinct Keys, two
   rows). Order-swapped variant (Finnhub first) included.
4. **Test 3 — midnight/PK edge:** epoch at exact UTC midnight; assert dedup PK date
   part and SK both match across adapters (guards the `strftime("%Y-%m-%d")` path in
   `generate_dedup_key` on any host tz — run once with `TZ` monkeypatched to a
   non-UTC zone via `time.tzset` to prove host-independence).
5. **Test 4 — FR-002 guard idempotence:** an already-aware `published_at` passes
   through the guard unchanged (byte-identical isoformat), and a synthetic naive one
   gets `+00:00`.

**Fails-before/passes-after protocol (explicit gate):** run the new test file on the
unmodified code and record the failure output; apply Changes A+B; run again and
record the pass. Both outputs go in the PR description. If Test 2 does NOT fail
before the fix, the test is vacuous — stop and rewrite it (highest-risk task, see
AR#3).

## 3. Backfill — OUT OF SCOPE (decided)

Already-written duplicate NEWS rows are NOT migrated:

- Rows carry `ttl_timestamp` (`TTL_DAYS`, handler.py:984) and age out automatically.
- Repo precedent: 501-purge-newsapi shipped code-only with "existing data NOT
  migrated"; the standing "no new AWS resources / prefer code-only" constraint also
  applies.
- Transition note (from spec AR#1 Attack 2): for up to the ingestion lookback
  window, re-crawled Finnhub stories won't dedup against their old naive-SK rows —
  bounded transient duplication, cleared by TTL. No action.

**Interaction with 1397 (oauth-dup-cleanup): none.** 1397 consolidates duplicate
USER records in `preprod-sentiment-users`; 1398 prevents duplicate NEWS records in
the ingestion table. Different entities, different tables, different keys, no shared
code path, no ordering constraint. Kept separate deliberately.

## 4. Rollout / Verification

- Unit gates: new test file + full `pytest tests/unit/ingestion/` +
  `pytest tests/unit/` (adapter tests included), ruff, bandit — per repo pre-push
  checklist.
- Post-deploy (preprod) spot check: after one ingestion cycle, query a story known
  to appear in both feeds; expect one item with `sources` length 2 and an
  `articles_updated`-style log line from dedup.py:216-220 (first time that log will
  ever fire for a cross-source pair).
- Consumer sweep (spec AR#1 Attack 3): grep consumers of `metadata.published_at`
  and the SNS `timestamp` field; confirm ISO-8601-with-offset parses everywhere
  (`news_item.py:158` already does).

---

## Adversarial Review #2 (plan)

**Attack 1 — "Change B's `replace(tzinfo=UTC)` could mislabel a genuinely local
naive datetime as UTC."** In this pipeline naive can only arise from
epoch-`fromtimestamp` on a UTC host (or a future buggy adapter). Mislabeling risk
exists only if a future adapter produces naive *local* time on a non-UTC host —
which is already broken data; the guard at least keeps the keyspace consistent and
the log/monitoring story simple. Alternative considered (raise on naive): rejected —
turning a dedup-quality bug into a hard ingestion failure is worse. The guard plus
the Test 3 host-tz proof is the right trade.

**Attack 2 — "Test 2 mocked-table assertions could pass trivially if the mock
doesn't enforce Key semantics."** That's why Test 1 (raw SK string equality) exists
independently, and why Test 2 asserts on the captured Key arguments themselves, not
just on return values. The moto variant closes the remaining gap by counting real
rows. And the fails-before gate catches any residual vacuousness empirically.

**Attack 3 — "Why not fix ONLY at the handler (Change B) and skip the adapter?"**
Because the adapter's naive datetime leaks elsewhere: `NewsArticle.published_at` is
consumed beyond dedup (metadata blob, `news_item` round-trip, any future comparison
against aware datetimes → `TypeError` on `<`). Fixing at the source is the real fix;
the handler guard is belt-and-braces, not the fix.

**Attack 4 — "Does epoch 1768487400 actually equal 2026-01-15T14:30:00Z?"**
Implementation task T2 computes the fixture epoch with
`int(datetime(2026,1,15,14,30, tzinfo=UTC).timestamp())` rather than trusting a
hardcoded literal — self-verifying fixture, no manual arithmetic to get wrong.

**Verdict:** Plan holds. Minimal diff, correct layer, non-vacuous test protocol,
backfill decision documented with precedent.
