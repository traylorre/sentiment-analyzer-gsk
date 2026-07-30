# Data Model: `waitForResponse` race sweep

**Not applicable.** This feature introduces no persisted entities, no schema, and no storage.

It changes Playwright test sources under `frontend/tests/e2e/`, adds one test helper module, adds
one scan script, and edits card entries in `CLEANUP-BOARD.html`. No DynamoDB table, no S3 object,
no API contract, and no product data structure is touched.

The nearest thing to a modelled entity is the classification the scan script assigns to each wait
call site, which exists only as scan output and is never persisted. The scanned population is every
`page.waitForResponse(...)` and every `page.waitForEvent('requestfailed'|'response')` under
`frontend/tests/e2e/`.

## Classification rule (FR-011)

Stated here and in the script itself, because SC-001's "RACY 0" would otherwise rest on an
undocumented heuristic:

- **`RACY`** — an awaited `page.waitForResponse(...)` or
  `page.waitForEvent('requestfailed'|'response')` whose **immediately preceding non-comment,
  non-blank line** performs a triggering action: `.fill(`, `.click(`, `.press(`, `.selectOption(`,
  `.clear(`, `.goto(`, `.reload(`, `.evaluate(`, `.type(`, `.check(`, `.tap(`, `.setInputFiles(`,
  `.dispatchEvent(`.
- **`PROMISE-FIRST`** — the wait is assigned to a variable before the triggering action and awaited
  after it.
- **`OTHER`** — neither shape. Requires human triage, and is printed under an explicit "requires
  human triage" banner rather than folded into the summary counts alone.

`.evaluate(` earns its place in the list from the tree, not from theory:
`error-visibility-search.spec.ts:158` triggers its request via
`retryButton.evaluate((el) => el.click())`.

The adjacency part of the rule is load-bearing. `chaos-scenarios.spec.ts:138` classifies as `OTHER`
rather than `RACY` only because an `await expect(...).toBeVisible({ timeout: 2000 })` sits between
its `page.reload()` and the wait.

## Counts

| Category | Baseline (inline sites) | Target (inline sites) |
|---|---|---|
| `RACY` | 27 | 0 |
| `PROMISE-FIRST` | 6 | 16 |
| `OTHER` | 1 (`chaos-scenarios.spec.ts:138`) | 1 (same site) |
| **Total** | **34** | **17** |

Plus, at target: exactly **18** `searchAndAwaitResponse(` call sites.

The total is **not** invariant, and an earlier draft's claim that it was fixed at 31 was wrong. The
18 helper-routed sites stop being inline wait call sites the moment they become
`searchAndAwaitResponse(...)` calls, and the helper contributes one internal wait in their place.
The target 16 breaks down as 6 pre-existing promise-first + 6 status-only inline conversions +
3 `requestfailed` inline conversions + 1 internal to the helper.
