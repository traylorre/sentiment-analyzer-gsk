# Phase 1 Data Model: Validation Gate Repair

**Feature**: `001-validate-gate-repair` | **Date**: 2026-07-30

## Terminology Note *(inherited)*

Retired framework names are never written here. They are called **legacy terms**.

## Scope of this document

This feature has no database, no API and no persisted state. "Data model" here means the internal
entities the checker and the gate driver operate on, derived from the spec's Key Entities section.
Naming them explicitly matters because the current checker's central defect is that it has no data
model at all: it treats a formatted text line as if it were structured data, and every correctness
bug in R6 follows from that.

---

## Entity: LegacyTerm

A string naming a framework the project has retired.

| Field | Type | Rule |
|---|---|---|
| `pattern` | str | The term as written in the authoritative array. Matched case-insensitively. |

**Rules**

- The authoritative collection lives in exactly one place, the checker module's term array. No other
  file may enumerate them. This is why the checker must exclude its own file from the scan.
- Terms are matched as patterns rather than literal strings, preserving current observable behaviour.
  One term contains characters that behave as wildcards and therefore matches several separator
  spellings. This is documented at the array and deliberately unchanged, since altering the term list
  is out of scope.
- Adding or removing terms is out of scope for this feature.

---

## Entity: ScanTarget

A single file the checker will read.

| Field | Type | Rule |
|---|---|---|
| `path` | relative path | Canonical form: repository-relative, forward slashes, no leading prefix. |

**Rules**

- **Normalisation is mandatory before any comparison** (FR-008, FR-027). Every path is resolved to
  the canonical form above regardless of how it was discovered. This is the fix for two distinct
  defects at once: the machine-generated file that stores paths in a different spelling than the
  exclusion list uses, and the exclusion mechanism that currently works only because a search tool
  happens to emit a leading prefix.
- Path and content are separate fields and never share a representation. This is the fix for the
  content-matched-exclusion defect (FR-007). The class of bug it eliminates is not "a filter was
  written wrong" but "a filter was applied to the wrong thing", and it cannot recur once the two are
  distinct values.

---

## Entity: Match

A single occurrence of a legacy term at a specific file and line.

| Field | Type | Rule |
|---|---|---|
| `path` | ScanTarget path | Canonical form. |
| `line_number` | int | 1-indexed. |
| `term` | LegacyTerm | Which term matched. |
| `line_text` | str | The full line. Used only for exemption detection and for reporting. **Never** compared against path exclusions. |
| `exempted_by` | Exemption or None | Populated during classification. |

**Rules**

- A single physical line may produce more than one Match if it contains more than one term. This is
  not a defect and it is how the board's single card yields two matches: two different terms on one
  very long line.
- Every Match is reported in a single run. The checker never stops at the first (FR-012).
- A Match with `exempted_by` set is not a violation. A Match with `exempted_by` unset is.

---

## Entity: Exemption

An explicit, justified marker that reclassifies a Match as a permitted record.

| Field | Type | Rule |
|---|---|---|
| `kind` | `inline` | **One member.** The set is closed (FR-013, amended 2026-07-30). |
| `justification` | str | Required and non-empty. |
| `location` | path plus line | Where a reviewer finds it. |

**The set has one member, not two.** An earlier revision typed `kind` as a union of `inline` and
`path-scope`, because three matches lived in a machine-generated file that cannot hold inline
markers. That turned out to be a misreading: the generated file's *content* contains no legacy term,
and all three matches were it recording the path of a badly named directory. Renaming the directory
removes the case, so `path-scope` has nothing to represent and is not modelled.

The checker still holds a path exclusion list. That list is **scan scoping**, a property of
ScanTarget discovery, and carries no exemption semantics. Modelling it as a kind of Exemption is what
made the previous checker's exclusion list read as a list of things that had been forgiven, when it
was really a list of places nobody had looked.

### kind = inline

- Detected by the token `legacy-term-ok:` appearing on the same line as the Match, followed by
  non-empty text.
- Case-insensitive, matching the checker's case-insensitive term matching. An exemption mechanism
  stricter than the matcher it exempts would fail to cover its own cases.
- Syntax-agnostic. The checker tests for the token as a substring and does not parse comment syntax,
  so the same rule serves Markdown, HTML, Python, YAML, shell, TypeScript and anything not yet
  encountered.
- **Line granularity makes the marker meaningless in minified or single-line documents.** The board
  file holds its entire card array on one physical line, so a marker there would exempt every card at
  once and permanently. Such files must be remediated by editing their content, never by marking
  them. Noted by adversarial review #3.
- The justification requirement is enforced, not advisory. A marker with an empty justification does
  not exempt, because FR-015 requires a human-readable reason and an unenforced requirement is a
  suggestion.
