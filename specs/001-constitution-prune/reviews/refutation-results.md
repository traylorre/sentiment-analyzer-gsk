# Refutation results

Six independent refuters re-verified the 30 claims in `STOW-POINT.md`. The author did not grade
its own work. All six reported.

## Verdict summary

| # | Claim | Verdict |
|---|---|---|
| 1 | `mock_aws` 36 across 7 files | **REFUTED** — 38 across 8 |
| 2 | `backend "s3"` at `main.tf:20` | CONFIRMED |
| 3 | line 39 log-redaction; `sanitize_for_log` absent | CONFIRMED |
| 4 | 267 `sanitize_for_log` in `src/` | CONFIRMED, mislabelled — ~238 call sites |
| 5 | 11 bullets at 33-43 | CONFIRMED, misleading — 10 requirements |
| 6 | exactly four heading styles | counts CONFIRMED, completeness **REFUTED** |
| 7 | lines 96/104 the only invisible headings | **REFUTED** — 22, not 2 |
| 8 | section 5 duplicated | CONFIRMED |
| 9 | no ECS/instance/autoscaling | CONFIRMED, extended |
| 10 | exactly one health route | **REFUTED** — two |
| 11 | version at 641, log 578-588 | CONFIRMED |
| 12 | residue grep returns 1 false positive | count CONFIRMED, conclusion **REFUTED** |
| 13 | 641 lines / 6000 words / 23-row table | **CONFIRMED, zero delta on all 23 rows** |
| 14 | zero cross-section references | **REFUTED** — 13 in the amendment log alone |
| 15 | L58 and L146 dismissals correct | **CONFIRMED**, with better evidence |
| 16 | `model_version` 7 sections, SAST 5 | sections CONFIRMED, SAST count wrong, sample presented as measurement |
| 17 | seam test passes, split viable | **REFUTED** |
| 18 | C-002 not a timing race | facts CONFIRMED, **inference REFUTED** |
| 19 | click geometry outside the menu | **CONFIRMED**, measured |
| 20 | component has no dismissal override | CONFIRMED |
| 21 | did not reproduce locally | CONFIRMED — 129 further runs, never failed |
| 22 | the `alert` node is a toast live region | **REFUTED** |
| 23 | retry posture | CONFIRMED, empirically proven in a real run |
| 24 | deploy gate runs zero sanity tests | **CONFIRMED AND UNDERSTATED** |
| 25 | 21 skip/fixme occurrences | **REFUTED** — 23 matches, and `fixme` is 0 |
| 26 | 3 files, ~22 tests | **CONFIRMED exactly** |
| 27 | only the `test.skip` was the defect | **PARTIALLY REFUTED** — my fix is broken |
| 28 | `retries: 0` correct reading | reading CONFIRMED, impact **REFUTED** |
| 29 | fixtures beat API keys | **REFUTED**, see contradiction below |
| 30 | caveman output vs input | conclusion CONFIRMED, reasoning **REFUTED** |

---

## THE HEADLINE: a real bug shipped to preprod behind four layers of failure-hiding

Claim 24 is confirmed and badly understated. Deploy run `30665082067` **reported success**. Its
`Run Playwright Sanity Tests` step:

```
Running 32 tests using 4 workers
  1 failed
    [Desktop Chrome] › tests/e2e/auth.spec.ts:24:7 › Authentication Flow › should show OAuth buttons
  16 skipped
  15 passed (26.6s)
Playwright sanity tests passed
```

A genuine defect — GitHub OAuth buttons missing from preprod — failed three times (retries were
live at 2) and the pipeline printed "passed" and wrote `"ready_for_production": true`
(`deploy.yml:1712-1719`). `deploy-prod` depends on this job (`:1898`).

**Four independent layers, any one of which alone makes the gate advisory:**

1. **All 16 sanity tests skip.** `data-api-guard.ts:15` hardcodes `http://127.0.0.1:8000`;
   `playwright.config.ts:6,49-51` omits the `webServer` block entirely when
   `PREPROD_FRONTEND_URL` is set, so nothing listens on 8000.
2. **The exit code is `tee`'s, not Playwright's.** `deploy.yml:1674-1678` pipes to `tee` then
   reads `$?`. The step shell is `/usr/bin/bash -e {0}` with **no `pipefail`** and no top-level
   `defaults:`. `PLAYWRIGHT_EXIT_CODE` is always 0. The `-eq 124` timeout branch is dead code.
