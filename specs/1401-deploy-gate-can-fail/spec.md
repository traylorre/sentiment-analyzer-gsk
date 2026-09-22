# Feature Specification: The preprod deploy gate can fail

**Feature Branch**: `card-8`

**Spec Number**: 1401 (allocated by the board on `cards/8.json`; not computed here)

**Created**: 2026-09-22

**Status**: Draft

**Input**: Card 8 — "the preprod deploy gate cannot fail: four layers each make it advisory, and a real bug already shipped through it"

**Run configuration**: `backwards_compatibility: none`, `security_tier: S2`, `operational_rigour: full`, `audience: maintainer`, `allow_git_log: false`, `md_is_canonical: true`

## Context

The `test-preprod` job in `.github/workflows/deploy.yml` runs 32 Playwright tests against the
deployed preprod frontend and reports success no matter what they do. Deploy run `30665082067`
is the proof: a genuine defect — GitHub OAuth buttons missing from preprod — failed three
consecutive times and the pipeline printed `Playwright sanity tests passed` and wrote
`"ready_for_production": true`.

Four independent layers each make the gate advisory. Any one alone is sufficient, so all four
must close or the gate stays advisory.

Card 8 requires the defect census be **regenerated against the current tree** rather than
trusted from the 2026-08-01 stow. It was. What follows is measured on this branch; the drift
from the stowed record is recorded under "Drift since the stow", and it is not cosmetic.

### The four layers, re-measured

| # | Layer | Measured location, this tree |
|---|---|---|
| L1 | All 16 `sanity.spec.ts` tests skip | `frontend/tests/e2e/helpers/data-api-guard.ts:15` hardcodes `http://127.0.0.1:8000`; `frontend/playwright.config.ts:6,51-79` omits the `webServer` block entirely when `PREPROD_FRONTEND_URL` is set, so nothing listens on 8000. **Confirmed by execution**: with `PREPROD_API_URL` pointed at a server returning 503 for OHLC, the three guarded tests in `sentiment-visibility.spec.ts` went from 3 skipped to 3 failed, each naming the observed 503 |
| L2 | The captured exit code is `tee`'s | `deploy.yml:1676-1677` pipes to `tee` then reads `$?` |
| L3 | The computed result is never read | `steps.playwright-sanity.outputs.passed` is written at `deploy.yml:1681,1685,1689` and read nowhere |
| L4 | Unconditional `exit 0` | `deploy.yml:1694`, commented "sanity tests are non-blocking for now" |

**L1 detail.** The guard probes `http://127.0.0.1:8000` once per worker and caches the result.
Against preprod there is no local API server — `playwright.config.ts:51` drops `webServer`
precisely because the target is remote — so the probe's `fetch` throws, `catch` at
`data-api-guard.ts:70-72` sets `_dataApisAvailable = false`, and every test whose `beforeEach`
calls `skipWithoutDataApis` skips green. Three files carry that call: `sanity.spec.ts:8`,
`chart-zoom-data.spec.ts:16`, `sentiment-visibility.spec.ts:10`. The gate runs the first of
them, so 16 of its 32 tests are structurally incapable of failing.

The same 11 lines carry a second defect the refuters logged separately: `data-api-guard.ts:62-72`
coerces *any* probe outcome — 500, auth regression, network blip, empty-but-200 — into the single
message "APIs not configured", asserting a cause it never established.

**L2 detail.** The `test-preprod` job spans `deploy.yml:1338-1736` and has **no `defaults:`
block** (the two in the file, at `:772` and `:1909`, belong to `deploy-preprod` and `deploy-prod`),
and the workflow has no top-level `defaults:`. So the step shell is GitHub's default
`bash -e {0}`, `pipefail` is unset — the file's only `set -o pipefail` is at `:800`, in a
different job — and `PLAYWRIGHT_EXIT_CODE=$?` after `... | tee playwright-output.txt` captures
`tee`'s status, which is 0 whenever `tee` can write its file. `PLAYWRIGHT_EXIT_CODE` is therefore
always 0, the `elif [ $PLAYWRIGHT_EXIT_CODE -eq 124 ]` timeout branch at `:1683` is unreachable,
and `passed=true` is written unconditionally.

