# Phase 0 Research: Validation Gate Repair

**Feature**: `001-validate-gate-repair` | **Date**: 2026-07-30
**Input**: [spec.md](./spec.md), [plan.md](./plan.md)

## Terminology Note *(inherited)*

Retired framework names are never written here. They are called **legacy terms**. See the spec's
Terminology Note for why. Evidence quotations below are redacted to preserve this.

---

## R1. How the gate runs every stage without early exit

**Decision**: Convert `validate` from a prerequisite list into a driver recipe that invokes each
stage as a sub-make, captures each exit code, prints a per-stage summary, and exits non-zero if any
stage failed.

**Rationale**: The defect is structural. `validate: fmt lint security sast check-banned-terms
check-test-target-headers check-waitforresponse-race` asks Make to satisfy seven prerequisites, and
Make abandons the goal at the first one that fails. The two stages after the failing one never run,
so their silence is indistinguishable from success. That is exactly the condition the spec's User
Story 1 describes, and it is why a second blocker (the header guard) sat undetected behind the first.

A driver recipe removes the prerequisite relationship, so Make's fail-fast no longer applies, while
each stage remains an ordinary target that can still be run on its own. `make lint` keeps working.
Exit codes are captured per stage rather than inferred from the goal's success.

**Alternatives considered**:

- **`make -k validate` (keep going).** Rejected. It is a property of the invocation, not the target,
  so it only helps a caller who already knows to pass it. Anyone running the documented `make
  validate` gets the old behaviour, and CI would need to remember the flag. A gate whose correctness
  depends on the caller remembering a flag is not repaired.
- **A standalone `scripts/validate.sh` driver.** Rejected as the primary mechanism. It duplicates
  the stage list in a second place, so the Makefile and the script can drift, and the failure mode of
  that drift is a stage silently dropping out of the gate. That is the same class of defect being
  fixed. The recipe keeps one list.
- **Chaining with `;` and collecting `$?` inline in one shell.** Rejected. It requires inlining every
  stage body into a single recipe, destroying the independently invokable targets and making the
  Makefile substantially harder to read.

**Cost accepted**: Roughly seven sub-make invocations per run, on the order of tens of milliseconds
total, against a gate already exceeding two minutes. Negligible.

---

## R2. Not mutating the working tree

**Decision**: The gate's formatting stage switches from `fmt` to `fmt-check`.

**Rationale**: `fmt` runs the formatter in write mode with no check flag, so running the gate can
rewrite tracked files. `fmt-check` already exists in the Makefile, already runs the formatter in
check mode, and is currently referenced by nothing. The fix is a one-word substitution in the stage
list with no new code.

**Evidence and an important correction**: The spec's FR-004 originally overstated this. An
independent refuter established that the tree is currently formatter-clean, so the mutating stage is
a no-op today and no damage is occurring. The hazard is latent, not active. The requirement stands
anyway, because the gate exists precisely for trees that are not already clean, and on such a tree
the current behaviour silently edits the developer's files mid-validation. Building a remediation
task around undoing damage would be wrong; substituting the target is right.

**Alternatives considered**: Leaving `fmt` and documenting the behaviour. Rejected, because a gate
that modifies its subject cannot produce a reproducible verdict, and SC-007 requires two consecutive
runs to leave the tree byte-identical.

---

## R3. Truthful gating labels

**Decision**: Every stage declares BLOCKING or ADVISORY in the summary output, and the label must
match observed behaviour.

**Rationale**: Two stages currently misrepresent themselves.

- The dependency-audit stage ends with an unconditional echo after a command whose failure is
  swallowed. Its last command always succeeds, so the stage structurally cannot fail. It is presented
  as a validation stage and is in fact a report.
- The static-analysis stage is mixed. Its first scanner's failure is swallowed; its second scanner
  runs with an error flag and genuinely does gate. A prior feature established that second behaviour
  deliberately, and FR-006 requires preserving it. The stage as a whole can fail, so it is BLOCKING,
  but the internal asymmetry is worth recording so a future reader does not "tidy" the swallowed
  first scanner into a blocking one by accident.

**Why the advisory stage is not promoted here**: Making the dependency-audit stage blocking would
hold the gate red until the separate dependency-alert backlog is cleared, directly contradicting
SC-001. The spec resolves this in FR-005a: label it truthfully, defer the promotion, record the
reason. This is a deliberate deferral to a separate feature, not an oversight.

