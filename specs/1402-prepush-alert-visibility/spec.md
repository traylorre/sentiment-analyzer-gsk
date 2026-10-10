# Feature Specification: Make the Pre-Push Security Alert Check See Every Open Alert

**Feature Branch**: `card-10` (spec 1402)
**Created**: 2026-10-10
**Status**: Implemented on `card-10`
**Card**: `cards/10.json`
**Input**: The pre-push security alert instruction in `AGENTS.md` reports 0 while 28 Dependabot
alerts are open. Carried forward from an uncommitted draft dated 2026-07-31 that targeted
`CLAUDE.md`, a file that no longer exists; its measurements are re-taken below.

## Problem Statement

`AGENTS.md` tells every agent to check security alerts before a push with:

```bash
gh api 'repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?state=open&per_page=100' --jq length
```

Measured 2026-10-10 with `gh` 2.97.0, authenticated as `traylorre` with scopes
`gist, read:org, repo, workflow`:

| Measurement | Result |
|---|---|
| The command above, verbatim | **`0`, exit 0** |
| Dependabot alerts open, paginated and slurped | **28** (3 critical, 10 high, 12 medium, 3 low) |
| Dependabot corpus, all states | **208** (172 fixed, 28 open, 8 auto_dismissed) |
| Code scanning alerts open | **0** |
| Code scanning corpus, all states | **156** (139 fixed, 17 dismissed) |
| Secret scanning corpus, all states | **0** (endpoint answers `[[]]`) |
| Open alerts the instruction reports | **0 of 28** |

The instruction is silent for two independent reasons. Each alone hides everything.

**Reason one, an entire alert family is never queried.** Dependabot findings live at a different
endpoint. The instruction never reads it, so all 28 open Dependabot alerts are invisible.

**Reason two, truncation.** The command reads one page. It filters `state=open` server-side, so
today it truncates only once more than 100 alerts are open at once. The earlier shape
(`code-scanning/alerts --jq '.[] | select(.state == "open")'`, measured 2026-07-31) filtered
client-side over a default page of 30. The 30 highest-numbered alerts were all `fixed`, so it
printed nothing while 5 were open. Raising `per_page` moves the threshold; it does not remove it.
Both corpora are already past 100.

### Pagination alone is not the fix

`--paginate` without `--slurp` applies `--jq` once per page. Measured 2026-10-10, the census
command this repository's own card carries prints two numbers:

```text
$ gh api 'repos/.../code-scanning/alerts?per_page=100' --paginate --jq length
100
56
```

`--slurp` with `--jq` is rejected by `gh` (`the --slurp option is not supported with --jq`). So the
shape that reads every page and then aggregates cannot be a single `gh api ... --jq` invocation.

A corpus floor protects against reading too few records. It does not protect against reading the
wrong field out of the right records. A one-character typo in a `jq` field path yields `null` for
every record at exit 0, and a typo in the state selector yields zero rows at exit 0. Both end where
the original defect ends: empty output and exit 0. `jq` has no exit status that means "looked and
found none" as distinct from "ran". The only construction that survives is a **positive anchor**: an
assertion that a known value is present, observed through the same field path the filter uses.

### Why prose cannot hold the fix

`AGENTS.md` is instructions. Nothing executes it, so no test fails when its command rots, and the
symptom of rot is a clean report. The broken shape has also been copied out of the instruction into
other documents. The corrected query must live in one executable place, and a detector must report a
restated copy.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See every open alert before pushing (Priority: P1)

An engineer or agent about to push runs one named check. It reports every open alert across both
families, or refuses in a way that cannot be mistaken for clean.

**Independent Test**: Run the check against this repository. It reports 0 open code scanning and 28
open Dependabot alerts, lists the Dependabot alerts, and exits 1. Its per-family counts equal an
independent `--paginate --slurp` reference count taken at the same time.

**Acceptance Scenarios**:

1. **Given** 28 open Dependabot alerts and 0 open code scanning alerts, **When** the check runs,
   **Then** it reports both counts, lists each open alert, and exits 1.