**L3 detail.** `deploy.yml:1638` shows the pattern the repo already uses correctly:
`Check Integration Test Results` reads `steps.integration-tests.outputs.passed != 'true'` and
`exit 1`s at `:1650`. `Check Unit Test Results` does the same at `:472-476`. Playwright has no
equivalent step. The only reader of the `playwright-sanity` step's outputs anywhere in the file
is `:1697`, and it reads `.skipped`, not `.passed`.

**L4 detail.** `deploy.yml:1694` is `exit 0` with no condition above it.

### Related and separate: the 22 `@external-api` tests run in zero CI contexts

Re-verified and unchanged. `gh secret list` on this repo returns exactly four secrets —
`CLAUDE_CODE_PAT`, `NEWSAPI_SECRET_ARN`, `PREPROD_JWT_SECRET`, `REPO_PAT`. **`TIINGO_API_KEY`
and `FINNHUB_API_KEY` still do not exist**, and `nightly-e2e.yml:71-72` references them. Both
Playwright jobs in `pr-checks.yml` exclude the tag (`:539`, `:621`, `--grep-invert "@external-api"`).

This is **operator work, not code work**: no change in this repository creates a GitHub secret.
It is carried to the board rather than fixed here.

### Drift since the stow, measured

Four findings, each material:

1. **`stash-A` is already applied in the tree.** All three of its hunks are present and live:
   `nightly-e2e.yml:67` is `--retries=0`, `playwright.config.ts:14` is `retries: 0`, and
   `sentiment-visibility.spec.ts:41-44` carries the `throw`. `git apply --check` on
   `specs/stash-triage/stash-A-e2e-retries-falsepass.patch` fails all three hunks for that reason.
   The card's plan — "fix D2 before applying stash-A" — is superseded: **the broken helper is not
   waiting in a patch, it is live in the tree**, so D2 is a fix-in-place, not a pre-apply repair.
2. **`deploy-prod` is `if: false`** (`deploy.yml:1895`, "TEMP: Skip production"), as are
   `build-sse-image-prod` (`:1739`) and `build-dashboard-image-prod`. The consequence chain the
   stow described — advisory gate → `ready_for_production: true` → prod — is currently severed at
   the last hop. The gate still lies, preprod still receives unvalidated deploys, and the lie is
   still written to the validation artifact; only the blast radius has shrunk, and it restores
   itself the moment prod is re-enabled.
3. **Line numbers drifted by one to four**: L4's `exit 0` is at `:1694`, not `:1695`; the tee
   pipeline is `:1676-1677`, not `:1674-1678`; `Check Integration Test Results` is `:1638-1650`.
   `ready_for_production` is at `:1718`, within a `Create Validation Metadata` step whose `if`
   (`:1708`) tests the integration tests **only**.
4. **`@radix-ui/react-dismissable-layer` is still pinned at `1.1.11`**
   (`frontend/package-lock.json:2252`), the exact version D3's measurement was taken against, so
   D3's mechanism stands unchanged.

### The spec-number allocator is stale in this repository

Found while minting. `.specify/scripts/bash/create-new-feature.sh` in this repo is the
**pre-card-126** version: it computes `max+1` from the worktree's own view and then runs
`git checkout -b`, which from a card worktree would both misnumber the spec and move the Dynamo
off `card-8`. The card-aware allocator specified by `~/dotfiles/specs/118-spec-number-allocation`
exists at `~/dotfiles/.specify/scripts/bash/create-new-feature.sh` and was never propagated into
this repository's vendored `.specify/`.

This spec was minted with the correct allocator, invoked from this worktree, which read
`specNumber: 1401` from `cards/8.json` and created `specs/1401-deploy-gate-can-fail/` without
touching the branch. The stale copy is carried to the board as a separate card; it is not card
8's work, but it is a live trap for every future Dynamo in this repo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A broken preprod deploy fails the pipeline (Priority: P1)

A change ships that breaks the preprod frontend in a way the sanity or auth suite detects. The
`test-preprod` job goes red, no validation artifact claiming `ready_for_production` is produced,
and the pipeline stops. Nobody has to read a log to find out.

