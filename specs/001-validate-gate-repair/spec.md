# Feature Specification: Validation Gate Repair

**Feature Branch**: `001-validate-gate-repair`
**Created**: 2026-07-30
**Status**: Draft
**Input**: Repair `make validate` so it is a trustworthy gate, and redesign the legacy-term checker so it can distinguish code that USES a retired framework from documentation that RECORDS that the framework was retired.

## Terminology Note *(read first)*

This document deliberately never writes the retired framework names in full. The checker under
discussion scans `specs/` and would flag this file, adding to the very corpus this feature exists to
clear. That is not a stylistic choice, it is the failure mode that produced two of the seventeen
current matches. Throughout, the scanned strings are referred to as **legacy terms**, and the
authoritative list lives in one place only: the `BANNED_TERMS` array in the checker script.

Any downstream artifact of this feature inherits this constraint.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer runs the validation gate and gets a truthful answer (Priority: P1)

A maintainer runs the repository's single validation command before pushing. Today that command
cannot succeed on a clean checkout, and its failure message names only the first stage that failed.
Two of the seven stages never run at all, so their silence is indistinguishable from success. The
maintainer needs a command whose exit code means what it says and whose output accounts for every
stage it claims to cover.

**Why this priority**: This is the whole point of the feature. Every other story is a precondition
or a hardening step. A gate that cannot pass is a gate nobody runs, and a gate nobody runs is
equivalent to no gate. Two shipped guards are currently inert because of it.

**Independent Test**: On a clean checkout, run the validation command. It exits 0, and its output
contains a distinct completion marker for every stage listed as a prerequisite.

**Acceptance Scenarios**:

1. **Given** a clean checkout with no local modifications, **When** the maintainer runs the
   validation command, **Then** it exits 0.
2. **Given** a clean checkout, **When** the validation command runs to completion, **Then** the
   output contains an execution marker for each of the three `check-*` guards, not merely the first
   one.
3. **Given** a repository where one guard would fail, **When** the validation command runs, **Then**
   the output still accounts for every stage, and the summary identifies which stages passed and
   which failed rather than stopping at the first failure.
4. **Given** a clean checkout, **When** the validation command completes, **Then** `git status`
   reports the working tree is unchanged from before the run.

---

### User Story 2 - A reviewer can tell a real violation from a historical record (Priority: P1)

A contributor writes a design document explaining that a retired framework was removed and why. A
second contributor reintroduces a dependency on that framework in application code. The legacy-term
checker must fail on the second and stay silent on the first. Today it cannot tell them apart, so it
fails on both, and the repository has learned to treat its failure as noise.

**Why this priority**: This is the design defect underneath the P1 symptom. Clearing the current
seventeen matches without fixing the classification rule guarantees the corpus regrows, because the
repository will keep producing documents that discuss the retired frameworks. It regrew once already
between the last clean state and today.

**Independent Test**: Introduce a legacy term into an application source file. The checker fails.
Introduce a legacy term into a designated documentation file using the sanctioned exemption
mechanism. The checker passes. Revert both.

**Acceptance Scenarios**:

1. **Given** a source file under the application tree, **When** a legacy term is added to it,
   **Then** the checker exits non-zero and names that file and line.
2. **Given** a documentation file whose purpose is to record the retirement, **When** it references a
   legacy term through the sanctioned exemption mechanism, **Then** the checker exits 0.
3. **Given** a documentation file that references a legacy term **without** the sanctioned exemption,
   **Then** the checker exits non-zero. Exemption must be explicit and visible, never inferred.
4. **Given** an exemption, **When** a reviewer reads it, **Then** the justification for that specific
   exemption is legible at the point of use, not stored in a separate registry.

---

### User Story 3 - The policy actually gates a merge (Priority: P2)

A contributor opens a pull request that reintroduces a retired framework reference. Today every
required merge check passes, because the legacy-term policy runs only when an individual developer
chooses to run it locally. The contributor merges. The policy is documented, believed to be
enforced, and is not.

**Why this priority**: P2 rather than P1 because it does not block the gate from working, but a
policy enforced only by voluntary local action is a policy that documents intent rather than
constraining behaviour. It is the difference between a rule and a suggestion. Deferred below P1
because enforcing an unreliable checker would be worse than not enforcing it, so the checker must be
correct first.

