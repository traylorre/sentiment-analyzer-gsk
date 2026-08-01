# Enforcement Recommendation: CodeQL JavaScript/TypeScript Coverage

**Feature**: `001-codeql-coverage` | **Deliverable of**: FR-017, FR-017a, SC-011
**Dates in ISO 8601 (`YYYY-MM-DD`), per constitution Amendment 1.5.**

This document is a **decision request**, not a decision. It is carried forward as a follow-up item
and is deliberately NOT applied inside this feature: FR-015 bars this feature from adding a merge
gate and SC-006 verifies the four required contexts are unchanged in name and count.

---

## Status of this document

**INCOMPLETE. Two fields are PENDING and are named as such rather than guessed.**

Both depend on data that does not exist yet, because it can only be produced by the first
`refs/heads/main` JavaScript/TypeScript analysis after merge (T033), and this branch has not been
pushed or merged. They are:

- the **severity threshold** and the **blocking position**, which FR-017 requires to be justified
  by the OBSERVED alert volume from T034 and T035
- the **decision-by date**, which is defined relative to the close-out date that T036 writes at
  baseline capture

Every other required item is complete below. **Do not read a PENDING field as "no threshold" or
"non-blocking by default".** A blank justified by absent data is the honest state; inventing a
threshold from an imagined volume is the failure this feature spent its whole design avoiding.

---

## 1. Severity threshold

**PENDING the T034/T035 volume.**

The threshold is to be chosen from the observed baseline distribution, not from a convention. The
rule that constrains the choice regardless of volume: **a non-blocking enforcement position is a
statement about the automated gate, not about triage urgency.** FR-016 requires disposition inside
the window regardless of severity, and `fix now` is the expected route for anything at critical or
high severity whatever this threshold ends up being.

## 2. Path scope

**RECOMMENDED, and not volume-dependent.** Three classes, already partitioned at FR-020:

| Path class | Members | Recommended treatment |
|---|---|---|
| Product code | `frontend/src` (173 files), `src/dashboard` (6 files) | In scope for any enforcement |
| Test code | `frontend/tests` (101 files) | Out of scope for enforcement; disposition still required |
| Non-shipping artifacts | root and `frontend/` build configuration, contract stubs under `specs/` | Out of scope for enforcement; disposition still required |

The scope ceiling this partitions is **290 in-scope files of 291 tracked** (measured at this
commit: `frontend/src` 173, `frontend/tests` 101, `src/dashboard` 6, leaving 10 configuration and
contract-stub files; one file, `tests/load/api-load-test.js`, sits under the root-anchored
`tests/**/*` exclusion). Note the ceiling is WIDER than the two dashboards, which is why the third
class exists at all: contract stubs under `specs/` are specification artifacts that never ship.

## 3. Blocking or non-blocking position

**PENDING the T034/T035 volume**, which is what FR-017 requires it to be justified by.

What is already settled and is NOT pending: the position **as of this feature landing** is
**non-blocking**, because FR-015 forbids adding a merge gate and SC-006 pins the required contexts
at exactly four. Adding `javascript-typescript` to the matrix ADDS the status context
`Analyze (javascript-typescript)` and renames nothing, so nothing branch protection names moves.
The question this document raises is whether that should CHANGE, and that is item 9.

## 4. Role that decides

**Admin Role (Project Owner: @traylorre)**, cited to `CONTRIBUTING.md:64`, whose listed
responsibilities already include "Respond to security incidents" (`CONTRIBUTING.md:74`).

Recorded with the citation rather than as a bare handle so a later reader can check it against a
source. A recommendation with no named recipient is a document, not a decision request.

## 5. Decision-by date

**PENDING.** Defined as **10 working days after the close-out date recorded at T036**, which is
itself computed from the timestamp of the first post-merge `refs/heads/main`
JavaScript/TypeScript analysis. Neither exists yet. Write the concrete ISO 8601 date here at
close-out; a duration with no start date is not a deadline.

## 6. Adjacent questions carried under this document's decider and date (FR-017a)

### 6a. The `frontend/tests` symmetry question

TRANSCRIBED from Clarification Q4. Not re-argued, because Q4 wrote the argument in full and a
second argument invites one that disagrees with the first.

