# Stow point

State after adversarial refutation of the first pass. Nothing pushed. All changes local.

Full refutation record: `reviews/refutation-results.md`. Six independent refuters, 30 claims.
The author did not grade its own work.

## Contents

- [Three blocking defects](#three-blocking-defects)
- [Working tree changes](#working-tree-changes)
- [What the refutation overturned](#what-the-refutation-overturned)
- [What survived](#what-survived)
- [Artifacts](#artifacts)
- [Owner decisions](#owner-decisions)
- [Open work](#open-work)

## Three blocking defects

Diagnosed to a named mechanism. Not yet fixed. Ordered by consequence.

### D1. The preprod deploy gate cannot fail. A real bug already shipped through it.

Deploy run `30665082067` reported **success**. Verified directly, not relayed:

```
Running 32 tests using 4 workers
✘  3 › auth.spec.ts:24 › should show OAuth buttons (8.8s)
✘ 24 › auth.spec.ts:24 › should show OAuth buttons (retry #1) (6.7s)
✘ 34 › auth.spec.ts:24 › should show OAuth buttons (retry #2) (6.3s)
   Error: expect(locator).toBeVisible() failed
```

That is the deploy for #994. GitHub OAuth buttons are missing from preprod, the test failed three
consecutive times, and the pipeline wrote `"ready_for_production": true` (`deploy.yml:1712-1719`).
`deploy-prod` depends on this job (`:1898`).

Four independent layers, any one of which alone makes the gate advisory:

1. **All 16 `sanity.spec.ts` tests skip.** `frontend/tests/e2e/helpers/data-api-guard.ts:15`
   hardcodes `http://127.0.0.1:8000`, and `frontend/playwright.config.ts:6,49-51` omits the
   `webServer` block entirely when `PREPROD_FRONTEND_URL` is set, so nothing listens on 8000.
2. **The exit code captured is `tee`'s, not Playwright's.** `deploy.yml:1674-1678` pipes to `tee`
   then reads `$?`. The step shell is `/usr/bin/bash -e {0}` with no `pipefail` and no top-level
   `defaults:`, so `PLAYWRIGHT_EXIT_CODE` is always 0. The `-eq 124` timeout branch is dead code.
3. **The computed result is never read.** `steps.playwright-sanity.outputs.passed` appears nowhere.
   Compare `Check Integration Test Results` (`:1640-1650`) and `Check Unit Test Results`
   (`:472-476`), both of which `exit 1`. Playwright has no equivalent.
4. **`deploy.yml:1695` is an unconditional `exit 0`**, commented "sanity tests are non-blocking for
   now".

**Related and separate:** the 22 guarded tests execute in zero CI contexts. `pr-checks.yml:449`
excludes them via `--grep-invert "@external-api"`. `nightly-e2e.yml` is the only workflow selecting
them, and five consecutive runs show `Running 22 tests / 22 skipped`, because `TIINGO_API_KEY` and
`FINNHUB_API_KEY` resolve empty. `gh secret list` returns only `CLAUDE_CODE_PAT`,
`NEWSAPI_SECRET_ARN`, `PREPROD_JWT_SECRET`, `REPO_PAT`. **Neither vendor key exists.** The YAML at
`nightly-e2e.yml:71-72` references secrets that were never created.

### D2. My own edit to `sentiment-visibility.spec.ts` does not work.

`:16` fires the search request via `searchInput.fill(ticker)` and yields. The 429 listener is
registered at `:23`, **after**. A first-attempt 429 is dispatched to zero listeners, `rateLimited`
stays `false`, control reaches `:49-50`, and the helper throws `Suggestion did not appear` having
never retried. The first attempt is when rate limiting is most likely.

Fix: register the listener before `:15`.

Three further defects in the same helper:

- **Strict-mode masking.** `getByRole('option', { name: new RegExp(ticker, 'i') })` matches `AAPL`
  and `AAPLW`. `waitFor()` enforces strict mode, so a multi-match throws inside the `try`, lands in
  the `catch` with `rateLimited === false`, and is reported as "did not appear".
- **Listener leak.** No `page.off`. Called twice on the same page at `:101` and `:107`.
- **Off-by-one.** `maxRetries = 3` is 3 attempts / 2 retries; the message says "after 3 retries".

Fall-through was checked and cannot happen; every loop exit is a `break` or a throw.

### D3. C-002 root cause found: a Radix listener-registration race, triggered by `force: true`.

`@radix-ui/react-dismissable-layer@1.1.11`, `dist/index.mjs:165-167`:

```js
const timerId = window.setTimeout(() => {
  ownerDocument.addEventListener("pointerdown", handlePointerDown);
}, 0);
```

The dismissal listener attaches one macrotask after the layer mounts. An outside `pointerdown`
arriving before that is never seen, and since no further pointer events occur, the menu stays open
permanently. A one-shot missed-event race latches into a stuck state.

Measured margin between listener registration and the outside click:

| Click | Margin |
|---|---|
| `click({ force: true })` | **4.7-11.4 ms** (8 samples) |
| `click()` | 65.0-138.4 ms (5 samples) |

`force: true` collapses the margin roughly tenfold. With a 50ms induced registration delay, force
gives 6/6 stuck and no-force 0/5.

**Fix: drop `force: true` at `frontend/tests/e2e/dialog-dismissal.spec.ts:168`.**

Do not attempt to reproduce first. 134 executions across repeat counts, worker counts, CPU
stressors, Mobile Chrome and the full suite have never reproduced it. Non-reproduction is not
absence.

## Working tree changes

| File | Change | Status |
|---|---|---|
| `frontend/playwright.config.ts:14` | `retries: process.env.CI ? 2 : 0` → `retries: 0` | correct but **nearly inert** |
| `.github/workflows/nightly-e2e.yml:67` | `--retries=1` → `--retries=0` | correct |
| `frontend/tests/e2e/sentiment-visibility.spec.ts` | `test.skip(...)` → `throw`, retry loop kept | **BROKEN, see D2** |

The config edit is nearly inert because both PR jobs already pass `--retries=0`
(`pr-checks.yml:446` and `:528`, two jobs, not one) and local already evaluated to 0. The only job
that inherited `retries: 2` is `deploy.yml:1674`, which discards its result. Retries at 2 were
empirically confirmed by the `Retry #1` / `Retry #2` lines in run 30665082067.

`npx tsc --noEmit` and `npx eslint` both exit 0, independently reproduced.

## What the refutation overturned

- **The seam claim is dead.** "Zero cross-section references" is refuted by 13 by-name pointers in
  the amendment log (578-588), five using the word "section" literally. A by-section split is not
  safe as-is.
- **Self-refutation:** `L576` points at `L641` via "at the bottom", and the map separately proposed
  deleting `L641` while asserting no deletion could break a pointer.
- **Criterion 3's judging method cannot work as specified.** Its word list (`was `, `previously`,
  `superseded`, `updated to`, `no longer`, `formerly`) is structurally blind to the amendment log,
  which is the largest residue block in the document.
- `mock_aws` is **38 across 8 files**, not 36 across 7 (non-recursive glob missed
  `tests/integration/ingestion/`).
- **Two health routes**, not one: `/chaos/health` at `src/lambdas/dashboard/handler.py:1607`.
- **22 bare pseudo-headings**, not 2. The 20 missed sit at one-tab indent in sections 7 and 8, two
  of them duplicated labels (`Pattern:` at 217 and 426).
- The 11-term cross-cutting table was a **sample presented as a measurement**. `secrets` spans 9
  sections, `acceptance criteria` 8, `approval` 8, `dashboard` 5 with 25 hits.
- 267 `sanitize_for_log` are **occurrences, not call sites**; roughly 238 are real invocations.
- Lines 33-43 are 11 list items but **10 requirements**; line 33 is a parent heading.
- 21 skip occurrences is really **23 matches** (21 requires two unstated exclusions), and `fixme`
  is 0.
- My C-002 reasoning was a non-sequitur, and both mechanisms I proposed are refuted.

## What survived

- All 23 word-count rows exact, ranges contiguous, summing to 6000 = `wc -w`.
- The duplicate section 5 at lines 52 and 57 (p0-004).
- **Trap 3 stands**: the refuter's own detector missed L96/L104 until hardcoded, and
  `ExpressionAttributeNames` sits at L99 inside the first of them.
- Both reference dismissals upheld: L58 points at `docs/deployment/`, which exists; L146 is
  intra-section at both granularities.
- No `aws_ecs_`/`aws_instance`/`aws_autoscaling`, extended to rule out Fargate, App Runner, Batch,
  Beanstalk, EKS, Lightsail and launch templates.
- Version footer at 641, amendment log at 578-588 exactly (footer now 635, see amendment below).
- `.specify/memory/constitution.md` was UNTOUCHED until the 31 July black/bandit amendment below.

## What the map rebuild added

Beyond confirming the refutation. Full detail in `reviews/cross-reference-map.md`.

- **Four sections legislate the pre-push gate independently**, none referencing another: 7-Testing
  (L246, L251), 8-Git (L405-416), 9-TechDebt (L570), 10-LocalSAST (L592, L624-631). This is the
  seam test failing in its exact stated form.
- **C1 settled on evidence.** The "(updated)" checklist at L619 is the one that conforms to the
  repo: `make validate` is Makefile:42, `make test-local` is Makefile:104. Keep L619, delete
  L411-417, fold in L409(d)'s feature-branch requirement. **Not yet applied**, owner has not
  ruled on C1.
- **Second dangling reference pair found**, missed by the refutation: L48 and L131 both defer to an
  undefined "documented policy" for raw-text storage. With L399's "the retention policy", three
  references and zero definitions.
- **Only 6 of 23 sections are free-standing on content**, 477 words, roughly 8% of the document.
- **Correction to the refutation record:** `make validate` *can* fail on a security finding, via
  `semgrep ... --error` (Makefile:81, no `|| true`). It is `pip-audit` (:73) and `bandit` (:78)
  that are neutered. So L632's "no HIGH/MEDIUM SAST findings" is enforced for Semgrep alone.
- **`black` was in a self-contradictory state in the repo** before the amendment: installed
  (`requirements-dev.txt:35`, `requirements-ci.txt:56`) while `pyproject.toml:66`,
  `.pre-commit-config.yaml:56`, `Makefile:60` and `pr-checks.yml:58` all recorded it removed.
- **Two measurement defects found in this rebuild's own first pass**, both fixed before publishing:
  a tokenizer that let `/` and `.` into tokens, collapsing `SAST/IaC` and undercounting the SAST
  span by two sections; and an unscoped `(or <word>)` residue rule that fired on `(or config)`.
- **Third defect, in `residue-check.sh` itself:** rule 3 matched `(updated)` case-sensitively while
  every real heading title-cases it, so the script reported the document clean while the C1 heading
  was still present. Fixed by folding case on rule 3 only; rule 4 must stay case-sensitive or every
  sentence opening with "added" or "moved" reads as edit-narration. All six rules re-probed.
- **C1 line numbers after the prune:** the ruff checklist is L332-346 (`### Pre-Push Requirements`),
  the Makefile-conforming one is L456-462 (`### Pre-Push Checklist (Updated)`). The L411/L619
  numbers above are pre-prune.

## Amendment applied 31 July 2026: black and bandit removed

Owner decision, executed as a constitution amendment first, per the brief's rule that retiring a
tool starts with the constitution rather than with the config. This is the procedure the Bandit
worked example in the brief says was skipped last time.

**Constitution edits, the only ones made. 641 -> 635 lines, 6000 -> 5953 words.**

| Line | Change |
|---|---|
| 407 | `(black/ruff format)` -> `(ruff format)` |
| 414 | `# Format (or black)` -> `# Format` |
| 594-605 -> 594-600 | "Two-Tier Local Security Scanning" collapsed to "Local Security Scanning", Semgrep tier only |
| 635-636 -> 632 | two Bandit acceptance criteria replaced by one Semgrep criterion |

No annotation, no version bump, nothing appended to the amendment log, per the hard constraints.
Removal reasoning goes in the commit message. `grep -iE '\b(black|bandit)\b'` on the constitution
returns nothing.

**The repo has not been touched.** The document now leads and the configuration is the thing that
disagrees. Sites are inventoried in the map under "Black and Bandit: the document now leads the
configuration": 5 black sites (2 real installs), 7 bandit sites. Two dependencies to resolve when
that work is scheduled: 6 `# nosec` pragmas in `src/` lose their reader, and
`pyproject.toml:91`'s `external = ["B108", "B202", "B324"]` becomes dead.

Owner directed that tool-coverage equivalence is out of scope here and belongs with later test
coverage work.

## Artifacts

Under `specs/001-constitution-prune/`:

- `reviews/refutation-results.md`: the full six-group record. **Read this first.**
- `reviews/phase0.json`: p0-001 CRITICAL, p0-002 HIGH, p0-004 HIGH all TRIAGED; p0-003 open.
- `reviews/cross-reference-map.md`: **REBUILT 31 July 2026** on eight detection strategies.
  Seam verdict reversed: a by-section split is not safe as-is. Carries the six prerequisites, the
  full-vocabulary term sweep, and the criterion 3 replacement.
- `checks/residue-check.sh`: replaces criterion 3's word list, which scores zero precision and
  zero recall on this document. Six rules, all six observed failing on induced perturbations.
- `reviews/accuracy-audit.json`: prior session, not re-verified in full.
- `reviews/carded-out-of-scope.md`: C-001 caveman, C-002 (now D3), C-003 reference reachability.
- `proposed-failing-tests-clause.md`: the broken-tests clause, not yet applied.

`CLEANUP-BOARD.html`: one new card added to the `fix` lane, "Systemic failure-hiding: gates that
cannot fail", covering the wider failure-hiding not in D1-D3.

## Owner decisions

- **p0-001**: surgical prune, evaluation-gated. F5 builds the baseline before F1 deletes anything.
- **p0-002**: ~1,700 words for the always-loaded portion. Target, not a hard CI gate.
- **p0-004**: delete constitution lines 52-55, keep the serverless section.
- **Broken tests**: a test is working or broken, no third state. No register, index or quarantine.
  A failed test is not re-run. Retrying inside a test is fine. No pre-authorised exception for
  dependency failures.
- Caveman plugin: not adopted.

## Open work

1. ~~Rebuild the cross-reference map on corrected evidence.~~ **DONE.** Seam verdict reversed.
   Six prerequisites now gate any split; all six are repairs that also cut word count, so they
   belong in F1 rather than blocking it. Re-map after F1 before committing to a split.
2. Fix D1, D2, D3.
3. `data-api-guard.ts`: remove from the preprod path; decide what replaces it on the PR path given
   the vendor secrets do not exist.
4. `cors-prod.spec.ts`, `cors-headers.spec.ts`: env-gated, skip on PRs.
5. `chaos.spec.ts`: 12 skips on `chaosAvailable`.
6. `navigation.spec.ts`, `signin-interaction.spec.ts`: 4 viewport-conditional skips, unread.
7. Battleplan Phase 1: F1-F6 decomposition. F5 gates F1.
8. Track 1 CodeQL burndown: #994 merged. #995, #996, #992 still queued.
9. Separate latent bug found in passing: `<Toaster />` is mounted nowhere in the frontend (0 hits
   outside `node_modules`), so every `toast()` call from the three hooks that import it renders
   nothing.

## Restructure applied 31 July 2026: rules-only rebuild

Driven by a dual-refuter pass (one blind necessity reviewer, one adversarial reviewer of the
owner's verdicts). They converged independently on 802 and ~820 projected words. Standard used:
`reviews/consumer-profile.md`, which defines the SA-1..SA-9 sub-agent task catalogue and the
failure-mode test a section must pass to survive.

**Result: 4046 words to 562.** Five sections: Scope, Security, Testing, Push rules, Pointers.

Owner decisions taken at this point:

- **Shape: rules-only, plus a new `docs/SERVICE-SHAPE.md`.** The constitution holds rules an
  agent can violate; the descriptive material (what the service is, topology, interfaces) moved.
- **Non-Functional Requirements: deleted outright**, not partitioned. The adversarial refuter
  overturned the owner's original "export it" call, on the grounds that an unmeasured SLA in
  `docs/` is not retired, it is relocated somewhere a later audit agent treats as policy and
  opens a false finding against. Availability 99.5% is in no alarm or SLO;
  `docs/operations/PERFORMANCE_VALIDATION.md` holds two conflicting p90 records (58.4 and 567.0),
  which shows the 500ms budget is unmonitored rather than missed.
- **Broken-tests clause: compressed version applied.** The rule the owner wanted ("flaky is not
  an option") was not in the document at all. `proposed-failing-tests-clause.md` was drafted and
  unapplied. Applied at roughly 60 words, keeping "no third state" and the prohibition on
  re-running, dropping the enumerated excuses and the evidence-capture paragraph.

### Sections deleted entirely

Purpose, Functional Requirements, Non-Functional Requirements, Deployment Requirements (both),
Interfaces (Minimal Contract), Acceptance Criteria (Minimal), Operational Notes, Standard Tests,
and every acceptance-criteria block.

### The rescue that mattered most

`ExpressionAttributeNames`/`ExpressionAttributeValues` for user-controlled values was the repo's
ONLY real injection rule, and it was buried inside the deployment section's architecture notes at
snapshot line 104. Both that section and the SQL-injection section were slated for removal. Had
both gone unexamined, 215 words of SQL policy for a database this repo does not have would have
survived in `docs/` while the actual rule was deleted. It is now in constitution section 2.

### Corrections made to already-partitioned files

- `docs/MODELING.md` stated `score: float(0-1)`. Wrong, and authored during this same feature.
  Real model is `score: -1.0..1.0` with a SEPARATE nullable `confidence: 0.0..1.0`
  (`src/lambdas/shared/models/news_item.py:20-25`). Corrected, with a note that negative scores
  are ordinary output.
- `docs/OBSERVABILITY.md` admin-controls section referenced `/v1/sources`, which never existed.
  Marked UNBUILT rather than repointed, so nobody audits the repo against it.

### Correction to both refuters' record

Both described SQS as underbuilt ("no FIFO, no reserved concurrency"). Direct check: there is no
work-queue SQS at all. The only `aws_sqs_queue` in the repo is a DLQ on the SNS topic
(`infrastructure/terraform/modules/sns/main.tf:5`). The old section 8 mandated "SQS for durable
queues and decoupling"; that tier was never built.

### Premise correction: nothing injects the constitution

No `settings.json`, no hook under `~/dotfiles/scripts/bin/`, no agent definition and no skill
references it. The only consumer is `.specify/templates/plan-template.md`. Remaining grep hits
are `.claude/handoff/` agent output, the same contamination that inflates the banned-terms gate.
The prune stands on accuracy grounds; the per-spawn-cost argument does not apply yet. `CLAUDE.md`
IS injected, which is why it is the next target.

## Open work

- `CLAUDE.md` under the same dual-refuter treatment. 5827 words, larger than the constitution
  was, and genuinely injected on every spawn. Its `## SAST` section is pasted twice verbatim.
- Regenerate `reviews/cross-reference-map.md`; its line citations do not survive this rebuild.
- Rebuild `constitution-prune-review.html` at repo root.
- Commit strategy: constitution, `docs/`, and `specs/001-constitution-prune/` only. The
  Playwright, workflow and board changes in the working tree are a different piece of work.