**Alternatives considered**: Removing the advisory stage from the gate entirely. Rejected. It
produces useful output, and removing it would reduce what the gate covers in a feature whose purpose
is to make coverage honest.

---

## R4. Implementation language for the checker rewrite

**Decision**: Rewrite as stdlib-only Python 3.13 at `scripts/check_banned_terms.py`, with unit tests
at `tests/unit/scripts/test_check_banned_terms.py`. Delete the Bash version.

**Rationale**: Three independent forces point the same way.

1. **The constitution requires it.** The Implementation Accompaniment Rule states that all
   implementation code must be accompanied by unit tests covering a happy path and at least one error
   path, at 80% coverage for new code. A rewritten checker is implementation code. Bash is not
   practically unit testable, and this repository has no Bash test harness.
2. **Three success criteria are only expressible as tests.** SC-004 (a deliberately introduced term
   is detected), SC-005 (a file containing both an excluded-path string and a term is still
   reported), and SC-006 (an empty exclusion configuration does not pass) each require constructing a
   filesystem state that must not be left behind. That is a `tmp_path` fixture, not a manual
   procedure. Attempting them by hand against the live repository is how the current defects survived.
3. **Precedent exists for the CI wiring.** The prior feature's guard is stdlib-only Python invoked
   directly in a workflow step with no install step, because the runner already provides the
   interpreter. Copying that shape means the new step needs no dependency management.

**One defect in the precedent is deliberately not copied**: that guard is 429 lines, wired into a
required job, and has zero unit tests. This feature follows its CI-wiring pattern and not its testing
posture.

**A structural benefit that falls out of the language change**: the fail-open defect has no Python
analogue. In Bash the exclusion filter is built by string concatenation and handed to a pattern
matcher; when the list is empty the pattern becomes empty, the matcher matches every line, every
finding is discarded, and the checker prints success on a repository with seventeen violations. In
Python an empty exclusion list is an empty list, and filtering by it removes nothing. The dangerous
direction becomes the impossible one rather than the guarded one. An explicit assertion and a test
are still added, because FR-009 asks for fail-closed behaviour to be a stated property rather than an
accident of implementation.

**Alternatives considered**:

- **Patch the Bash in place.** Rejected. It leaves the constitution's test requirement unmet, and the
  filename cannot be imported by pytest.
- **Keep Bash, add a shell test harness.** Rejected. Introducing a new test framework to this
  repository to test one script is disproportionate, and the repository already has an established
  home for script tests in `tests/unit/scripts/`.

**Filename note**: underscores rather than hyphens, so the module is importable. The hyphenated name
is the mechanical reason the current checker could never have been tested.

---

## R5. Exemption mechanism

**Decision (amended 2026-07-30): exactly one mechanism, the inline marker.** The token
`legacy-term-ok:` followed by non-empty justification text, appearing on the same line as the match.
Case-insensitive, matching the checker's own case-insensitive term matching.

The path-scope exclusion originally proposed as a second mechanism was eliminated rather than
implemented. See "Why one mechanism and not two" below. The checker still carries a path exclusion
list, but its role is **scan scoping** (deciding which trees are searched at all) with no exemption
semantics attached, which is a different thing and is not part of the sanctioned set.

**Why the marker is syntax-agnostic**: The checker looks for the token anywhere on the line and does
not care what comment syntax wraps it. That single rule covers every format the repository needs:

| Format | Wrapper | Needed for |
|---|---|---|
| Markdown, HTML | `<!-- legacy-term-ok: reason -->` | FR-016, and the drift document |
| Python, YAML, shell, Make | `# legacy-term-ok: reason` | Future source and config cases |
| TypeScript, JavaScript | `// legacy-term-ok: reason` | Future frontend cases |

This is one mechanism with several lexical wrappers, not several mechanisms. The checker's rule is a
single substring test. It satisfies FR-016 without the checker needing to know any file's language,
which also means a format nobody anticipated works on the first try.

**Why one mechanism and not two.** This reversed twice, and the reversal is the most instructive
thing in this document.

FR-013 originally demanded exactly one mechanism. Adversarial review #1 found that unsatisfiable
against FR-017: three matches live in a machine-generated file that a tool rewrites, so any inline
marker placed there is destroyed on the next regeneration. A path-scoped mechanism looked
structurally required, FR-013 was amended to a minimal enumerated set, and two was recorded as the
floor rather than a convenience.