**Independent Test**: Open a pull request containing a legacy term in an application source file and
confirm a required check fails. Alternatively, if the decision is to not enforce in CI, confirm the
spec records that decision with its justification.

**Acceptance Scenarios**:

1. **Given** a pull request introducing an unexempted legacy term, **When** the merge checks run,
   **Then** at least one required check fails.
2. **Given** the project decides against CI enforcement, **When** a reader consults this feature's
   artifacts, **Then** an explicit, justified decision is recorded rather than an unstated omission.

---

### User Story 4 - The checker cannot be silently bypassed (Priority: P2)

An attacker, or an ordinary contributor working around a nuisance, wants a legacy term to pass
unnoticed. Two structural weaknesses currently allow it. First, the exclusion filter is applied to
the checker's whole output line, which includes the matched file content, so content that merely
mentions an excluded path suppresses its own finding. Second, if the exclusion list is ever emptied,
the filter degenerates and the checker reports success unconditionally.

**Why this priority**: These are latent rather than active. No current match exploits them. But a
security checker whose empty configuration means "everything passes" fails in the most dangerous
possible direction, and a content-sensitive filter is a bypass that requires no privileges to use.

**Independent Test**: Construct a file containing both an excluded-path string and a legacy term.
The checker must still fail. Separately, empty the exclusion list and confirm the checker does not
report success.

**Acceptance Scenarios**:

1. **Given** a file whose content includes text matching an excluded path **and** a legacy term,
   **When** the checker runs, **Then** it reports the violation.
2. **Given** an empty exclusion configuration, **When** the checker runs, **Then** it either scans
   everything or refuses to run. It must not report success by default.
3. **Given** any exclusion configuration, **When** exclusions are applied, **Then** they are matched
   against file paths only, never against file content.

---

### Edge Cases

- **Generated files that regenerate their own violations.** The secrets baseline is machine-written
  and stores paths of scanned files. Three current matches are its records of a retired-framework
  archive directory. Hand-editing them is futile because the next regeneration restores them. The
  exemption mechanism must survive regeneration, meaning it cannot live inside the generated file.
- **Near-miss exclusion prefixes.** The archive directory is already excluded, but the generated file
  stores the path without a leading `./` while the exclusion is written with one. A rule that depends
  on incidental path spelling is fragile. Path matching must normalise before comparing.
- **Legacy terms are matched as patterns, not literal strings.** One entry in the list contains
  characters that behave as wildcards, so it matches separators the author may not have intended.
  This is currently harmless and possibly deliberate, but it is undocumented and a future term
  containing pattern metacharacters could match far more or far less than intended.
- **Case sensitivity.** Matching is case-insensitive. An exemption mechanism must be equally
  case-insensitive or it will fail to cover the matches it is meant to cover.
- **The exemption becomes the bypass.** Any per-line opt-out can be pasted onto a genuine violation.
  Mitigation is that exemptions are visible in review and must carry a justification, not that they
  are impossible.
- **This feature's own artifacts.** Every document this feature produces is scanned. They must either
  avoid the legacy terms entirely or use the sanctioned exemption.
- **A guard fails while another guard also fails.** The maintainer needs both reported from one run,
  otherwise fixing the first reveals the second and the loop repeats once per defect.
- **Concurrent or dirty working tree.** The gate must be safe to run when the tree has uncommitted
  work, which it is not today.

## Requirements *(mandatory)*

### Functional Requirements

**Gate structure**

- **FR-001**: The validation gate MUST execute every stage it lists, regardless of whether an earlier
  stage failed.
- **FR-002**: The validation gate MUST report a per-stage pass or fail summary at the end of a run.
- **FR-003**: The validation gate MUST exit non-zero if any stage failed, and exit 0 only when all
  stages passed.
- **FR-004**: The validation gate MUST NOT modify any tracked file as a side effect of running. It
  MUST verify formatting rather than apply it. Note this hazard is currently latent, not active: the
  tree happens to be formatter-clean, so the mutating stage is a no-op today. The requirement stands
  because the gate must be safe on a tree that is not already clean, which is the case it exists for.
- **FR-005**: Every stage inside the validation gate MUST declare its gating status explicitly, and
  that status MUST match its actual behaviour. A stage that cannot fail MUST be labelled advisory in
  the gate's own output. A stage presented as blocking MUST be able to block.
