# Data Model: waitForResponse race regression guard

**Feature**: `002-waitforresponse-lint-guard` | **Date**: 2026-07-30

This feature persists nothing. There is no database, no file format, no serialized state, and no
API payload. What follows is the vocabulary the guard operates on, recorded so that tasks.md and
the adversarial reviews use the same words for the same things.

---

## Entities

### Call site

A single `page.waitForResponse(...)` or `page.waitForEvent('requestfailed'|'response')` occurrence
in a `*.ts` file under `frontend/tests/e2e/`.

| Attribute | Value |
|---|---|
| Identity | `file:line` |
| Classification | `RACY` \| `PROMISE-FIRST` \| `OTHER` |
| Population at `35d5f61` (pre-001) | **34** real sites across 6 files (41 naive grep hits minus 7 comment lines) |
| Pre-001 distribution | `RACY 27` / `PROMISE-FIRST 6` / `OTHER 1`, total **34** |
| Population post-001 | **17** |
| Post-001 target | `RACY 0` / `PROMISE-FIRST 16` / `OTHER 1`, total **17** |

Comment lines are excluded from the population. A guard that counts commented-out code produces
false positives, and a guard that produces false positives gets disabled.

**The population shrinks across 001, and this is the number most likely to be got wrong.** The
naive expectation is 27 + 6 + 1 = 34 before and after. It is not: 001 FR-005 routes **18** of the 27
racy sites through `searchAndAwaitResponse(...)`, and those sites stop being wait call sites
altogether once they become helper calls. The helper contributes **one** internal wait in their
place.

```
34  pre-001 population
−18  helper-routed sites cease to be call sites
 +1  the helper's own internal wait
= 17  post-001 population

PROMISE-FIRST 16 = 6 pre-existing (001 FR-004, byte-unchanged)
                 + 6 status-503 inline conversions
                 + 3 requestfailed inline conversions
                 + 1 helper-internal
OTHER          1 = chaos-scenarios.spec.ts:138, held back by 001 FR-003
RACY           0
```

This reproduces 001 SC-001 and 001 T018 criterion 1 exactly. An implementer who sees the detector
print `17` and "corrects" it to `34` has broken the check; the number to trust is 001's, not
intuition's.

### Classification

| Value | Definition | Effect on exit code |
|---|---|---|
| `RACY` | Awaited wait whose immediately preceding non-comment, non-blank line performs a triggering action | **Exit 1** when count > 0 |
| `PROMISE-FIRST` | Wait assigned to a variable before the triggering action, awaited after it | None |
| `OTHER` | Neither shape; requires human triage | **None** — printed under a banner, never blocks |

`OTHER` deliberately does not gate. A shape the classifier cannot place is a prompt for a human,
not a blocked commit. The one known `OTHER` at `35d5f61` is `chaos-scenarios.spec.ts:138`, where an
intervening `await expect(...).toBeVisible({ timeout: 2000 })` separates `page.reload()` from the
wait.

### Trigger-action token

A method-call fragment whose presence on the preceding line makes a wait `RACY`. Thirteen tokens,
defined **once**, in the detector's module docstring:

```
.fill(  .click(  .press(  .selectOption(  .clear(  .goto(  .reload(
.evaluate(  .type(  .check(  .tap(  .setInputFiles(  .dispatchEvent(
```

**This list is not stable and must not be duplicated.** It grew from seven entries to thirteen during
001's AR#3, when `.evaluate(` was found in live use at `error-visibility-search.spec.ts:158`
(`retryButton.evaluate((el) => el.click())`). A second copy in another language would drift, and the
drift's failure mode is a detector narrower than the defect — which is exactly how three
`waitForEvent` sites hid behind a `waitForResponse`-only framing. Spec FR-002 and SC-009 exist to
keep the count at one.

`specs/001-.../tasks.md:61-63` enumerates all thirteen tokens as prose. That is documentation, not
an executable second source of truth, which is why SC-009’s grep excludes `specs/`.

### Scan run

One execution of the detector.

| Attribute | Notes |
|---|---|
| Files scanned | **48** on the tree the guard runs on (47 at `35d5f61` plus `helpers/search-helpers.ts`, added by 001 T004); 6 contain matches. Must be reported (contract C3) |
| Counts | `RACY` / `PROMISE-FIRST` / `OTHER` / **total** — four numbers required by 001 T001 criterion 5, plus files-scanned added by contract C3 |
| Exit code | Per contract C2 |
| Runtime budget | Under 2 seconds, measured not estimated (SC-010) |

A run that scanned zero files exits non-zero (FR-013). "Found no violations" and "found no files"
must be distinguishable, or renaming the scan root silently turns the guard green forever.

### Enforcement point

An invocation of the detector wired into a developer or CI workflow.

| Point | Location | Authority | Bypassable |
|---|---|---|---|
| Local hook | `.pre-commit-config.yaml`, `repo: local` | Refuses `git commit` | Yes — `SKIP=<hook-id>` |
| Blocking step | `Lint` job, `pr-checks.yml` | Fails a **required** status check | No |
| Advisory ride-along | `Pre-commit Hooks` job | None — job is not required | Irrelevant |
| Local convenience | `make validate` | Developer-invoked | Trivially |

Only the second row can stop a merge. That distinction is the feature's central design fact and is
recorded here so it is not re-lost: `main`'s `required_status_checks.contexts` is
`["Secrets Scan", "Lint", "Run Tests", "Playwright E2E Tests"]`.

### Planted violation

A temporary act-then-wait call site introduced solely as FR-007 evidence.

| Attribute | Value |
|---|---|
| Lifetime | Exists only during Phase D verification |
| Committed | **Never** — SC-015 asserts a clean tree |
| Purpose | Prove non-zero exit in all four verification modes; prove zero exit after revert |

The planted violation is the only thing that distinguishes "the guard is installed" from "the guard
works". Without it, every success criterion could be satisfied by a guard that always exits 0.

---

## Relationships

```
Scan run ──scans──► 48 files ──contains──► 17 call sites   (post-001 steady state)
                                             │
                                     classified by
                                             │
                                             ▼
                             Trigger-action token list (13, single definition site)
                                             │
                                        yields
                                             ▼
                              Classification ──RACY > 0──► exit 1
                                             │
                                     consumed by
                                             ▼
                        Enforcement points (local hook, required Lint step)
                                             │
                                    proven live by
                                             ▼
                                    Planted violation
```

## Non-entities

Deliberately absent, each because its absence is a requirement rather than an omission:

- **Suppression list / baseline file / allowlist** — forbidden by FR-009. A guard that ships
  pre-suppressed is the thing it was meant to prevent.
- **Violation history or trend data** — the guard is binary and stateless. Trend data would invite
  "only 3 violations this week" framing where the correct number is zero.
- **Per-file or per-test exemptions** — no mechanism, deliberately. FR-009 requires a future
  violation be fixed, not exempted.
