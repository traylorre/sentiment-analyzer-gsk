# Contract: detector CLI

**Feature**: `002-waitforresponse-lint-guard` | **Satisfies**: spec FR-012
**Subject**: `scripts/scan-waitforresponse-race.py`
**Owner**: Feature `001-waitforresponse-race-sweep`, task T001
**Consumer**: this feature's two enforcement points
**Status**: **ACCEPTED BY THE OWNER.** As of `3b86d9c`, every requirement below is carried by a
001 T001 acceptance criterion (5, 6, 8, 12, 13), and 001's Clarification C4 records the amendment.
This file remains the contract of record and the place to read the reasoning; 001 T001 is where an
implementer will actually encounter it. See AR#3 G-01 in `../tasks.md` for why the split mattered:
four of these requirements were not gaps in 001 but direct contradictions of its written criteria.

---

## Why this contract exists

The detector **does not exist yet**. Every task in `001/tasks.md` is unchecked. 002 is wiring
against an interface that has been described in prose but never executed, so the interface is
pinned here before any wiring is written. Discovering the real signature during verification, and
quietly bending the wiring to fit it, is the failure this document prevents.

002 **consumes** the detector. It does not own it. Any divergence between this contract and 001's
delivered script is resolved by amending 001 T001, with the amendment recorded, not by editing the
script from inside 002 (spec FR-010).

---

## C1 — Invocation

```bash
python3 scripts/scan-waitforresponse-race.py
```

| Property | Requirement |
|---|---|
| Interpreter | Any CPython 3.13 on `PATH` as `python3`. MUST NOT require `.venv`. |
| Arguments | None required. The default invocation scans the full root. |
| Working directory | Repository root. |
| Imports | **Standard library only.** No import of anything in `requirements-dev.txt`, `requirements-ci.txt`, or `requirements.txt`. |
| Executable bit | Not required. Invoked via the interpreter, so no shebang and no `chmod +x`. |

**Amendment against 001 T001 criterion 8.** That criterion specifies invocation as
`source .venv/bin/activate && python scripts/scan-waitforresponse-race.py`. That remains a valid way
to run it. This contract adds that venv availability MUST NOT be a **precondition**, because the CI
`Lint` job has no venv (`pr-checks.yml:35-65` installs only `ruff`). If 001's implementation
introduces a third-party import, that is a defect against spec FR-005 and blocks 002.

---

## C2 — Exit codes

| Code | Meaning | Required by |
|---|---|---|
| `0` | `RACY == 0` **and** at least one file was scanned | spec FR-013 |
| `1` | `RACY > 0` | 001 T001 criterion 6 |
| non-zero, not `1` | Any internal error: unreadable file, unparseable input, missing scan root, zero files scanned | spec FR-008, FR-013 |

Hard constraints:

- Exit `0` MUST NOT be reachable when the scan examined zero files. "No violations found" and "no
  files found" are different facts and MUST NOT share an exit code. A renamed or moved scan root is
  the cheapest possible route to a permanently green inert guard.
- The detector MUST NOT catch a scanning exception and exit `0`. Swallowing an error into a pass is
  the silent-failure pattern the constitution forbids and is a defect against spec FR-008.

**Amendment against 001 T001 criterion 6**, which specifies only the `0` / `1` split. The
zero-file and internal-error cases are new and originate in AR#1 finding F-13.

---

## C3 — Output

### Findings, on stdout

One line per call site:

```
frontend/tests/e2e/<file>.spec.ts:<line> <CLASSIFICATION>
```

`CLASSIFICATION` is one of `RACY`, `PROMISE-FIRST`, `OTHER`.

### Summary, on stdout

MUST report all **five** numbers:

| Field | Note |
|---|---|
| `RACY` count | Drives the exit code |
| `PROMISE-FIRST` count | — |
| `OTHER` count | Does **not** affect the exit code |
| **total** | Required by 001 T001 criterion 5, which says "a summary line with the **four** counts". 001 T002 ("total **34**") and T018 ("total **17**") are unverifiable without it. |
| **files scanned** | **New in this contract** (spec FR-013). Not required by 001. |

An earlier draft of this contract listed four fields and silently dropped `total`. Implementing that
literally would have broken 001 T001 criterion 5 and made 001's own before/after gates
unverifiable. Caught as AR#2 finding D-07.

