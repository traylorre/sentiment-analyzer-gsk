# Tasks: Sweep the act-then-wait `waitForResponse` race class

**Feature Branch**: `001-waitforresponse-race-sweep`
**Input**: Design documents from `/specs/001-waitforresponse-race-sweep/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/helper-api.md, quickstart.md

**Format**: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no ordering dependency)
- **[Story]**: US1 (trustworthy CI signal, P1), US2 (named interaction, P2), US3 (board states verified facts, P3)
- Every task cites the FR/SC it satisfies and states testable acceptance criteria

---

## How to read the line numbers in this document

Line numbers in this document are **PRE-SWEEP locators** recorded against commit `8c27271`. Phase C
conversions are net line-additive, so downstream line numbers **WILL** drift during implementation.
Match sites by file plus the quoted original statement plus the enclosing test or function name.
Never match by line number alone.

This applies to the verification tasks too. T018 states expected scan output as **per-file counts**
plus enclosing test or function names, deliberately not as line numbers, because the post-sweep scan
cannot report pre-sweep lines and a line-pinned expectation would read as a failure that is not
there.

---

## Standing Constraints (apply to every task)

| Constraint | Source | Enforcement |
|---|---|---|
| Every commit GPG-signed (`git commit -S`) | CLAUDE.md, plan Constitution Check | Commit fails without a signature; never bypass |
| Never `--no-verify` / `commit -n` | CLAUDE.md, `block-no-verify.sh` hook | Hook denies the command |
| Activate the venv before any Python work (`source .venv/bin/activate`) | CLAUDE.md | `python --version` must report 3.13.x |
| Test-only changes. No product code. | FR-007 | `git diff --stat` must show no path under `frontend/src/` |
| Permitted paths outside `frontend/tests/e2e/`: `scripts/scan-waitforresponse-race.py`, `CLEANUP-BOARD.html`, `specs/001-waitforresponse-race-sweep/` | FR-007 | Audited by T025 |
| The Playwright E2E job stays **non-required** | FR-009, Out of Scope | No edit to `.github/workflows/pr-checks.yml` |
| Target is the **customer** dashboard (Next.js/Amplify), run via `npx playwright test` from `frontend/` | CLAUDE.md two-dashboard rule | Every touched file already carries `// Target: Customer Dashboard (Next.js/Amplify)` (verified) |
| Verification runs use `--project="Desktop Chrome"` only | plan Technical Context, AR#2 N-06 | The other four configured projects are not exercised by CI and are not verified here |
| The fault-injection patch is **never committed** | SC-003(a) | T022 confirms a clean tree |

---

## Phase A — Scan artifact and baselines (FR-011, SC-001, SC-004)

**Purpose**: make the "zero racy sites" claim reproducible, and capture the before-state so SC-001
and SC-004 have something to compare against. Nothing in Phase C may start until T002 has recorded
the baseline, because a baseline taken after a conversion is worthless.