**Why this priority**: this is the card. The defect it names is that this scenario does not
currently happen; run `30665082067` is the counter-example on record.

**Independent Test**: induce a failing assertion in the suite the gate runs, and require the job
to fail. Because none of the four layers can be exercised locally, each is tested at its own seam
(see "Verification" below), and the four together are argued rather than run.

**Acceptance Scenarios**:

1. **Given** a Playwright test that fails against preprod, **When** `test-preprod` runs,
   **Then** `PLAYWRIGHT_EXIT_CODE` is Playwright's own non-zero code, `passed=false` is written,
   a `Check Playwright Sanity Results` step reads it and `exit 1`s, and the job fails.
2. **Given** `timeout 300` kills the Playwright run, **When** the exit code is captured,
   **Then** it is 124 and the timeout branch — currently unreachable — reports `reason=timeout`.
3. **Given** all 32 tests pass, **When** the check step runs, **Then** it is a no-op and
   `Create Validation Metadata` writes `ready_for_production: true` honestly.
4. **Given** the preprod Amplify URL is absent, **When** the gate runs, **Then** the job fails
   rather than recording a skip as a pass: a deploy whose frontend URL never materialised has not
   been validated.

---

### User Story 2 — The 16 sanity tests actually execute against preprod (Priority: P1)

The sanity suite runs against the deployed preprod frontend instead of skipping on a probe to a
localhost port that nothing in the remote context is listening on.

**Why this priority**: L1 alone makes half the gate's tests incapable of failing, so closing
L2-L4 without it would produce a gate that can fail on 16 tests and still cannot on the other 16.
The two P1 stories are one gate.

**Independent Test**: run the suite with `PREPROD_FRONTEND_URL` and `PREPROD_API_URL` set against
any reachable deployment and assert the sanity tests report a pass or a failure, never a skip.

**Acceptance Scenarios**:

1. **Given** `PREPROD_API_URL` is set, **When** the guard probes, **Then** it probes that URL and
   not `127.0.0.1:8000`.
2. **Given** the guard is in remote mode and the probe does not yield candles, **When** a guarded
   test starts, **Then** it **fails** with the observed cause, rather than skipping green. In
   preprod, absent market data is a defect, not a configuration note.
3. **Given** the guard is in local mode (no `PREPROD_API_URL`), **When** the probe fails,
   **Then** it still skips — nightly and developer runs are unchanged — but the skip message
   states what was actually observed rather than asserting "APIs not configured".

---

### User Story 3 — The rate-limit retry helper works (Priority: P2)

`sentiment-visibility.spec.ts`'s `searchAndSelectTicker` retries on a 429 from the search
endpoint and reports honestly when it gives up.

**Why this priority**: D2. The helper is live in the tree and broken four ways; it converts a
rate-limited run into a confident, wrong "did not appear" failure. P2 because the tests it serves
are `@external-api` and currently execute nowhere, so it is latent — but it becomes live the
moment the vendor secrets exist, and it is in the card's work items.

**Independent Test**: unit-level reasoning against the listener-registration order plus a
strict-mode probe on a two-match ticker prefix.

**Acceptance Scenarios**:

1. **Given** the first search request returns 429, **When** the helper runs, **Then** the
   response listener is already registered and the retry happens. The listener was registered at
   `:23`, after `fill()` at `:16`. **Measured, 6 samples**: the search request reaches the network
   at 33-61 ms while `fill()` returns at 38-69 ms, so the old registration point was **4-9 ms
   after the request had already left the page**, and any response landing in that window reaches
   zero listeners. A 429 from a rate limiter is the fastest response there is, because it does no
   upstream work.
   **Correction to the stow's record**: it states this as a certain miss ("a first-attempt 429 is
   dispatched to zero listeners"). It is a narrow race, not a certainty — a probe of the old
   ordering did observe the 429 when the response came back slower than the window. The fix stands
   because it closes the window outright at no cost, but the mechanism is probabilistic.
2. **Given** a ticker whose symbol prefixes another (`AAPL`/`AAPLW`), **When** the helper waits
   for the option, **Then** it resolves the exact symbol rather than throwing a strict-mode
   violation that the `catch` reports as "did not appear". **Measured**: against a two-row result
   set, `getByRole('option', { name: /AAPL/i }).waitFor()` fails with
   `strict mode violation: ... resolved to 2 elements`.