Expected summary on the post-001 tree: `RACY 0 / PROMISE-FIRST 16 / OTHER 1`, total **17**, across
**48** files scanned. The total drops from 34 because 18 helper-routed sites cease to be inline wait
call sites and the helper adds one internal wait (001 SC-001).

### Triage banner

`OTHER` sites MUST appear under an explicit **"requires human triage"** heading listing file,
enclosing test or function name, and statement text (001 T001 criterion 10). This banner MUST NOT
affect the exit code: a shape the classifier cannot place is a prompt for a human, not a blocked
commit.

### Remediation guidance

On a `RACY` finding the output MUST include a literal corrected example, not only a count, so a
contributor can act without opening the spec (spec FR-006). Verifiable by asserting the output
contains a line matching `const <name>Promise = page.waitForResponse` positioned before the
triggering action.

**Amendment against 001 T001 criterion 5.** No 001 criterion requires remediation guidance;
criterion 5 specifies `file:line CLASSIFICATION` lines plus a summary and nothing more. This is a
third change request, filed here rather than absorbed silently into 002's wiring.

**Amendment against 001 T001 criterion 5 (output stream).** 001 does not specify stdout versus
stderr for findings. This contract requires stdout so the enforcement points can capture and assert
on it. Fourth change request.

---

## C4 — Classification rule (reproduced, not redefined)

The rule has exactly one definition site: the detector's module docstring (001 T001 criterion 3,
spec FR-002). It is reproduced here for review convenience only. **If this section and the script
disagree, the script wins and this document is wrong.**

- **RACY** — an awaited `page.waitForResponse(...)` or
  `page.waitForEvent('requestfailed'|'response')` whose immediately preceding non-comment,
  non-blank line performs a triggering action.
- **PROMISE-FIRST** — the wait is assigned to a variable before the triggering action and awaited
  after it.
- **OTHER** — neither shape. Requires human triage.