2. **Given** a corpus larger than one page, **When** the check runs, **Then** the records it
   examined equal the full paginated corpus.
3. **Given** a family returns fewer records than its recorded floor (including zero), **When** the
   check runs, **Then** the verdict is COULD-NOT-DETERMINE, never CLEAN.
4. **Given** no open alerts in either family, **When** the check runs, **Then** it exits 0 and
   prints the corpus size and anchor values it examined per family.

### User Story 2 - A clean verdict a broken query cannot produce (Priority: P1)

**Independent Test**: Introduce each defect one at a time: a mistyped projection field path, a
mistyped state field name, a single-page fetch. Each exits 2 naming the anchor that failed.

**Acceptance Scenarios**:

1. **Given** a mistyped field path, **When** the check runs, **Then** the field anchor fails because
   fewer records resolve the path than were fetched.
2. **Given** a mistyped state field, **When** the check runs, **Then** the vocabulary anchor fails.
3. **Given** a single-page fetch, **When** the check runs, **Then** the corpus floor fails and names
   the shortfall.
4. **Given** `gh` is absent, unauthenticated, offline, or lacks scope for one family, **When** the
   check runs, **Then** that family is COULD-NOT-DETERMINE and the run exits 2, even when the other
   family read cleanly.

### User Story 3 - One executable location, and copies are reported (Priority: P2)

**Independent Test**: A reader of `AGENTS.md` finds one make target and no raw query. The copy
detector, run over a tree containing a restated alert query, reports it by path and line and exits 1.
Run over this repository after the sweep, it exits 0 and states that it saw the sanctioned location.

**Acceptance Scenarios**:

1. **Given** a document restates an alert-list query, **When** the detector runs, **Then** it
   reports the path and line and exits 1.
2. **Given** the sanctioned script is missing from the scan or no longer contains every endpoint,
   **When** the detector runs, **Then** it exits 2, because a detector that cannot see the one
   location it knows to exist is not looking.
3. **Given** a file the detector was told to scan cannot be read, **When** it runs, **Then** it
   exits 2.

### Edge Cases

- **`{owner}`/`{repo}` placeholders** expand from the caller's working directory. The check names
  its repository explicitly and accepts `--repo` to override.
- **A pipeline's exit status** is the last command's. The check calls `gh` as a subprocess and reads
  its exit status directly; no shell pipeline sits between the fetch and the verdict.
- **A genuinely clean repository.** Floors bind the all-states corpus, not the open count, so the
  anchors keep working after every alert is closed.
- **Stale floors.** An alert family can be reset or a repository transferred. The floors are a
  recorded table in the script, with a stated procedure for revising them.
