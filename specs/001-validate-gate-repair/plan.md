# Implementation Plan: Validation Gate Repair

**Branch**: `001-validate-gate-repair` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-validate-gate-repair/spec.md`

## Terminology Note *(inherited, mandatory)*

This plan never writes the retired framework names in full, for the reason given in the spec's
Terminology Note: every artifact under `specs/` is scanned by the checker this feature repairs, so
naming them here would enlarge the corpus the feature exists to clear. They are called **legacy
terms** throughout. The authoritative list lives in exactly one place, the checker's own term array.

This constraint is not optional and applies to every downstream artifact: `research.md`,
`data-model.md`, `contracts/`, `quickstart.md`, and `tasks.md`.

## Summary

Repair the repository's validation gate so that it runs every stage it advertises, reports a
truthful per-stage result, and can pass on a clean checkout. Two stages currently block it: the
legacy-term checker and the test-target-header guard. Neither is reachable past the other because
Make halts at the first failing prerequisite.

The technical approach has four parts:

1. **Gate structure.** Convert `validate` from a prerequisite list into a driver recipe that invokes
   each stage as a sub-make, records each exit code, and prints a per-stage summary before exiting
   non-zero if any stage failed. Swap the mutating format stage for the already-present check-only
   variant.
2. **Checker rewrite.** Replace the Bash checker with a stdlib-only Python module under `scripts/`,
   carrying unit tests. This is driven by the constitution's Implementation Accompaniment Rule rather
   than by preference: the Bash version cannot be meaningfully unit tested, and three of the spec's
   success criteria (SC-004, SC-005, SC-006) are assertions about checker behaviour under conditions
   that only a test harness can construct.
3. **Exemption mechanism.** One sanctioned mechanism: a syntax-agnostic inline marker carrying a
   justification, refused outright in application source. The second mechanism this plan originally
   called structurally necessary was eliminated instead of built, by fixing the badly named
   directory that made it look necessary.
4. **Corpus remediation.** Adjudicate every match under a written rule, fix the root cause that
   regenerates matches, and bring the test-target-header guard to green by correcting a scope defect
   in the guard rather than by writing false headers into files.

### Finding that changes the shape of the work

The spec was written against a corpus of seventeen matches. Running this planning step's own setup
script raised it to eighteen. `.specify/templates/plan-template.md` line 21 carries a legacy term in
its "Primary Dependencies" example. `.specify/` is on the exclusion list, so the template is
invisible to the checker, but every plan generated from it lands in `specs/`, which is scanned.

The template injects a match into every generated plan. Whether that match *survives* depends on
whether the author fills in the Technical Context block, which is what `/speckit.plan` normally does.

**Corrected by adversarial review, because the first draft of this section overclaimed.** The
original text called this "a match factory emitting one new match per feature planned, indefinitely"
and "the single highest-leverage edit in the feature." The refuter surveyed all 254 `specs/*/plan.md`
files: **exactly one** retains the placeholder, and the template has carried it since the repository's
first constitution commit. The realized escape rate is roughly 0.4%, not 100%. The generalisation was
drawn from a sample of two, one of which was this feature's own draft.

What survives the correction: it is a real latent hazard with a one-line fix, it has escaped twice in
254 attempts, and both escapes are in the current corpus. What does not survive: the claim that it is
the feature's highest-leverage edit, or that the gate would reliably go red again after the next
feature. It is worth fixing because it is nearly free, not because it is urgent.

## Technical Context

**Language/Version**: Python 3.13 (checker rewrite, stdlib only), GNU Make 4.3 (gate driver), Bash
(existing recipe bodies)
**Primary Dependencies**: None added. The checker is stdlib-only by design, matching the precedent
set by the prior feature's guard so that CI needs no install step. `pytest` (already present) for the
new unit tests.
**Storage**: N/A. No runtime data, no AWS resources, no persistence.
**Testing**: `pytest` under `tests/unit/scripts/`, which already exists and already hosts two script
test modules. Plus the gate's own behaviour, verified by running it.
**Target Platform**: Developer workstations (Linux, WSL2) and `ubuntu-latest` GitHub Actions runners.
**Project Type**: Repository tooling. No application source changes.
**Performance Goals**: The full gate must stay under roughly five minutes. Removing fast-fail
(spec F6, accepted) means every run now pays the full static-analysis cost, currently the dominant
term at over two minutes. The checker itself must stay under two seconds on this repository.
**Constraints**: No new required status contexts (branch protection is owner-gated, FR-022a). No
new AWS resources. No dependency version changes (out of scope). Must not write legacy terms into
any artifact. Must preserve the comprehensive static-analysis stage's existing blocking behaviour
(FR-006), which a prior feature deliberately established.
**Scale/Scope**: 15 distinct offending lines across 7 files, which the current checker reports as 17
term-hits (see the counting note below, the difference matters for verification). 11 files failing
the header guard. 7 gate stages, 1 workflow job, 1 pre-commit hook, 6 directory renames.

## Constitution Check

*GATE: evaluated before Phase 0, re-evaluated after Phase 1.*

The constitution governs a cloud sentiment-analysis service. Most of it addresses runtime concerns
this feature does not touch. The clauses that do apply:

| Clause | Applies | Status |
|---|---|---|
| Implementation Accompaniment Rule: all implementation code accompanied by unit tests, happy path plus at least one error path, 80% coverage on new code | YES. The checker rewrite is implementation code. | **PASS by design.** `tests/unit/scripts/test_check_banned_terms.py` is a required deliverable, not optional. SC-004, SC-005 and SC-006 are each directly expressible as a test case. |
| Functional Integrity Principle: never make a test pass by editing fixtures to match broken code | YES. Tempting failure mode here is to satisfy the header guard by pasting false headers into infrastructure tests. | **PASS.** FR-024 adjudication explicitly routes infrastructure tests to a scope correction in the guard rather than to a false declaration. |
| CI must include SAST, secret scanning and dependency checks | YES, indirectly. This feature restores the gate that runs them locally. | **PASS.** No scanner is removed. The dependency-audit stage stays in the run, relabelled advisory per FR-005a. |
| Testing matrix: LOCAL and DEV run unit tests only, with mocks | YES for the new tests. | **PASS.** The new tests are pure filesystem fixtures under `tmp_path`. No AWS, no network. |
| Terraform, IaC, deployment, IAM, DynamoDB, observability, dashboard, model versioning clauses | NO. No runtime code, no infrastructure, no data path. | N/A |

**Result: PASS. No violations, so Complexity Tracking stays empty.**

One pre-existing gap observed and deliberately not fixed here: the prior feature's guard
(`scripts/scan-waitforresponse-race.py`, 429 lines, wired into a required CI job) has zero unit
tests, which does not meet the Implementation Accompaniment Rule. That is pre-existing debt outside
this feature's scope. It is recorded so the precedent is followed selectively: this feature copies
that guard's CI wiring pattern, and does not copy its absence of tests.

## Key Design Decisions

Full reasoning, alternatives and evidence are in [research.md](./research.md). Summary:

| ID | Decision |
|---|---|
| D1 | `validate` becomes a driver recipe over sub-makes, accumulating exit codes, no early exit. Stages stay independently invokable. |
| D2 | Formatting stage in the gate switches to the check-only variant that already exists and is currently unused. Zero new code. |
| D3 | Each stage declares BLOCKING or ADVISORY in the summary. The dependency-audit stage is labelled ADVISORY and stays that way (FR-005a). |
| D4 | Checker rewritten as stdlib-only Python with unit tests. Bash version deleted. |
| D5 | **Exactly one** exemption mechanism: a syntax-agnostic inline marker with mandatory justification. A second, path-scoped mechanism was designed and then eliminated once the generated-file case was traced to a badly named directory rather than to generated content. |
| D6 | The header guard is corrected to accept a third sanctioned declaration for tests that target infrastructure rather than either dashboard. One of the eleven failing files already invented this form organically. |
| D7 | The checker is wired into the existing required lint job, following the prior feature's precedent exactly. No new required context. |
| D8 | `make audit-exemptions` enumerates every exemption in one command, with a recorded baseline count. |
| D9 | An inline marker under application source, infrastructure or frontend source is an error in itself, not merely ignored (FR-028, clarified 2026-07-30). |

## Corpus Disposition (FR-019)

Adjudication rule, stated once and applied uniformly:

> An occurrence is **corrected** when the surrounding text asserts that a retired framework is
> current. An occurrence is **exempted** when the surrounding text records that the framework was
> retired, or discusses it as prior art. A legacy term reaching a machine-generated file is
> **corrected at its source, never exempted**: determine whether the term is in generated content or
> merely in a path the file records, and if it is a path, rename the path. Text that describes the
> checker itself is reworded so it does not need an exemption at all.

The distinction is between a document that would mislead a contributor into reintroducing the
framework, and a document that explains why it is gone. The first is the violation the checker
exists to catch. The second is the record the project agreed to keep.

| File | Matches | Disposition | Basis |
|---|---|---|---|
| `.specify/templates/plan-template.md` | 1, not counted (excluded path) | **Correct** | Root cause, though a slow-acting one: two escapes in 254 generated plans. Nearly free to fix, which is the reason to do it. See the corrected finding above. |
| `specs/001-validate-gate-repair/plan.md` | 0, already remediated | **Correct** | Was 1. Injected into this file by the planning setup script and removed during planning by filling in the real Technical Context. Listed with a count of zero so the table sums to 17 and an FR-019 audit against it succeeds. |
| `specs/1268-cors-404-headers/plan.md` | 1 | **Correct** | Unfilled template placeholder, same origin as the above. Asserts nothing intentionally. |
| `specs/1157-auth-cache-headers/research.md` | 5 | **Correct** (rewrite) | Asserts the framework is the application's current primary dependency. Only true positives in the corpus. Resolved 2026-07-30, see below. |
| `specs/1157-auth-cache-headers/plan.md` | 3 | **Correct** (rewrite) | Same. |
| `specs/1157-auth-cache-headers/spec.md` | 1 | **Correct** (rewrite) | Same. |
| `docs/cleanup/diagram-drift.md` | 2 | **Exempt, inline marker** | The matching row records a drift claim sourced from an archived spec and refuted against live code. A record that the framework is gone. Textbook exemption case. |
| `.secrets.baseline` | 3 | **Correct, by directory rename** | Machine-generated. See below: the term is in a *directory name*, not in any file's contents, so renaming removes the cause and no exemption is needed. |
| `CLEANUP-BOARD.html` | 2 | **Reword** (FR-020) | One card, one field, describing this very defect. Rewording removes the need for any exemption. Its match count is also stale and gets corrected in the same edit. |

### Counting note: "17" is a property of the current checker, not of the repository

The corpus is 17 across 7 files as the **current Bash checker counts it**, and that number is an
artifact of how it counts rather than a fact about the repository. The same corpus is legitimately
described three ways:

| Counting basis | Value |
|---|---|
| term times line hits, what the Bash checker reports | **17** |
| distinct offending lines | 15 |
| raw occurrences of a term | 19 |

`docs/cleanup/diagram-drift.md:133` alone is one line, two term-hits, and four occurrences. The board
card is one line and two term-hits for the same reason: two different terms on one very long line.

This has a direct consequence for the rewrite, and it is the reason the Risks table was corrected. A
faithful Python rewrite that reports per-line or per-occurrence would produce 15 or 19 and look like
a regression. A rewrite that reproduces exactly 17 has replicated a quirk of `grep -c` piping, not
satisfied a specification. **Equivalence must therefore be established on the set of (file, line)
pairs**, which is stable under all three bases, and the reporting basis chosen deliberately and
documented rather than inherited by accident.

Everything downstream that says "17" means the 15 distinct lines that the current checker reports as
17 term-hits. Fixing this ambiguity is itself a small deliverable.

**Dispositions.** All matches now have one. Eight are mechanically simple. Nine belong to one
superseded feature directory and are rewritten per the 2026-07-30 clarification.

### The generated-file matches are a directory name, and fixing that collapses the mechanism set

The three matches in the secrets baseline were originally planned as the justification for a second
exemption mechanism. Investigation prompted by the owner showed that framing was wrong.

`mock-event-factory.yaml` contains **zero** legacy terms. All three matches are the baseline
recording that file's *path*, and the term sits in the enclosing directory's name. The baseline is
not a file that mentions a retired framework. It is a file that lists a badly named directory.

**Resolved 2026-07-30: rename the six legacy-named paths.** Six paths repo-wide carry a legacy term
in their name. Only one currently leaks into the corpus, but the owner elected to rename all six so
that no path anywhere can leak into a future generated file that records paths.

The consequence is larger than three matches, and it reverses a prior adversarial-review finding:

> AR#1 finding F2 held that "exactly one exemption mechanism" was unsatisfiable, because
> machine-generated files cannot take inline markers (FR-017) and therefore a path-scoped mechanism
> was structurally required. That was true only because a legacy-named directory leaked into a
> generated file. Remove the bad names and the generated-file case has no instances.

**The sanctioned exemption set therefore collapses from two mechanisms to one: the inline marker.**
FR-013 asked for the set to be as small as possible; one is the floor, and the original instinct that
AR#1 had to reject turns out to be achievable after the root cause is fixed rather than exempted.

The exclusion list still exists, but its role narrows to what it should always have been: **scan
scoping**, deciding which trees are searched at all, with no exemption semantics attached. That is a
cleaner model to reason about and one fewer mechanism to audit under FR-026.

If a generated file ever legitimately contains a legacy term in its *content*, FR-013 must be amended
to re-add the path-scoped mechanism. Recorded so a future contributor sees that as an amendment
rather than an oversight.

Cost, recorded rather than glossed: four files under `specs/1217-*` reference the archive path in
prose and go stale. They sit inside excluded trees so the gate will not notice, which is precisely
why they need fixing deliberately rather than being left to the checker.

### The nine occurrences in the superseded auth-cache-headers spec: resolved

The nine matches in `specs/1157-auth-cache-headers/` are the only occurrences in the corpus that
state, in the present tense, that the application is built on a retired framework. Under the
adjudication rule they are corrections rather than exemptions. Three dispositions were offered to
the owner: move the directory under the excluded archive path, add a superseded banner plus nine
inline markers, or rewrite the occurrences.

**Resolved 2026-07-30: rewrite the occurrences.** Each of the nine lines is corrected to name the
resolver the dashboard actually uses. Recorded in the spec's Clarifications section.

**The premise was corrected before the decision was confirmed, and the decision held.** The first
version of this section claimed all nine occurrences assert present-tense currency. An independent
refuter graded each line: only four do (`plan.md:13`, `plan.md:79`, `research.md:98`, `spec.md:81`).
The other five are a section heading, a research question, a general statement about the framework's
capabilities, a line inside a fenced code sample, and a research-task list item. A line-by-line
application of the adjudication rule would exempt those five.

The owner was shown the corrected breakdown, including that rewriting the fenced code sample puts a
code snippet into a shipped research document that its authors never wrote, and elected to rewrite
all nine anyway. That is recorded here as a deliberate choice against the rule's line-by-line
reading, not as an application of it.

**Implementation consequence, which is where the cost actually lands.** The five non-assertive lines
cannot be token-swapped. A heading, a question and a code sample each need the surrounding sentence
to remain coherent and truthful after substitution, and the code sample in particular must not be
made to look like a verbatim record of something the research produced. Whoever executes this needs
to read each of the nine in context, and the five are the slow ones.

Consequences for task generation:

- The exemption baseline gains nothing from this directory. Under the recommended-but-rejected
  banner option it would have gained nine, which is most of a fresh baseline for one directory.
- Nine line edits across three files, each needing the surrounding sentence to stay coherent after
  substitution. A "Primary Dependencies" field is a token swap; a sentence reading "the application
  uses a framework that allows setting response headers" needs the claim itself re-checked against
  the current stack, not just the noun replaced.
- The accepted cost is that this edits documents describing a decision made at a different time.
  That is the owner's call and is recorded rather than hidden. The rule is what makes it defensible:
  a present-tense assertion that a retired framework is current is exactly the violation class the
  checker exists to catch, and these are the corpus's only true positives. Exempting the only real
  violations would have made the rule decorative.

## Header Guard Disposition (FR-024)

The guard requires every file matching its two globs to contain a `Target:` line naming a dashboard.
It fails on eleven. Reading all eleven shows the guard has a scope defect rather than the repository
having eleven delinquent files.

Five of the eleven exercise infrastructure that sits beneath or beside both dashboards: a web
application firewall, an identity provider, a content delivery network, a function URL access
policy, and backend log groups. There is no true answer to "which dashboard does this target",
so the guard is demanding a declaration that would have to be false to satisfy it. Writing one
would be exactly the anti-pattern the constitution's Functional Integrity Principle names: making
the check pass by corrupting the input rather than fixing the check.

One file has already solved this organically. `tests/e2e/test_log_visibility.py` opens with a
`Target:` line that explicitly declares it targets backend log groups and neither dashboard UI. The
guard rejects it because the pattern insists on the literal word for a dashboard. The repository
invented the missing third category on its own, and the guard did not know about it.

**Decision: teach the guard the third category** rather than write ten more false headers. The
guard's purpose is preserved exactly. It still forces an explicit, reviewed declaration on every
scanned test file, which is the whole point given this repository's documented history of confusing
its two dashboards. It stops forcing that declaration to be untrue.

| File | Disposition |
|---|---|
| `frontend/tests/e2e/cors-headers.spec.ts` | Add customer-dashboard header. It is a browser test in the customer suite. Genuinely missing. |
| `tests/e2e/test_admin_lockdown_preprod.py` | Add admin-dashboard header. Its subject is admin route lockdown. |
| `tests/e2e/test_chaos_lockdown_preprod.py` | Add admin-dashboard header. Same suite, same subject. |
| `tests/e2e/test_cloudfront_sse.py` | Infrastructure declaration. Targets a CDN distribution and firewall. |
| `tests/e2e/test_cognito_auth.py` | Infrastructure declaration. Targets an API gateway authorizer. |
| `tests/e2e/test_function_url_restricted.py` | Infrastructure declaration. Targets a function URL access policy. |
| `tests/e2e/test_waf_protection.py` | Infrastructure declaration. Targets a firewall rule set. |
| `tests/e2e/test_log_visibility.py` | Infrastructure declaration. **Needs an edit after all.** Its header declares what the file is *not* ("not either dashboard UI") rather than naming the third category, so no widened pattern accepts it without also accepting anything that merely mentions a dashboard. Corrected by adversarial review #3, which verified that widening the pattern still leaves all eleven files failing. |
| `tests/e2e/test_cors_404_e2e.py` | Confirm during implementation. Reads as gateway-level, likely infrastructure. |
| `tests/e2e/test_cors_e2e.py` | Confirm during implementation. Reads as full-stack auth flow, may be customer. |
| `tests/e2e/test_cors_prod_headers.py` | Confirm during implementation. Reads as gateway-level, likely infrastructure. |

Eight of eleven are settled. The three CORS files need one read each during implementation to assign
correctly, which is a task detail rather than an open design question. FR-025's anti-regression half
is covered by a test asserting that a scanned file with no declaration at all still fails.

## Project Structure

### Documentation (this feature)

```text
specs/001-validate-gate-repair/
├── plan.md              # This file
├── research.md          # Phase 0: decisions, alternatives, evidence
├── data-model.md        # Phase 1: checker entities and their rules
├── quickstart.md        # Phase 1: how to run, exempt, and audit
├── contracts/
│   └── checker-cli.md   # Phase 1: checker CLI and gate output contract
├── checklists/
│   └── requirements.md  # Stage 1 output, complete
└── tasks.md             # Phase 2, produced by /speckit.tasks
```

### Source Code (repository root)

This feature changes repository tooling only. No application source is touched, which is why there is
no `src/` entry below.

```text
Makefile                                   # FOUR edits, not three:
                                           #  1. validate -> driver recipe (D1)
                                           #  2. fmt -> fmt-check in the stage list (D2)
                                           #  3. check-test-target-headers pattern widened (D6)
                                           #  4. audit-exemptions target added (D8)
                                           #  plus .PHONY completion, see Risks
scripts/
├── check_banned_terms.py                  # NEW. Replaces check-banned-terms.sh
├── check-banned-terms.sh                  # DELETED. Four consumers must be updated, see below
└── scan-waitforresponse-race.py           # UNCHANGED. Referenced as CI-wiring precedent only
tests/unit/scripts/
└── test_check_banned_terms.py             # NEW. Covers SC-004..SC-006, SC-013, FR-007..FR-012, FR-028
                                           #  MUST import the term list, never literal a term,
                                           #  or the checker flags its own test file
.github/workflows/pr-checks.yml            # One step added to the existing required lint job
.pre-commit-config.yaml                    # One hook added, mirroring the prior feature's
.specify/templates/plan-template.md        # Placeholder scrubbed

# Consumers of the deleted script, found by adversarial review
specs/1217-*/quickstart.md, tasks.md       # Runnable `bash scripts/check-banned-terms.sh` commands
specs/1218-*/quickstart.md, tasks.md       # Same
docs/cleanup/validator-inventory.md        # Inventory row goes stale