Trigger-action tokens (13, as extended by 001 AR#3):

```
.fill(  .click(  .press(  .selectOption(  .clear(  .goto(  .reload(
.evaluate(  .type(  .check(  .tap(  .setInputFiles(  .dispatchEvent(
```

`.evaluate(` is not hypothetical: `error-visibility-search.spec.ts:158` triggers via
`retryButton.evaluate((el) => el.click())`. A token list stopping at `.reload(` misses it, which is
how the list came to be extended in the first place.

---

## C5 — Scan root

`frontend/tests/e2e/`, recursively, every `*.ts` file including `helpers/` (001 T001 criterion 1).

This is the **customer** dashboard suite (Next.js/Amplify). It is not `tests/e2e/`, which is the
admin HTMX suite. Two existing scripts (`scripts/audit-e2e-skips.py`,
`scripts/check-false-pass-patterns.sh`) default to the admin suite, and CLAUDE.md records four
separate incidents caused by confusing the two. 001 T001 criterion 11 requires the docstring and
`--help` to name the root explicitly for this reason.

The guard MUST NOT widen this root. Extending coverage to Playwright specs elsewhere is carded
under spec FR-011(c).

---

## C6 — Verification of this contract

Phase A of the implementation plan is a gate, not a formality. Before any wiring is written:

| Check | Command | Expected |
|---|---|---|
| Stdlib-only, statically | `grep -nE '^\s*(import\|from) ' scripts/scan-waitforresponse-race.py` | Every module in the 3.13 standard library |
| Stdlib-only, dynamically | `python3 -I -S scripts/scan-waitforresponse-race.py` | Runs; exit 0 on the post-001 tree |
| Clean exit | `python3 scripts/scan-waitforresponse-race.py; echo $?` | `0`, with `RACY 0 / PROMISE-FIRST 16 / OTHER 1`, total 17, 48 files scanned |
| Zero-file case | Temporarily rename the scan root, re-run | Non-zero exit, not `0` |
| Summary completeness | Inspect output | **Five** numbers: RACY, PROMISE-FIRST, OTHER, total, files scanned |
| Ignores any file list | Invoke with arbitrary file arguments | Scans its own root regardless; never narrows to the given list |

**The dynamic check must use `-I -S`.** `env -u VIRTUAL_ENV python3 …` does **not** leave the venv:
it clears a marker variable while `.venv/bin` stays on `PATH`, so `python3` still resolves to
`.venv/bin/python3` with `sys.prefix` inside the venv. Verified in this repo. Scrubbing `PATH`
instead selects the system interpreter, which is 3.12 or 3.10 on a CLAUDE.md-conformant machine and
therefore tests the wrong version. `-I` (isolated) with `-S` (no `site`) keeps 3.13 and removes
site-packages, which is precisely the FR-005 property. Caught as AR#2 finding N-01.

The "ignores any file list" row exists because `pass_filenames: false` plus a filesystem-walking
detector is what makes SC-003 work at all: after `git restore --staged`, the planted file is
untracked and `pre-commit run --all-files` would not pass it to the hook. If the detector ever
gains a "scan only the files given to me" mode, SC-003 goes inert with no other symptom (AR#2 N-17).

Any failure here is an amendment against 001 T001, filed before proceeding to Phase B.

---

## C7 — Amendment log (filed by T003)

**Status: T002 executed in full on 2026-07-30 against `main` at `d6e64fc`. All eight criteria
passed. The amendment log below is empty because nothing diverged, not because the check was
skipped** (T003 criterion 3).

`scripts/scan-waitforresponse-race.py` was **not** edited by this feature, and no repair branch
was required (T003 criterion 2).

### Amendments filed

**None.**

### Evidence, per T002 criterion

| Crit | Check | Observed | Verdict |
|---|---|---|---|
| 1 | Stdlib-only, statically | Imports are `sys, argparse, os, re, pathlib` only | PASS |
| 2 | Stdlib-only, dynamically | `python3 -I -S scripts/scan-waitforresponse-race.py` → exit 0 | PASS |
| 3 | Clean exit and counts | `RACY 0 / PROMISE-FIRST 16 / OTHER 1 / total 17 / files scanned 48`, exit 0 | PASS |
| 4 | Five summary numbers | All five present on the `SUMMARY:` line | PASS |
| 5(i) | Zero-file, root renamed | Exit **2**; root restored; `git status --short` empty | PASS |
| 5(ii) | Zero-file, empty directory | Exit **2** via `WAITFORRESPONSE_SCAN_ROOT` at an empty `mktemp -d` | PASS |
| 6 | Ignores any file list | Invoked with `README.md Makefile /etc/hosts does-not-exist.ts`; output byte-identical to the no-argument run, 48 files scanned, exit 0 | PASS |
| 7 | Remediation guidance | Planted violation → `RACY` at line 8, exit 1, remediation block emitted; plant deleted; `git status --short` empty | PASS |
| 8 | Gate completeness | All six C6 rows plus both non-C6 contract requirements observed at Phase A (below) | PASS |

Criterion 3's figures are 001's pinned values and were **not** adjusted to match the detector; the
detector matched them.

### Criterion 5 was performed literally

5(i) renamed `frontend/tests/e2e` to `frontend/tests/e2e__t002_renamed`, ran the detector, and moved
it back in the same shell invocation. The env override was used only for 5(ii), which needs an
existing-but-empty directory that a rename cannot produce. Both shapes reach the same
`files_scanned == 0` branch and both exit 2, which is the property FR-013 requires: a detector that
raises on a missing root but returns 0 on an empty one would pass 5(i) and fail 5(ii).

### Criterion 8, itemised

C6 has six rows and all six are covered by criteria 1, 2, 3, 5, 4 and 6 respectively. Two further
contract requirements sit outside the C6 table and were also observed here, so Phase A is a complete
contract gate rather than a partial one:

- **Findings on stdout** (this document's "Findings, on stdout" and "Summary, on stdout" sections,
  plus the fourth change request at C3). With a violation planted, findings, summary and remediation
  all landed on stdout (2357 bytes) and stderr was empty (0 bytes).
- **In-script `sys.version_info >= (3, 13)` floor** (fold-in item 7, 001 T001 criterion 13). Present
  at `scripts/scan-waitforresponse-race.py:75`.

### Consequence

T003 criterion 4 is satisfied: no T002 criterion is failing, so Phase B is unblocked.
