# Phase 1 Contract: Checker CLI and Gate Output

**Feature**: `001-validate-gate-repair` | **Date**: 2026-07-30

## Terminology Note *(inherited)*

Retired framework names are never written here. They are called **legacy terms**. Illustrative output
below uses `<TERM>` as a stand-in.

## Why this feature has a contract at all

The checker exposes two interfaces that other things depend on, so both are contracts rather than
implementation details:

1. A **command-line interface** consumed by a Make target, a workflow step, and a pre-commit hook.
2. An **exit code and output format** that a human reads under time pressure when a merge is blocked.

The second matters more than usual here. Once wired into a required job the checker can block every
merge in the repository, and it fails closed. FR-022b exists because a fail-closed gate with an
opaque message is an outage. The output format below is therefore a requirement, not a suggestion.

---

## Contract 1: `scripts/check_banned_terms.py`

### Invocation

```text
python3 scripts/check_banned_terms.py [--list-exemptions] [--root PATH]
```

Stdlib only. No install step, no arguments required for the default case. Runs from any working
directory: the repository root is derived from the script's own location, not from the caller's cwd.

### Options

| Option | Behaviour |
|---|---|
| *(none)* | Scan and report. The default and the only mode any caller currently uses. |
| `--list-exemptions` | Enumerate every exemption and exit 0. Does not report violations. Backs FR-026. |
| `--root PATH` | Override the scan root. Exists for tests, which scan a `tmp_path` fixture. **Exclusions must behave identically under any root** (FR-027); this option is how that property gets tested rather than asserted. |

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Every occurrence is either absent or carries a sanctioned exemption. |
| 1 | At least one unexempted occurrence found, **or** the configuration is unusable. |
| 2 | Reserved. Not used. |

Exit 1 deliberately covers both a real violation and a broken configuration. Fail-closed (FR-009)
means a checker that cannot determine the answer must not report success. The two cases are
distinguished by the message, never by the exit code, because a caller that could pass on "the
checker is broken" would defeat the purpose.

### Output: success

```text
=== Legacy-Term Scanner ===
Scanned: 1,284 files under <root>
Exemptions honoured: 1 inline covering 2 occurrence(s)

PASS: 0 unexempted occurrences.
```

The exemption line is on the success path deliberately. A passing gate that silently honoured
exemptions reads identically to a passing gate with nothing to honour, and the difference is exactly
what FR-026 asks the project to keep visible.

The line counts **markers**, not matches, and states both numbers because they differ. One line can
name several banned terms under a single justification, and the repository's only exemption does
exactly that: one marker, two term-hits. Reporting the match count alone would make that line read as
two exemptions, and since this count is the SC-012 baseline, a line would register as growth in the
exemption surface for saying two words. `--list-exemptions` was already specified in marker terms
below; the implementation had drifted from it and was corrected in phase 4.

### Output: violation

```text
=== Legacy-Term Scanner ===
Scanned: 1,284 files under <root>
Exemptions honoured: 1 inline covering 2 occurrence(s)

FAIL: 2 unexempted occurrences.

  src/lambdas/dashboard/handler.py:47
    matched: <TERM>
    | from <TERM> import something
    remedy: this is application source. Remove the reference. Exemptions are for
            records that the framework was retired, not for code that uses it.

  docs/notes/migration.md:12
    matched: <TERM>
    | We used to run on <TERM> before the migration.
    remedy: if this records the retirement, append an exemption marker with a
            justification on the same line:
              <!-- legacy-term-ok: records the pre-migration runtime -->
            See specs/001-validate-gate-repair/quickstart.md
```

Every violation report carries path, line number, the matched term, the offending line, and a
remedy. The remedy is tailored: source paths are told to remove, documentation paths are told how to
exempt. A single generic message would push every blocked contributor to the same wrong action.

### Output: exemption marker in a forbidden location

```text
  src/lambdas/dashboard/handler.py:47
    matched: <TERM>
    | from <TERM> import something  # legacy-term-ok: needed for now
    ERROR: exemption markers are not permitted under src/.
    remedy: remove the reference. Exemptions record that a framework was
            retired; this tree holds code, not records, so no exemption
            applies here. See FR-028.
```

Distinct from an ordinary violation and deliberately so (FR-028, SC-013). The marker itself is named
as the error rather than being silently ignored. If it were ignored, the line would report as an
ordinary violation and the contributor's likely next move would be to assume the marker was
malformed and try harder to make it work. Same exit code, very different next action.