- **FR-005a**: Converting a currently-advisory stage into a blocking one is OUT OF SCOPE for this
  feature where doing so would import a separate feature's backlog. Specifically, the dependency-audit
  stage reports findings from the open dependency-alert backlog; making it block would keep the gate
  red until that separate feature lands, contradicting SC-001. It MUST therefore be labelled advisory
  here, and the decision to make it blocking is deferred with a written rationale.
- **FR-006**: The existing failing behaviour of the comprehensive static-analysis stage MUST be
  preserved.

**Checker correctness**

- **FR-007**: The checker MUST apply path exclusions to file paths only, never to matched file
  content.
- **FR-008**: The checker MUST normalise paths before comparing them against exclusions, so that
  equivalent spellings of the same path are treated identically.
- **FR-009**: The checker MUST NOT report success when its exclusion configuration is empty or
  unreadable. It MUST fail closed.
- **FR-010**: The checker MUST exit non-zero when a legacy term appears in application source,
  configuration, or infrastructure files without a sanctioned exemption.
- **FR-011**: The checker MUST exit 0 when every remaining occurrence carries a sanctioned exemption.
- **FR-012**: The checker MUST report every violating file and line in a single run, not stop at the
  first.

**Exemption mechanism**

- **FR-013**: The project MUST define a minimal enumerated set of sanctioned exemption mechanisms,
  each with a written applicability rule, and the checker MUST honour only those. Exactly one
  mechanism is not achievable: an inline marker cannot reach machine-generated files (FR-017), so a
  path-scoped mechanism is structurally required alongside it. The set MUST be as small as possible
  and MUST NOT grow without amending FR-018's adjudication rule.
- **FR-014**: An exemption MUST be visible at or adjacent to the line it exempts.
- **FR-015**: An exemption MUST carry a human-readable justification.
- **FR-016**: The exemption mechanism MUST work in the file formats where exemptions are actually
  needed, at minimum Markdown and HTML.
- **FR-017**: The exemption mechanism MUST NOT require editing machine-generated files, because such
  edits do not survive regeneration.
- **FR-018**: The project MUST record a written adjudication rule stating which occurrences qualify
  for exemption, sufficient for a future contributor to decide a new case without re-opening this
  debate.

**Corpus remediation**

- **FR-019**: Each of the seventeen current matches MUST be individually adjudicated as either a
  genuine stale reference to correct, or a legitimate record to exempt. The disposition of each MUST
  be recorded.
- **FR-020**: The board card introduced by the prior feature MUST be reworded so it describes the
  legacy terms without reproducing them.
- **FR-021**: After remediation, the checker MUST report zero unexempted matches.

**Second blocker: test target headers**

- **FR-024**: The test-target-header guard currently fails on 11 files that lack the required header.
  Each MUST be individually adjudicated as either a file that should carry the header, or a file the
  guard should not be scanning. The disposition of each MUST be recorded.
- **FR-025**: After remediation the test-target-header guard MUST exit 0, and MUST still fail when a
  scanned test file is added without the required header.

**Exemption hygiene**

- **FR-026**: Every exemption in the repository MUST be enumerable by a single command, so that
  exemptions can be audited rather than silently accumulating. This mirrors the project's existing
  pragma-audit practice for suppression comments.

**Checker robustness**

- **FR-027**: Path exclusion MUST NOT depend on incidental output formatting of the underlying search
  tool. Exclusions currently match only because the search emits a `./` prefix; changing the scan root
  would silently disable every exclusion at once. Matching MUST be explicit about what it compares.

**Enforcement**

- **FR-022**: The project MUST either enforce the legacy-term policy in a check that gates merges, or
  record an explicit justified decision not to.
- **FR-022a**: If enforced, the policy MUST be wired into a job that is ALREADY a required context.
  Adding a new required context requires a branch-protection change, which is owner-gated and outside
  this feature's authority. The prior feature established this pattern by wiring its guard into the
  existing required lint job.
- **FR-022b**: Because the checker fails closed on a broken configuration (FR-009), and because it
  would gate merges repository-wide, its failure output MUST identify the specific cause and the
  remedy. A fail-closed gate with an opaque message blocks every merge in the repository.

**Downstream propagation**

- **FR-023**: Completion of this feature MUST close the open validation task in the prior feature's
  task list, and that closure MUST propagate to every downstream artifact of that feature.

### Key Entities

- **Legacy term**: A string naming a framework the project has retired. The authoritative list is the
  checker's own array. Terms are matched case-insensitively.