- **A marker under an application source, infrastructure, or frontend source tree is an error in
  itself** (FR-028, clarified 2026-07-30). It does not exempt, and it is reported with its own
  message rather than being silently ignored. Those trees hold code, and the AdjudicationRule exempts
  records of retirement, so no legitimate exemption can exist there. Reporting the marker rather than
  the term matters: silently ignoring it would surface as an ordinary violation, and a contributor's
  likely next move would be to assume the marker was malformed and try harder to make it work.
  The path test reuses the canonical ScanTarget path, so there is one notion of a path in the
  checker rather than two.

### The eliminated second mechanism

An earlier revision defined `kind = path-scope`: an entry in the checker's exclusion list, compared
against canonical paths as a prefix, reserved for machine-generated files. It was justified by
FR-017, which forbids exemptions that require editing regenerated files.

It is recorded here as removed rather than deleted silently, because the reasoning that produced it
was sound and a future contributor may well re-derive it. The premise it rested on was that a
machine-generated file contained a legacy term. It did not. It contained the *path* of a badly named
directory. Renaming the directory removed the case, and with it the mechanism.

**If you are about to re-add this**: first check whether the term is in generated content or in a
path the generated file records. If it is a path, rename the path. Only a term genuinely present in
generated content justifies amending FR-013.

**Invariant**: an empty exclusion list must never cause a passing result (FR-009). In the Python
implementation an empty list filters nothing, so the dangerous direction is unreachable rather than
guarded, but an explicit assertion and a test record it as an intended property.

---

## Entity: AdjudicationRule

The written policy deciding whether a Match qualifies for exemption. Not a runtime entity. It is
recorded here because FR-018 requires it to be durable and unambiguous enough that a future
contributor can decide a new case without reopening the debate, and SC-009 makes its clarity
measurable by requiring an independent reader to reach the same dispositions.

> An occurrence is **corrected** when the surrounding text asserts that a retired framework is
> current. An occurrence is **exempted** when the surrounding text records that the framework was
> retired, or discusses it as prior art. A legacy term reaching a machine-generated file is
> **corrected at its source, never exempted**: determine whether the term is in generated content or
> merely in a path the file records, and if it is a path, rename the path. Text that describes the
> checker itself is reworded so it needs no exemption.

The operative distinction: a document that would mislead a contributor into reintroducing the
framework is a violation. A document explaining why the framework is gone is the record the project
agreed to keep. The current corpus contains both, which is why a checker that cannot tell them apart
fails on all of it and gets treated as noise.

---

## Entity: Stage

One unit of the validation gate that independently passes or fails.

| Field | Type | Rule |
|---|---|---|
| `name` | str | The Make target name. |
| `gating` | `BLOCKING` \| `ADVISORY` | Must match observed behaviour (FR-005). |
| `exit_code` | int | The sub-make's exit code. **Note it is always 2 on any failure**: GNU Make normalises every recipe failure to 2 regardless of what the underlying command returned, so this field cannot distinguish a stage that exited 1 from one that exited 5. Verified by adversarial review #3. PASS or FAIL is the only meaningful signal; do not build logic on the value. |
| `outcome` | `PASS` \| `FAIL` \| `ADVISORY` | Derived. |

**Rules**

- Every Stage runs regardless of any earlier Stage's outcome (FR-001).
- Every Stage produces an execution marker, so a Stage that ran and passed is distinguishable from a
  Stage that never ran (SC-002). The absence of this distinction is the original defect.
- The gate exits non-zero if any BLOCKING Stage failed, and 0 only when all BLOCKING Stages passed
  (FR-003).
- An ADVISORY Stage never affects the gate's exit code. Labelling it as such is what makes the gate's
  verdict honest rather than what makes it lenient: the stage was already unable to fail, and the
  only change is that it now says so.

**Current stage inventory**

| Stage | Gating | Note |
|---|---|---|
| format check | BLOCKING | Switched to the check-only variant so the gate does not mutate the tree. |
| lint | BLOCKING | Unchanged. |
| dependency audit | ADVISORY | Structurally cannot fail. Promotion deferred by FR-005a to the dependency-alert feature. |
| static analysis | BLOCKING | Mixed internally: one scanner's failure is swallowed, the second genuinely gates and must stay that way (FR-006). |
| legacy-term check | BLOCKING | Rewritten by this feature. |
| test-target headers | BLOCKING | Scope corrected by this feature. |
| E2E race guard | BLOCKING | Unchanged. |

---

## Relationships

```text
LegacyTerm  ──matched in──▶  ScanTarget  ──produces──▶  Match
                                                          │
                                          ┌───────────────┴───────────────┐
                                          ▼                               ▼
                                  exempted_by = None              exempted_by = Exemption
                                   → VIOLATION                     → permitted record
                                          │                               │
                                          └──────────┬────────────────────┘
                                                     ▼
                                        AdjudicationRule decides which

Stage ──aggregated by──▶ gate driver ──▶ per-stage summary + single exit code
```

## State transitions

A Match has no persisted lifecycle. Within one run it is classified exactly once, and the
classification is a pure function of the line text and the exclusion list. There is no ordering
dependence between Matches, which is what allows every violation to be reported in a single pass
rather than the checker stopping at the first.
