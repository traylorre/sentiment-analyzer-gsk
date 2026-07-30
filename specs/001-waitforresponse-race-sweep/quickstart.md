# Quickstart: verifying the `waitForResponse` race sweep

All commands from the repo root unless stated. Python steps need the venv:
`source .venv/bin/activate`.

## 1. Inventory scan (SC-001)

```bash
python scripts/scan-waitforresponse-race.py
```

Baseline before the sweep: `RACY 27 / PROMISE-FIRST 6 / OTHER 1` (34 inline sites total).
Target after the sweep: `RACY 0 / PROMISE-FIRST 16 / OTHER 1` (17 inline sites total), exit code 0.

The total drops because the 18 helper-routed sites stop being inline wait call sites once they
become `searchAndAwaitResponse(...)` calls, and the helper adds one internal wait. The 16 is
6 pre-existing promise-first + 6 status-only inline conversions + 3 `requestfailed` inline
conversions + 1 inside the helper. Check the other half of SC-001 too:

```bash
grep -rn "searchAndAwaitResponse(" frontend/tests/e2e/ --include="*.spec.ts" | wc -l   # expect 18
```

The script exits non-zero while any `RACY` site remains, so it doubles as a check the dependent
regression-guard feature can wire into CI.

## 2. Smoke run (SC-002 — precondition only, not evidence)

```bash
cd frontend
npx playwright test tests/e2e/chaos-degradation.spec.ts \
  tests/e2e/chaos-scenarios.spec.ts tests/e2e/chart-edge-cases.spec.ts \
  tests/e2e/ticker-search-gaps.spec.ts \
  tests/e2e/chaos-cross-browser.spec.ts tests/e2e/chaos-error-boundary.spec.ts \
  --project="Desktop Chrome"
```

`chaos-cross-browser.spec.ts` (`:35`) and `chaos-error-boundary.spec.ts` (`:63`) are not edited by
this feature but they call `triggerHealthBanner`, so they are in the helper's blast radius and must
run.

Green here proves nothing about the race. Pre-fix code passes this too. It only catches gross
breakage from the conversions.

## 3. Fault injection (SC-003a — the actual gate)

The race does not reproduce on an idle machine, so force it. Temporarily insert a delay between the
action and the listener registration, which is exactly the gap the race exploits.

**Pick the target carefully. Injection is only sound where the mock produces exactly one matching
response.** The two valid targets:

| Target test | Racy site | Why it is sound |
|---|---|---|
| `ticker-search-gaps.spec.ts:22` | `:38` | Returns a single 200 with empty results. Not an error, so `retry: 1` does not fire a second response |
| `chart-edge-cases.spec.ts` | `:72` | Single matching response from its `route.fulfill` mock |

**`chaos-degradation.spec.ts:196` is NOT a valid target.** PR #981 already converted that test's
racy site. It is now promise-first at `:231-237` and is one of the 6 protected already-correct sites
(FR-004). Restoring this feature's conversions will not bring the old shape back, so injecting
there measures nothing.

**The 6 status-only 503 sites (`chaos-helpers.ts:364/367/370`,
`chaos-scenarios.spec.ts:102/105/108`) and the 3 `requestfailed` sites
(`chaos-scenarios.spec.ts:219/222/225`) cannot be validated by injection at all.** `retry: 1`
(`frontend/src/app/providers.tsx:48`) plus the blanket `page.route('**/api/**', …503)` mean a
matching response keeps arriving, so the listener resolves however wide the injected gap. Their
non-reproduction is EXPECTED and does not falsify anything. They are covered by the contention
procedure in section 4 (SC-003b) only.

**Step 1, pre-fix baseline.** Restore the two target files to their pre-sweep content. Do not use
`git stash`: by the time you reach Phase D the conversions are committed, so there is nothing to
stash.

```bash
BASE=$(git merge-base main HEAD)
git checkout $BASE -- frontend/tests/e2e/ticker-search-gaps.spec.ts \
                      frontend/tests/e2e/chart-edge-cases.spec.ts
# widen the gap at the racy site, in the spec file, e.g.:
#   await searchInput.fill('ZZZZZ');
#   await new Promise((r) => setTimeout(r, 250));   // <-- injected
#   await page.waitForResponse('**/api/v2/tickers/search**');
cd frontend
npx playwright test tests/e2e/ticker-search-gaps.spec.ts \
  tests/e2e/chart-edge-cases.spec.ts --project="Desktop Chrome"
cd .. && git checkout HEAD -- frontend/tests/e2e/ticker-search-gaps.spec.ts \
                              frontend/tests/e2e/chart-edge-cases.spec.ts
```

**Expected: FAIL at the injected site.** If it passes, the diagnosis is wrong: stop and re-analyse
rather than proceeding. That stop condition is the whole value of this step, and it applies to these
two sites only.

**Step 2, post-fix.** The seam moved. After conversion both targets are single
`searchAndAwaitResponse(...)` calls, so the fill and the await both live inside the helper. The
delay MUST go inside `frontend/tests/e2e/helpers/search-helpers.ts`, between
`await searchInput.fill(query);` and `await responsePromise;`.

Injecting the delay in the `.spec.ts` file instead does NOT satisfy this step. There, the only
position after the action is after the helper has already awaited, so the delay lands once the
promise has resolved and the test passes without exercising anything.

**Negative control.** With the delay in that seam, flip the helper's statement order to the pre-fix
shape (create the promise below the fill). It MUST fail. Restore promise-first: it MUST pass. If
both orderings pass, the delay is not in the seam and the result is void.

**Expected: PASS, with the negative control failing.**

Do **not** commit the injection patch.

## 4. Contention (SC-003b)

```bash
cd frontend
npx playwright test tests/e2e/chaos-degradation.spec.ts \
  tests/e2e/chaos-scenarios.spec.ts tests/e2e/chart-edge-cases.spec.ts \
  tests/e2e/ticker-search-gaps.spec.ts \
  tests/e2e/chaos-cross-browser.spec.ts tests/e2e/chaos-error-boundary.spec.ts \
  --project="Desktop Chrome" --repeat-each=20 --workers=8
```

**Expected: 20/20 for every affected test.** This is the only verification the 6 status-only and
3 `requestfailed` sites get, since injection is unsound on them (section 3).
`chaos-cross-browser.spec.ts` and `chaos-error-boundary.spec.ts` are here because they call
`triggerHealthBanner` without being edited.

## 5. Test-count parity (SC-004)

Compare the pass/fail/skip tally against the pre-sweep run. It must be identical except that
failures become passes. Any drop in the passed count, or any new skip, means a test was weakened to
reach green.

## 6. Board validation (SC-005)

```bash
python - <<'PY'
import json
s = open('CLEANUP-BOARD.html').read()
i = s.index('const CARDS = ') + len('const CARDS = ')
cards, _ = json.JSONDecoder().raw_decode(s[i:])
print('cards:', len(cards))          # expect 120 (118 + 2 new)
PY
```

The two new cards are the merge-required follow-up and the `dynamodb_throttle` dead-branch trap
(FR-009). FR-008's two edits are in place and do not change the count.

Then open the board in a browser and confirm it renders with no console error.

## Reference

PR #981 (`8c27271`) is the merged reference conversion — one site, promise-first, 15s cap.