- **Match**: A single occurrence of a legacy term at a specific file and line.
- **Exemption**: An explicit, justified, visible marker that reclassifies a match as a permitted
  record rather than a violation.
- **Adjudication rule**: The written policy that decides whether a given match qualifies for
  exemption.
- **Stage**: One unit of the validation gate that independently passes or fails.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The validation gate exits 0 on a clean checkout of the default branch.
- **SC-002**: A single validation run produces an execution marker for 100% of its stages. Today two
  of seven produce none.
- **SC-003**: The count of unexempted legacy-term matches is 0, reduced from 17.
- **SC-004**: A deliberately introduced legacy term in an application source file causes the checker
  to fail, demonstrated by a red-team insertion and revert. This is the anti-regression proof: a
  checker that passes because it stopped looking is worse than one that fails.
- **SC-005**: A file containing both an excluded-path string and a legacy term is still reported.
- **SC-006**: An empty exclusion configuration does not produce a passing result.
- **SC-007**: Running the validation gate twice in succession leaves the working tree byte-identical
  to its state before the first run.
- **SC-008**: 100% of the 17 current matches have a recorded disposition.
- **SC-009**: An independent reader who did not write the adjudication rule, applying it to all 17
  current matches, reaches the same disposition recorded under FR-019. This makes the rule's clarity
  a measurable property rather than an assertion.
- **SC-010**: The number of validation stages whose declared gating status contradicts their actual
  behaviour is 0, reduced from at least two.
- **SC-011**: The test-target-header guard exits 0, with all 11 currently failing files dispositioned.
- **SC-012**: Every exemption in the repository can be listed by one command, and the total count is
  recorded as a baseline so future growth is visible.

## Assumptions

- The retired frameworks are genuinely retired and no application code legitimately needs them. The
  policy's premise is not in question, only its enforcement.
- The existing list of legacy terms is correct and complete. Adding or removing terms is out of scope.
- Documents that record the retirement have ongoing value and should not be deleted to satisfy the
  checker. Deleting the evidence that something was removed is a worse outcome than a noisy checker.
- The secrets baseline is regenerated by tooling and will continue to record archive paths, so any
  solution depending on its contents staying edited will fail.
- Developers run the validation gate locally today. If they do not, repairing it is still a
  precondition for making it a required check.
- The pre-commit hook set already runs one of the currently non-failing scanners in blocking mode, so
  removing that scanner from the validation gate does not create a coverage hole.

## Out of Scope

- The Dependabot alert backlog. Separate feature.
- The code-scanning alert backlog. Separate feature.
- Any dependency version change.
- Adding, removing, or editing entries in the legacy-term list.
- Rewriting the detection logic of the two newer guards. This feature makes them run and brings the
  repository into compliance with them. Narrowing which paths a guard scans IS in scope where FR-024
  adjudication concludes a file should never have been scanned, because that is a scope decision
  rather than a detection-logic change.
- Making the dependency-audit stage blocking. Deferred by FR-005a.
- Deleting the archived specification directories that the exclusions already cover.

## Dependencies

- The prior feature's guards must remain functional and unmodified.
- The pre-commit configuration and CI workflow definitions are in scope for reading, and in scope for
  modification only insofar as FR-022 requires.

---

## Adversarial Review #1

**Reviewer**: orchestrator (logical attack) + independent refuter agent (factual verification against
live repo state). The reviewer did not grade its own factual claims; ten claims were handed to a
separate agent instructed to disprove them and to default to REFUTED under ambiguity.

### Refuter verdicts on claims the spec was built from

| Claim | Verdict | Consequence |
|---|---|---|
| Gate halts at legacy-term check; two later stages never run | CONFIRMED | Spec premise holds |
| Gate mutates the working tree via the formatting stage | **REFUTED** | Mechanism real, effect absent. FR-004 reworded to state the hazard is latent |
| Dependency-audit stage cannot fail; one SAST scanner cannot fail, the other can | CONFIRMED | FR-005 / FR-005a |
| Exclusion filter matches file CONTENT, suppressing real findings | CONFIRMED, demonstrated with a live probe | FR-007 |
| Empty exclusion list makes the checker report PASS | CONFIRMED, demonstrated on a copy | FR-009 |
| Checker runs in no CI workflow and no pre-commit hook | CONFIRMED | FR-022 |
| Corpus is exactly 17 matches across 7 named files | CONFIRMED exactly | FR-019 |
| Board matches are one card, 132 cards total | CONFIRMED | FR-020 |
| One legacy term behaves as a wildcard pattern | CONFIRMED | Edge case retained |
| The legacy-term check is the ONLY thing blocking the gate | **REFUTED** | See F3 below. Scope expanded |