3. **Given** the helper is called twice on one page (`:101`, `:107`), **When** it returns,
   **Then** it has removed its listener.
4. **Given** the helper exhausts its attempts, **When** it throws, **Then** the message states
   the true count. `maxRetries = 3` yields 3 attempts and 2 retries; the message says
   "after 3 retries".

---

### User Story 4 — The dialog-dismissal flake is removed at its root (Priority: P3)

`dialog-dismissal.spec.ts`'s "user menu: outside click closes" no longer latches into a permanent
stuck state on a loaded runner.

**Why this priority**: D3, GitHub issue #950. Root-caused to `@radix-ui/react-dismissable-layer@1.1.11`
attaching its `pointerdown` dismissal listener inside a `setTimeout(…, 0)`, one macrotask after
the layer mounts. `force: true` collapses the margin between registration and the outside click
from 65.0-138.4 ms to 4.7-11.4 ms, roughly tenfold; with a 50 ms induced delay, force gives 6/6
stuck and no-force 0/5. P3 because it is a one-line change to a test that is not on the deploy
gate's path.

**Independent Test**: the test passes without `force: true`. **Do not attempt to reproduce the
flake**: 134 executions across repeat counts, worker counts, CPU stressors, Mobile Chrome and the
full suite never reproduced it, and non-reproduction is not absence.

**Acceptance Scenarios**:

1. **Given** `frontend/tests/e2e/dialog-dismissal.spec.ts:168`, **When** the trigger is clicked,
   **Then** the click is an ordinary `click()` preceded by the existing
   `scrollIntoViewIfNeeded()`, and the test passes.

## Requirements *(mandatory)*

### Functional

- **FR-001** The captured Playwright exit code MUST be Playwright's own, not `tee`'s. (L2)
- **FR-002** `steps.playwright-sanity.outputs.passed` MUST be read by a step that exits non-zero
  when it is not `true`, mirroring `Check Integration Test Results`. (L3, L4)
- **FR-003** A skipped Playwright run (no Amplify URL) MUST fail the job, not pass it. (L4)
- **FR-004** `Create Validation Metadata` MUST NOT write `ready_for_production: true` unless the
  Playwright gate passed. Its `if` MUST state that condition explicitly rather than relying on
  step ordering.
- **FR-005** The data-API guard MUST probe the preprod API when running against preprod. (L1)
- **FR-006** In remote mode the guard MUST NOT skip; an unavailable data API MUST fail. (L1)
- **FR-007** The guard MUST report the cause it observed, never a cause it assumed, in both modes.
- **FR-008** The 429 retry helper MUST register its listener before the request it watches for.
- **FR-009** Option locators in the suites the gate runs MUST be unambiguous under Playwright
  strict mode. They are matched by the row's own `id="ticker-option-<symbol>"`
  (`ticker-input.tsx:200`), which is exact and cannot be prefix-masked.

  **Anchoring the accessible name does not work, and this was measured rather than assumed.**
  The symbol and company spans (`ticker-input.tsx:215-217`) are adjacent with no whitespace text
  node between them — the gap is the `ml-2` CSS margin, which contributes nothing to the
  accessible name — so Chromium computes the option's name as `"AAPLApple Inc."`, not
  `"AAPL Apple Inc."`. A first attempt at this spec used `/^AAPL\b/i`; it matches **zero**
  options, because the character after `AAPL` is `A`, a word character. The probe that caught it
  reported `anchored /^AAPL\b/i = 0` against `bare /AAPL/i = 2`. Do not reintroduce a name-anchored
  locator here: symbol and company name run together, so no case-insensitive pattern can reliably
  find the boundary.
- **FR-010** The retry helper MUST remove its listener, and MUST state its true attempt count.
- **FR-011** `dialog-dismissal.spec.ts:168` MUST NOT pass `force: true`.

### Non-functional

- **NFR-001** No new skip, `continue-on-error`, `|| true` or `if: always()` may be introduced on
  the gate path. The card exists because of that class of construct.
