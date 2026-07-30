# Research: `waitForResponse` race sweep

## R1 — Is promise-first actually the canonical fix?

**Source**: playwright.dev, `class-page` (retrieved via Context7, 2026-07-30).

> "Ensure the promise is initiated before the action that triggers the request."

The documented shape, repeated for `waitForRequest`, `waitForNavigation` and `waitForEvent`:

```js
const requestPromise = page.waitForRequest('https://example.com/resource');  // note: no await
await page.getByText('trigger request').click();
const request = await requestPromise;
```

**Conclusion**: the target pattern is the vendor-documented one, not a local invention. The 6
already-correct sites in this repo independently arrived at it.

## R2 — Why does the race fire against mocks specifically?

`page.waitForResponse()` subscribes at call time and does not replay already-received responses.
The same is true of `page.waitForEvent('requestfailed')`. With a real network the round-trip
reliably outlives the microtask gap between the action and the subscription, so act-then-wait
usually works by luck. 24 of the 27 racy sites are answered by `route.fulfill`, which replies with
no network latency, collapsing that margin; the other 3 (`chaos-scenarios.spec.ts:219/222/225`) are
answered by `route.abort` under the `api_timeout` scenario, which collapses it further still. Under
CI worker contention the JS gap widens and the mock wins.

**Evidence, not inference**: the failure artifact for run 30512923260 contains a page snapshot taken
at the moment of timeout showing the search combobox holding `TSLA` and the results listbox already
rendering `option "TSLATesla Inc. NASDAQ" [selected]`. The response arrived and rendered; only the
listener missed it.

## R3 — Product-code behaviour that constrains conversions

Read from `frontend/src`, not from comments.

| Fact | Source | Consequence |
|---|---|---|
| No debounce exists | `ticker-input.tsx:33-39` keys `useQuery` on `query`; no debounce hook under `frontend/src` | A successful `fill()` produces exactly one request. The `// Debounced search query` comment at `:33` is false and misled an earlier spec draft. |
| Empty query never fetches | `ticker-input.tsx:37` — `enabled: query.length >= 1` | `fill(''); fill('X')` is safe to bracket with one listener. |
| Errors retry once | `providers.tsx:48` — `retry: 1` | An errored search yields a *second* response ~1s later. This is the real multi-response source, and it only affects error-path sites. |
| Repeats within 30s may be cache-served | `ticker-input.tsx:38` — `staleTime: 30000` | A wait around a repeated query can hang with no request at all. Already documented at `ticker-search-gaps.spec.ts:242-247`. |

## D1 — Shared helper vs 27 inline conversions

**Decision**: both. A predicate-parameterised helper for the 18 URL-scoped search sites; inline
promise-first for the 9 non-search sites.

**Rationale**: the sites are not homogeneous. 18 wait on the ticker-search endpoint.
`chaos-scenarios.spec.ts:102/105/108` wait on `r.url().includes('/api/') && r.status() === 503`,
`chaos-helpers.ts:364/367/370` wait on `resp.status() === 503` with no URL predicate at all under a
blanket `page.route('**/api/**', …503)`, and `chaos-scenarios.spec.ts:219/222/225` use
`page.waitForEvent('requestfailed')`, which takes no predicate at all.