3. **The computed result is never read.** `steps.playwright-sanity.outputs.passed` appears
   nowhere. Compare `Check Integration Test Results` (`:1640-1650`, `exit 1`) and
   `Check Unit Test Results` (`:472-476`, `exit 1`). There is no equivalent for Playwright.
4. **`deploy.yml:1695` — `exit 0` unconditionally**, commented "sanity tests are non-blocking for
   now".

## The 22 guarded tests run in ZERO CI contexts

- **pr-checks** (`:449`) uses `--grep-invert "@external-api"`; all three files carry that tag, so
  they are never collected. Real run 30665082082: 30 spec files, 154 tests, no sanity tests.
- **nightly-e2e** is the only workflow selecting them, and five consecutive runs show
  `Running 22 tests / 22 skipped` (runs 30607255780, 30515839975, 30424876942, 30325010275,
  30233864892).

## Contradiction between refuters, resolved

Group F reported that CI already has real vendor keys, citing `nightly-e2e.yml:71-72`. Group E
checked whether the secrets those lines reference actually exist:

```
TIINGO_API_KEY:
FINNHUB_API_KEY:
```

empty in the nightly run env block, and `gh secret list` returns only `CLAUDE_CODE_PAT`,
`NEWSAPI_SECRET_ARN`, `PREPROD_JWT_SECRET`, `REPO_PAT`. **Neither key exists.**

**Group E is right.** F verified that the workflow *references* the secrets; E verified whether
they *resolve*. The YAML is wired to secrets that were never created, so nightly has executed zero
tests for at least five consecutive nights while reporting green.

This makes my claim 29 wrong for a different reason than F gave: the choice is not
fixtures-versus-keys, because the keys do not exist.

---

## Cross-reference map: the central claim is refuted

I quoted constitution lines 578-588 in my own map and still reported zero cross-section
references. Those lines name other sections **by their exact heading strings**, and five use the
word "section" literally. 13 pointers across 5 target sections (7-Testing, 8-Git,
SensitiveSecDocs, 9-TechDebt, 10-LocalSAST).

**Self-refutation:** `L576` says "Maintain a Version and Last Amended date **at the bottom**",
pointing at `L641`, which my own table places in section 10. My map claims at its line 116 that
"removing it cannot silently break a pointer elsewhere", and elsewhere says L641 "must go".

**Two sections are 100% inbound-dependent.** `Acceptance Criteria (serverless stack)` (104-112):
7 of 7 bullets point into 57-95 and 96-103. `Acceptance Criteria (Minimal)` (387-395): 6 of 6
point into sections 1, 3 and 4.

**Contradictions the map missed:**

- Two competing pre-push checklists. `L624` is titled `Pre-Push Checklist (updated)`, superseding
  `L411`. L413-416 calls `ruff check`/`ruff format` and drops SAST; L627-630 calls
  `make validate`/`make test-local` and drops the lint calls.
- Two normative output schemas for the same object: `L47` has `text_snippet?: string`; `L380` has
  `received_at: ISO8601` and types `score` differently.
- Bidirectional 5b↔6 coupling: L91 → "the dashboard" (L120); L140 → "the metrics backend" (L91).
- `L153` [6-Obs] depends on `/v1/sources` defined at `L374` [Interfaces], 221 lines away.
- Section 10's required patterns (L610-614) are unreadable without L31, L39 and L33-43.
- `the retention policy` at L399 is dangling, defined nowhere.

**The term table was a sample presented as a measurement.** Eight terms tie or beat SAST's span;
three beat `model_version`'s: `secrets` 9 sections, `acceptance criteria` 8, `approval` 8, `CI` 7,
`IAM` 6, `dashboard` 5 (25 hits, more raw mass than either term I singled out).

**Revised seam verdict: a by-section split is not safe as-is.** Prerequisites: delete the
amendment log and version footer together as one atomic change including L576; merge each
Acceptance Criteria block back into the section it tests; reconcile the two pre-push checklists;
resolve the L47/L380 schema divergence.

**What held:** both my dismissals were upheld (L58 points at `docs/deployment/`, which exists and
I never verified; L146 is intra-section at both granularities). Segmentation is sound, all 23
boundaries verified. **Trap 3 stands** — the refuter's own detector missed L96/L104 until
hardcoded, and `ExpressionAttributeNames` sits at L99 inside the first of them.