### Output: unusable configuration

```text
=== Legacy-Term Scanner ===

FAIL: configuration is unusable, refusing to report success.
  cause: the term list is empty
  remedy: scripts/check_banned_terms.py defines the authoritative term list.
          An empty list means the scanner cannot detect anything, which is not
          the same as finding nothing.
```

Names the cause and the remedy separately, per FR-022b. This path exists so that a
repository-blocking failure is self-explaining without reading the source.

### Output: `--list-exemptions`

```text
=== Legacy-Term Exemptions ===

inline (1):
  docs/cleanup/diagram-drift.md:133  records refuted drift claim from archived spec

Total: 1
```

Sorted by path, so the output is diffable and a growing baseline is visible in review. Only inline
markers appear: the sanctioned set has one member, so this listing is complete by construction.
Scan-scope exclusions are deliberately absent, because they decide what is searched rather than what
is forgiven.
Backs SC-012.

### Behavioural guarantees

These are the properties tests assert, each traceable to a requirement:

| Guarantee | Requirement | Test posture |
|---|---|---|
| Exclusions compare against paths only, never content | FR-007 | A fixture file whose *content* contains an excluded path string plus a term is still reported (SC-005). |
| Paths are normalised before comparison | FR-008 | Equivalent spellings of one path are excluded identically. |
| Empty exclusion list does not produce a pass | FR-009 | Scans everything or refuses. Never reports success by default (SC-006). |
| Unexempted term in source fails | FR-010 | Red-team insertion and revert (SC-004). |
| Exempted occurrences pass | FR-011 | Marker with justification exempts; marker with empty justification does not. |
| A marker under source, infrastructure or frontend source is itself an error | FR-028 | Insertion and revert, with the message naming the marker rather than the term (SC-013). |
| Every violation reported in one run | FR-012 | A fixture with three violations reports three. |
| Behaviour independent of scan root spelling | FR-027 | Identical results under a relative and an absolute `--root`. |
| The checker excludes its own file | *(implied)* | The module holds the authoritative term list and must not report itself. |

---

## Contract 2: gate output

### Invocation

```text
make validate
```

Unchanged. This matters: the documented entry point stays the same, so no caller needs updating and
no one needs to learn a flag for the gate to behave correctly. A repair that required a new
invocation would leave the old one broken.

### Guarantees

- Every stage runs, regardless of any earlier stage's outcome (FR-001).
- Every stage produces an execution marker, so "ran and passed" is distinguishable from "never ran"
  (SC-002).
- A per-stage summary is printed at the end (FR-002).
- Exit 0 only when every blocking stage passed (FR-003).
- The working tree is byte-identical before and after (FR-004, SC-007).
- Each stage's declared gating status matches its actual behaviour (FR-005, SC-010).
- Individual stages remain independently invokable. `make lint` keeps working.

### Output: summary block

```text
================ validate summary ================
  format check          BLOCKING   PASS
  lint                  BLOCKING   PASS
  dependency audit      ADVISORY   reported
  static analysis       BLOCKING   PASS
  legacy terms          BLOCKING   FAIL
  test target headers   BLOCKING   FAIL
  e2e race guard        BLOCKING   PASS
==================================================
FAIL: 2 of 6 blocking stages failed. See output above.
```

The advisory stage reports rather than passing or failing, because it structurally cannot fail and
printing PASS for it would be the same misrepresentation the feature exists to remove. The count
denominator is blocking stages only, for the same reason.

Both failing stages appear in one run. That is the property the whole feature turns on: the current
gate would have shown only the first, and the second stayed hidden behind it long enough that the
original specification was written without knowing it existed.

---

## Contract 3: CI step

Added to the existing required lint job in `.github/workflows/pr-checks.yml`.

| Property | Value | Reason |
|---|---|---|
| Host job | the existing required lint job | Required contexts are fixed at four and branch protection is owner-gated (FR-022a). This is the only place the check can actually block a merge. |
| Invocation | the checker directly, not through pre-commit | The pre-commit job's skip mechanism must not be able to reach it. Matches the prior feature's guard exactly. |
| Install step | none | Stdlib only, and the job already provisions the interpreter. |
| Condition | always run | Steps are fail-fast. Without it, any earlier lint failure means the guard never runs and reports nothing. |
| Comment | required | Explaining why a legacy-term scan lives in a job named for linting. The prior feature's step carries the same explanation, and without it the step looks misfiled and invites a tidy-up that would silently downgrade it to advisory with no symptom until a violation merged green. |