- [ ] **T001** [US1] Write the committed inventory scan at `scripts/scan-waitforresponse-race.py`
  - **Files**: `scripts/scan-waitforresponse-race.py` (NEW)
  - **Satisfies**: FR-011, and enables SC-001
  - **Acceptance criteria**:
    1. The script scans every `*.ts` file under `frontend/tests/e2e/` (spec files **and** `helpers/`).
    2. It classifies **both** `page.waitForResponse(...)` **and**
       `page.waitForEvent('requestfailed'|'response')`. A script that matches only `waitForResponse`
       fails this task — that method-name framing is exactly what hid 3 sites (AR#2 N-01).
    3. The classification rule is documented **in the script itself** (module docstring), verbatim
       to FR-011: `RACY` = an awaited wait whose immediately preceding non-comment, non-blank line
       performs a triggering action (`.fill(`, `.click(`, `.press(`, `.selectOption(`, `.clear(`,
       `.goto(`, `.reload(`, `.evaluate(`, `.type(`, `.check(`, `.tap(`, `.setInputFiles(`,
       `.dispatchEvent(`); `PROMISE-FIRST` = wait assigned to a variable before the triggering
       action and awaited after it; `OTHER` = neither, requires human triage.
       The `.evaluate(` token is not hypothetical: `error-visibility-search.spec.ts:158` triggers
       via `retryButton.evaluate((el) => el.click())`. A token list missing it would misclassify a
       live shape.
    4. Comment lines are **excluded from the call-site population**. Verified count: a naive
       `grep -rn "waitForResponse\|waitForEvent"` over `frontend/tests/e2e/` returns **41** lines, of
       which **7 are comments** (`error-visibility-search.spec.ts:141`, `helpers/chaos-helpers.ts:338`,
       `helpers/chaos-helpers.ts:392`, `ticker-search-gaps.spec.ts:37`, `:230`, `:236`, `:243`).
       The script MUST report **34**, not 41.
    5. Output names every site as `file:line CLASSIFICATION` plus a summary line with the four counts.
    6. `sys.exit(1)` when `RACY > 0`; `sys.exit(0)` otherwise. Assert both branches by running the
       script before and after Phase C (T002 → exit 1; T018 → exit 0).
    7. It classifies `chaos-scenarios.spec.ts:138` as `OTHER` (an intervening
       `await expect(...).toBeVisible({ timeout: 2000 })` separates its `page.reload()` from the wait).
       If it reports `RACY` there, the adjacency rule is not implemented correctly.
    8. Runs under the project venv: `source .venv/bin/activate && python scripts/scan-waitforresponse-race.py`.
    9. NOT wired into pre-commit or any workflow (spec C4). `grep -rn "scan-waitforresponse-race" .pre-commit-config.yaml .github/` returns nothing.
    10. `OTHER` sites are printed under an explicit **"requires human triage"** banner, not folded
        into the summary counts alone. A shape the classifier cannot place must be *visible*, or it
        gets counted as clean by omission. The banner lists each `OTHER` site with its file, its
        enclosing test or function name, and the statement text.
    11. The module docstring carries `# Target: Customer Dashboard (Next.js/Amplify)` and the
        `--help` output names `frontend/tests/e2e/` as the scanned root. Two existing scripts
        (`scripts/audit-e2e-skips.py`, `scripts/check-false-pass-patterns.sh`) default to the
        **admin** pytest suite under `tests/`, and this repo has a documented history of confusing
        the two dashboards (CLAUDE.md, "Two Dashboards"). A reader must not have to open the source
        to learn which suite this scans.

- [ ] **T002** [US1] Capture the pre-sweep scan baseline (depends on T001)
  - **Files**: none modified; output recorded in the T001/T002 commit message and pasted into this
    file's `## Execution Log` section below
  - **Satisfies**: SC-001 (the "before" half)
  - **Acceptance criteria**:
    1. Run **before any conversion exists in the tree**.
    2. Output is exactly `RACY 27 / PROMISE-FIRST 6 / OTHER 1`, total **34**.
    3. Exit code is **1**.
    4. The 27 RACY lines match the spec inventory table exactly:
       `ticker-search-gaps.spec.ts` 38/77/82/109/129/144/162/211/219 (9);
       `chaos-degradation.spec.ts` 131/138/178/183/188 (5);
       `chart-edge-cases.spec.ts` 72/130/161/218 (4);
       `helpers/chaos-helpers.ts` 364/367/370 (3);
       `chaos-scenarios.spec.ts` 102/105/108 (3) and 219/222/225 (3).
    5. The 6 PROMISE-FIRST lines are `chaos-degradation.spec.ts:231`, `chaos-scenarios.spec.ts:251`,
       `error-visibility-search.spec.ts:142`, `:157`, `ticker-search-gaps.spec.ts:231`, `:237`.
    6. **Any deviation from 27/6/1/34 halts the sweep** until the inventory or the classifier is
       reconciled. A baseline that does not reproduce the spec's numbers means one of them is wrong.

- [ ] **T003** [P] [US1] Capture the pre-sweep Playwright pass/fail/skip tally
  - **Files**: none modified; tally recorded in `## Execution Log`
  - **Satisfies**: SC-004 (the "before" half)
  - **Acceptance criteria**:
    1. `cd frontend && npx playwright test tests/e2e/chaos-degradation.spec.ts tests/e2e/chaos-scenarios.spec.ts tests/e2e/chart-edge-cases.spec.ts tests/e2e/ticker-search-gaps.spec.ts tests/e2e/chaos-cross-browser.spec.ts tests/e2e/chaos-error-boundary.spec.ts --project="Desktop Chrome"`
    2. The passed / failed / skipped counts are written down verbatim, with the git SHA they were
       taken at.
    3. This is a **counting** run, not an evidential one. Do not cite it as evidence the race exists
       or is fixed (SC-002 is explicitly non-evidential).
  - **Parallel**: independent of T001/T002 — no shared files.

---

## Phase B — The helper (FR-005, US2)

- [ ] **T004** [US2] Create `searchAndAwaitResponse` per the contract
  - **Files**: `frontend/tests/e2e/helpers/search-helpers.ts` (NEW)
  - **Satisfies**: FR-005, FR-006, FR-012 (contract G2), US2 acceptance scenarios 1 and 2
  - **Acceptance criteria**:
    1. Signature matches `contracts/helper-api.md` exactly:
       `searchAndAwaitResponse(page, searchInput, query, options?: { predicate?, timeout?, clearFirst? }): Promise<Response>`.
    2. **G1** — the response promise is created before any interaction with the input. A reviewer
       reading the function body sees `const responsePromise = page.waitForResponse(...)` on a line
       strictly above the first `searchInput.fill(...)`. The scan (T001) classifies the helper's
       internal wait as `PROMISE-FIRST`.
    3. **G2** requires that the listener cannot escape as an unhandled rejection, **even when an
       interaction throws**. "Awaited on every return path" is not a checkable criterion here: the
       helper has exactly one return path, so the wording is vacuous, and it does not cover the real
       hole, which is `searchInput.fill()` throwing *before* the await is ever reached. Check the
       shape instead. It MUST be one of the two forms the contract now names
       (`contracts/helper-api.md`, "Required shape for the throw path"), and a reviewer states which:
       - **Option A**, `try { ...clearFirst/fill... } finally { }` wrapping the interactions, with
         the `finally` attaching a rejection sink on the throw path, or
       - **Option B**, `.catch(() => {})` attached to `responsePromise` **at creation**, on the line
         it is created, so the promise is never unhandled regardless of what happens after.

       This is the helper, which is **new code**. Unlike the 6 protected inline sites, there is no
       FR-004 obstacle to doing it properly, so the FR-012 "no `try/finally` required" carve-out
       does not apply here. That carve-out exists for sites this feature may not touch.
    4. **G3** — a caller-supplied `predicate` is passed through unmodified. No wrapping, no `&&`,
       no widening. Assert by reading the body: the supplied predicate reaches `waitForResponse`
       untouched.
    5. Defaults: `predicate` = `(r) => r.url().includes('/api/v2/tickers/search')`,
       `timeout` = `15000` (FR-006), `clearFirst` = `false`.
    6. A comment on the default predicate records that it matches **13 of the 18** URL-scoped sites,
       not all 18, and points at the contract's "Sites requiring an explicit predicate" table
       (AR#2 D-06).
    7. `clearFirst: true` performs `fill('')` before `fill(query)`, both inside the single listener,
       with a comment citing `ticker-input.tsx:37` (`enabled: query.length >= 1`) as why an empty
       fill cannot trigger a request.
    8. Non-guarantees N1 (cache-served queries) and N2 (`retry: 1` disambiguation) are stated in the
       JSDoc so a caller cannot assume them.
    9. File carries the `// Target: Customer Dashboard (Next.js/Amplify)` header.
    10. `cd frontend && npx tsc --noEmit` passes.

---

## Phase C — Conversions (FR-001, FR-002, FR-003, FR-004, FR-006, FR-010, FR-012)

**Ordering is deliberate and MUST be preserved**: `chart-edge-cases` → `ticker-search-gaps` →
`chaos-scenarios` → `chaos-degradation` → `chaos-helpers`. `chaos-helpers.ts` is last because
`triggerHealthBanner` is a precondition of the whole chaos suite; its change must be validated
against already-converted callers and against the two unedited callers
(`chaos-cross-browser.spec.ts:35`, `chaos-error-boundary.spec.ts:63`). Smallest blast radius first
for everything above it.

### C.1 — `chart-edge-cases.spec.ts` (4 sites)

- [ ] **T005** [US1] Convert the 4 URL-scoped sites to `searchAndAwaitResponse`
  - **Files**: `frontend/tests/e2e/chart-edge-cases.spec.ts`
  - **Satisfies**: FR-001, FR-002, FR-005, FR-006, FR-012
  - **Acceptance criteria**:
    1. Sites `:72`, `:130`, `:161`, `:218` — each currently `await searchInput.fill('AAPL');` followed
       by `await page.waitForResponse('**/api/v2/tickers/search**');` — become a single
       `await searchAndAwaitResponse(page, searchInput, 'AAPL');`.
    2. All four sites use the **default** predicate. Justified: the original is the glob
       `'**/api/v2/tickers/search**'`, and the default `r.url().includes('/api/v2/tickers/search')`
       matches the same population. No widening, so FR-002 is satisfied with no declaration needed.
    3. No query scoping is added. Justified per research D4: the `beforeEach` mock at
       `chart-edge-cases.spec.ts:32-40` `route.fulfill`s a **200** for ticker search, so `retry: 1`
       never fires and exactly one matching response exists per test.
    4. Each of the four tests contains exactly **one** converted wait, so **no `test.setTimeout(60000)`
       is added here** (FR-006 applies only above two waits). Verify by counting
       `searchAndAwaitResponse(` per test body.
    5. Import added: `import { searchAndAwaitResponse } from './helpers/search-helpers';`.
    6. `npx tsc --noEmit` passes and
       `npx playwright test tests/e2e/chart-edge-cases.spec.ts --project="Desktop Chrome"` is green.
    7. The scan (T001) reports zero `RACY` in this file.

### C.2 — `ticker-search-gaps.spec.ts` (9 sites)

- [ ] **T006** [US1] Convert the 9 URL-scoped sites to `searchAndAwaitResponse`
  - **Files**: `frontend/tests/e2e/ticker-search-gaps.spec.ts`
  - **Satisfies**: FR-001, FR-002, FR-005, FR-006, FR-010, FR-012
  - **Acceptance criteria**:
    1. Sites `:38`, `:77`, `:82`, `:109`, `:129`, `:144`, `:162`, `:211`, `:219` all become
       `searchAndAwaitResponse(...)` calls with the default predicate (all nine originals are the
       glob `'**/api/v2/tickers/search**'` — no widening, no declaration needed).
    2. **`.clear()` → `clearFirst: true` at `:219`** (test `'duplicate ticker switches to existing
       chip without adding'`). The original sequence is
       `await searchInput.clear(); await searchInput.fill('GOOGL'); await page.waitForResponse(...)`.
       The helper's `clearFirst: true` performs `fill('')`. Playwright documents `locator.clear()`
       as equivalent to `fill('')`, so this is not a behavioural change and needs no declaration
       beyond a one-line note in the commit message. No fallback shape is offered; use the helper.
    3. **FR-010 hold-out**: `ticker-search-gaps.spec.ts:242-247` is left **byte-unchanged**. It
       deliberately omits a wait because the repeated `AAPL` query is served from React Query cache
       inside the 30s `staleTime` window (`ticker-input.tsx:38`) and no network request occurs.
       Introducing `searchAndAwaitResponse` there would hang until timeout (contract N1).
       `git diff frontend/tests/e2e/ticker-search-gaps.spec.ts` shows no hunk touching that range.
    4. The two already-correct sites `:231` and `:237` are left **byte-unchanged** (FR-004, spec C5).
    5. No test in this file exceeds two converted waits (max is 2, in the tests at `:46` and `:206`),
       so **no `test.setTimeout(60000)` is added here**. Verify by counting.
    6. The stale comment at `:37` ("Wait for debounced search response") disappears with the
       conversion. Do not replace it with another debounce claim — there is no debounce
       (`ticker-input.tsx:33-39`, research R3).
    7. `npx tsc --noEmit` passes; the file is green under `--project="Desktop Chrome"`.
    8. The scan reports zero `RACY` in this file and still reports `:231`/`:237` as `PROMISE-FIRST`.

### C.3 — `chaos-scenarios.spec.ts` (6 sites: 3 `waitForResponse` + 3 `waitForEvent`)

- [ ] **T007** [US1] Convert `:102/:105/:108` inline, keeping the status-only predicate
  - **Files**: `frontend/tests/e2e/chaos-scenarios.spec.ts`
  - **Satisfies**: FR-001, FR-002 (accepted-risk exception), FR-003, FR-006, FR-012
  - **Acceptance criteria**:
    1. Each of the three sites becomes promise-first inline:
       `const r1 = page.waitForResponse((r) => r.url().includes('/api/') && r.status() === 503, { timeout: 15000 });`
       then the fill(s), then `await r1;`.
    2. The predicate is **byte-identical** to the original. It is NOT routed through the helper and
       NOT narrowed to `/tickers/search` — that would change what the test asserts (FR-005, contract N3).
    3. No query scoping is added. This is the FR-002 accepted-risk exception: under
       `dynamodb_throttle`'s blanket 503 route any failing response legitimately signals "the API is
       failing", which is what the health-monitor failure counter keys on. The commit message MUST
       restate the residual risk: these waits confirm *a* failure occurred, not *this search's*
       failure, so a regression making only one of three searches fail would still satisfy them.
    4. `{ timeout: 15000 }` on every converted call (FR-006).
    5. **FR-003 hold-out**: `chaos-scenarios.spec.ts:138` is left **byte-unchanged**. Its action is
       `page.reload()`, the `lambda_cold_start` handler delays 3s before `route.continue()`, and an
       `await expect(skeletons.first()).toBeVisible({ timeout: 2000 })` sits between them — leaving a
       worst-case ordering margin of about **1s** (not the 2.8s an earlier draft claimed). The reason
       is recorded in the commit message, and the scan continues to classify it `OTHER`.
    6. `chaos-scenarios.spec.ts:251` (already correct) is left **byte-unchanged** (FR-004).

- [ ] **T008** [US1] Convert the 3 `waitForEvent('requestfailed')` sites inline
  - **Files**: `frontend/tests/e2e/chaos-scenarios.spec.ts` (depends on T007 — same file)
  - **Site identification** (pre-sweep `:219/:222/:225`, which will have drifted by the time T007
    lands): the three occurrences of the exact statement
    `await page.waitForEvent('requestfailed', { timeout: 5000 });`
    inside the test titled `'API timeout — errors communicated, no blank screens'`. There are
    exactly three in the file and all three are in that test. Match on the statement text, not the
    line.
  - **Satisfies**: FR-001, FR-002 (accepted-risk exception), FR-006, FR-012
  - **Acceptance criteria**:
    1. Each becomes promise-first inline:
       `const f1 = page.waitForEvent('requestfailed', { timeout: 15000 });` then the fill(s), then
       `await f1;`.
    2. These convert **inline, not through the helper** — `waitForEvent('requestfailed')` takes no
       predicate at all, so there is nothing for the helper to parameterise (contract N3).
    3. Per-call timeout is raised from the original `5000` to `15000` (FR-006). The change is
       declared in the commit message as a diagnosability change, explicitly not the fix.
    4. These sites fire under `api_timeout`'s `route.abort`, which collapses the action-to-listener
       margin further than `route.fulfill` does — record that in the commit message as why they are
       in the same class despite the different method name (AR#2 scope-definition lesson).
    5. The scan (T001) reports all three as `PROMISE-FIRST`, proving the classifier covers
       `waitForEvent`, not just `waitForResponse`. Verify by the scan's per-file count for
       `chaos-scenarios.spec.ts`, not by the reported line numbers, which have drifted.

- [ ] **T009** [US1] Add `test.setTimeout(60000)` to the two multi-wait tests in this file
  - **Files**: `frontend/tests/e2e/chaos-scenarios.spec.ts` (depends on T007, T008)
  - **Satisfies**: FR-006
  - **Site identification**: by **test title**, not by line. Both tests have already been edited by
    T007/T008, so their pre-sweep line numbers (`:88`, `:210`) are stale locators only.
  - **Acceptance criteria**:
    1. `test.setTimeout(60000)` is the first statement in the test titled
       `'database throttle — health banner appears, cached data visible'`, which contains the three
       converted status-503 waits from T007.
    2. `test.setTimeout(60000)` is the first statement in the test titled
       `'API timeout — errors communicated, no blank screens'`, which contains the three converted
       `requestfailed` waits from T008.
    3. No other test in this file receives one. Verify by walking every `test(` block in the file
       and counting converted waits per block; each of the others holds at most one. Do not rely on
       the pre-sweep block starts `:28`, `:123`, `:150`, `:240`.
    4. Rationale comment on each: `playwright.config.ts` sets no top-level `timeout` (verified — the
       `timeout` keys at `:67`/`:76` are `webServer` timeouts), so the cap is Playwright's default
       30000ms, and a second hung 15000ms wait would blow the test cap before the per-call cap fires,
       reporting opaquely — the exact outcome FR-006 exists to prevent.

### C.4 — `chaos-degradation.spec.ts` (5 sites)

- [ ] **T010** [US1] Convert `:131` and `:138` with their **original status-bearing predicates passed explicitly**, query-scoped
  - **Files**: `frontend/tests/e2e/chaos-degradation.spec.ts`
  - **Satisfies**: FR-001, FR-002, FR-005, FR-006, FR-012, US1 acceptance scenario 3
  - **Acceptance criteria**:
    1. `:131` becomes
       `await searchAndAwaitResponse(page, searchInput, 'AAPL', { predicate: (r) => r.url().includes('/tickers/search') && r.url().includes('q=AAPL') && r.status() === 500 });`
    2. `:138` becomes
       `await searchAndAwaitResponse(page, searchInput, 'GOOG', { clearFirst: true, predicate: (r) => r.url().includes('/tickers/search') && r.url().includes('q=GOOG') && r.status() === 200 });`
    3. **The default predicate MUST NOT be used at either site.** The default is URL-only and would
       drop the `status() === 500` / `status() === 200` checks, **widening** the match — which FR-002
       forbids and contract G3 explicitly refuses to protect against
       (`contracts/helper-api.md:46-47`). A reviewer confirms by seeing an explicit `predicate:` on
       both calls.
    4. **Query scoping is mandatory here, and this is the highest-risk predicate change in the
       feature.** This test's mock returns 500 on the first request and 200 on every later one, and
       `providers.tsx:48` sets `retry: 1`, so the failed AAPL search fires a retry roughly 1s later.
       A promise-first listener for `/tickers/search` + `status === 200` registered before
       `fill('GOOG')` could match the **AAPL retry** instead of the GOOG response, and the test would
       then assert on a state GOOG has not reached — passing for the wrong reason (spec Edge Cases,
       research D4). The `q=` parameter name is verified at `frontend/src/lib/api/tickers.ts:28-31`;
       input is upper-cased before it reaches the query (`ticker-input.tsx` `handleChange`), so the
       literal matches the fill value with no case handling (spec C2).
    5. The predicate change is **declared in the commit message** as a deliberate tightening under
       FR-002, naming both sites and the retry it defends against.
    6. The test at `:109` ('single failure does not trigger banner') contains exactly two converted
       waits, so it does **not** get `test.setTimeout(60000)` (FR-006 applies above two).
    7. Green under `--project="Desktop Chrome"`, and green under `--repeat-each=20 --workers=8` in
       T023 — a mis-scoped predicate here shows up as a nondeterministic pass, not a clean failure,
       so contention is the check that matters.

- [ ] **T011** [US1] Convert the three AAPL/GOOG/MSFT waits to the default predicate, **declaring the narrowing**
  - **Files**: `frontend/tests/e2e/chaos-degradation.spec.ts` (depends on T010 — same file)
  - **Site identification** (pre-sweep `:178/:183/:188`, drifted by T010): the three occurrences of
    `await page.waitForResponse((r) => r.url().includes('/tickers/search'));` inside the test titled
    `'cross-endpoint success prevents banner despite other endpoint failures'`. That predicate text
    with **no** status clause appears only in that test; the two in T010's test carry
    `&& r.status() === 500` / `=== 200`. Match on the statement text plus the test title.
  - **Satisfies**: FR-001, FR-002, FR-005, FR-006, FR-012
  - **Acceptance criteria**:
    1. Interaction 1 → `await searchAndAwaitResponse(page, searchInput, 'AAPL');`
       Interaction 2 → `await searchAndAwaitResponse(page, searchInput, 'GOOG', { clearFirst: true });`
       Interaction 3 → `await searchAndAwaitResponse(page, searchInput, 'MSFT', { clearFirst: true });`
    2. **The narrowing is explicitly declared.** The original predicate is
       `(r) => r.url().includes('/tickers/search')`; the default is
       `(r) => r.url().includes('/api/v2/tickers/search')`. This **narrows** the match from any path
       containing `/tickers/search` to the versioned API path only. Narrowing is permitted by FR-002
       (it cannot weaken an assertion) but MUST be called out — the commit message names all three
       sites and the exact before/after predicate strings
       (`contracts/helper-api.md:48-50`, AR#2 D-06).
    3. No query scoping is added at these three, and the justification is **stronger** than an
       earlier draft claimed. That draft said "the 503s in this test come from the sentiment
       endpoint, which the narrowed search-scoped predicate cannot match". That is false: **there
       are no 503s in this test at all.** The route is
       `page.route('**/api/v2/sentiment**', … 503)` (pre-sweep `chaos-degradation.spec.ts:153`), but
       the app's sentiment URLs are `/api/v2/tickers/{ticker}/sentiment/history` and
       `/api/v2/configurations/{id}/sentiment`. Neither contains the literal segment
       `/api/v2/sentiment`, so the glob never matches and no 503 is ever produced. The test titled
       `'cross-endpoint success prevents banner despite other endpoint failures'` therefore passes
       **vacuously** today: nothing fails, so of course no banner appears.
       What actually justifies skipping query scoping is the search route alone: it `route.fulfill`s
       a **200** every time (pre-sweep `:162-171`), so `retry: 1` never fires and exactly one
       matching response exists per interaction. The conversion is correct as written.
       The dead route is **not** fixed here (FR-009 scope discipline, same class as the
       `dynamodb_throttle` dead branch). It is carded by T027.
    4. Green under `--project="Desktop Chrome"`.

- [ ] **T012** [US1] Raise the test budget for multi-wait tests (FR-006)
  - **Files**: `frontend/tests/e2e/chaos-degradation.spec.ts`, `frontend/tests/e2e/helpers/chaos-helpers.ts` (depends on T010, T011)
  - **Design note**: the raise for `triggerHealthBanner`'s three waits goes **inside the helper**,
    not into each caller. `chaos-helpers.ts` already imports from `@playwright/test`, so it imports
    `test` and calls `test.setTimeout(60000)` on entry to `triggerHealthBanner`. This covers all
    seven `triggerHealthBanner(page)` call sites at once, and keeps `chaos-cross-browser.spec.ts`
    and `chaos-error-boundary.spec.ts` byte-unchanged. Per-caller raises were rejected: they grow
    the diff from 5 files to 7 and leave the rule for a future caller to remember, which is the same
    failure mode that produced this bug class.
  - **Site identification**: by **function name** (`triggerHealthBanner` in
    `helpers/chaos-helpers.ts`) and by **test title** (`'cross-endpoint success prevents banner
    despite other endpoint failures'` in `chaos-degradation.spec.ts`). The pre-sweep `:148` locator
    has drifted by T010/T011.
  - **Acceptance criteria**:
    1. `triggerHealthBanner` raises the cap as its first statement, and `chaos-helpers.ts` imports
       `test` from `@playwright/test`. The call is
       **`test.setTimeout(Math.max(test.info().timeout, 60000));`**, not a bare
       `test.setTimeout(60000)`. A bare call is an unconditional override and would silently *lower*
       a caller's deliberate cap: `chaos-accessibility.spec.ts:29` sets `test.setTimeout(30_000)` at
       the describe level, and `chaos-accessibility.spec.ts` imports `triggerHealthBanner`. The
       helper may only ever raise.
    2. In `chaos-degradation.spec.ts`, `test.setTimeout(60000)` is the first statement of the test
       titled `'cross-endpoint success prevents banner despite other endpoint failures'`, which
       holds the three converted waits from T011 (cross-artifact finding CX-2: FR-006's rule catches
       this test but its own enumeration omitted it).
    3. `git diff --stat frontend/tests/e2e/chaos-cross-browser.spec.ts frontend/tests/e2e/chaos-error-boundary.spec.ts`
       is **empty**. Those two files are affected but not modified. This is the criterion that
       proves the helper-side design landed; a non-empty diff here means someone applied the
       rejected per-caller design.
    4. No test that already fits inside the 30s budget gets a raise. FR-006 applies only above two
       converted waits; verify by counting per test.
    5. `cd frontend && npx tsc --noEmit` passes. `helpers/chaos-helpers.ts` is imported by **six**
       spec files (`chaos-cross-browser`, `chaos-cached-data`, `chaos-error-boundary`,
       `chaos-degradation`, `chaos-accessibility`, `chaos-scenarios`), and two of them
       (`chaos-cached-data.spec.ts`, `chaos-accessibility.spec.ts`) appear in **no** verification
       command in this feature. A type check is the only thing that covers them.
  - **Satisfies**: FR-006

- [ ] **T013** [US1] Convert `triggerHealthBanner`'s 3 waits to promise-first, keeping status-only predicates
  - **Files**: `frontend/tests/e2e/helpers/chaos-helpers.ts` (depends on T005–T012)
  - **Site identification** (pre-sweep `:364/:367/:370`, drifted by T012's import and
    `test.setTimeout` insertion): the three occurrences of the exact statement
    `await page.waitForResponse((resp) => resp.status() === 503);` inside the function
    `triggerHealthBanner`. Match on the function name plus the statement text.
  - **Satisfies**: FR-001, FR-002 (accepted-risk exception), FR-005, FR-006, FR-012
  - **Acceptance criteria**:
    1. Each of the three becomes promise-first inline:
       `const f1 = page.waitForResponse((resp) => resp.status() === 503, { timeout: 15000 });`
       then the fill(s), then `await f1;`.
    2. The predicates stay **status-only**. They are NOT narrowed to `/tickers/search` — that is
       explicitly Out of Scope (spec Out of Scope, FR-005) and is the exact contradiction AR#1 F-04
       resolved.
    3. `triggerHealthBanner` does **not** call `searchAndAwaitResponse` (contract N3).
    4. `{ timeout: 15000 }` on all three (FR-006).
    5. **Sequenced last on purpose.** After this edit, re-run the full chaos suite — including the
       two unedited callers — before committing:
       `cd frontend && npx playwright test tests/e2e/chaos-degradation.spec.ts tests/e2e/chaos-scenarios.spec.ts tests/e2e/chaos-cross-browser.spec.ts tests/e2e/chaos-error-boundary.spec.ts --project="Desktop Chrome"`.
       All green, or the change is reverted and re-analysed rather than patched forward.
    6. The `dynamodb_throttle` dead branch (pre-sweep `chaos-helpers.ts:169-189`; identify it by the
       byte-identical `if`/`else` inside the `dynamodb_throttle` scenario, both returning 503) is
       **NOT** fixed here (FR-009). `git diff` shows no hunk touching that block. It is carded by
       T027 instead.
    7. `cd frontend && npx tsc --noEmit` passes. Same reason as T012 crit. 5: six spec files import
       this module and two of them are exercised by no verification command here.

- [ ] **T014** [US1] Soften the `triggerHealthBanner` docstring's determinism claim
  - **Files**: `frontend/tests/e2e/helpers/chaos-helpers.ts` (depends on T013 — same file)
  - **Satisfies**: FR-005 ("Consequence of the FR-002 exception")
  - **Site identification**: the JSDoc block immediately above
    `export async function triggerHealthBanner(page: Page): Promise<void>` in
    `helpers/chaos-helpers.ts` (pre-sweep `:334-344`, drifted by T012 and T013), and the inline
    comment inside that function beginning `// Wait for the 503 response after each search`
    (pre-sweep `:360-362`). Match by function name and comment text.
  - **Acceptance criteria**:
    1. The docstring currently reads *"Uses `page.waitForResponse()` after each search interaction
       (not `waitForTimeout`) to ensure the failure is recorded by the health monitor before
       proceeding. This makes the trigger deterministic rather than timing-dependent."* Both
       sentences are now false: "after each search interaction" describes the bug being removed, and
       the determinism claim never held under a status-only predicate.
    2. The replacement states what the predicate actually proves: **a** failing response was observed
       before proceeding, not that **this particular search's** failure was recorded. Any of the three
       searches, or a `retry: 1` retry, can satisfy it.
    3. The inline comment ("Wait for the 503 response after each search to confirm the failure was
       recorded") gets the same correction — it carries the identical false claim.
    4. The replacement text records the residual risk verbatim from FR-002's exception: a regression
       that made only one of three searches fail would still satisfy these waits.
    5. **This edit is carried by its own task on purpose**, so it cannot be lost as an incidental
       change inside T013 (FR-005 requires exactly this).
    6. No behavioural change in this task. `git diff` shows comment/docstring lines only.

### C.6 — Cross-cutting conversion guards

- [ ] **T015** [P] [US1] Audit FR-010: no wait introduced where the query is cache-served
  - **Files**: read-only across `frontend/tests/e2e/` (depends on T005–T014)
  - **Satisfies**: FR-010
  - **Acceptance criteria**:
    1. Enumerate every converted site and confirm none repeats a query already issued within the same
       test inside the 30s `staleTime` window (`ticker-input.tsx:38`).
    2. `ticker-search-gaps.spec.ts:242-247` is byte-unchanged and still carries its comment
       explaining why it deliberately asserts on the UI instead of waiting.
    3. No `searchAndAwaitResponse` call and no new `waitForResponse` exists anywhere a wait did not
       exist before the sweep. Diff the scan's site list against the T002 baseline: the post-sweep
       site set is a subset of the baseline set plus the one helper-internal wait.
    4. Any site found to be cache-served is reverted to a UI assertion following the
       `:242-247` precedent, and the finding recorded.

- [ ] **T016** [P] [US1] Audit FR-004: the 6 already-correct sites are byte-unchanged
  - **Files**: read-only (depends on T005–T014)
  - **Satisfies**: FR-004, spec C5
  - **Acceptance criteria**:
    1. `git diff main...HEAD -- frontend/tests/e2e/error-visibility-search.spec.ts` is **empty**.
    2. `git diff` hunks for `chaos-degradation.spec.ts` touch no line in `:231-237`;
       `chaos-scenarios.spec.ts` touches no line at `:251`; `ticker-search-gaps.spec.ts` touches no
       line at `:231` or `:237`. (Line numbers shift with edits — verify by content, matching the
       exact original statements.)
    3. None of the six adopts the helper (spec C5: touching them adds diff surface with no defect
       fixed, and blurs the CI signal this feature depends on).
    4. The scan still classifies all six as `PROMISE-FIRST`.

- [ ] **T017** [P] [US1] Audit FR-012: every converted wait is awaited on the success path
  - **Files**: read-only (depends on T005–T014)
  - **Satisfies**: FR-012
  - **Acceptance criteria**:
    1. Every inline promise-first conversion (T007, T008, T013 — 9 sites) has a matching `await`
       of the stored promise on the success path. No promise is created and left unawaited.
    2. `try/finally` is **NOT** added at the inline sites, and that is deliberate, not an omission.
       An unhandled rejection can only occur when an intervening action throws, and an intervening
       action that throws fails the test anyway, so the rejection rides an already-failing test
       (FR-012, AR#2 N-05). Confirm no reviewer added one.
    3. The helper's internal await (contract G2) covers all 18 helper-routed sites.
    4. Total: 18 helper-routed + 9 inline = 27, matching FR-001.

---

## Phase D — Verification (SC-001 … SC-004)

**Ordering**: scan first (cheapest, catches a miscount before burning suite time), then smoke, then
fault injection, then contention. Injection precedes contention because it is the falsifiable step —
if it fails to reproduce at a sound target, the diagnosis is wrong and contention results would be
meaningless.

- [ ] **T018** [US1] Post-sweep scan reports RACY 0 (SC-001)
  - **Files**: none modified (depends on Phase C)
  - **Satisfies**: SC-001, and verifies FR-001, FR-003, FR-011
  - **How this gate is checked**: by **per-file counts** and **enclosing test or function names**.
    Every expectation below is deliberately free of line numbers. Phase C is net line-additive, so
    pinning post-sweep scan output to pre-sweep lines (`:102/105/108`, `:219/222/225`,
    `:364/367/370`, `:138`) would report a failure that is not there. An implementer who checks
    lines will conclude the sweep broke. Check counts.
  - **Acceptance criteria**:
    1. `source .venv/bin/activate && python scripts/scan-waitforresponse-race.py` reports exactly
       `RACY 0 / PROMISE-FIRST 16 / OTHER 1`, total **17**.
    2. Exit code is **0** (T002 recorded exit 1 — both branches of FR-011's exit contract are now
       exercised).
    3. `PROMISE-FIRST` distributes **per file** exactly as follows, and each row is checked against
       the scan's own per-file output:

       | File | PF count | What they are |
       |---|---|---|
       | `chaos-scenarios.spec.ts` | 7 | 3 status-503 conversions in `'database throttle — health banner appears, cached data visible'` + 3 `requestfailed` conversions in `'API timeout — errors communicated, no blank screens'` + 1 pre-existing (FR-004 protected) |
       | `helpers/chaos-helpers.ts` | 3 | the 3 status-503 conversions inside `triggerHealthBanner` |
       | `error-visibility-search.spec.ts` | 2 | both pre-existing, FR-004 protected, file byte-unchanged |
       | `ticker-search-gaps.spec.ts` | 2 | both pre-existing, FR-004 protected |
       | `chaos-degradation.spec.ts` | 1 | pre-existing, the merged #981 conversion, FR-004 protected |
       | `helpers/search-helpers.ts` | 1 | the helper's own internal wait |
       | `chart-edge-cases.spec.ts` | 0 | all 4 sites are now helper calls, so no inline wait remains |
       | **Total** | **16** | 6 pre-existing + 6 status-only + 3 `requestfailed` + 1 helper-internal |

    4. The single `OTHER` is in `chaos-scenarios.spec.ts`, inside the test titled
       `'cold start — loading skeletons appear during delay'`. That is the `page.reload()` site held
       back by FR-003. Its count for that file is **1**; no other file reports an `OTHER`. It appears
       under the T001 crit. 10 "requires human triage" banner, which is expected and is not a
       failure.
    5. `RACY` is **0 in every file**, not merely 0 in total.
    6. `grep -rn "searchAndAwaitResponse(" frontend/tests/e2e/ --include="*.spec.ts" | wc -l`
       returns exactly **18**. The `--include="*.spec.ts"` filter is load-bearing: without it the
       helper's own `export async function searchAndAwaitResponse(` definition line is counted and
       the answer is 19. Flagged as CX-4.
    7. The 18 distribute as `chart-edge-cases.spec.ts` 4 + `ticker-search-gaps.spec.ts` 9 +
       `chaos-degradation.spec.ts` 5 = 18, across **3** spec files, not 4 (see CX-1). Check with
       `grep -rc` per file, not by eye.

- [ ] **T019** [US1] Smoke run (SC-002 — precondition only, non-evidential)
  - **Files**: none modified (depends on T018)
  - **Satisfies**: SC-002
  - **Acceptance criteria**:
    1. Runs the six-file command from `quickstart.md` section 2, including
       `chaos-cross-browser.spec.ts` and `chaos-error-boundary.spec.ts` (in the helper's blast radius
       via `triggerHealthBanner`).
    2. All tests pass under `--project="Desktop Chrome"`.
    3. The result is recorded as **"catches gross breakage from the conversions"** and explicitly
       **NOT** as evidence the race is fixed. Pre-fix code passed this too (10/10 locally). Citing it
       as evidence fails this task (SC-002 is labelled non-evidential for exactly this reason).

- [ ] **T020** [US1] Fault injection against **pre-fix** code — MUST FAIL (SC-003a, the gate)
  - **Files**: temporary uncommitted patch to `frontend/tests/e2e/ticker-search-gaps.spec.ts` and `frontend/tests/e2e/chart-edge-cases.spec.ts` (depends on T019)
  - **Satisfies**: SC-003(a)
  - **Restoring pre-fix content**: **do not `git stash`.** Every Phase C task commits, so the tree
    is clean and `git stash` has nothing to stash. Check the pre-fix files out of the merge base
    instead:
    ```bash
    BASE=$(git merge-base main HEAD)     # 8c27271 at time of writing
    git checkout "$BASE" -- frontend/tests/e2e/ticker-search-gaps.spec.ts \
                            frontend/tests/e2e/chart-edge-cases.spec.ts
    # ... inject, run, record ...
    git checkout HEAD -- frontend/tests/e2e/ticker-search-gaps.spec.ts \
                         frontend/tests/e2e/chart-edge-cases.spec.ts
    ```
    Both files are self-contained at the base commit (neither imported `search-helpers.ts` before
    this feature), so checking them out alone leaves a compiling tree.
  - **Acceptance criteria**:
    1. The two target files hold their merge-base content, restored by the `git checkout "$BASE" --`
       command above. `git diff --stat` shows changes confined to those two files.
    2. Inject `await new Promise((r) => setTimeout(r, 250));` **between** the triggering action and
       the listener registration at:
       - `ticker-search-gaps.spec.ts:22` → site `:38` (its mock returns a single 200 with empty
         results; not an error, so `retry: 1` does not fire a second response), and
       - `chart-edge-cases.spec.ts` → site `:72` (its `beforeEach` mock at `:32-40` `route.fulfill`s
         a single 200 for ticker search).
    3. `cd frontend && npx playwright test tests/e2e/ticker-search-gaps.spec.ts tests/e2e/chart-edge-cases.spec.ts --project="Desktop Chrome"` → **both injected tests FAIL**.
    4. **These are the ONLY two valid injection targets.**
       - `chaos-degradation.spec.ts:196` is **not** one: PR #981 (`8c27271`) already converted its
         racy site; it is promise-first at `:231-237` and protected by FR-004, so restoring the
         merge-base content cannot bring the old shape back, because the merge base already contains
         that conversion (AR#2 D-02).
       - The 6 status-only 503 sites and the 3 `requestfailed` sites are **unsound** targets:
         `retry: 1` (`providers.tsx:48`) plus the blanket `page.route('**/api/**', …503)` keep
         supplying a matching response, so the listener resolves however wide the gap. Their
         non-reproduction is EXPECTED and falsifies nothing (AR#2 N-02).
    5. **STOP CONDITION.** If either injected pre-fix test **passes**, the diagnosis is falsified.
       Halt the feature, do not proceed to T021, and re-analyse. Recorded honestly in T022.

- [ ] **T021** [US1] Same injection against **converted** code — MUST PASS (SC-003a)
  - **Files**: temporary uncommitted patch to `frontend/tests/e2e/helpers/search-helpers.ts`
    (depends on T020 passing its stop condition)
  - **Satisfies**: SC-003(a)
  - **The seam, named exactly.** Post-conversion, both injection targets are single
    `await searchAndAwaitResponse(page, searchInput, ...);` calls. There is no "between the action
    and the listener" position left in the spec file. The only position after the action visible
    there is after the helper has already awaited its response. A delay placed there proves nothing
    and passes trivially, which would let this half of the primary gate be marked green by an
    implementation that tests nothing. So the patch goes **inside the helper**:
    ```ts
    // frontend/tests/e2e/helpers/search-helpers.ts (TEMPORARY, never committed)
    await searchInput.fill(query);
    await new Promise((r) => setTimeout(r, 250));   // <-- injected here, and only here
    await responsePromise;
    ```
    That is the same 250ms gap T020 injected, moved to the one place it can still be observed: after
    the triggering action, before the await. It passes only because the listener was registered
    before the fill.
  - **Acceptance criteria**:
    1. The Phase C conversions are back in the tree:
       `git checkout HEAD -- frontend/tests/e2e/ticker-search-gaps.spec.ts frontend/tests/e2e/chart-edge-cases.spec.ts`,
       and `git status` shows those two files clean before the patch goes in.
    2. `await new Promise((r) => setTimeout(r, 250));` is inserted into
       `frontend/tests/e2e/helpers/search-helpers.ts`, on its own line **between** the
       `await searchInput.fill(query);` line and the `await responsePromise;` line.
    3. **The patched file MUST be `search-helpers.ts`.** A patch applied in a `.spec.ts` file does
       **NOT** satisfy this task, regardless of what the run reports. Verify with
       `git diff --name-only` before running: it must list `search-helpers.ts` and nothing else.
    4. `cd frontend && npx playwright test tests/e2e/ticker-search-gaps.spec.ts tests/e2e/chart-edge-cases.spec.ts --project="Desktop Chrome"` → **both tests PASS**.
    5. **Negative control, and it is a hard gate.** The same helper-side delay must *discriminate*
       between the two shapes. Run it twice, changing only the helper's statement order:
       - **PRE-FIX shape**: inside the helper, move `const responsePromise = page.waitForResponse(…)`
         to *below* `await searchInput.fill(query);`, keeping the 250ms delay between them. The two
         target tests MUST **FAIL**.
       - **POST-FIX shape**: restore the promise-first order, keep the same 250ms delay. The two
         target tests MUST **PASS**.

       **If both runs pass, the injection is landing in the wrong place and the result is void.**
       T021 is not satisfied, no pass is recorded, and the injection is re-sited and re-run. A delay
       that cannot make the pre-fix shape fail is not measuring ordering.
    6. Together with T020 this demonstrates the conversion **removes** the race rather than reducing
       its probability — which a green contention run alone cannot show.
    7. The injection patch is reverted:
       `git checkout HEAD -- frontend/tests/e2e/helpers/search-helpers.ts`. `git status` is clean of
       it before any commit.

- [ ] **T022** [US1] Record the fault-injection result honestly, including the stop condition
  - **Files**: `specs/001-waitforresponse-race-sweep/tasks.md` (`## Execution Log` section below) (depends on T020, T021)
  - **Satisfies**: SC-003(a) — the falsifiability half
  - **Acceptance criteria**:
    1. The log records, for each of the two sound targets: the injected delay, the pre-fix result,
       the post-fix result, and the exact command.
    2. **If pre-fix code did NOT fail under injection at either sound target, that is written down as
       a falsification of the diagnosis, the sweep is halted, and no "fixed" claim is made
       anywhere** — not in the commit message, not on the board, not in the PR description. Reporting
       green after a failed injection fails this task outright.
    3. The log states plainly that the 6 status-only and 3 `requestfailed` sites were **not** validated
       by injection and are covered by contention (T023) only, so a future reader does not mistake
       partial coverage for full coverage.
    4. No overstatement. The spec exists to correct an overstated board claim; an overstated result
       here reproduces the exact failure mode (AR#1 self-defeat check).
    5. `git status` confirms the injection patch was never committed, specifically that
       `frontend/tests/e2e/helpers/search-helpers.ts` carries no injected delay and no flipped
       statement order.

- [ ] **T023** [US1] Contention run across every affected file (SC-003b)
  - **Files**: none modified (depends on T021)
  - **Satisfies**: SC-003(b)
  - **Acceptance criteria**:
    1. `cd frontend && npx playwright test tests/e2e/chaos-degradation.spec.ts tests/e2e/chaos-scenarios.spec.ts tests/e2e/chart-edge-cases.spec.ts tests/e2e/ticker-search-gaps.spec.ts tests/e2e/chaos-cross-browser.spec.ts tests/e2e/chaos-error-boundary.spec.ts --project="Desktop Chrome" --repeat-each=20 --workers=8`
    2. **20/20 for every affected test.** A single flake fails this task; it is not retried away.
    3. The file list **MUST** include `chaos-cross-browser.spec.ts` and
       `chaos-error-boundary.spec.ts` — they call `triggerHealthBanner` (`:35`, `:63`) and are in the
       helper's blast radius (AR#2 N-03) — and `chaos-scenarios.spec.ts`.
    4. This is the **only** verification the 6 status-only and 3 `requestfailed` sites receive, since
       injection is unsound on them. Record that scoping alongside the result.
    5. A mis-scoped predicate from T010 surfaces here as a nondeterministic pass rather than a clean
       failure — inspect the T010 sites specifically if any repeat is red.
    6. **Record total wall-clock for the six-file run and compare it against the CI hard wall.**
       `.github/workflows/pr-checks.yml` wraps the Playwright step in `timeout 900` (15 minutes) with
       `timeout-minutes: 20` on the job, and this feature raises roughly ten tests from a 30s cap to
       a 60s cap. Raised caps do not cost time on green runs, but they double the cost of every red
       one, and the `timeout 900` kill is a silent, uninformative failure mode. Log the single-pass
       wall-clock (not the `--repeat-each=20` total) alongside the contention result, and flag it if
       it is within 30% of 900s. This is a recorded observation, not a pass/fail bar. The sweep is
       not gated on it, but a future reader needs the number.

- [ ] **T024** [P] [US1] Test-count parity (SC-004)
  - **Files**: none modified (depends on T023)
  - **Satisfies**: SC-004
  - **Acceptance criteria**:
    1. Post-sweep passed / failed / skipped tallies compared against the T003 baseline.
    2. Identical **except** that failures become passes. Any drop in `passed`, any new `skipped`, or
       any deleted test fails this task.
    3. `git diff` shows no new `test.skip`, `test.fixme`, `test.only`, or deleted `test(` block
       across `frontend/tests/e2e/`.
    4. No assertion was weakened to reach green — cross-checked against T010/T011's declared
       predicate changes, which are the only intentional predicate edits in the feature.

- [ ] **T025** [P] [US1] Scope-confinement audit (FR-007)
  - **Files**: none modified (depends on Phase C, Phase E)
  - **Satisfies**: FR-007
  - **Acceptance criteria**:
    1. `git diff --name-only main...HEAD` lists **only**: paths under `frontend/tests/e2e/`,
       `scripts/scan-waitforresponse-race.py`, `CLEANUP-BOARD.html`, and
       `specs/001-waitforresponse-race-sweep/`.
    2. **Zero** paths under `frontend/src/` — no product-code change to search, caching, or the
       health banner.
    3. No workflow file is touched. `.github/workflows/pr-checks.yml` is unchanged, so the Playwright
       E2E job stays non-required (FR-009, Out of Scope).
    4. No `package.json` / `package-lock.json` change — no new dependency (plan Technical Context).
    5. Every commit on the branch is GPG-signed: `git log --show-signature main...HEAD` shows a good
       signature on each, and no commit was made with `--no-verify`.

---

## Phase E — Board (FR-008, FR-009, SC-005, US3)

**Method (all three tasks)**: JSON surgery, not regex. `raw_decode` the array after `const CARDS = `,
mutate card-by-card in Python, re-dump with `json.dumps(..., ensure_ascii=False)` at default
separators, splice back, then re-parse and re-count. The file is in git; a corrupt write is
recoverable, a silently mangled card is not.

- [ ] **T026** [P] [US3] Correct the two existing cards (FR-008)
  - **Files**: `CLEANUP-BOARD.html`
  - **Satisfies**: FR-008, US3 acceptance scenarios 1 and 2
  - **Acceptance criteria**:
    1. **Card "Playwright E2E red on every PR: chaos-degradation banner-reappear test times out"**:
       - The claim *"fails on main and every PR (observed 2026-07-30 on the #977/#978/#979 runs)"* is
         **removed**. It is false — Playwright was **green** on those main runs. The job is
         intermittently red on PRs, not persistently red on main.
       - Replaced with the verified rate and its sampling method: **5 of 25 runs (~20%)** attributable
         to this race class, sampled from the 30 most recent `PR Checks` runs as of 2026-07-30, of
         which 25 executed the Playwright job; 6 were red and 5 are attributable (the sixth,
         `30460832567`, is the unrelated user-menu flake #950). The method MUST record that
         `pr-checks.yml` runs with `--retries=0`, without which the rate is not re-derivable
         (`nightly-e2e` does not pass it).
       - The run/commit distinction is stated: `30512621168` is a `push` run whose sibling
         `pull_request` run on the same commit (`30512623219`) passed, so ~20% describes **runs**,
         not commits.
       - Re-scoped from one test to **this sweep**: 27 sites across 5 files, not
         `chaos-degradation.spec.ts:196` alone. That test's cited site `:229` was already fixed by
         PR #981 (`8c27271`).
       - `next_action` rewritten to point at this feature branch.
    2. **Card "MASTER: CI/CD hygiene"**: its `evidence` children list currently ends with *"Playwright
       pr-checks job red on every PR (chaos-degradation flake, non-required so silent)"*. That child
       entry is rewritten to the same corrected framing (~20% attributable across sampled PR runs,
       race-class sweep, main was green). The rest of the children list is left untouched.
    3. **Card count is unchanged by this task** — both are in-place edits.
    4. Rationale recorded in the commit message: the board is the campaign's ground truth, and a card
       asserting "fails on main" when the cited main runs were green corrodes trust in every other
       card (US3).

- [ ] **T027** [US3] Add the two follow-up cards (FR-009)
  - **Files**: `CLEANUP-BOARD.html` (depends on T026 — same file)
  - **Satisfies**: FR-009
  - **Acceptance criteria**:
    1. **Card 1 — merge-required follow-up decision.** Records the owner's deferred decision on making
       the Playwright E2E job merge-required. Evidence: the job's ~20% attributable false-red rate is
       what blocks the decision; this sweep removes the blocker. Cites
       `.github/workflows/pr-checks.yml` and this feature branch. `next_action`: revisit after the
       sweep has been green across several PR runs. **This feature MUST NOT change the job's required
       status** — the card records the decision, it does not make it.
    2. **Card 2, dead chaos-mock traps (ONE card covering BOTH instances).** They are the same
       class: a mock that does not do what its surrounding code claims, with tests passing because
       of it rather than despite it. Keeping them on one card holds the count at 118 → 120.
       - **Instance A, `dynamodb_throttle` dead branch.** `chaos-helpers.ts:169-189` has
         byte-identical `if`/`else` branches, both returning 503, despite the `else` comment claiming
         *"Read operations may still succeed (cached)"* (verified in tree). Three of the 27 swept
         sites (`chaos-scenarios.spec.ts:102/105/108`) resolve **only** because that dead branch also
         returns 503. If the comment-to-code mismatch is ever corrected so reads succeed, those three
         waits break.
       - **Instance B, dead sentiment route.** `chaos-degradation.spec.ts:153` registers
         `page.route('**/api/v2/sentiment**', … 503)`, but the app's sentiment URLs are
         `/api/v2/tickers/{ticker}/sentiment/history` and `/api/v2/configurations/{id}/sentiment`.
         Neither contains the literal segment `/api/v2/sentiment`, so the glob **never matches** and
         no 503 is ever produced. The test titled `'cross-endpoint success prevents banner despite
         other endpoint failures'` therefore passes vacuously: it asserts no banner appears in a
         scenario where nothing fails. Fixing the glob would make the test assert what its title
         claims, and may well turn it red.
       - `next_action`: fix both mocks in one change and re-verify the tests that depend on them:
         the three `chaos-scenarios` waits for A, the cross-endpoint test for B.
       - **This feature MUST NOT fix either one.** Both are recorded, not repaired (FR-009).
    3. Both cards use the existing card schema keys: `title`, `lane`, `severity`, `evidence`,
       `citation`, `next_action`, `source` (verified against the current array).
    4. Card count goes **118 → 120**.

- [ ] **T028** [US3] Validate the board (SC-005)
  - **Files**: none modified (depends on T026, T027)
  - **Satisfies**: SC-005
  - **Acceptance criteria**:
    1. The `CARDS` array literal still parses:
       ```bash
       python - <<'PY'
       import json
       s = open('CLEANUP-BOARD.html').read()
       i = s.index('const CARDS = ') + len('const CARDS = ')
       cards, _ = json.JSONDecoder().raw_decode(s[i:])
       print('cards:', len(cards))
       PY
       ```
       prints `cards: 120`.
    2. Baseline confirmed: the pre-edit count is **118** (verified in tree at branch start).
    3. The board opens in a browser and renders with **no console error** — a parse that succeeds in
       Python but breaks the page's own JS still fails this task.
    4. Spot-check the two edited cards render with their corrected text and the two new cards appear
       in their lanes.
    5. `git diff CLEANUP-BOARD.html` touches only the `CARDS` array — no incidental reformatting of
       the surrounding HTML, CSS, or unrelated cards.

---

## Dependencies & Execution Order

```
Phase A (T001 → T002; T003 [P])
        │
        ▼
Phase B (T004)
        │
        ▼
Phase C, order MANDATORY:
  T005 chart-edge-cases
   └─► T006 ticker-search-gaps
        └─► T007 → T008 → T009  chaos-scenarios
             └─► T010 → T011 → T012  chaos-degradation (+ helper-side setTimeout)
                  └─► T013 → T014  chaos-helpers  ◄── LAST (triggerHealthBanner precondition)
                       └─► T015 [P] T016 [P] T017 [P]  guards
        │
        ▼
Phase D (T018 → T019 → T020 → T021 → T022 → T023 → T024 [P] / T025 [P])
        │
Phase E (T026 → T027 → T028)  ── independent of Phase D, may run alongside
```

### Why the Phase C order is not negotiable

`chaos-helpers.ts` (T013/T014) is last because `triggerHealthBanner` is a precondition of the whole
chaos suite. Its blast radius is every chaos test in six importing files plus the two unedited
callers, so it must be validated against **already-converted** callers. Converting it first would
mean a chaos-suite failure could originate in the helper or in an unconverted caller, with no way to
tell which. Everything above it is ordered smallest blast radius first: `chart-edge-cases` (4 sites,
self-contained mocks) → `ticker-search-gaps` (9 sites, self-contained) → `chaos-scenarios`
(6 sites, shared chaos scenarios) → `chaos-degradation` (5 sites, the highest-risk predicates).

### Parallel Opportunities

- **T003** with T001/T002 — no shared files.
- **T015 / T016 / T017** — read-only audits over different concerns, after Phase C.
- **T024 / T025** — read-only audits, after T023.
- **Phase E (T026–T028)** with all of Phase D — disjoint files (`CLEANUP-BOARD.html` vs test sources).
- **T005 and T006** touch disjoint files and have no code dependency, but the stated order is
  preserved deliberately (blast-radius sequencing) and they are **not** marked `[P]`.

---

# Coverage Analysis

Produced after task generation, non-destructively. Every claim below was checked against the working
tree at `frontend/tests/e2e/` and `CLEANUP-BOARD.html`, not against the artifacts alone.

## 1. Requirements coverage

### Functional requirements

| Req | Summary | Tasks | Status |
|---|---|---|---|
| FR-001 | All 27 racy sites converted | T005, T006, T007, T008, T010, T011, T013 (impl); T017 (27 = 18+9 count); T018 (verify RACY 0) | COVERED |
| FR-002 | No weakening; tighten where the window widens; declare meaning changes | T005 (no widening, justified), T006 (no widening), T007 (exception, risk restated), T008 (exception), T010 (**tightening**, declared), T011 (**narrowing**, declared), T013 (exception) | COVERED |
| FR-003 | `chaos-scenarios.spec.ts:138` left unconverted with recorded reason | T007 crit. 5 (byte-unchanged + reason recorded); T018 crit. 4 (scan reports `OTHER`) | COVERED |
| FR-004 | 6 already-correct sites unmodified | T006 crit. 4, T007 crit. 6, T016 (dedicated audit) | COVERED |
| FR-005 | Predicate-parameterised helper; `triggerHealthBanner` stays status-only; docstring corrected | T004 (helper + G3), T013 (status-only retained), T014 (**docstring**, its own task by requirement) | COVERED |
| FR-006 | 15000ms per call + `test.setTimeout(60000)` above two waits | T004 crit. 5 (default), T005–T008/T010/T011/T013 (explicit 15000), T009 (chaos-scenarios), T012 (`chaos-degradation`'s cross-endpoint test + the helper-side `Math.max` raise covering all 7 `triggerHealthBanner` callers, leaving the 2 outside callers byte-unchanged) | COVERED |
| FR-007 | No product code; confinement + named exceptions | T025 (dedicated audit) | COVERED |
| FR-008 | Two existing board cards corrected | T026 | COVERED |
| FR-009 | Two follow-up cards added; job stays non-required; dead branch not fixed | T027 (both cards), T013 crit. 6 (dead branch untouched), T025 crit. 3 (no workflow edit) | COVERED |
| FR-010 | Cache-served sites identified and left alone | T006 crit. 3 (`:242-247` hold-out), T015 (dedicated audit) | COVERED |
| FR-011 | Scan committed, rule documented in-script, both APIs, non-zero exit on RACY | T001 (all four obligations as separate criteria); T002 + T018 exercise both exit branches | COVERED |
| FR-012 | Success-path await; helper's internal guarantee; no `try/finally` requirement at the inline sites | T004 crit. 3 (G2 as a checkable code shape: `try`/`finally` or `.catch` at creation), T017 (dedicated audit incl. the deliberate absence of `try/finally` inline) | COVERED |

### Success criteria

| Criterion | Summary | Verification tasks | Status |
|---|---|---|---|
| SC-001 | Scan reports RACY 0 / PF 16 / OTHER 1, total 17; exactly 18 helper call sites | **T002** (before: 27/6/1, total 34), **T018** (after, both halves) | COVERED |
| SC-002 | Suite passes locally — precondition, non-evidential | **T019** (incl. an explicit criterion forbidding its citation as evidence) | COVERED |
| SC-003(a) | Fault injection at the two sound targets; pre-fix FAILS, post-fix PASSES | **T020** (pre-fix + stop condition), **T021** (post-fix), **T022** (honest record) | COVERED |
| SC-003(b) | Contention 20/20 across all affected files | **T023** (file list includes `chaos-cross-browser`, `chaos-error-boundary`, `chaos-scenarios`) | COVERED |
| SC-004 | Test count unchanged; nothing skipped, deleted, or weakened | **T003** (baseline), **T024** (comparison) | COVERED |
| SC-005 | `CARDS` parses, board renders, 118 → 120 | **T028** | COVERED |

**Gaps found: 0.** Every FR-001…FR-012 has at least one implementing task and every SC-001…SC-005 has
at least one dedicated verification task. Four requirements that are easy to lose as incidental edits
were given **their own tasks** rather than being folded into a neighbour, because a criterion buried
in another task's acceptance list is a criterion that gets skipped: T014 (docstring, required by
FR-005 to be carried explicitly), T022 (honest injection record incl. the stop condition), T015
(FR-010 cache-served audit), T017 (FR-012 await audit).

## 2. Reverse check — tasks that trace to nothing

Every task traces. No scope creep found.

| Task | Traces to |
|---|---|
| T001, T002 | FR-011, SC-001 |
| T003 | SC-004 (baseline half) |
| T004 | FR-005, FR-006, FR-012, US2 |
| T005–T008, T010, T011, T013 | FR-001, FR-002, FR-005, FR-006, FR-012 |
| T009, T012 | FR-006 |
| T014 | FR-005 ("Consequence of the FR-002 exception") |
| T015 | FR-010 |
| T016 | FR-004, spec C5 |
| T017 | FR-012 |
| T018–T024 | SC-001…SC-004 |
| T025 | FR-007, FR-009 (job stays non-required) |
| T026 | FR-008, US3 |
| T027 | FR-009 |
| T028 | SC-005 |

Two tasks warrant a note because they sit closest to the scope-creep line:

- **T012** touches exactly two files: `frontend/tests/e2e/chaos-degradation.spec.ts` and
  `frontend/tests/e2e/helpers/chaos-helpers.ts`. It does **not** edit
  `chaos-cross-browser.spec.ts` or `chaos-error-boundary.spec.ts`. The raise for
  `triggerHealthBanner`'s three waits lives inside the helper, so all seven callers inherit it and
  those two files stay byte-unchanged. T012 crit. 3 requires their diff to be empty. It traces to
  FR-006's normative rule, not to creep. See CX-3.
- **T022** produces a written record rather than code. It traces to SC-003(a), whose entire value is
  the falsifiable stop condition — a gate with no recorded outcome is not a gate.

## 3. Cross-artifact consistency check

### Numbers that agree (verified against the tree, not just the documents)

| Claim | Artifacts asserting it | Tree verification | Result |
|---|---|---|---|
| 27 racy sites | spec.md:83, plan.md:8/31, research.md:51, data-model.md:36 | 4 (`chart-edge-cases`) + 9 (`ticker-search-gaps`) + 5 (`chaos-degradation`) + 3 (`chaos-helpers`) + 3 + 3 (`chaos-scenarios`) = **27** | AGREE |
| 34 total inline sites | spec.md:64-65, data-model.md:38, quickstart.md:12 | 41 grep hits − 7 comment lines = **34** | AGREE |
| 18 helper-routed + 9 inline | spec.md:113, plan.md:8/106-109, research.md:48, contracts N3 | 4+9+5 = **18**; 3+3+3 = **9** | AGREE |
| 6 already-correct, protected | spec.md:85-87 | `chaos-degradation:231`, `chaos-scenarios:251`, `error-visibility-search:142`/`:157`, `ticker-search-gaps:231`/`:237` = **6** | AGREE |
| 1 triaged `OTHER` | spec.md:89, data-model.md:37 | `chaos-scenarios.spec.ts:138`, `page.reload()` then `expect(...).toBeVisible({timeout:2000})` then the wait — confirmed intervening assertion | AGREE |
| Baseline 34 → target 17 | data-model.md:33-38, quickstart.md:12-13, SC-001 | 16 PF (6+6+3+1) + 1 OTHER = **17**; arithmetic closes | AGREE |
| Board 118 → 120 | spec.md SC-005, plan.md:156, quickstart.md:122 | `raw_decode` on the live file returns **118** cards | AGREE |
| 5 files converted | plan.md:31 | `chart-edge-cases`, `ticker-search-gaps`, `chaos-scenarios`, `chaos-degradation`, `chaos-helpers` = **5** | AGREE |
| 24 `route.fulfill` + 3 `route.abort` | spec.md:20-24, research.md:25-27 | `dynamodb_throttle` and `triggerHealthBanner` both `route.fulfill`; `api_timeout` aborts → 24 + 3 = **27** | AGREE |
| No top-level test timeout | spec.md:243, plan.md:28, research.md:90 | `frontend/playwright.config.ts` — the only `timeout` keys are at `:67`/`:76`, both under `webServer` | AGREE |
| Both `triggerHealthBanner` outside callers | plan.md:92-93, quickstart.md:38 | `chaos-cross-browser.spec.ts:35`, `chaos-error-boundary.spec.ts:63` | AGREE |
| `dynamodb_throttle` branches byte-identical | spec.md:361-364, FR-009 | `chaos-helpers.ts:169-189` — both branches fulfil 503 with the same body | AGREE |

### Disagreements found — 4 (CX-1 and CX-3 now CLOSED in the artifacts, not just in tasks)

- **CX-1 (MEDIUM), `contracts/helper-api.md:4`. CLOSED, no action left.** An earlier draft of the
  contract stated *"Consumers: the 18 URL-scoped ticker-search wait sites across **4 spec files**."*
  **The contract has already been corrected** and now reads "across 3 spec files". Nothing further is
  required of any task. The reasoning is preserved below because the arithmetic is worth keeping:
  there are **3** spec files, not 4:
  `chart-edge-cases.spec.ts` (4) + `ticker-search-gaps.spec.ts` (9) + `chaos-degradation.spec.ts` (5)
  = 18. The fourth file a reader would reach for is `chaos-scenarios.spec.ts`, whose 6 sites are
  explicitly **inline** and explicitly **not** helper consumers by the same contract's own N3
  (`contracts/helper-api.md:72-76`). The site count (18) was correct everywhere; only the file count
  was wrong. **Closed twice over**: the contract line now reads "3 spec files", and T018 crit. 7
  independently states "across **3** spec files, not 4".

- **CX-2 (MEDIUM) — `spec.md:248-250` and `research.md:94-96`.** FR-006's normative rule is "any test
  containing more than two converted waits MUST get an explicit `test.setTimeout(60000)`". Its
  illustrative list then names only *"tests that call `triggerHealthBanner`"* and *"the three-search
  sequences (`chaos-scenarios.spec.ts:102/105/108` and `:219/222/225`)"*. That list **omits
  `chaos-degradation.spec.ts:148`** ('cross-endpoint success prevents banner despite other endpoint
  failures'), which is itself a three-search sequence containing three converted waits at
  `:178/:183/:188` (verified in tree). The rule captures it; the enumeration does not. A reader
  implementing from the list alone would leave that test on the default 30s cap with three 15s
  waits — the exact opaque-timeout outcome FR-006 exists to prevent. **Closed in tasks**: T012
  crit. 1 and 2 add it and record that the rule governs the list.

- **CX-3 (was HIGH), `plan.md:92-93` vs `spec.md:248-250`. RESOLVED BY DESIGN, no escalation
  needed.** The apparent conflict was: the plan's Source Code tree labels `chaos-cross-browser.spec.ts`
  and `chaos-error-boundary.spec.ts` **"UNCHANGED BUT AFFECTED"**, while FR-006 requires
  `test.setTimeout(60000)` on tests that call `triggerHealthBanner`, and both files do (`:35`, `:63`).
  Read as a per-caller obligation, both files would have to be edited and the labels would be wrong.

  **The per-caller reading is superseded.** The raise goes **inside `triggerHealthBanner`** itself:
  `chaos-helpers.ts` already imports from `@playwright/test`, so it imports `test` and calls
  `test.setTimeout(Math.max(test.info().timeout, 60000))` on entry. All seven `triggerHealthBanner`
  callers inherit the raised cap, and the two outside callers stay **byte-unchanged**. This is the
  design recorded in spec.md FR-006 ("Where `test.setTimeout(60000)` goes") and in T012's Design
  note; per-caller raises were explicitly rejected there because they grow the diff and leave the
  rule for a future caller to remember.

  Consequences:
  - **`plan.md:92-93` is correct as written.** The "UNCHANGED BUT AFFECTED" labels stand. No plan
    edit is required, and the earlier demand to restate the count as "7 modified files" is **wrong**
    and is withdrawn. The modified-file count remains **5 converted + the 2 new files**, with
    `chaos-cross-browser.spec.ts` and `chaos-error-boundary.spec.ts` outside it.
  - **No owner escalation is needed.** The earlier note calling for "the plan correction or an owner
    escalation before proceeding" referred to a T012 criterion that does not exist and to a plan
    change that must not be made. Withdrawn.
  - **T012 has FOUR original criteria plus a fifth added for the type check.** Its **crit. 3**
    requires `git diff --stat` on those two files to be **empty**, the opposite of editing them.
    That criterion is the check that the helper-side design actually landed. Any reference elsewhere
    to "T012 crit. 3-6" or "crit. 5 requiring an owner escalation" is stale and has been deleted.

  Downgraded from HIGH to CLOSED: the disagreement does not change the diff's shape, because the
  design that removes it was already applied to the task body.

- **CX-4 (LOW) — `quickstart.md:21` vs `spec.md:302` (SC-001).** SC-001 requires *"exactly 18
  `searchAndAwaitResponse(` call sites MUST exist under `frontend/tests/e2e/`"*. The quickstart's
  command scopes with `--include="*.spec.ts"`. That filter is **required**, not incidental: the
  helper's own definition line `export async function searchAndAwaitResponse(` lives in
  `helpers/search-helpers.ts` and matches the pattern, so an unfiltered grep over
  `frontend/tests/e2e/` returns **19**, not 18. (Import lines do not match — they carry no open
  paren.) The command is right and the SC wording is loose. Anyone verifying SC-001 literally from
  the spec text will read a failure that is not there. **Closed in tasks**: T018 crit. 6 states the
  filter is load-bearing and names the 19-vs-18 trap.

### Consistency notes that are not disagreements

- **FR-005 vs contract N3, mild tension.** FR-005 says the helper must accept a caller-supplied
  predicate *"so that non-search callers are not forced onto a search-scoped one"*, which reads as
  though non-search callers might use it. N3 says the helper *"is not used by the 9 non-search
  sites"*. Both are true in outcome — the parameterisation exists so the helper **could** serve them,
  and the design chooses inline conversion anyway. No task change needed; noted so a future reader
  does not read N3 as a contradiction of FR-005.
- **`.clear()` vs `fill('')` at `ticker-search-gaps.spec.ts:219`.** The contract's `clearFirst`
  performs `fill('')` (`contracts/helper-api.md:26`); the original at that site uses
  `searchInput.clear()`. **Not a behavioural change**: Playwright documents `locator.clear()` as
  equivalent to `fill('')`. An earlier draft treated this as a substitution needing a declaration and
  offered a keep-the-`.clear()` fallback; both were over-cautious and have been removed. T006 crit. 2
  now carries it as a one-line commit-message note with no fallback.
- **Stale test comment**, `ticker-search-gaps.spec.ts:37` — *"Wait for debounced search response"*.
  Same false-debounce premise as the product comment at `ticker-input.tsx:33` that misled an earlier
  spec draft (AR#1 F-09). The product comment is Out of Scope; this test comment disappears with the
  conversion. Covered by T006 crit. 6, which forbids replacing it with another debounce claim.

## 4. Summary

**Gaps found: 0** across FR-001…FR-012 and SC-001…SC-005 — no requirement needed a task added to
close a hole, because the four highest-drop-risk obligations were promoted to standalone tasks
during generation (T014, T015, T017, T022) rather than left as sub-criteria.

**Cross-artifact disagreements found: 4** (CX-1 through CX-4). All four are closed, and **none of
them now requires an artifact edit or an owner decision**:

1. **CX-1**: `contracts/helper-api.md:4` already reads "3 spec files". Corrected in the contract;
   T018 crit. 7 states the same number independently. Nothing outstanding.
2. **CX-3**: resolved by the helper-side `test.setTimeout` design, not by a plan edit.
   `plan.md:92-93`'s "UNCHANGED BUT AFFECTED" labels are **correct as written** and must not be
   changed. The modified-file count stays 5; no escalation is needed. See the rewritten CX-3 entry.
3. **CX-2**: `spec.md`/`research.md`'s FR-006 enumeration omits `chaos-degradation`'s cross-endpoint
   test. Safe to leave: T012 crit. 2 adds it and records that the rule, not the list, governs.
4. **CX-4**: SC-001's grep wording is loose. Safe to leave: T018 crit. 6 names the filter and the
   19-vs-18 trap.

---

## Execution Log

*(populated during implementation — T002 baseline, T003 tally, T022 injection record)*

| Task | Date | Result |
|---|---|---|
| T002 | | |
| T003 | | |
| T018 | | |
| T020 | | |
| T021 | | |
| T022 | | |
| T023 | | |
| T024 | | |
| T028 | | |

---

## Adversarial Review #3

An independent implementation-readiness review, run against the task list rather than against the
spec: the question was not "is the plan right" but "can someone execute this without guessing". Two
design decisions were verified against Playwright's own source and against the tree rather than
taken on trust. First, that `test.setTimeout()` called from a helper module resolves through
`currentTestInfo()` and therefore affects only the currently running test, which is what makes the
helper-side raise in T012 sound rather than a global side effect. Second, that both named
fault-injection targets produce exactly one matching response, which is what makes T020's stop
condition falsifiable instead of noisy. The review initially returned **BLOCKED**, on three grounds:
stale line anchors that Phase C's own edits would invalidate, a Coverage Analysis generated against
a superseded design decision, and a fault-injection task whose criteria could be satisfied by an
implementation that tested nothing.

### Findings

| ID | Sev | Finding | Resolution |
|---|---|---|---|
| F-01 | CRITICAL | Line numbers cited by T008, T009, T011, T012, T013, T014 and T018 are pre-sweep. Phase C edits top-down and every conversion is net line-additive, so downstream lines drift before the task that cites them runs. T018 is the worst case: it pins **post**-sweep scan output to **pre**-sweep lines, so the SC-001 gate would read as a failure that is not there. | Standing note added near the top declaring all line numbers PRE-SWEEP locators against `8c27271`. Every affected task gained a **Site identification** block matching on file + quoted original statement + enclosing test or function name. T018 rewritten entirely as per-file counts plus enclosing names, with the line-pinning trap called out explicitly. |
| F-02 | CRITICAL | Coverage Analysis contradicted the current T012. Section 2 said T012 edits `chaos-cross-browser.spec.ts` and `chaos-error-boundary.spec.ts`; CX-3 said "T012 applies the timeout to all four files", cited a nonexistent "crit. 3-6" and a "crit. 5" demanding owner escalation, and demanded plan.md be restated as "7 modified files". T012's body had already moved the raise inside `triggerHealthBanner`, and its crit. 3 requires those two files' diff to be **empty**. An implementer could act on either reading. | CX-3 rewritten: the helper-side raise supersedes the per-caller design, `plan.md:92-93` is correct as written, no owner escalation needed, and every reference to a T012 criterion number that does not exist is deleted. Section 2's file list corrected. CX-1 marked already closed (the contract already reads "3 spec files"). Section 4 summary rewritten to show zero outstanding artifact edits. |
| F-03 | CRITICAL | T021 said "apply an equivalent 250ms delay after the action". Post-conversion both targets are single `searchAndAwaitResponse(...)` calls, so the only "after the action" position in the spec file is after the helper has already awaited. A delay there proves nothing and passes trivially, and half the primary gate could be marked green by an implementation that tests nothing. | T021 now names the file and the seam: patch `helpers/search-helpers.ts`, inserting the delay between `await searchInput.fill(query);` and `await responsePromise;`. Added an acceptance criterion that the patched file MUST be `search-helpers.ts` and that a `.spec.ts` patch does NOT satisfy the task, plus a negative control: the same delay must FAIL on the pre-fix shape and PASS on the post-fix shape, and if both pass the result is void. |
| F-04 | HIGH | T020/T021 said "stash the Phase C conversions", but every Phase C task commits, so `git stash` has nothing to stash. The restoration step was inoperable. | Replaced with `git checkout $(git merge-base main HEAD) -- <files>` to get pre-fix content and `git checkout HEAD -- <files>` to restore, with the specific files named for each target. |
| F-05 | HIGH | Contract G2 promised no dangling listener can become an unhandled rejection, but if `searchInput.fill()` throws inside the helper, `responsePromise` is never awaited, so the guarantee was unachievable as stated. T004 crit. 3 checked "awaited on every return path", vacuous where there is exactly one return path. | Contract G2 reworded to describe what the code delivers, and the Behaviour section now requires a `try { … } finally { }` shape or a `.catch(() => {})` attached at creation. T004 crit. 3 checks that shape specifically, and notes that the helper is new code so FR-004 is no obstacle to doing it properly. |
| F-06 | HIGH | T011 crit. 3 stated a false fact: "the 503s in this test come from the sentiment endpoint". The route glob `**/api/v2/sentiment**` matches none of the app's sentiment URLs, so no 503 is ever produced and the cross-endpoint test passes vacuously. | T011 crit. 3 corrected: the conversion is right and needs no query scoping, on stronger grounds than claimed (the search route's unconditional 200). T027 extended to card the dead route alongside the `dynamodb_throttle` dead branch, as one card covering both dead-mock traps, holding the count at 118 → 120. |
| F-07 | MEDIUM | T012 and T013 both touch `helpers/chaos-helpers.ts`, imported by six spec files, two of which (`chaos-cached-data.spec.ts`, `chaos-accessibility.spec.ts`) appear in no verification command in the feature. Nothing covered them. | `npx tsc --noEmit` added as an acceptance criterion to both tasks, with the reason recorded. |
| F-08 | MEDIUM | FR-006's "explicit 15000ms on every converted call" is unauditable at the 18 helper-routed sites, which pass no `timeout` argument and rely on the helper default. | FR-006 reworded: explicitly 15000ms at the 9 inline sites, via the helper's documented `timeout` default at the 18 helper-routed sites. |
| F-09 | MEDIUM | FR-011's trigger-action token list omitted `.evaluate(`, `.type(`, `.check(`, `.tap(`, `.setInputFiles(`, `.dispatchEvent(`. A live instance already exists at `error-visibility-search.spec.ts:158`, which triggers via `retryButton.evaluate((el) => el.click())`. Unclassifiable shapes were also invisible in the output. | Token list extended in spec.md FR-011, data-model.md's classification rule, and T001 crit. 3. New T001 criterion requires `OTHER` sites to print under a "requires human triage" banner so unclassified shapes are visible rather than silently counted as clean. |
| F-10 | MEDIUM | No task recorded suite wall-clock against the CI hard wall, while roughly ten tests are being raised from a 30s to a 60s cap. `pr-checks.yml` wraps the run in `timeout 900` with `timeout-minutes: 20`, and a `timeout 900` kill is a silent, uninformative failure. | T023 crit. 6 added: record single-pass wall-clock for the six-file run, compare against the 900s wall, flag if within 30%. Recorded observation, not a pass/fail bar. |
| F-11 | MEDIUM | T006 crit. 2 and the Coverage Analysis treated `.clear()` → `fill('')` as a behavioural change needing a commit-message declaration, with a fallback to keep `.clear()` outside the helper. Playwright documents `locator.clear()` as equivalent to `fill('')`. | Downgraded to a one-line commit-message note in T006 crit. 2; the fallback removed. Coverage Analysis note corrected to match. |
| F-12 | MEDIUM | T012's helper-side `test.setTimeout(60000)` is an unconditional override. `chaos-accessibility.spec.ts:29` sets a deliberate `test.setTimeout(30_000)` suite cap and that file imports `triggerHealthBanner`, so a bare call would silently *lower* it in one direction and raise it in the other. | T012 crit. 1 now requires `test.setTimeout(Math.max(test.info().timeout, 60000))`, which can only raise. |
| F-13 | LOW | `spec.md` FR-005 cited the `triggerHealthBanner` docstring at `chaos-helpers.ts:345`; `:345` is the `export async function` line and the docstring occupies `:334-344`. | Citation corrected to `chaos-helpers.ts:334-344`. |
| F-14 | LOW | T001 did not require `scripts/scan-waitforresponse-race.py` to declare which dashboard it targets. Two existing scripts (`scripts/audit-e2e-skips.py`, `scripts/check-false-pass-patterns.sh`) default to the admin pytest suite, and the repo has a documented history of confusing the two dashboards. | T001 crit. 11 added: the module docstring carries `# Target: Customer Dashboard (Next.js/Amplify)` and `--help` names `frontend/tests/e2e/` as the scanned root. |

### Highest-risk task

**T012.** A late design decision (raise inside `triggerHealthBanner` rather than per caller) was
applied to the task body but not to the Coverage Analysis, which had been generated against the old
decision. The two readings demanded opposite diffs (edit two extra files, or prove their diff is
empty), and an implementer could reasonably have acted on either. Now resolved by F-02.

### Most likely to be silently wrong

**T021.** Its criteria were satisfiable by an implementation that tests nothing: a delay placed after
an already-awaited helper call passes trivially and looks like evidence. This is the failure mode the
whole feature exists to correct, reproduced inside the feature's own gate. Now resolved by F-03's
named seam and negative control.

### Gate

**READY FOR IMPLEMENTATION. 0 CRITICAL, 0 HIGH remaining.**