- **Secret scanning** is a third family whose corpus is 0. A floor on an empty corpus cannot tell
  "none ever" from "wrong endpoint", so it stays out of scope. Push protection already blocks at push
  time (`SECURITY.md`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The check MUST read the complete corpus of each family it covers across all pages.
- **FR-002**: The check MUST cover the code scanning and Dependabot families.
- **FR-003**: The check MUST produce exactly three verdicts: FINDINGS (exit 1), CLEAN (exit 0), and
  COULD-NOT-DETERMINE (exit 2). COULD-NOT-DETERMINE outranks FINDINGS, and neither is reported as
  CLEAN under any condition.
- **FR-004**: Each family MUST assert a corpus floor on its all-states record count, recorded as a
  table in the script with the procedure for revising it. Failing the floor is COULD-NOT-DETERMINE.
- **FR-005**: Every field path the check filters or projects on MUST carry a positive field anchor:
  the count of records where that path resolves to a usable value equals the count fetched, observed
  through the identical path the projection uses.
- **FR-006**: The state field MUST carry a vocabulary anchor: every record's state is drawn from the
  family's known set. An unknown state is COULD-NOT-DETERMINE, so a new state is a reason to look.
- **FR-007**: No pass condition may be an absence alone (FR-005 and FR-006 are its instances).
- **FR-008**: The fetch's exit status MUST be read directly from the fetch, never through a filter.
- **FR-009**: Pages MUST be joined before anything is counted.
- **FR-010**: The target repository MUST be explicit.
- **FR-011**: CLEAN output MUST state per family the corpus size examined and the anchors observed.
- **FR-012**: FINDINGS output MUST identify each open code scanning alert by number, rule id and path,
  and each open Dependabot alert by number, severity, ecosystem, package, manifest and advisory id.
- **FR-013**: The literal alert-list queries MUST live in exactly one executable location. Prose
  names that location's make target and does not restate the query.
- **FR-014**: The check and the copy detector MUST be standalone make targets. Neither is added to
  `make validate`, to any git hook, or to CI as a blocking step. The check needs network and a
  credential; the board has ruled that a blocking alert gate is an operator decision because 28 open
  alerts would stop every push.
- **FR-015**: Live documentation and scripts that restate the query or point at the retired
  `CLAUDE.md` checklist MUST be repointed to the make target. `specs/`, `cards/` and `docs/archive/`
  are excluded: `specs/` dirs are dated records adjudicated by card #9, and `cards/` is the board's.
- **FR-016**: The copy detector MUST report a restated alert-list query by path and line, MUST be
  exercised against a fixture holding a known restatement, and MUST distinguish "scanned and found
  nothing" from "could not scan" by asserting that it saw the sanctioned location.
- **FR-017**: This feature MUST NOT change any alert's state, add any cloud resource, or add any
  credential or scope.

### Key Entities

- **Alert family**: an endpoint with its own state vocabulary, field paths and corpus floor.
- **Corpus**: every record of one family across all states and all pages.
- **Anchor**: an assertion whose pass condition is the presence of an expected value, observed
  through the same path the filter reads.
- **Verdict**: FINDINGS, CLEAN, or COULD-NOT-DETERMINE.

## Success Criteria *(mandatory)*

- **SC-001**: Against this repository the check reports 0 open code scanning and 28 open Dependabot
  alerts (or the counts an independent paginated reference returns at the same moment) and exits 1.
- **SC-002**: The records examined per family equal the paginated reference and exceed 100.
- **SC-003**: A mistyped projection path exits 2 naming the field anchor.
- **SC-004**: A mistyped state field exits 2 naming the vocabulary anchor.
- **SC-005**: A single-page fetch exits 2 naming the corpus floor.
- **SC-006**: With `gh` unauthenticated or absent, the check exits 2 and its output does not contain
  the CLEAN verdict line.
- **SC-007**: A CLEAN verdict prints corpus sizes and anchor values.
- **SC-008**: The copy detector reports a fixture restatement by path and line and exits 1; over this
  repository after the sweep it exits 0 and names the sanctioned location it anchored on.
- **SC-009**: The copy detector exits 2 on an unreadable input and on a scan missing the sanctioned
  location.
- **SC-010**: `AGENTS.md` holds one instruction for checking alerts, which names the make target and
  holds no raw query.
- **SC-011**: `make validate` and the git hooks are unchanged by this feature apart from `.PHONY`.

## Out of Scope

- Fixing, dismissing or triaging any alert.
- What CodeQL or Dependabot scan, and their configuration.
- A blocking alert gate in a hook, in `make validate` or in CI. Carried to the operator through the
  board with the measured counts.
- Editing any `specs/` directory other than this one (card #9).
- Secret scanning coverage (corpus 0; push protection covers it).

## Assumptions

1. `gh` is installed and authenticated wherever the check runs; when it is not, the verdict is
   COULD-NOT-DETERMINE.
2. The repository is public and the `repo` scope reads both families. Measured 2026-10-10.
3. Alert corpora grow in normal operation; alerts change state and are not deleted.
4. `gh` 2.97.0 behaviour: `--paginate --slurp` emits one JSON array of page arrays; `--slurp` with
   `--jq` is rejected; `--paginate` follows the Dependabot endpoint's cursor links. Measured.