That reasoning was correct given a premise nobody had checked. Prompted by the owner, the premise was
tested: **the machine-generated file's contents contain zero legacy terms.** All three matches are
that file recording the *path* of a scanned file, and the term sits in the enclosing directory's
name. The file does not mention a retired framework. It lists a badly named directory.

Rename the directory and the generated-file case has no instances, so the second mechanism has
nothing to serve. One becomes achievable after all.

The lesson worth carrying: adversarial review #1 correctly derived that two mechanisms were needed
*given* the corpus as described, and the derivation was sound. It was working from a description of
the corpus rather than from the corpus, and the description had silently equated "a generated file
containing a term" with "a generated file listing a badly named path". Those need different fixes,
and only one of them requires a mechanism.

**Applicability rule**, which is the thing that keeps the set from growing:

> The inline marker is the only sanctioned exemption. It applies where a human wrote the line and a
> human will keep writing it, and only where the line records that a framework was retired rather
> than asserting it is current. It is refused outright under application source, infrastructure and
> frontend source (FR-028).
>
> If a machine-generated file is ever found to contain a legacy term, do not reach for a path-scoped
> exemption. First establish whether the term is in the file's *content* or merely in a path the file
> records. If it is a path, rename the path; that is a root-cause fix and needs no mechanism. Only a
> term genuinely present in generated *content* would justify amending FR-013 to re-add a second
> mechanism.

**Prior art followed**: the repository already uses `# pragma: allowlist secret` for its secret
scanner. The marker deliberately reads the same way so it needs no explanation to anyone who has seen
the existing convention.

### R5b. Marker scope: refused in application source

**Decision (owner, 2026-07-30): an inline marker under application source, infrastructure, or
frontend source is an error in itself.** Recorded as FR-028 and SC-013.

The spec's edge cases originally acknowledged that any per-line opt-out is pasteable onto a genuine
violation, and chose review visibility plus a mandatory justification as the mitigation rather than
making it impossible. This decision tightens that choice in the one place where the weaker mitigation
would cost something real.

**Rationale**: the adjudication rule exempts records that a framework was retired. Application
source, infrastructure and frontend source contain code, not records. So no legitimate exemption can
exist in those trees, which means refusing them there removes a bypass without removing any
capability anyone would legitimately want. It converts "a reviewer should notice this" into "this
cannot merge".

**Implementation note that keeps this cheap**: the check is a path-prefix test on a value the checker
already computes for exclusion purposes, so it reuses the normalisation from R6 rather than adding a
second notion of what a path is. One rule, one test.

**Important distinction, and the reason FR-028 says "error in itself"**: silently ignoring the marker
would mean the line is reported as an ordinary violation, and the contributor's most likely next move
is to assume the marker was malformed and try harder to make it work. Reporting the marker itself as
the error tells them the mechanism does not apply here and that removal is the only remedy. Same exit
code, very different next action.

**Not extended to documentation.** Markers there stay deterred rather than impossible, per the spec's
original choice: documentation is where legitimate records live, and the audit command plus review
visibility are the proportionate controls.

---

## R6. Checker correctness defects and their fixes

Four defects, all confirmed against live state, two demonstrated with probes.

| Defect | Current behaviour | Fix |
|---|---|---|
| **Content-matched exclusions** (FR-007) | Exclusions are applied to the search tool's whole output line, which is `path:lineno:content`. Any file whose *content* mentions an excluded path suppresses its own finding. Demonstrated: a probe file containing both an excluded-path string and a term was entirely absent from output, while a control containing only the term was reported. | Separate path from content before filtering. Exclusions compare against the path field only, never the content field. |
| **Fail-open on empty config** (FR-009) | An empty exclusion list produces an empty filter pattern, which matches every line, discarding every finding. Demonstrated on a copy: prints success and exits 0 on a repository with seventeen real matches. | No analogue in the Python rewrite, plus an explicit assertion and a test. |
| **Accidental prefix anchoring** (FR-027) | Exclusions match only because the search tool emits a leading `./` on every path. Changing the scan root to an absolute path or a glob would silently disable every exclusion at once, and the corpus would jump by roughly three orders of magnitude. | Normalise every path to a repository-relative form before comparing, and compare explicitly. Correctness stops depending on a tool's output formatting. |
| **Near-miss path spelling** (FR-008) | The machine-generated file stores paths without the leading prefix the exclusion is written with, so an already-excluded directory is not excluded there. This is what puts three of the seventeen matches in the corpus. | The same normalisation fixes it. Both spellings resolve to one canonical form. |

