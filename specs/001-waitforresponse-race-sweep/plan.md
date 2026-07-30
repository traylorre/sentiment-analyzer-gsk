# Implementation Plan: Sweep the act-then-wait `waitForResponse` race class

**Branch**: `001-waitforresponse-race-sweep` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-waitforresponse-race-sweep/spec.md`

## Summary

Convert 27 Playwright call sites from act-then-wait to promise-first ordering, tightening predicates
where earlier registration would let a stale `retry: 1` response satisfy the wait. Introduce one
predicate-parameterised helper for the 18 URL-scoped search sites; the other 9 (6 status-only 503,
3 `waitForEvent('requestfailed')`) convert inline. Commit the inventory scan so the "zero racy
sites" criterion is reproducible. Prove the fix by forcing the race with injected delay against pre-
and post-fix code at the two sites where injection is sound, because the race does not reproduce on
an idle machine.

## Technical Context

**Language/Version**: TypeScript 5.x (test sources only)
**Primary Dependencies**: `@playwright/test` ^1.57.0; no new dependencies
**Storage**: N/A
**Testing**: Playwright (customer dashboard suite, `frontend/tests/e2e/`), run via `npx playwright test`
**Target Platform**: Desktop Chrome (Chromium) only, matching `.github/workflows/pr-checks.yml`; CI on ubuntu-latest.
The other four configured Playwright projects (Mobile Chrome, Mobile Safari, firefox, webkit) are not
exercised by CI and are therefore not verified by this feature.
**Project Type**: web (frontend test infrastructure)
**Performance Goals**: N/A. The relevant metric is the Playwright job's attributable false-red rate, target 0.
**Constraints**: Test-only. No product code. No new AWS resources. GPG-signed commits. Playwright E2E job stays non-required.
**Test-level timeout**: `playwright.config.ts` sets no `timeout`, so the cap is Playwright's default 30000ms.
Any test with more than two converted waits gets an explicit `test.setTimeout(60000)` so FR-006's
15000ms per-call cap can actually bind (FR-006, research D3).
**Scale/Scope**: 27 conversions across 5 files, 1 new helper, 1 new scan script, 4 board-card edits
(2 cards corrected, 2 added).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution governs the sentiment-analyzer service (ingestion, inference, admin API, secrets,
DB access). This feature changes only Playwright test sources and a board file. Gate-by-gate:

| Gate | Applicability | Status |
|---|---|---|
| Functional requirements (ingest, dedupe, sentiment, admin API) | Not touched | PASS (N/A) |
| Availability / latency / throughput NFRs | Not touched | PASS (N/A) |
| Auth on management endpoints | Not touched | PASS (N/A) |
| Secrets not in source control | No secrets introduced; mocks contain synthetic tickers only | PASS |
| TLS in transit | Not touched | PASS (N/A) |
| SQL injection / unsafe DB access | No DB access | PASS (N/A) |
| Log redaction | No logging changes | PASS (N/A) |

Project-level gates that do apply:

| Gate | Status |
|---|---|
| GPG-signed commits, no `--no-verify` | Enforced by pre-commit and the block-no-verify hook |
| No new AWS resources | PASS — none |
| Two-dashboard rule: this is the **customer** dashboard (Next.js/Amplify), tested by `frontend/tests/e2e/*.spec.ts` via `npx playwright test`, not the HTMX/Lambda pytest suite | PASS — every touched file carries the `// Target: Customer Dashboard (Next.js/Amplify)` header |
| No unjustified fallback patterns | PASS — conversions remove a failure mode, add none |
| No silent failures | Strengthened: FR-006's explicit 15s cap makes a hung wait report as a `waitForResponse` timeout instead of an opaque test timeout |

**Result: PASS.** No violations, no complexity deviations to track.

## Project Structure

### Documentation (this feature)

```text
specs/001-waitforresponse-race-sweep/
├── spec.md              # Stage 1 + AR#1 appendix + Clarifications appendix
├── plan.md              # this file + AR#2 appendix
├── research.md          # decisions D1-D4 with rationale and rejected alternatives
├── data-model.md        # N/A rationale (no data entities)
├── contracts/
│   └── helper-api.md    # the helper's signature and behavioural contract
├── tasks.md             # Stage 7 + AR#3 appendix
└── quickstart.md        # how to run the verification procedures
```

### Source Code (repository root)

```text
frontend/
├── src/                                  # READ ONLY — no changes
└── tests/e2e/
    ├── helpers/
    │   ├── search-helpers.ts             # NEW — predicate-parameterised search-and-await
    │   └── chaos-helpers.ts              # MODIFIED — 3 sites (364/367/370), plus the `test`
│                                     #   import and the helper-side setTimeout raise (T012)
    ├── chaos-degradation.spec.ts         # MODIFIED — 5 sites
    ├── chaos-scenarios.spec.ts           # MODIFIED — 6 sites (3 waitForResponse, 3 waitForEvent)
    ├── chart-edge-cases.spec.ts          # MODIFIED — 4 sites
    ├── ticker-search-gaps.spec.ts        # MODIFIED — 9 sites
    ├── chaos-cross-browser.spec.ts       # UNCHANGED BUT AFFECTED (calls triggerHealthBanner at :35)
    ├── chaos-error-boundary.spec.ts      # UNCHANGED BUT AFFECTED (calls triggerHealthBanner at :63)
    └── error-visibility-search.spec.ts   # UNCHANGED — already correct

scripts/
└── scan-waitforresponse-race.py          # NEW — the committed inventory scan (FR-011)

CLEANUP-BOARD.html                        # MODIFIED — 2 cards corrected, 2 added
```

## Design Decisions

Full rationale and rejected alternatives in [research.md](./research.md). Summary:

- **D1 — Helper vs 27 inline conversions.** Both. One helper
  (`searchAndAwaitResponse`) for the 18 URL-scoped search sites; inline promise-first for the
  9 non-search sites (6 status-only 503, whose predicates must stay status-only per FR-005, and
  3 `waitForEvent('requestfailed')` sites, which take no predicate at all).
- **D2 — Response wait vs UI-outcome assertion.** Keep response waits. Switching to UI assertions
  would change what several tests prove (that a *request* was made and answered, which is what
  `recordSuccess()`/failure-counter behaviour keys on). Out of scope to redesign assertions during a
  race fix.
- **D3 — Timeout policy.** Explicit 15000ms on every converted call, plus
  `test.setTimeout(60000)` on any test containing more than two converted waits. Rationale in
  FR-006: it is a diagnosability choice, not a fix. 4 of the 5 observed failures hit the 30s
  *test-level* timeout, so a per-call cap below it converts opaque test timeouts into named
  `waitForResponse` timeouts. On multi-wait tests that reasoning inverts unless the test cap is
  raised: `chaos-degradation.spec.ts:196` runs about seven sequential waits inside one 30s budget,
  so the second hang would blow the test cap first and report opaquely.
- **D4 — Predicate scoping.** Tighten to include the query where a prior interaction's `retry: 1`
  response could otherwise match. Applies to the URL-scoped error-path search sites; success-path
  sites produce exactly one response and need no tightening. Does **not** apply to the 6 status-only
  or 3 `requestfailed` sites, which are an explicit accepted risk under the FR-002 exception.

## Implementation Phases

**Phase A — Scan artifact (FR-011).** Commit `scripts/scan-waitforresponse-race.py`, which
classifies every `waitForResponse` and `waitForEvent('requestfailed'|'response')` under
`frontend/tests/e2e/` as RACY / PROMISE-FIRST / OTHER and exits non-zero if any RACY remain. The
classification rule is documented in the script itself (FR-011), keyed on the immediately preceding
non-comment, non-blank line. Establishes the 27/6/1 baseline (34 total) before any edit, so SC-001
has a before-and-after.

The script is **standard-library only** and is written to a consumed interface, because the dependent
regression-guard feature wires it into a pre-commit hook and the required CI `Lint` job. Beyond the
RACY exit branch it must report files-scanned, exit non-zero on a zero-file scan, print findings to
stdout with remediation guidance, ignore file arguments in favour of its fixed root, and assert its
own interpreter floor. FR-011 states the obligations; T001 criteria 5, 6, 8, 12 and 13 make each one
checkable. Getting this wrong is not cosmetic: a venv-only or file-list-driven detector passes every
test in this feature and is inert in the one that consumes it.

**Phase B — Helper (FR-005).** Add `frontend/tests/e2e/helpers/search-helpers.ts` with a
predicate-parameterised `searchAndAwaitResponse`. Contract in `contracts/helper-api.md`.

**Phase C — Conversions (FR-001, FR-002, FR-010, FR-012).** Per file, smallest blast radius first:
`chart-edge-cases` (4) → `ticker-search-gaps` (9) → `chaos-scenarios` (6: 3 `waitForResponse` +
3 `waitForEvent`) → `chaos-degradation` (5) → `chaos-helpers` (3, plus the `triggerHealthBanner`
docstring correction required by FR-005). `chaos-helpers.ts` last because `triggerHealthBanner` is a
precondition of the whole chaos suite, so its change must be validated against already-converted
callers and against the two unedited callers (`chaos-cross-browser.spec.ts:35`,
`chaos-error-boundary.spec.ts:63`).

**Phase D — Verification (SC-003).** Fault injection first (a), then contention (b). Injection runs
only at the two sound targets, `ticker-search-gaps.spec.ts:22` (site `:38`) and
`chart-edge-cases.spec.ts` (site `:72`), where the mock produces exactly one matching response. It
is the falsifiable step: it must make pre-fix code fail *at those sites*. If it does not, the
diagnosis is wrong and the work stops for re-analysis rather than proceeding to a green-looking
result. Non-reproduction at the 6 status-only or 3 `requestfailed` sites is expected and is not a
stop condition; those are covered by contention only.

**Phase E — Board (FR-008, FR-009).** JSON surgery on `CLEANUP-BOARD.html`: `raw_decode` the array
after `const CARDS = `, edit the two cards in place, append the merge-required follow-up card, add
the `dynamodb_throttle` dead-branch card, re-dump, validate parse and count (118 → 120).

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Predicate tightening changes what a test proves | Medium | High | FR-002 requires per-site justification; AR#3 reviews each changed predicate |
| `triggerHealthBanner` conversion destabilises the chaos suite | Medium | High | Converted last, validated against already-converted callers; full chaos suite run before commit |
| Fault injection fails to reproduce on pre-fix code **at a single-response site** (`ticker-search-gaps.spec.ts:22` → site `:38`, `chart-edge-cases.spec.ts` → site `:72`) | Low | Critical | Stop condition. It would falsify the diagnosis. Scope matters: non-reproduction at the 6 status-only 503 sites or the 3 `requestfailed` sites is EXPECTED, because `retry: 1` plus the blanket `**/api/**` 503 route keep supplying a matching response, so it is not a stop condition there. Those 9 are covered by contention SC-003(b) only. `chaos-degradation.spec.ts:196` is not an injection target at all: PR #981 already converted its site. |
| A converted site is actually cache-served and now hangs | Low | Medium | FR-010; the one known instance is already documented at `ticker-search-gaps.spec.ts:242-247` |
| Board JSON surgery corrupts the file | Low | Medium | Parse-and-count validation after re-dump; the file is in git |

## Complexity Tracking

No constitution violations. One design choice warrants justification:

| Choice | Why needed | Simpler alternative rejected because |
|---|---|---|
| A helper *and* inline conversions, rather than one uniform treatment | The 27 sites are not homogeneous. 18 are URL-scoped to ticker search, 6 wait on any 503 with no URL predicate, and 3 are `waitForEvent('requestfailed')` waits that accept no predicate | Forcing all 27 through a search-scoped helper would narrow the 6 status-only predicates and could not express the 3 event waits at all, changing what those tests assert (AR#1 finding F-04) |

---

## Adversarial Review #2

Reviewer: an independent agent, run against the full artifact suite (spec, plan, research,
data-model, contract, quickstart) rather than any single document, and instructed to treat every
artifact claim as a suspect until checked against the tree. The orchestrator did not accept the
three CRITICAL findings on the reviewer's word: the missed `waitForEvent('requestfailed')` sites,
the stale fault-injection target, and the fabricated C1 import evidence were each re-verified
independently against the working tree before being written into the artifacts.

### Drift findings

| ID | Sev | What drifted | Resolution |
|---|---|---|---|
| D-01 | CRITICAL | SC-001 was arithmetically impossible. It claimed post-sweep PROMISE-FIRST 30 with the total invariant at 31, but the 18 helper-routed sites stop being inline call sites once they become `searchAndAwaitResponse(...)` calls, and the helper adds one internal wait. | SC-001 rewritten to RACY 0 / PROMISE-FIRST 16 / OTHER 1, total 17, with the 16 derived term by term, plus a requirement that exactly 18 `searchAndAwaitResponse(` call sites exist. data-model.md and quickstart section 1 corrected to match. |
| D-02 | CRITICAL | The fault-injection gate named `chaos-degradation.spec.ts:196` / "dismissed banner reappears" as its target. PR #981 already converted that site; it is promise-first at `:231-237` and protected by FR-004, so stashing this feature's work cannot restore the old shape. | SC-003(a) and quickstart section 3 retargeted to the two sites whose mock produces exactly one matching response: `ticker-search-gaps.spec.ts:22` (site `:38`) and `chart-edge-cases.spec.ts` (site `:72`). |
| D-03 | HIGH | SC-005 and quickstart section 6 said 118 → 119, but the work adds two cards. | 118 → 120 everywhere; FR-009 now authorises both cards by name. |
| D-04 | HIGH | FR-002 (tighten predicates) contradicted FR-005 (exempt `triggerHealthBanner`), with no stated resolution. | FR-002 gained an explicit accepted-risk exception covering the 6 status-only and 3 `requestfailed` sites, with the reason and the residual risk both stated. |
| D-05 | HIGH | C1's evidence was fabricated: seven importers claimed, six exist; `helpers/verification.ts` only mentions chaos-helpers in a comment; the two specs said to "import it today" contain zero references. | C1's evidence rewritten to the verified grep. The conclusion (new `search-helpers.ts`) is unchanged and strengthened. |
| D-06 | HIGH | The contract claimed its default predicate "matches the 18 URL-scoped sites' existing behaviour". False for 5 of 18: two carry status checks the default would drop (widening, which FR-002 forbids) and three use a shorter path (narrowing, permitted but undeclared). | Defaults rationale corrected to the 13 glob-pattern sites; G3 amended; a "sites requiring an explicit predicate" list added naming all five. |
| D-07 | MEDIUM | plan.md contradicted itself on board scope: Technical Context said "3 board-card edits", Project Structure said "2 cards corrected, 1 added". | Both now read "2 cards corrected, 2 added". |
| D-08 | MEDIUM | SC-001's "RACY 0" silently depended on an undocumented adjacency heuristic, which is the only reason `chaos-scenarios.spec.ts:138` classifies as `OTHER`. | FR-011 now states the classification rule in full and requires the script to document it; data-model.md states it too. |
| D-09 | MEDIUM | research D4's "Applies to" clause captured `chaos-scenarios.spec.ts:102/105/108`, which the spec exempts elsewhere. | D4's applies / does-not-apply lists rewritten to match the FR-002 exception. |

### New findings

| ID | Sev | Finding | Resolution |
|---|---|---|---|
| N-01 | CRITICAL | Three sites of the same act-then-wait class were missed: `chaos-scenarios.spec.ts:219/222/225`, each `fill(X)` followed by `page.waitForEvent('requestfailed', { timeout: 5000 })` under `api_timeout`, which uses `route.abort` and so fires with even less latency than `route.fulfill`. | Scope 24 → 27. Inventory table gains a `waitForEvent` row; FR-001 updated; the 3 join the inline-conversion group (9 inline, 18 helper-routed). |
| N-02 | HIGH | Injection is unsound on the 6 status-only and 3 `requestfailed` sites: `retry: 1` plus the blanket `**/api/**` 503 route mean a matching response keeps arriving, so the listener resolves whatever the injected gap. The Risk table treated any non-reproduction as a critical stop. | SC-003(a), quickstart section 3, and the Risk row now scope the stop condition to the single-response sites and state that non-reproduction elsewhere is expected. |
| N-03 | HIGH | Two files that call `triggerHealthBanner` (`chaos-cross-browser.spec.ts:35`, `chaos-error-boundary.spec.ts:63`) appeared in no file list and no verification command, so the helper's blast radius was under-verified. | Both added to the Source Code tree as UNCHANGED BUT AFFECTED, and to the quickstart smoke and contention commands, along with `chaos-scenarios.spec.ts`. |
| N-04 | HIGH | FR-006's timeout reasoning inverted on multi-wait tests. `chaos-degradation.spec.ts:196` runs about seven sequential waits inside the default 30000ms test cap, so the second 15000ms hang blows the test cap first and reports opaquely, the exact outcome FR-006 exists to prevent. | FR-006 keeps 15000ms per call and adds a mandatory `test.setTimeout(60000)` for any test with more than two converted waits. Mirrored into research D3 and this plan. |
| N-05 | MEDIUM | FR-012 was unimplementable as written, and the merged reference commit violated it: `chaos-degradation.spec.ts:231-236` leaves the promise unawaited if a `fill()` throws, and FR-004 forbids amending it. | FR-012 relaxed to a success-path await plus the helper's internal guarantee, with the reasoning stated so a future reader does not read it as an oversight. The "never as an unhandled rejection" absolute is removed. |
| N-06 | MEDIUM | Technical Context claimed a Chromium/Firefox/WebKit target, but every verification command and CI itself run `--project="Desktop Chrome"` only. | Target Platform narrowed to Desktop Chrome, with a note that the other four configured projects are not exercised by CI and are not verified here. |
| N-07 | LOW | The sampling method omitted that `pr-checks.yml` passes `--retries=0`, without which the ~20% rate is not re-derivable from other workflows (`nightly-e2e` does not pass it). | Flag recorded in the spec's Context section as part of the method. |

### Scope-definition lesson

The class was defined by method name (`waitForResponse`, and an explicit exclusion list that named
`waitForEvent('response')`) rather than by shape. That is why 3 of 27 sites were missed: they use
`waitForEvent('requestfailed')`, which is the same defect with a different call. The class is a
shape, a listener registered after the action that triggers it, and the committed scan (FR-011) now
encodes the shape rule so the definition cannot drift back to a list of method names.

### Gate

**0 CRITICAL, 0 HIGH remaining.**