# Directory renames (owner decision 2026-07-30, all six legacy-named paths)
specs/archive/001-*-purge/                 # The one that leaks into the secrets baseline
specs/archive/1040-add-sse-*-dep/
specs/1217-*-infra-purge/                  # Also needs its exclusion-list entry updated
docs/archive/*-purge/                      # Directory plus two files inside it
.secrets.baseline                          # Regenerated after the renames, not hand-edited

# Remediation targets
specs/1157-auth-cache-headers/             # Nine occurrences rewritten (four assertive, five not)
specs/1268-cors-404-headers/plan.md        # Placeholder corrected
docs/cleanup/diagram-drift.md              # Inline marker added. The only exemption in the feature
CLEANUP-BOARD.html                         # Card 131 reworded (FR-020)
frontend/tests/e2e/cors-headers.spec.ts    # Header added
tests/e2e/test_*.py                        # Headers added, or resolved by the D6 guard widening
```

**Structure Decision**: Repository tooling, single tree, no new packages. The checker lands in
`scripts/` next to the prior feature's guard, and its tests land in `tests/unit/scripts/`, which
already exists and already hosts two script test modules. The filename uses underscores rather than
hyphens so pytest can import it directly, which the hyphenated Bash name made impossible and which
is a precondition for satisfying the constitution's test requirement.

## Complexity Tracking

> Empty by design. Constitution Check returned PASS with no violations.

## Risks

| Risk | Mitigation |
|---|---|
| Removing fast-fail makes every failing run pay full static-analysis cost. Accepted trade per spec F6. | The per-stage summary means one run now surfaces every failure, replacing N runs that each surfaced one. Net time to green should fall even though time per run rises. |
| Wiring the checker into a required job means a checker defect blocks every merge repository-wide. | FR-009 fails closed and FR-022b requires the failure message to name the cause and the remedy. The unit tests exist specifically so this code is not first exercised in a blocking position. |
| The inline marker is itself a bypass, pasteable onto a genuine violation. | Accepted and documented in the spec's edge cases. Mitigated by review visibility, a mandatory justification, and FR-026's one-command audit with a recorded baseline so growth is detectable. |
| Rewriting Bash to Python could change matching semantics silently, for instance around case handling or pattern metacharacters. | Verify against the **set of (file, line) pairs**, not a count. See the counting note below: a scalar comparison would produce false alarms and false confidence in equal measure. The rewrite is pinned to that set before any remediation edit lands. |
| Correcting the header guard's scope could be mistaken for weakening it. | The guard still requires an explicit declaration on every scanned file. Only the set of acceptable declarations grows, from two to three, and the third was already in use in the repository before this feature. SC-004's red-team insertion proves detection still works. |
| **`make -n validate` fabricates a clean verdict.** Corrected by adversarial review #3, which reproduced the real behaviour rather than reasoning about it. The driver recipe does execute under `-n` because it contains `$(MAKE)`, but `-n` propagates through MAKEFLAGS, so every sub-make dry-runs, returns 0, and the driver prints a summary showing **all seven stages PASS and exits 0** without running anything. That is worse than the behaviour originally documented here: it is a gate reporting success it did not earn, which is the exact defect this feature exists to remove, reintroduced by its own fix. | Detect dry-run mode in the driver, via `$(findstring n,$(MAKEFLAGS))`, and either suppress the summary or print an unmissable banner stating the results are not real. Do not ship the driver without this. |
| **`.PHONY` omits three of the seven stages.** `check-test-target-headers`, `check-waitforresponse-race` and `check-iam-patterns` are absent from the declaration at the top of the Makefile. Pre-existing and currently harmless, but D1 makes those names load-bearing sub-make targets: a same-named file or directory at the repository root would silently no-op the stage while the driver records a clean exit. | Complete the `.PHONY` declaration as part of the D1 edit. One line, and it removes a failure mode where the gate reports success for a stage that never ran, which is the original defect wearing a different hat. |
| **The header guard's globs are not recursive.** `frontend/tests/e2e/*.spec.ts` and `tests/e2e/test_*.py` match top level only. No blind spot exists today (38 and 42 files respectively, identical recursively), but the guard stops seeing new tests the moment anyone adds a subdirectory. | Out of scope to fix, recorded so it is a known limit rather than a latent surprise. Note it in the guard's own comment during the D6 edit. |
| `make audit-pragma` depends on a scanner slated for deletion. | Not this feature's problem and deliberately not folded in. The scanner's removal is tracked by a board card added 2026-07-30, which flags that the pragma audit's `# nosec` coverage has no replacement in the successor tool and would be silently lost. This feature leaves `audit-pragma` untouched. |
