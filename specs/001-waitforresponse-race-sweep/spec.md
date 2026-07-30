# Feature Specification: Sweep the act-then-wait `waitForResponse` race class

**Feature Branch**: `001-waitforresponse-race-sweep`
**Created**: 2026-07-30
**Status**: Draft (post Adversarial Review #1)
**Input**: User description: "Sweep the act-then-wait `page.waitForResponse` race class across the frontend Playwright E2E suite"

## Context

The customer-dashboard Playwright suite (`frontend/tests/e2e/`) contains 27 call sites where a
network listener is registered *after* the action that triggers the request:

```ts
await searchInput.fill('AAPL');
await page.waitForResponse('**/api/v2/tickers/search**');
```

`page.waitForResponse()` subscribes at call time and does not inspect responses already received.
Playwright's own documentation is explicit: *"Ensure the promise is initiated before the action that
triggers the request."* (playwright.dev, `class-page`). 24 of the 27 sites are answered by a
`route.fulfill` mock, which replies with no network latency at all, so the response can land inside
the gap between the action and the subscription. The remaining 3 are `page.waitForEvent('requestfailed')`
waits under the `api_timeout` chaos scenario, which uses `route.abort` and therefore fires with even
less latency than `route.fulfill`. When the event lands in the gap, the listener goes on waiting for
a second one that never arrives and the test dies at its timeout.

### Confirmed CI failures

Sampling method, so this is re-derivable: the 30 most recent `PR Checks` workflow runs as of
2026-07-30, of which 25 actually executed the Playwright job. Six of those 25 were red; five are
attributable to this race class. The sixth (`30460832567`) is the unrelated user-menu dismissal
flake tracked separately as #950. `pr-checks.yml` runs Playwright with `--retries=0`, so a red run
means one failed attempt, not three. That flag is part of the method: without it the rate is not
re-derivable from other workflows, because `nightly-e2e` does not pass it.

| Run | Test | Failing site | Cap hit |
|---|---|---|---|
| 30512923260 | `chaos-degradation.spec.ts:196` | `:229` (already fixed by #981) | `waitForResponse` 5000ms |
| 30512621168 | `ticker-search-gaps.spec.ts:22` | `:38` | test-level 30000ms |
| 30510400002 | `ticker-search-gaps.spec.ts:46` | `:77` | test-level 30000ms |
| 30463441189 | `ticker-search-gaps.spec.ts:206` | `:211` | test-level 30000ms |
| 30463171597 | `chart-edge-cases.spec.ts:144` | `:161` | test-level 30000ms |

Attributable red rate in the sampled window: **5 of 25 runs (~20%)**.

Two cautions this table earns:

1. **The binding cap is usually the test-level timeout, not the `waitForResponse` timeout.** Only
   the first failure hit a per-call cap. Raising per-call timeouts would not have changed the shape
   of the other four. Timeout policy is therefore secondary; ordering is the fix.
2. **Run/commit distinction.** `30512621168` is a `push`-event run; its sibling `pull_request` run
   on the same commit (`30512623219`) passed. Runs are not independent samples of distinct commits,
   so the ~20% figure describes runs, not commits, and is stated that way deliberately.

The Playwright E2E job is **not** merge-required, so these reds are absorbed silently. Playwright
was green on the recent main runs (#976/#977/#978/#979) — the job is intermittently red on PRs, not
persistently red. The board card claiming otherwise is corrected by FR-008.

One instance is already fixed and merged: PR #981 (`8c27271`) converted
`chaos-degradation.spec.ts:229`. That commit is the reference implementation.

### Inventory (verified against `8c27271`)

31 `waitForResponse` plus 3 `waitForEvent('requestfailed')` occurrences exist in
`frontend/tests/e2e/`, 34 total, fully accounted for as 27 racy + 6 already-correct + 1 triaged.

An earlier draft of this section said "No other same-class API (`waitForRequest`,
`waitForEvent('response')`, `waitForNavigation`) appears in the suite." That sentence was wrong. It
enumerated `waitForEvent('response')` specifically and thereby excluded
`waitForEvent('requestfailed')` on a technicality, which hid three sites of exactly the same class.
Recorded as a scope-definition lesson: **the class is defined by SHAPE (a listener registered after
the triggering action), not by method name.** The committed scan (FR-011) encodes the shape rule so
the definition cannot drift back to a method-name list.

| File | Racy sites | Lines |
|---|---|---|
| `ticker-search-gaps.spec.ts` | 9 | 38, 77, 82, 109, 129, 144, 162, 211, 219 |
| `chaos-degradation.spec.ts` | 5 | 131, 138, 178, 183, 188 |
| `chart-edge-cases.spec.ts` | 4 | 72, 130, 161, 218 |
| `helpers/chaos-helpers.ts` | 3 | 364, 367, 370 (inside `triggerHealthBanner`) |
| `chaos-scenarios.spec.ts` | 3 | 102, 105, 108 |
| `chaos-scenarios.spec.ts` (`waitForEvent('requestfailed')`) | 3 | 219, 222, 225 |
| **Total** | **27** | |

Already correct, and the target state to copy — do not modify: `chaos-degradation.spec.ts:231`,
`chaos-scenarios.spec.ts:251`, `error-visibility-search.spec.ts:142`, `:157`,
`ticker-search-gaps.spec.ts:231`, `:237`.

Triaged and **not** racy in practice: `chaos-scenarios.spec.ts:138`. Its action is `page.reload()`,
and the backing `lambda_cold_start` handler delays 3s before `route.continue()`. An
`await expect(...).toBeVisible({ timeout: 2000 })` sits between the reload and the wait, so the
listener can register up to 2s later than the action. The worst-case margin ahead of the response is
therefore about 1s, not the 2.8s an earlier draft claimed. Still safe, but the correct margin is
what is recorded. Act-then-wait in form, safe in practice. Left unconverted with this reason
recorded (FR-003). That intervening assertion is also why the FR-011 classifier files it as `OTHER`
rather than `RACY`: the classification rule keys on the immediately preceding non-comment,
non-blank line.

### The 27 do not share one shape

An earlier draft asserted all sites were `fill()` + wait on the ticker-search endpoint. That is
false for 9 of them, and the difference drives the design:

- 18 sites wait on the ticker-search endpoint (URL-scoped).
- `chaos-scenarios.spec.ts:102/105/108` wait on `r.url().includes('/api/') && r.status() === 503`.
- `helpers/chaos-helpers.ts:364/367/370` wait on `resp.status() === 503` with **no URL predicate at
  all**, under a `page.route('**/api/**', …503)` blanket block (`chaos-helpers.ts:347`).
- `chaos-scenarios.spec.ts:219/222/225` wait on `page.waitForEvent('requestfailed')`, which takes no
  URL predicate at all, under the `api_timeout` scenario's `route.abort`.

A single search-scoped helper cannot absorb the last nine without narrowing their predicates, which
would change what they assert. They get inline promise-first conversion instead: 9 inline
(6 status-only 503 + 3 `requestfailed`) and 18 helper-routed.

### Product-code facts that constrain the fix

Established by reading `frontend/src`, not by reading comments:

- **There is no debounce.** `ticker-input.tsx:33-39` keys `useQuery` directly on `query`; no
  debounce hook exists anywhere under `frontend/src`. The source comment `// Debounced search query`
  at `ticker-input.tsx:33` is wrong, and it misled an earlier draft of this spec.
- **An empty fill cannot trigger a request.** `ticker-input.tsx:37` sets `enabled: query.length >= 1`.
  React Query does not fetch while disabled, and with no debounce there is no trailing fire from the
  previous value. `fill(''); fill('X')` sequences are therefore safe to bracket with a single
  listener.
- **Errors produce a second response.** `providers.tsx:48` sets `retry: 1`, so a failed search fires
  a retry roughly 1s later. This, not debounce, is the real source of multiple responses — and only
  on error paths.
- **Repeat queries within 30s may serve from cache with no network request at all.**
  `ticker-input.tsx:38` sets `staleTime: 30000`. A wait registered around a cache-served query hangs
  until timeout. `ticker-search-gaps.spec.ts:242-247` already documents this and deliberately omits
  a wait.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CI signal is trustworthy (Priority: P1)

An engineer opens a PR. The Playwright E2E job either passes, or it fails for a reason that is
about their change. It does not fail because a mock answered faster than a listener attached.

**Why this priority**: This is the whole point. A job with a ~20% false-red rate teaches everyone to
ignore it, which is worse than not running it — a real frontend regression lands unnoticed behind
the noise. It also blocks the owner's deferred decision on making the job merge-required, which
cannot happen while the job flakes.

**Independent Test**: Convert the sites and run the suite under the adversarial-timing procedure in
SC-003, which forces the failure mode rather than hoping to observe it.

**Acceptance Scenarios**:

1. **Given** a converted call site, **When** the mocked response resolves before the test's next
   statement executes, **Then** the wait still observes it and the test proceeds.
2. **Given** a converted call site, **When** the response is genuinely slow, **Then** the wait blocks
   until it arrives or the configured timeout elapses, exactly as before.
3. **Given** a converted site whose predicate is not query-scoped, **When** a prior interaction's
   `retry: 1` response is in flight, **Then** the wait resolves on the intended request and not on
   the stale retry.

---

### User Story 2 - The interaction has a name (Priority: P2)

A test author needs "type a query and wait for the search response". They call one documented helper
instead of hand-rolling a two-statement sequence whose correctness depends on statement order.

**Why this priority**: Converting sites inline fixes today's bug and leaves the 25th author free to
reintroduce it. Naming the interaction reduces the opportunity. It does not remove it — nothing in
this feature *enforces* helper use; that is the dependent regression-guard feature. Lower than P1
because the conversions deliver the CI benefit on their own.

**Independent Test**: A new test can perform a search-and-await in a single call, and that call is
race-free by construction.

**Acceptance Scenarios**:

1. **Given** the helper, **When** a caller uses it, **Then** the listener is registered before the
   fill without the caller having to think about ordering.
2. **Given** a caller needing a non-search predicate, **When** it uses the helper, **Then** it can
   supply its own predicate rather than being forced onto a search-scoped one.

---

### User Story 3 - The board states verified facts (Priority: P3)

Someone reading `CLEANUP-BOARD.html` gets the actual failure history, not an overstated one.

**Why this priority**: The board is the campaign's ground truth. A card asserting "fails on main and
every PR" when the cited main runs were green corrodes trust in every other card. Cheap to fix,
independent of the code change.

**Acceptance Scenarios**:

1. **Given** the Playwright flake card, **When** it is read, **Then** it states the verified rate
   with its sampling method and does not claim main was red from this cause.
2. **Given** the `MASTER: CI/CD hygiene` card, **When** its children list is read, **Then** it
   carries the same corrected framing.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All 27 inventoried racy call sites MUST be converted so the response or event listener
  is registered before the action that triggers the request.
- **FR-002**: Conversion MUST NOT weaken what a test asserts. Each converted predicate MUST remain
  at least as specific as the original. Where promise-first registration widens the window such that
  a prior interaction's response could satisfy the predicate, the predicate MUST be tightened
  (for example by matching the query string) so the wait resolves on the intended request. Any
  deliberate change to a predicate's meaning MUST be called out in the task that makes it.

  **Exception, accepted as a stated risk**: the 6 status-only sites
  (`helpers/chaos-helpers.ts:364/367/370`, `chaos-scenarios.spec.ts:102/105/108`) and the 3
  `requestfailed` sites (`chaos-scenarios.spec.ts:219/222/225`) are exempt from the tightening
  requirement. They run under blanket failure routes (`page.route('**/api/**', …503)`, or
  `api_timeout`'s `route.abort`) where ANY failing response legitimately signals "the API is
  failing", which is exactly what the health-monitor failure counter keys on. Per-request sequencing
  is not what those tests assert, so matching a retry or a sibling endpoint's failure is not a false
  pass. Residual risk, recorded rather than hidden: these waits confirm "a failure occurred", not
  "THIS search's failure occurred". A regression that made only one of three searches fail would
  still satisfy them.
- **FR-003**: `chaos-scenarios.spec.ts:138` MUST be left unconverted, with the recorded reason that
  its 3s `lambda_cold_start` delay leaves an ordering margin of roughly 1s even after the
  intervening 2000ms assertion, which makes the gap immaterial.
- **FR-004**: The six already-correct sites MUST remain unmodified.
- **FR-005**: A shared helper MUST expose the search-and-await interaction for the 18 URL-scoped
  search sites. The helper MUST accept a caller-supplied predicate so that non-search callers are
  not forced onto a search-scoped one. `triggerHealthBanner`'s three waits MUST become promise-first
  but MUST retain their existing status-only predicate; narrowing them to `/tickers/search` is out
  of scope for this feature.

  **Consequence of the FR-002 exception**: `triggerHealthBanner`'s docstring
  (`chaos-helpers.ts:334-344`; `:345` is the `export async function` line itself) currently claims
  its waits "confirm the failure was recorded" for each
  search. The status-only predicate does not prove that: it proves a failing response was observed,
  which any of the three searches or a retry could have produced. The docstring MUST be updated to
  match what the predicate actually proves, and a task MUST carry that edit explicitly so it is not
  lost as an incidental change.
- **FR-006**: Every converted call MUST resolve to a 15000ms timeout, chosen so a hung wait fails
  inside Playwright's 30s test-level timeout and reports as a `waitForResponse` timeout rather than
  an opaque test timeout. This is a diagnosability requirement, not a fix; ordering is the fix.

  **How it is carried, and therefore how it is audited**, differs by site class. The earlier wording
  "explicit 15000ms on every converted call" was unauditable at the helper-routed sites, which pass
  no `timeout` argument at all:
  - **The 9 inline sites** (`chaos-scenarios.spec.ts` 3 status-503 + 3 `requestfailed`,
    `helpers/chaos-helpers.ts` 3 status-503) MUST carry a literal `{ timeout: 15000 }` on the call.
    Audited by reading the call.
  - **The 18 helper-routed sites** carry it via the helper's documented `timeout` default of `15000`
    (`contracts/helper-api.md`, Defaults table). They pass no `timeout` argument, and MUST NOT be
    expected to. Audited at the helper's default, once, not at 18 call sites.

  **Multi-wait tests need the test cap raised for the per-call cap to bind.** `playwright.config.ts`
  sets no `timeout`, so the test-level cap is Playwright's default 30000ms. A test with several
  sequential 15000ms waits blows the 30s test cap before the second per-call cap can fire, and
  reports opaquely, which is the exact outcome FR-006 exists to prevent.
  `chaos-degradation.spec.ts:196` performs about seven sequential waits inside that one 30s budget
  (two `triggerHealthBanner` calls at 3 waits each, plus the TSLA wait). Therefore: any test
  containing more than two converted waits MUST get an explicit `test.setTimeout(60000)`. Affected
  tests are those that call `triggerHealthBanner` and those that perform the three-search sequences
  (`chaos-scenarios.spec.ts:102/105/108` and `:219/222/225`), plus the test at
  `chaos-degradation.spec.ts:148`, which holds three converted waits at `:178/:183/:188`.

**Where `test.setTimeout(60000)` goes.** For tests that own their converted waits directly, the call
sits at the top of the test. For the three waits inside `triggerHealthBanner`, the raise belongs in
the helper itself: `chaos-helpers.ts` already imports from `@playwright/test`, so it can import
`test` and call `test.setTimeout(Math.max(test.info().timeout, 60000))` on entry, using `Math.max` rather
than a bare `60000` so the helper can only ever raise a caller's cap, never lower it
(`chaos-accessibility.spec.ts:29` sets a deliberate `test.setTimeout(30_000)` and imports this
helper). That covers all seven `triggerHealthBanner(page)`
call sites at once, including `chaos-cross-browser.spec.ts:35` and `chaos-error-boundary.spec.ts:63`,
which are otherwise untouched by this feature. Per-caller raises were rejected: they would grow the
diff from 5 files to 7, and would leave the rule for a future caller to remember, which is the same
failure that produced this bug class in the first place.

- **FR-007**: No product-code changes. Test changes MUST be confined to `frontend/tests/e2e/`.
  The board edits under FR-008 and FR-009, and the scan script under FR-011 (which lives under
  `scripts/`), are the only permitted changes outside that directory.
- **FR-008**: The Playwright flake card and the `MASTER: CI/CD hygiene` card in
  `CLEANUP-BOARD.html` MUST be corrected to the verified facts and re-scoped to this sweep.
- **FR-009**: Two follow-up cards MUST be created in `CLEANUP-BOARD.html`: (1) the owner's deferred
  decision on making the Playwright E2E job merge-required, and (2) the `dynamodb_throttle`
  dead-branch trap (`chaos-helpers.ts:169-189`, byte-identical `if`/`else` branches, recorded in
  Edge Cases). This feature MUST NOT change the job's required status and MUST NOT fix the dead
  branch.
- **FR-010**: Sites where the query is served from React Query cache with no network request MUST
  be identified and left unconverted. A wait MUST NOT be introduced where none exists today. The
  helper MUST NOT be applied to a repeat of the same query within the 30s `staleTime` window.
- **FR-011**: The inventory scan MUST be committed as a runnable artifact so SC-001 is reproducible
  by anyone, rather than existing only in a shell history. The scan MUST document its classification
  rule explicitly, in the script itself, so SC-001's "RACY 0" does not rest on an undocumented
  heuristic. The rule is: **RACY** = an awaited `page.waitForResponse(...)` or
  `page.waitForEvent('requestfailed'|'response')` whose immediately preceding non-comment,
  non-blank line performs a triggering action (`.fill(`, `.click(`, `.press(`, `.selectOption(`,
  `.clear(`, `.goto(`, `.reload(`, `.evaluate(`, `.type(`, `.check(`, `.tap(`, `.setInputFiles(`,
  `.dispatchEvent(`). Anything else that is neither that shape nor promise-first is `OTHER` and
  requires human triage, and `OTHER` sites MUST be printed under an explicit "requires human triage"
  banner so a shape the classifier cannot place is visible rather than counted as clean by omission.

  The token list is not theoretical. `.evaluate(` is live in the suite today:
  `error-visibility-search.spec.ts:158` triggers its request with
  `retryButton.evaluate((el) => el.click())`. A list stopping at `.reload(` would miss it. The
  earlier six-token list was the same method-name-shaped mistake that hid the three
  `waitForEvent('requestfailed')` sites.
- **FR-012**: Converted sites MUST await the listener promise on the success path, so a timeout
  surfaces as a test failure. The helper additionally handles the throw path internally (contract G2, which specifies the
  required shape rather than promising an unconditional await). A
  `try/finally` is **not** required at the inline sites, and this is deliberate rather than an
  oversight: an unhandled rejection can only occur when an intervening action throws, and an
  intervening action that throws fails the test regardless. The rejection is then noise attached to
  an already-failing test, not a new failure mode. The absolute "awaited on every path, never as an
  unhandled rejection" wording of an earlier draft was unimplementable: the merged reference
  conversion at `chaos-degradation.spec.ts:231-236` leaves the promise unawaited if a `fill()`
  throws, and FR-004 protects that site from amendment.

### Key Entities

- **Racy call site**: defined by shape, not by method name. An awaited `page.waitForResponse(...)`
  or `page.waitForEvent('requestfailed'|'response')` whose triggering action executes immediately
  before it. Formalised as the classifier rule in FR-011.
- **Promise-first conversion**: listener created, action performed, promise awaited.
- **Search-and-await helper**: the named interaction covering fill-then-wait, parameterised by
  predicate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the sweep the committed inventory scan (FR-011) reports **RACY 0,
  PROMISE-FIRST 16, OTHER 1, total 17** inline occurrences across `frontend/tests/e2e/`. The 16
  is computed as 6 pre-existing promise-first + 6 status-only inline conversions + 3 `requestfailed`
  inline conversions + 1 internal to the helper. The `OTHER` is the single triaged site
  (`chaos-scenarios.spec.ts:138`). The total drops from 34 because the 18 helper-routed sites stop
  being inline wait call sites when they become `searchAndAwaitResponse(...)` calls, and the helper
  contributes one internal wait in their place. Additionally, exactly **18**
  `searchAndAwaitResponse(` call sites MUST exist under `frontend/tests/e2e/`, counted over
  `*.spec.ts` only. An unfiltered grep also matches the helper's own `export async function` line
  and returns 19, which would read as a false failure.
- **SC-002** *(precondition, non-evidential)*: the customer-dashboard Playwright suite passes
  locally. This is a smoke check only. Pre-fix code passed 10/10 locally, so local green proves
  nothing about the race and MUST NOT be cited as evidence of the fix.
- **SC-003** *(the actual gate)*: the race is **forced**, not merely hoped-absent. Two procedures,
  both required:
  - **(a) Fault injection.** With a temporary patch that awaits a delay between the action and the
    listener registration on the pre-fix code, the injected tests MUST fail. The same injection
    against the converted code MUST pass. This demonstrates the conversion removes the race rather
    than reducing its probability. The injection patch MUST NOT be committed.

    **Valid injection targets are only sites whose mock produces exactly one matching response.**
    Named explicitly: `ticker-search-gaps.spec.ts:22` (site `:38`, which returns a single 200 with
    empty results and does not retry because it is not an error) and `chart-edge-cases.spec.ts`
    (site `:72`).

    `chaos-degradation.spec.ts:196` is **NOT** a valid injection target. PR #981 already converted
    its racy site; it is now promise-first at `:231-237` and is one of the 6 protected
    already-correct sites under FR-004. Stashing this feature's conversions does not bring the old
    shape back.

    Injection is **unsound** on the 6 status-only 503 sites and the 3 `requestfailed` sites.
    `retry: 1` (`frontend/src/app/providers.tsx:48`) plus the blanket
    `page.route('**/api/**', …503)` mean a matching response keeps arriving, so the listener
    resolves anyway no matter how wide the injected gap is. Non-reproduction at those sites is
    EXPECTED and does not falsify the diagnosis. Those 9 sites are covered by the contention
    procedure (b) only.
  - **(b) Contention.** `npx playwright test <the affected files> --project="Desktop Chrome"
    --repeat-each=20 --workers=8` MUST pass 20/20 for every affected test. The file list MUST
    include `chaos-cross-browser.spec.ts` and `chaos-error-boundary.spec.ts`, which call
    `triggerHealthBanner` (at `:35` and `:63` respectively) and are therefore affected without being
    edited, and `chaos-scenarios.spec.ts`.
- **SC-004**: Test count is unchanged — no test is skipped, deleted, or weakened to reach green.
  Verified by comparing the pre- and post-sweep pass/fail/skip tallies.
- **SC-005**: The `CARDS` array literal in `CLEANUP-BOARD.html` still parses (via `raw_decode` on
  the text following `const CARDS = `), the board renders without a JS error, and the array length
  goes from 118 to 120 (two cards added by FR-009: the merge-required follow-up and the
  `dynamodb_throttle` dead-branch trap; FR-008 edits two existing cards in place).

## Edge Cases

- **Dangling listener promises.** A promise created and not awaited becomes an unhandled rejection
  on timeout, which Playwright may surface against an unrelated test. Bounded, not eliminated: the
  only way to reach that state is for an intervening action to throw, which fails the test anyway,
  so the rejection rides an already-failing test. FR-012 requires the success-path await and the
  helper's internal guarantee (contract G2), and deliberately does not require `try/finally` at the
  inline sites.
- **Cross-interaction predicate matching.** `retry: 1` means an errored search fires a second
  response ~1s later. A status-only predicate registered early can match that retry instead of the
  intended request. Covered by FR-002. Highest-risk instance:
  `chaos-degradation.spec.ts:131/138`, whose mock returns 500 on the first call and 200 thereafter.
- **Cache-served repeats.** `staleTime: 30000` means a repeated query may produce no request at all.
  Covered by FR-010.
- **`triggerHealthBanner` is called by the tests that flake.** Changing it changes the preconditions
  of every chaos test, so its blast radius is the whole chaos suite, not one file.
- **The race does not reproduce on an idle dev box.** Covered by SC-003(a), which forces it.
- **Timeouts that mask rather than fix.** Raising a cap makes a race less likely without removing
  it. FR-006 sets timeouts for diagnosability only and is explicitly not the fix.
- **Empty fill.** Settled, not open: `enabled: query.length >= 1` means it cannot trigger a request.
- **A latent trap in `dynamodb_throttle`.** `chaos-helpers.ts:169-189` has byte-identical `if`/`else`
  branches (both 503) despite a comment claiming reads may succeed from cache. Three of the 27 sites
  work only because of that dead branch. Out of scope to fix; carded under FR-009 so a future
  correction of the comment-to-code mismatch does not silently break them.

## Out of Scope

- Making the Playwright E2E job merge-required (owner deferred; carded, not done).
- Adopting `eslint-plugin-playwright` wholesale. Its 59 rules include none for this pattern, and
  enabling it would flag unrelated violations across the suite.
- The regression guard preventing reintroduction — separate feature, depends on this one.
- Narrowing `triggerHealthBanner`'s predicates from status-only to URL-scoped.
- Fixing the `dynamodb_throttle` dead branch, or the wrong `// Debounced search query` comment.
- Any product-code change to search, caching, or the health banner.
- The other known Playwright flakes tracked separately (sanity-suite Tiingo latency, user-menu
  dismissal #950).

---

## Adversarial Review #1

Reviewer: independent agent, instructed to treat the spec as a suspect and verify every factual
claim against the repo and CI. Orchestrator independently re-verified the highest-impact findings
before accepting them (the three additional CI runs, `enabled: query.length >= 1`, `retry: 1`, and
the chaos-helper predicates) rather than taking the reviewer's word.

### Findings

Historical record. Counts and section titles below are as they stood at AR#1 (24 racy,
118 to 119 cards). Adversarial Review #2 later raised the count to 27 and the cards to 120; see
plan.md's AR#2 appendix. Left unedited so the review trail is not rewritten after the fact.

| ID | Sev | Finding | Resolution |
|---|---|---|---|
| F-01 | CRITICAL | Only 2 CI failures cited; 5 exist. Runs `30510400002`, `30463441189`, `30463171597` are the same `waitForResponse` timeout and were omitted. | Failure table rewritten with all 5. Orchestrator re-verified each via `gh run view --log-failed`. |
| F-02 | CRITICAL | SC-001 cites an "inventory scan" that exists nowhere in the repo — unrunnable criterion. | FR-011 added requiring the scan be committed; SC-001 now cites it and states exact expected counts. |
| F-03 | CRITICAL | SC-003 "adversarial timing" undefined; two engineers could not run the same test. | SC-003 rewritten as two concrete required procedures: fault injection (a) and contention (b), with exact commands and pass bars. |
| F-04 | HIGH | FR-005 contradicted FR-002: routing `triggerHealthBanner` through a search-scoped helper narrows its status-only predicate. | FR-005 rewritten — helper takes a caller-supplied predicate; `triggerHealthBanner` keeps status-only. Narrowing moved to Out of Scope. |
| F-05 | HIGH | FR-007 ("confined to `frontend/tests/e2e/`") contradicted FR-008 (edit root-level `CLEANUP-BOARD.html`). | FR-007 reworded to scope the confinement to test changes and name the permitted exceptions. |
| F-06 | HIGH | Missing category: sites that deliberately omit a wait because React Query serves from cache (`staleTime: 30000`). Converting one would hang. | FR-010 added. `ticker-search-gaps.spec.ts:242-247` cited as the existing documented instance. |
| F-07 | HIGH | Predicates match on URL+status but never on query. `retry: 1` means promise-first can match a prior interaction's retry, passing for the wrong reason. Worst case `chaos-degradation.spec.ts:131/138`. | FR-002 rewritten to require predicate tightening where the window widens. New acceptance scenario US1-3. |
| F-08 | HIGH | SC-002 accepted "passes locally", which the spec's own edge case declares meaningless. | SC-002 demoted to a labelled non-evidential precondition; SC-003 is the sole gate. |
| F-09 | MEDIUM | The "debounce" premise is false — no debounce exists; the source comment lies. Real multiplicity is `retry: 1`. | Product-code facts section added; edge case rewritten around retry. Verified directly. |
| F-10 | MEDIUM | "All 24 share one shape" false for 6 of 24 (3 wait on any `/api/` 503, 3 on any 503 with no URL predicate). | New section "The 24 do not share one shape"; FR-005 design changed accordingly. |
| F-11 | MEDIUM | FR-006 was a requirement to hold a meeting, and misidentified the binding cap — 4 of 5 failures hit the test-level timeout, not a per-call one. | FR-006 now states the value (15000ms) and its purpose (diagnosability), explicitly not the fix. Caution added to the failure table. |
| F-12 | MEDIUM | SC-005 claimed the HTML file "parses as valid JSON" — impossible. | Restated against the `CARDS` array literal via `raw_decode`, with the exact 118→119 count. (Reviewer overreached slightly: the array literal does parse; the file does not. Wording fixed either way.) |
| F-13 | MEDIUM | Sampling method unstated and double-counting: `30512621168` is a push run whose sibling PR run passed. | Method, window, and the run/commit distinction now stated explicitly in the Context section. |
| F-14 | MEDIUM | The `fill('')` edge case was left open as a gating unknown; it is settled — `enabled: query.length >= 1`. | Moved from open question to settled fact with citation. |
| F-15 | LOW | US2 claimed naming the interaction "removes the opportunity" to reintroduce; nothing enforces it. | Softened to "reduces", with the enforcement gap named and pointed at the dependent feature. |
| F-16 | LOW | `dynamodb_throttle`'s `if`/`else` branches are byte-identical; 3 of the 24 sites depend on that dead branch. | Recorded as an edge case and carded. Not fixed here. |

### Self-defeat check

The reviewer was asked specifically whether a spec criticising an overstated board claim contained
overstated claims of its own. It did: the "2 of 17" rate was both understated in magnitude and
derived by an unstated method. This is the same failure mode the spec exists to correct on the
board. Corrected, with the method now written down so the next reader can re-derive it.

### Gate

**0 CRITICAL, 0 HIGH remaining.** All 3 CRITICAL and 5 HIGH findings resolved in the text above.
8 MEDIUM/LOW also resolved rather than deferred, except F-16 which is deliberately carded as out of
scope.

---

## Clarifications

Five ambiguities were identified. **All five were resolved from the codebase without user input.**
None are deferred to the Phase 2 summary.

### C1 — Where does the helper live?

**Question**: New `helpers/search-helpers.ts`, or extend the existing `helpers/chaos-helpers.ts`?

**Answer**: New file, `frontend/tests/e2e/helpers/search-helpers.ts`.

**Evidence**: `grep -rn "from './helpers/chaos-helpers'" frontend/tests/e2e/` returns exactly SIX
importers, all chaos-scoped: `chaos-cross-browser`, `chaos-cached-data`, `chaos-error-boundary`,
`chaos-degradation`, `chaos-accessibility`, `chaos-scenarios`. `helpers/verification.ts` only
*mentions* chaos-helpers in a comment; it does not import it. `chart-edge-cases.spec.ts` and
`ticker-search-gaps.spec.ts` contain ZERO references to chaos-helpers.

That strengthens the conclusion rather than weakening it: two of the four files needing the search
helper do not import the chaos module at all today, so putting a general search helper there would
force them to start importing chaos route machinery for a plain search interaction.

An earlier draft of this clarification claimed seven importers including `helpers/verification.ts`,
and claimed `chart-edge-cases.spec.ts` and `ticker-search-gaps.spec.ts` imported it today. Both
claims were fabricated from a carelessly read grep. Caught in Adversarial Review #2 and corrected
here.

### C2 — What exactly does a query-scoped predicate match on?

**Question**: Research D4 requires tightening predicates "by matching the query string". What is the
actual parameter name?

**Answer**: `q`. A query-scoped predicate is `r.url().includes('q=GOOG')`.

**Evidence**: `frontend/src/lib/api/tickers.ts:28-31` — `api.get('/api/v2/tickers/search', { params: { q: query, limit } })`.
Input is upper-cased before it reaches the query (`ticker-input.tsx` `handleChange`,
`e.target.value.toUpperCase()`), so the literal matches the test's own fill value with no case
handling needed.

### C3 — What language for the scan script (FR-011)?

**Answer**: Python 3.13, at `scripts/scan-waitforresponse-race.py`, run under the project venv.

**Evidence**: `scripts/` already holds `audit-e2e-skips.py`, which does the closely analogous job of
scanning the E2E suite and reporting counts. Following that precedent keeps one idiom for "scan the
test suite and report", and Python is the repo standard with venv and pre-commit already wired.

### C4 — Should the scan be enforced in CI as part of this feature?

**Answer**: No. Commit it as a runnable artifact only.

**Evidence**: enforcement is the dependent regression-guard feature, listed in this spec's Out of
Scope. The script exits non-zero when `RACY > 0` so the guard can wire it in without modification,
but this feature does not add it to pre-commit or any workflow.

### C5 — Should the six already-correct sites adopt the helper for consistency?

**Answer**: No. Leave them byte-unchanged.

**Evidence**: FR-004. They are already race-free, so touching them adds diff surface and review load
with no defect fixed, and it would blur the CI signal this feature depends on — if the flake
survives, the diff should contain only changes that could plausibly have caused it.