### Findings

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| F1 | CRITICAL | FR-005, SC-001 and Out of Scope were jointly unsatisfiable. FR-005 demanded every stage be able to fail; the dependency-audit stage reports the open alert backlog; making it block would hold the gate red until a separate feature lands, contradicting SC-001 and the Out of Scope disclaimer. | FR-005 reworded from "every stage must be able to fail" to "every stage must declare its gating status truthfully". FR-005a added to defer the blocking decision with rationale. Out of Scope updated. SC-010 restated in terms of truthful declaration. |
| F2 | HIGH | FR-013 required exactly one exemption mechanism while FR-017 forbade editing generated files. The three generated-file matches are unreachable by any inline marker, so one mechanism cannot cover the corpus. | FR-013 reworded to a minimal enumerated set with written applicability rules, explicitly justifying why one is impossible and capping growth. |
| F3 | HIGH | The spec assumed the legacy-term check was the only blocker. Refuter ran every prerequisite individually: the test-target-header guard also fails, on 11 files. This was invisible because make halts earlier. Fixing legacy terms alone would NOT have turned the gate green, and the feature would have reported success against a still-red gate. | FR-024 and FR-025 added covering adjudication and remediation of all 11 files. SC-011 added. Out of Scope amended so narrowing a guard's scan scope is permitted where adjudication warrants it. |
| F4 | MEDIUM | User Story 3 required a *required* check to fail, but the default branch's required contexts are fixed at four and branch protection is owner-gated, outside this feature's authority. | FR-022a added, constraining enforcement to a job that is already required. Follows the precedent set by the prior feature, which wired its guard into the existing required lint job rather than adding a context. |
| F5 | MEDIUM | Nothing made exemptions auditable. Exemptions would accumulate invisibly, reproducing the suppression-comment sprawl the project already guards against elsewhere. | FR-026 added requiring one-command enumeration. SC-012 added recording a baseline count so growth is visible. |
| F6 | MEDIUM | Requiring all stages to run removes fast-fail. Every run pays the full static-analysis cost even when the first stage fails, a real usability regression on a gate that already exceeds two minutes. | Accepted as a deliberate trade and recorded here rather than discovered later. Completeness of reporting is worth more than early exit on a gate whose failure mode was incomplete reporting. Mitigation belongs in planning, not in the spec. |
| F7 | MEDIUM | Path exclusions work only because the underlying search tool emits a `./` prefix. Changing the scan root would silently disable every exclusion simultaneously, and the corpus would jump by three orders of magnitude. The correctness is accidental. | FR-027 added. This is distinct from the content-matching defect: the checker has failure modes in both directions, under-reporting on content collision and over-reporting if the scan root changes. |
| F8 | LOW | SC-009 was not mechanically verifiable. | Restated as a rubric test: an independent reader applying the rule reaches the same disposition on all 17 matches. |
| F9 | LOW | FR-004's premise overstated the harm, per the refuter. | Reworded to state the hazard is latent and to justify why the requirement stands anyway. |

### Adjudication input discovered during review

The refuter's independent read of the corpus found that **zero of the 17 matches are application
code**. Nine are in one archived specification that discusses the retired framework as prior art, two
are the board card describing this very defect, three are machine-generated path records, two are a
drift document whose matching line explicitly states the drift was refuted, and one is another spec.
The gate is currently failing entirely on documentation about the gate.

This materially shapes FR-018's adjudication rule: the rule must be biased toward exemption for
historical and generated records, because that is what the entire corpus consists of, while remaining
strict for source, configuration and infrastructure. It also means SC-004's red-team insertion is not
optional. With no real violation anywhere in the corpus, a deliberately introduced one is the only
available proof that the checker still detects anything at all.

### Gate statement

**0 CRITICAL, 0 HIGH remaining.** F1, F2 and F3 resolved by specification amendment. F6 accepted as a
documented trade-off. Proceed to planning.

Two consequences carry forward and must not be lost: the feature is materially larger than reported
because of F3, and the anti-regression proof in SC-004 is now load-bearing rather than a nicety.