**Note on the direction of these defects.** The checker is wrong in both directions at once. It
under-reports when content collides with an excluded path, and it would over-report catastrophically
if the scan root changed. Neither is a tuning problem. Both are the result of treating a formatted
output line as structured data.

**Pattern metacharacters** (spec edge case, no requirement attached): terms are matched
case-insensitively as patterns rather than literals, and one term contains characters that behave as
wildcards, so it matches several separator spellings. This is currently harmless and may be
deliberate. The rewrite preserves the observable behaviour and documents it at the term list, rather
than changing it, because altering the term list is explicitly out of scope.

**Self-exclusion**: the checker contains the term list, so it must exclude its own file. The current
version does this by filename. The rewrite does it by resolved path, which is one more instance of
not depending on incidental spelling.

---

## R7. The header guard's scope defect

**Decision**: Extend the guard to accept a third sanctioned declaration, for test files that target
infrastructure rather than either dashboard.

**Rationale**: The guard requires a `Target:` line naming one of two dashboards, on every file
matching its globs. Eleven files fail. Reading all eleven shows five of them exercise a firewall, an
identity provider, a content delivery network, a function URL access policy, and backend log groups.
None of those belongs to a dashboard. The guard is demanding a declaration that can only be satisfied
by writing something untrue.

**The motivating evidence, with a correction.** `tests/e2e/test_log_visibility.py` opens with a
`Target:` line stating it targets backend log groups and neither dashboard UI. Someone reached for
the convention's intent and found the vocabulary missing, which is the clearest available signal that
a third category is needed.

An earlier draft went further and claimed the repository had "already solved this organically", so
that widening the guard would resolve that file untouched. Adversarial review #3 disproved it: the
header declares what the file is *not* rather than naming a category, so no widened pattern accepts
it without also accepting any file that merely mentions a dashboard. Verified by running the widened
pattern, which still leaves all eleven files failing. The file needs an edit like the others. The
argument for a third category stands; the convenient corollary did not.

**Why this is a scope correction and not a weakening**: the guard's purpose, stated in the project
instructions, is to stop contributors confusing two dashboards that have caused four separate
incidents. It achieves that by forcing an explicit declaration on every scanned test. That property
is untouched. Only the set of acceptable answers grows from two to three, and the third was already
in use. The guard still fails a file with no declaration, which FR-025 requires and which gets a test.

**Alternatives considered**:

- **Write dashboard headers into the five infrastructure tests.** Rejected, and not marginally. The
  constitution's Functional Integrity Principle names this exact anti-pattern: making a check pass by
  corrupting its input rather than fixing the check. It would also actively defeat the guard's
  purpose, since a firewall test labelled as a dashboard test is precisely the confusion the guard
  exists to prevent.
- **Remove the infrastructure tests from the guard's globs.** Rejected as the primary approach. It
  buys silence rather than information, and the glob would need maintaining as a deny list forever.
  The spec's amended Out of Scope does permit narrowing scan scope where adjudication warrants it, so
  this stays available as a fallback if the third category proves unworkable for a specific file.

---

## R8. Merge-gate enforcement

**Decision**: Add one step to the existing required lint job in the pull-request workflow, and one
pre-commit hook for local feedback.

**Rationale**: The policy is currently enforced by nothing. The checker appears in no workflow and no
hook, and the only reference to the gate anywhere in the workflow directory is a comment. A policy
that runs only when an individual chooses to run it locally documents intent rather than constraining
behaviour.

FR-022a constrains where it can go. The default branch's required contexts are fixed at four and
branch protection is owner-gated, outside this feature's authority. So the step must join a job that
is already required. The lint job is required; the pre-commit job is not.

**Precedent to copy exactly**: the prior feature faced this identical constraint and put its
Playwright race guard inside the lint job, with a long comment explaining that the apparent misfiling
is deliberate and that moving it would silently downgrade the guard to advisory with no symptom until
a violation merged green. The new step follows that shape, including running the checker directly
rather than through pre-commit so the pre-commit job's skip mechanism cannot reach it, and including
the always-run condition so an earlier lint failure does not suppress it.