The asymmetry is larger than glob anchoring alone suggests. The Python side is an
**extraction-level** exclusion removing 393 files from the database entirely, verified from the
extractor invocation. The `frontend/tests` side is 101 files matching no exclusion pattern at all.
Narrowing or widening either side requires editing a rule in the shared config, which **FR-008**
bars until the surviving control question is answered. The asymmetry is therefore **preserved
deliberately for this feature's duration, because resolving it would require exactly the unprobed
rule change FR-008 exists to prevent.**

**Question for the decider**: should the two sides be made symmetric, and in which direction?
Excluding `frontend/tests` loses coverage of about 19,900 lines; including root `tests/` gains
393 Python files that have never been in a CodeQL database.

### 6b. The FR-004b dependency-install constraint

**This is a constraint on any future change, not a question.** Any future dependency install
**MUST NOT** be placed in a job that both holds `security-events: write` and is reachable from an
untrusted reference.

The reason, measured: the analysis job holds `security-events: write` and is triggered by
`pull_request` on a **public** repository. An install step there would execute
contributor-authored package lifecycle scripts inside a job holding write access to the
security-events surface. Fork runs get a downgraded read-only token; branch pushes by any account
with write access do not.

**The cost of the current no-install decision is recorded, not assumed away**: without installed
dependencies, type resolution and library modelling degrade, which weakens taint tracking through
framework boundaries in exactly the first-party code this feature exists to cover, and the owner
directive names taint analysis specifically. The measured resolution-warning evidence is at the
evidence log's FR-004a field.

## 7. The §10 local-SAST gap

Recorded in `plan.md`'s Constitution Check and written to the registry as **TD-025**.

`make sast` runs `bandit -c pyproject.toml -r src/` and `semgrep scan --config auto ... src/`.
Both are scoped to `src/` only. After this feature lands, CodeQL covers `frontend/` and no local
pre-push tier does. This is a **widened asymmetry, not a regression**: before this feature neither
tier covered `frontend/`, and nothing that used to be checked stopped being checked.

**Question for the decider**: extend the local tier with a JavaScript/TypeScript ruleset over
`frontend/src` and `src/dashboard`, or record a deliberate decision that the local tier stays
Python-only and CodeQL is the sole JavaScript/TypeScript tier?

## 8. Deferral 1, carried verbatim

Routed here from Clarification Q2 so it reaches this document's named decider under this
document's decision-by date, rather than expiring inside a clarifications appendix.

> Constitution §9 cites `docs/TECH_DEBT_REGISTRY.md` at `.specify/memory/constitution.md` lines
> 527, 569 and 584, but the registry has lived at `docs/reference/TECH_DEBT_REGISTRY.md` since
> `f8db8d2` (PR #668). Amend §9 to the real path, or move the file back?

Not blocking, and not this feature's to fix.

## 9. Promoting CodeQL to a required status check

**Deliberately OUT OF SCOPE of this feature, and an owner question.**

This feature adds no merge gate (FR-015) and changes no required context (SC-006). The four
required contexts on `main` are `Secrets Scan`, `Lint`, `Run Tests` and `Playwright E2E Tests`,
verified unchanged. **CodeQL gates nothing today**, before or after this change.

Adversarial Review #1 finding 20 concluded the case for promotion is strong, on the grounds that a
scanner which gates nothing produces data rather than enforcement. That conclusion is recorded, not
adopted. Promotion is a new merge gate and belongs to its own feature with its own evidence, which
is what this document exists to produce the input for.

**If it is ever promoted**: branch protection will name the per-language context string
(`Analyze (python)`, `Analyze (javascript-typescript)`), and a later matrix edit would silently
retire the context that names it. The FR-022 warning comment now sitting above the `codeql` job is
the guard against exactly that, and it is the only such guard; verify it is still there before
promoting.

---

## Checklist for the decider

- [ ] 1. Severity threshold, chosen from the observed baseline distribution
- [ ] 2. Path scope, confirmed or amended
- [ ] 3. Blocking or non-blocking position, justified by the observed volume
- [ ] 4. Decider named and confirmed: Admin Role (Project Owner: @traylorre), `CONTRIBUTING.md:64`
- [ ] 5. Decision-by date written as a concrete ISO 8601 date
- [ ] 6a. `frontend/tests` symmetry: make symmetric, and in which direction, or leave as is
- [ ] 6b. FR-004b install constraint: acknowledged as binding on future changes
- [ ] 7. §10 local-SAST gap (TD-025): extend the local tier, or record Python-only as deliberate
- [ ] 8. Deferral 1: amend constitution §9's path, or move the registry file back
- [ ] 9. Promote CodeQL to a required status check, or record a decision not to