**Rejected — one uniform search-scoped helper for all 27**: would narrow the 6 status-only
predicates to `/tickers/search` and could not express the 3 event waits, changing what those tests
assert. That is a semantic change smuggled inside a race fix (AR#1 F-04).

**Rejected — 27 inline conversions, no helper**: fixes today and leaves the interaction unnamed, so
the next author hand-rolls it again. The 6 already-correct sites prove local fixes do not generalise.

## D2 — Response wait vs UI-outcome assertion

**Decision**: keep response waits. Do not convert to UI assertions.

**Rationale**: a UI assertion (the option appearing in the `Ticker search results` listbox) is
race-free by construction and was seriously considered. But several tests exist specifically to
prove a *request* was made and answered — the health banner's failure counter and `recordSuccess()`
key on responses, not on rendered options. Replacing the response wait with a UI wait would change
what those tests prove.

**Rejected because**: redesigning assertions during a race fix conflates two changes and makes the
CI signal ambiguous. If the flake survives, we would not know whether the ordering fix failed or the
assertion swap broke something. Carried as a possible future simplification, not done here.

## D3 — Timeout policy

**Decision**: explicit `{ timeout: 15000 }` on every converted call.

**Rationale**: not a fix — ordering is the fix, and a longer cap only makes a race less likely.
The value is diagnosability. Four of the five observed failures hit Playwright's 30s *test-level*
timeout, which reports as an opaque "Test timeout of 30000ms exceeded" and does not name the wait.
A per-call cap comfortably below the test timeout converts those into
"`page.waitForResponse: Timeout 15000ms exceeded`", which names the failing construct.

**Corollary — multi-wait tests need `test.setTimeout(60000)`.** The reasoning above holds only while
a single hung wait fits inside the test budget. `playwright.config.ts` sets no `timeout`, so the
test-level cap is Playwright's default 30000ms. `chaos-degradation.spec.ts:196` performs about seven
sequential waits inside that one budget (two `triggerHealthBanner` calls at 3 waits each, plus the
TSLA wait), so a second 15000ms hang blows the 30s test cap before the per-call cap can fire, and
reports opaquely. That is the exact outcome D3 exists to prevent, so any test containing more than
two converted waits gets an explicit `test.setTimeout(60000)`. Affected: the test at `chaos-degradation.spec.ts:148` (three waits at :178/:183/:188), tests calling
`triggerHealthBanner`, and the three-search sequences in `chaos-scenarios.spec.ts`
(`:102/105/108` and `:219/222/225`).

**Rejected — leave the default 30s**: keeps every future failure opaque.
**Rejected — keep 5s**: too tight for CI contention; it is what made the first failure fire early.
**Rejected — raise the per-call cap instead of the test cap**: makes the race less likely without
removing it, which is the masking behaviour FR-006 explicitly disclaims.

## D4 — Predicate scoping

**Decision**: tighten predicates to include the query where a prior interaction's response could
otherwise satisfy the wait. Leave single-response success paths alone.

**Rationale**: promise-first registration widens the window backwards. With `retry: 1`, an errored
search fires a retry ~1s later. The highest-risk instance is `chaos-degradation.spec.ts:131/138`,
whose mock returns 500 on the first call and 200 on every later call: a listener for
`/tickers/search` + `status === 200` registered before `fill('GOOG')` can match the *AAPL retry*
rather than the GOOG response, and the test would then assert on a state that GOOG has not reached
yet — passing for the wrong reason.

**Applies to**: the URL-scoped ticker-search error-path sites, where a preceding interaction errored
and the predicate therefore needs query scoping (`q=GOOG`, per spec C2).

**Does not apply to**: success-path URL-scoped sites, which produce exactly one response (no
debounce, per R3). It also does **not** apply to the 6 status-only sites
(`chaos-helpers.ts:364/367/370`, `chaos-scenarios.spec.ts:102/105/108`) or the 3 `requestfailed`
sites (`chaos-scenarios.spec.ts:219/222/225`). An earlier draft's "applies to error-path sites"
wording captured those, which contradicted the spec's own exemption. They are an explicit accepted
risk under the FR-002 exception: they run under blanket failure routes where ANY failing response
legitimately signals "the API is failing", which is exactly what the health-monitor failure counter
keys on. Per-request sequencing is not what they assert, so matching a retry or a sibling endpoint's
failure is not a false pass. Residual risk, stated rather than hidden: those waits confirm "a
failure occurred", not "THIS search's failure occurred".

## D5 — Verification strategy

**Decision**: fault injection as the primary gate; contention as a secondary.

**Rationale**: the race does not reproduce on an idle dev box — pre-fix code passed 10/10 under
`--repeat-each=10 --workers=4`. Any strategy resting on local green measures nothing, which is
exactly the trap AR#1 flagged in the first draft's SC-002.

Injection makes the claim falsifiable: patch a delay between the action and the listener
registration in the pre-fix code and the test MUST fail. If it does not, the diagnosis is wrong and
the work stops. Only then does post-fix green mean anything.

Injection is only sound where the mock produces exactly one matching response, so the targets are
`ticker-search-gaps.spec.ts:22` (site `:38`) and `chart-edge-cases.spec.ts` (site `:72`). At the 6
status-only 503 sites and the 3 `requestfailed` sites, `retry: 1` plus the blanket
`page.route('**/api/**', …503)` keep supplying a matching response, so the listener resolves however
wide the injected gap is. Non-reproduction there is expected and is not a stop condition; those
sites are covered by contention only.

**Rejected — CPU throttling alone**: probabilistic, so a green run is weak evidence.
**Rejected — trusting CI over several PRs**: slow, and a 20% rate needs many runs to distinguish
"fixed" from "got lucky".