---

## C-002 root cause found, and my reasoning was a non-sequitur

**The mechanism.** `@radix-ui/react-dismissable-layer@1.1.11`, `dist/index.mjs:165-167`:

```js
const timerId = window.setTimeout(() => {
  ownerDocument.addEventListener("pointerdown", handlePointerDown);
}, 0);
```

The dismissal listener attaches one macrotask **after** the layer's effect flushes. An outside
`pointerdown` arriving before that is never seen, and because no further pointer events occur, the
menu stays open **forever**. A one-shot missed-event race latches into a permanent stuck state.

**My inference was false.** I argued "Playwright polled 5000ms across 9 attempts, therefore not a
race". A latching missed-event race looks exactly like a hard 5-second failure. The facts were
right; the conclusion did not follow, and it steered the whole diagnosis.

The "9 ×" is genuine: nine poll records spanning 4901ms with Playwright's standard backoff
`[2.9, 102.7, 253.4, 508.6, 1004.9, 1003.4, 1007.0, 1018.2]`. The outside click's before/after DOM
payloads are 8 bytes each, so it mutated nothing.

**`force: true` is the trigger, measured.** Margin between listener registration and the outside
pointerdown:

| Click | Margin |
|---|---|
| `click({ force: true })` | **4.7-11.4 ms** (8 samples) |
| `click()` | 65.0-138.4 ms (5 samples) |

`force: true` collapses the safety margin roughly **10×**. With a 50ms induced registration delay:
force gives 6/6 stuck, no-force gives 0/5 stuck. On a 2-vCPU runner with 4 workers and a dev
server compiling, losing 11ms in a macrotask queue is trivial.

**Fix: drop `force: true` at `dialog-dismissal.spec.ts:168`.** My recommendation was right; my
stated reason was wrong.

**My two mechanisms are both refuted:**

- *`pointer-events: none` blocks the click.* Refuted. A capture-phase probe recorded the
  pointerdown reaching `document` on every run. `body` does carry
  `style="pointer-events: none"` (Radix modal) and `elementFromPoint(640,360)` returns `HTML`, but
  the event is still delivered. The listener simply is not there yet.
- *A force click lands a pointerdown Radix attributes to inside the layer.* Refuted by the Radix
  source: `isPointerInsideReactTreeRef` is set only by `onPointerDownCapture` on the layer
  element, and the layer does not exist when the trigger's pointerdown fires — it mounts *because*
  of it. It is also unconditionally reset at the end of every `handlePointerDown`.

**Claim 22 refuted.** The empty `alert` node is Next.js's `__next-route-announcer__` in a shadow
root, not a toast live region. And a separate finding falls out of that: **`<Toaster />` is mounted
nowhere in the app** — `grep -rn "Toaster"` excluding `node_modules` returns 0 hits. Three hooks
`import { toast } from 'sonner'`, so every `toast()` call renders nothing. Carded separately.

**Claim 21 confirmed and extended.** 129 further executions across conditions I never tried
(40 repeats at 12 workers, 24 CPU stressors, Mobile Chrome, the full e2e suite) never reproduced
the assertion. Non-reproduction is not absence.

**Claim 19 confirmed by measurement.** Viewport is 1280x720; menu settles at roughly x 12-268,
y 434-662. The click at (640, 360) is far outside.

**Two triggers do exist in the DOM** (`desktop-nav.tsx:130`, `header.tsx:68`) with distinct Radix
ids, but only one is visible at 1280px, so `visible=true` resolves to 1 and the duplicate did not
cause this. Note `signin-interaction.spec.ts:39` targets the other one.

**My "CI backend was erroring" claim is refuted for this test.** Its own network log holds three
requests: `401 POST /api/v2/auth/refresh`, `201 POST /api/v2/auth/anonymous`,
`404 GET /api/v2/runtime`. No OHLC call, no `ResourceNotFoundException`. Those belonged to other
tests in the job. They still matter as CPU load, not as page behaviour.

## My own fix is broken

`sentiment-visibility.spec.ts:16` fires the search request; the 429 listener is registered at
`:23`, **after**. A first-attempt 429 reaches zero listeners, `rateLimited` stays false, and the
helper throws "did not appear" having never retried. The first attempt is when rate limiting is
most likely. Fix: register the listener before `:15`.