**The pre-commit hook is deliberately secondary.** It gives fast local feedback and is not
load-bearing, because that job is not a required context.

**Consequence that raises the stakes on correctness**: a checker in a required job blocks every merge
in the repository when it fails. Combined with fail-closed behaviour, a defect in the checker or its
configuration is a repository-wide outage. This is why FR-022b requires the failure output to name
the specific cause and the remedy, and why the unit tests are non-negotiable. This code must not be
first exercised in a blocking position.

---

## R9. Exemption auditability

**Decision**: A `--list-exemptions` mode on the checker, surfaced as `make audit-exemptions`, that
prints every inline marker with its path, line, and justification, plus a total count. Since the
sanctioned set is one mechanism, that listing is complete by construction. Scan-scope exclusions are
deliberately not listed as exemptions: they decide what is searched, not what is forgiven, and
conflating the two is what made the previous checker's exclusion list look like an exemption list.

**Rationale**: FR-026 requires one-command enumeration so exemptions can be audited rather than
silently accumulating. The repository already has this instinct: `make audit-pragma` audits
suppression comments for the linter and the security scanner. The naming and behaviour deliberately
mirror it.

SC-012 requires recording the resulting count as a baseline so future growth is visible. Under the
recommended disposition set that baseline is small, which is the point. If the count ever climbs, the
adjudication rule is being applied loosely and FR-018 needs revisiting rather than the count needing
accepting.

---

## R10. Root cause: the match factory

**Decision**: Scrub the legacy term from `.specify/templates/plan-template.md`. Treat this as a
required task, not a cleanup nicety.

**Discovery**: This was found by executing this planning step, not by inspection. Running the setup
script raised the corpus from 17 to 18. The template's line 21 carries a legacy term as an example
value in its "Primary Dependencies" field. The template directory is on the exclusion list, so the
template itself is invisible to the checker, but every plan generated from it lands in `specs/`,
which is scanned. Filling in this plan's real Technical Context removed the injected match and the
checker confirmed the count returned to 17.

**Why it matters more than its size suggests**: one match per feature planned, forever. Two matches
in the current corpus are already its output: `specs/1268-cors-404-headers/plan.md` line 21 is the
placeholder left unedited, and this file's first draft was the second. Remediating the corpus without
this fix produces a gate that is green on merge day and red again after the next feature is planned.
The spec's User Story 2 argued that the corpus regrows and cited one prior instance. This is the
mechanism, and it regrew during the planning of the feature that exists to stop it.

**Scope check**: this is not "adding or removing entries in the legacy-term list", which is out of
scope. It is removing a use of a term from a template, which is ordinary corpus remediation under
FR-019, and it happens to be the only remediation that prevents recurrence.

**Follow-on**: the two other specs carrying the same unedited placeholder are corrected by the same
reasoning. Whether any downstream template carries similar examples is worth one check during
implementation.

---

## Stage 4 clarification outcomes

| # | Question | Outcome |
|---|---|---|
| Q1 | Disposition of the nine matches in the superseded auth-cache-headers spec directory: move under the excluded archive path, add a status banner plus nine inline markers, or rewrite the occurrences. | **Resolved 2026-07-30: rewrite the occurrences.** The recommendation had been to move the directory, on the grounds that it was the smallest change and preserved every word. The owner chose correction over preservation. The reasoning is sound and worth recording: these are the corpus's only true positives, and exempting the only real violations by relocating them would have left the adjudication rule untested against the exact case it was written for. |
| Q2 | Should an inline marker under application source, infrastructure, or frontend source be an error in itself (R5b)? | **Resolved 2026-07-30: yes.** Adopted as FR-028 and SC-013. See R5b above. |
| Q3 | Exact wording of the third `Target:` declaration category, and whether the three CORS test files are infrastructure or customer-facing. | Not escalated. Adopt the form already in use in the repository. The three CORS files need one read each during implementation. Task detail, not a design question. |

No open questions remain. Task generation is unblocked.

---

## Summary of resolved unknowns

All Technical Context fields are resolved. No NEEDS CLARIFICATION markers remain. The three open
questions above are dispositional choices with recommendations, not unresolved technical unknowns.
