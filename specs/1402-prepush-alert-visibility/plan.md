# Implementation Plan: Pre-Push Security Alert Check (spec 1402)

**Spec**: `specs/1402-prepush-alert-visibility/spec.md` | **Card**: `cards/10.json`

## Technical Context

- **Language**: Python 3.13 standard library only, matching `scripts/check_banned_terms.py`, so the
  module imports as `scripts.check_security_alerts` and is unit tested under `tests/unit/scripts/`.
- **External tool**: `gh` 2.97.0, invoked as `gh api --paginate --slurp repos/<repo>/<endpoint>`.
  The script parses the slurped JSON itself, so no `jq` sits between the fetch and the verdict.
- **Testing**: pytest unit tests over record fixtures shaped like the live API's records, plus a
  stub `gh` on `PATH` for the subprocess contract (exit status, malformed output, missing binary).
  The live runs that settle SC-001 to SC-006 are recorded in `evidence.md`.

## Design

One module, `scripts/check_security_alerts.py`, two modes.

**`check` (default, network).** A `FAMILIES` table holds, per family: endpoint, state vocabulary,
corpus floor, and named field paths as tuples. One accessor, `dig(record, path)`, serves the anchors
and the projection, so a mistyped tuple fails its anchor instead of printing blanks.

Per family, in order, each failure is COULD-NOT-DETERMINE naming the condition:

1. `gh` runs and exits 0; stdout parses as a list of page lists.
2. Corpus floor: record count >= floor.
3. Vocabulary anchor: every `state` is in the family's set.
4. Field anchors: every named path resolves to a non-empty value on every record.

Then the open records are projected and printed. Exit: 2 if any family is COULD-NOT-DETERMINE, else
1 if any family has open alerts, else 0.

**`--scan-copies` (offline).** Reads `git ls-files` (exit status checked), drops `specs/`, `cards/`
and `docs/archive/`, and reports every line matching an alert-list endpoint (built from `FAMILIES`,
so the pattern cannot drift from the check) outside this script. Positive anchor: this script is in
the scanned set and the same pattern finds every family's endpoint in it. Exit 0 clean, 1 findings,
2 could not scan.

**Floors** are the 2026-10-10 corpus sizes (code scanning 156, Dependabot 208). `--print-corpus`
prints the live sizes for revising them.

**Make targets**: `check-security-alerts` and `check-alert-query-copies`. Neither joins
`make validate` nor a hook (spec FR-014, board ruling).

## Rejected

- **Shell with `jq` and `PIPESTATUS`**: the anchors and the three verdicts are counted logic; shell
  makes them untestable as units, which is why `check_banned_terms.py` replaced its shell version.
- **Two scripts**: the detector's pattern must be built from the same endpoint table the check uses,
  and the detector's sanctioned location is that table's file.
- **A detector that parses `gh api` command lines for `--paginate`**: a correctly paginated copy still
  violates FR-013 and still rots. Reporting any restatement is simpler and stricter.
- **A floor of 101**: it catches one-page truncation only. The measured corpus also catches a fetch
  that stops after any page.