Three more defects in the same helper: strict-mode masking (`AAPL` also matches `AAPLW`, throws
inside the `try`, reported as "did not appear"), a listener leak (no `page.off`, called twice at
`:101`/`:107`), and an off-by-one in the message (3 attempts, 2 retries).

**`retries: 0` is nearly a no-op.** Both PR jobs already pass `--retries=0`
(`pr-checks.yml:446`, `:528` — note there are *two* Playwright jobs, which I missed). Local was
already 0. The only job that inherited `retries: 2` is `deploy.yml:1674`, which discards its
result. Retries at 2 were empirically confirmed in run 30665082067 (`Retry #1`, `Retry #2`).

**My trace-degradation worry was wrong.** `playwright.config.ts:23-24` sets `screenshot: 'on'` and
`trace: 'retain-on-failure'`; neither is retry-conditional. `testInfo.retry` is used nowhere.

---

## Failure-hiding found across the repo, none of it by me

**HIGH**

- **210 skip sites in the Python suite**; 118 runtime-conditional, **59 matching "not
  implemented"** — branching on the live response to convert a missing endpoint into a pass.
  `tests/e2e/test_notifications.py:79,116,161,194,286`,
  `tests/e2e/test_sentiment.py:125,161,190,243`.
- **`data-api-guard.ts:62-72`** coerces any OHLC failure — 500, auth regression, network blip,
  empty-but-200 — into "APIs not configured" and skips green, asserting a cause it never
  established.
- **`scripts/check-false-pass-patterns.sh`** uses `--staged-only` and **no-ops in CI**,
  self-documented at `pr-checks.yml:271-274`. The guard against this class of defect does not run
  where it matters.

**MEDIUM**

- **`make validate` cannot fail on a security finding.** `Makefile:73,78` end `pip-audit ... ||
  true` and `bandit ... || true`, both dependencies of `validate` (`:42`).
- **`tests/conftest.py:57-73`** auto-marks any file with `preprod` in its **name** and drops it
  from `-m "not preprod"` runs. Renaming a file removes it from the gate with no signal.
- **`pr-checks.yml:119-126`** `--ignore`s all of `tests/e2e` and `tests/integration/timeseries`
  plus six preprod files.
- **`xfail_strict` unset** in `pyproject.toml`, so XPASS is not a failure. Plus a live imperative
  `pytest.xfail()` at `tests/integration/test_cors_prod_origins.py:117` converting a
  security-relevant assertion failure into a non-failure.
- **Frontend unit suite never runs in CI.** 51 files under `frontend/tests/unit/`; zero workflow
  references vitest. `Makefile:117` aliases `test` to the Python suite.
- Failure→skip conversions at `tests/e2e/test_circuit_breaker.py:112,187`,
  `test_failure_injection.py:202,406`, `test_rate_limiting.py:224,257,271`.
- **`deploy.yml:2146`** summary job is `if: always()` and only echoes results; never exits
  non-zero.

**Clean**

- No Python test-retry mechanism exists: no `pytest-rerunfailures`, `pytest-retry`, `flaky`,
  `--reruns`, `@pytest.mark.flaky`. `--strict-markers` (`pyproject.toml:151`) would error on a
  stray marker. `tenacity` is production code, not test tooling.
- `.only(` = 0 occurrences. `fixme` = 0. `describe.skip` = 0.
- The chaos job deliberately avoids `continue-on-error`, reasoned at `pr-checks.yml:478-480`.
- Branch protection required contexts: `Secrets Scan`, `Lint`, `Run Tests`,
  `Playwright E2E Tests`.
- `npx tsc --noEmit` and `npx eslint` both exit 0 on the changed files, independently reproduced.

---

## Corrections the refuters made to my briefings

- The matches-vs-lines trap I warned about does not exist in either dataset; claim 1's error came
  from a non-recursive glob.
- My suspicion that `egg-info/` inflated the 267 was unfounded — it contributes zero.
- My trace-degradation hypothesis was unfounded.
- My "fixtures vs real API keys" framing was a false dichotomy, and then wrong again about why.
- I told a refuter there were two modified files; `git diff` shows three.
- Group E initially concluded "no Playwright retries anywhere" by reading the modified working
  tree, and corrected itself against the deploy run log.