- **NFR-002** Behaviour of `pr-checks.yml` and `nightly-e2e.yml` is unchanged. This spec touches
  the preprod gate and the tests it runs, nothing else. Local-mode guard behaviour stays a skip
  so nightly does not go red for a condition no code change can fix.

### Out of scope

- Creating `TIINGO_API_KEY` / `FINNHUB_API_KEY`. Operator action; carried to the board.
- Re-enabling `deploy-prod`. It is `if: false` by a standing decision this card did not take.
- `stash-B` (the 331 KB doc-audit patch). It amends documents that have changed since it was cut
  and the card requires a fresh refuter pass over it; that is a distinct piece of work with a
  distinct risk profile, and bundling it with a gate change would make both harder to review.
- The wider failure-hiding census the refuters logged (210 Python skip sites, `conftest.py`'s
  filename auto-marking, `xfail_strict` unset, `make validate`'s neutered `pip-audit`/`bandit`,
  the frontend unit suite never running in CI, the `summary` job at `:2141` that only echoes).
  Already carded as "Systemic failure-hiding: gates that cannot fail".

## Verification

None of the four layers can be exercised on this host: there is no preprod deployment reachable
from here, `frontend/node_modules` is not installed in this worktree, and the gate only runs
inside `test-preprod`. Verification is therefore per-seam and is stated as such rather than
claimed as an end-to-end run.

| Claim | How it is checked here | Limit |
|---|---|---|
| L2 fix captures the right code | `bash` harness reproducing `set +e` + pipe-to-`tee` under `bash -e` with no `pipefail`, asserting the old form yields 0 and the new form yields the command's code and 124 on timeout | Not run inside Actions |
| L3/L4 fix gates | YAML parses; the new step's `if` is asserted against the four output states (pass, fail, timeout, skipped) | Requires a real run to observe |
| L1 fix | Guard's branch behaviour asserted by reading; `PREPROD_API_URL` confirmed already wired as a convention at `deploy.yml:1577` | Needs a reachable preprod to run |
| D2 fix | Measured against the running app with a mocked search endpoint: listener/request timing over 6 samples; strict-mode violation reproduced on the old locator; new locator resolves to 1, waits and clicks | The helper's own tests need market data, so the mechanism was probed rather than the shipped function |
| D3 fix | **Run**: the test passes without `force: true`, 8/8 under `--repeat-each=8`. Radix mechanism re-confirmed against the installed tree: `@radix-ui/react-dismissable-layer` is 1.1.11 and `dist/index.mjs:165-166` still registers the pointerdown listener inside `setTimeout(..., 0)` | Flake is not reproducible by design; this confirms the click lands, not that the flake is gone |

What was actually executed on this host: `npm ci` (574 packages), `tsc --noEmit` exit 0, `eslint`
exit 0 on all four changed files, the L2 shell harness, `dialog-dismissal.spec.ts` 8/8,
`sentiment-visibility.spec.ts` in both guard modes (3 skipped local, 3 failed remote), and four
throwaway locator/timing probes since deleted.

## Risks

- **R-1 (accepted, and the point of the card).** Turning the gate on can block deploys. If the
  preprod deployment does not serve real OHLC data, the 16 sanity tests will now fail instead of
  skipping, and `test-preprod` will go red. That is the correct behaviour — it is the difference
  between a gate and a comment — but it is a behaviour change the operator should expect on the
  next deploy rather than discover. It cannot be measured from this worktree. Flagged in the
  final report.
- **R-2.** `sanity.spec.ts` has never actually executed against preprod, so its assertions are
  unproven at that target. Its first real run may surface test defects rather than product
  defects. FR-009 removes the one such defect already identified (unanchored option regex); others
  may exist. The honest response to a red gate is to read the failure, not to re-add the skip.

## Success Criteria

- **SC-001** Each of the four layers has a named, committed change closing it, and no layer is
  closed by a construct that reintroduces advisory behaviour.
- **SC-002** A failing Playwright test in `test-preprod` produces a failed job.
- **SC-003** `ready_for_production: true` is written only when both the integration tests and the
  Playwright gate passed.
- **SC-004** D2's four defects and D3's one are fixed in the tree.
- **SC-005** The census in this document is measured against this branch, and every file:line in
  it resolves.
