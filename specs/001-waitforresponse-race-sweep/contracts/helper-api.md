# Contract: `searchAndAwaitResponse`

**Location**: `frontend/tests/e2e/helpers/search-helpers.ts`
**Consumers**: the 18 URL-scoped ticker-search wait sites across 3 spec files
(`chart-edge-cases.spec.ts` 4, `ticker-search-gaps.spec.ts` 9, `chaos-degradation.spec.ts` 5).

## Signature

```ts
export async function searchAndAwaitResponse(
  page: Page,
  searchInput: Locator,
  query: string,
  options?: {
    predicate?: (response: Response) => boolean;
    timeout?: number;
    clearFirst?: boolean;
  },
): Promise<Response>;
```

## Behaviour

1. Create the response promise **before** any interaction with the input. This ordering is the
   entire point of the helper and MUST NOT be reordered.
2. If `clearFirst` is true, `fill('')` before filling the query. Safe to bracket inside the single
   listener because an empty query never fetches (`ticker-input.tsx:37`,
   `enabled: query.length >= 1`). Playwright documents `locator.clear()` as equivalent to
   `fill('')`, so a caller replacing an existing `.clear()` with `clearFirst: true` is not changing
   behaviour.
3. `fill(query)`.
4. Await and return the matched `Response`.

**Required shape for the throw path.** The interactions MUST be structured so the promise cannot be
left unhandled if `fill()` throws. One of these two, and the implementation states which:

```ts
// Option A: try/finally, with the finally attaching the sink
const responsePromise = page.waitForResponse(predicate, { timeout });
let ok = false;
try {
  if (clearFirst) await searchInput.fill('');
  await searchInput.fill(query);
  ok = true;
} finally {
  // Reached on the throw path too. Without this the listener rejects at `timeout`
  // with nobody awaiting it, which surfaces against an unrelated test.
  if (!ok) responsePromise.catch(() => {});
}
return await responsePromise;

// Option B: sink attached at creation
const responsePromise = page.waitForResponse(predicate, { timeout });
responsePromise.catch(() => {});   // on the creation line; promise is never unhandled
if (clearFirst) await searchInput.fill('');
await searchInput.fill(query);
return await responsePromise;
```

Neither is optional. This is new code, so unlike the 6 already-correct inline sites there is no
FR-004 constraint against writing it properly.

## Defaults

| Option | Default | Rationale |
|---|---|---|
| `predicate` | `(r) => r.url().includes('/api/v2/tickers/search')` | Matches the 13 glob-pattern sites' existing behaviour. It does **not** match all 18: see "Sites requiring an explicit predicate" below |
| `timeout` | `15000` | FR-006 / research D3 — below the 30s test-level timeout so failures name the wait. Tests with more than two converted waits also need `test.setTimeout(60000)` for this cap to bind |
| `clearFirst` | `false` | Callers that clear are explicit about it |

## Sites requiring an explicit predicate

Five of the 18 URL-scoped sites are not covered by the default. The default was described in an
earlier draft as matching all 18; that was untrue.

| Site | Original predicate | Effect of the default | Required |
|---|---|---|---|
| `chaos-degradation.spec.ts:131` | `url.includes('/tickers/search') && r.status() === 500` | Drops the status check, **widening** the match. FR-002 forbids this | MUST pass the original predicate explicitly |
| `chaos-degradation.spec.ts:138` | `url.includes('/tickers/search') && r.status() === 200` | Same widening | MUST pass the original predicate explicitly |
| `chaos-degradation.spec.ts:178` | `url.includes('/tickers/search')` (no `/api/v2` prefix) | **Narrows** the match. Permitted, but must be called out per FR-002 | Declare the narrowing in the converting task |
| `chaos-degradation.spec.ts:183` | same as `:178` | Narrows | Declare the narrowing |
| `chaos-degradation.spec.ts:188` | same as `:178` | Narrows | Declare the narrowing |

## Guarantees

- **G1**: The listener is registered before the action. Callers cannot get the ordering wrong.
- **G2**: The listener never escapes as an unhandled rejection, **including when an interaction
  throws**. On the success path the promise is awaited and returned. On the throw path the helper
  has already attached a rejection sink (Behaviour, "Required shape for the throw path"), so the
  caller sees the interaction's own error and the listener's later timeout rejection is swallowed
  rather than surfacing against an unrelated test.

  An earlier wording, *"the returned promise is always awaited inside the helper"*, promised more
  than any code could deliver: if `searchInput.fill()` throws, control never reaches the await, so
  no amount of "awaited on every return path" covers the case. The guarantee is now stated as what
  the required shape actually produces. It is also the reason G2 is checkable: a reviewer looks for
  the `finally` sink or the `.catch(() => {})` on the creation line, rather than counting return
  paths in a function that has one.

  This is the internal guarantee FR-012 relies on. The inline sites are still not required to carry
  `try/finally`. They are existing code, several of them FR-004-protected, and their unhandled-
  rejection window only opens on a throw that fails the test anyway.
- **G3**: The helper does not widen a *supplied* predicate. A caller supplying a predicate gets
  exactly that predicate. The **default** predicate carries no such guarantee: it is URL-only, so it
  widens any site whose original predicate included a status check. Any caller whose original
  predicate included a status MUST supply that predicate explicitly (see the table above).

## Non-guarantees, stated so callers do not assume them

- **N1**: It does not detect cache-served queries. Calling it for a repeat of the same query inside
  the 30s `staleTime` window will hang until timeout, because no request is made
  (`ticker-input.tsx:38`). Callers in that situation must assert on the UI instead — see
  `ticker-search-gaps.spec.ts:242-247` for the existing precedent. Enforced by FR-010, not by code.
- **N2**: It does not disambiguate between a request and its `retry: 1` retry
  (`providers.tsx:48`). Where a prior interaction errored, the caller MUST supply a query-scoped
  predicate (FR-002 / research D4).
- **N3**: It is not used by the 9 non-search sites. `chaos-scenarios.spec.ts:102/105/108` and
  `chaos-helpers.ts:364/367/370` wait on status without a URL predicate and keep doing so, and
  `chaos-scenarios.spec.ts:219/222/225` use `page.waitForEvent('requestfailed')`, which takes no
  predicate at all. All 9 get inline promise-first conversion instead (FR-005), under the accepted
  risk recorded in the FR-002 exception.

## Usage

```ts
// URL-scoped search site (the common case)
await searchAndAwaitResponse(page, searchInput, 'AAPL');

// Clearing before the next query
await searchAndAwaitResponse(page, searchInput, 'GOOG', { clearFirst: true });

// Error-path site needing a query-scoped predicate (research D4)
await searchAndAwaitResponse(page, searchInput, 'GOOG', {
  clearFirst: true,
  predicate: (r) => r.url().includes('q=GOOG') && r.status() === 200,
});
```

## What this contract replaces

```ts
// Before — listener registered after the action that triggers it
await searchInput.fill('');
await searchInput.fill('GOOG');
await page.waitForResponse((r) => r.url().includes('/tickers/search'));
```
