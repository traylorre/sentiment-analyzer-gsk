# Feature Specification: CodeQL Coverage Expansion

**Feature Branch**: `001-codeql-coverage`
**Created**: 2026-07-30
**Status**: Draft
**Input**: User description: "Expand CodeQL scanning coverage. Two parts: add JavaScript/TypeScript to the analysis matrix so the customer dashboard is scanned at all, and resolve a self-contradiction in the CodeQL config file."

## Context

### Owner directive (verbatim)

> "I want codeql to pass because it alerts to variant and Taint analysis vulnerabilities. There shouldn't be a tension if the goal is to reduce vulnerabilities. Of course, every new line of code is increased exposure, so adding anything means more code to get passing vs codeql."

**Reading of the directive that governs this spec: coverage is the goal, not a low alert count.**
Turning on JavaScript/TypeScript scanning will very likely RAISE the open alert number.
That is an accepted and expected outcome of this feature, not a regression and not a failure
of this feature. No reviewer, gate, or later reader should treat the new alerts as evidence
that this work went wrong. The alerts were always there. Until now nothing was looking.

### Established facts (measured, do not re-derive)

| # | Fact | How it was established |
|---|------|------------------------|
| F1 | The analysis matrix is `language: ['python']` only. The TypeScript customer dashboard under `frontend/` is never scanned. | `.github/workflows/pr-checks.yml` line 294 at `c010178` (job `codeql`, `name: Analyze`, opens line 282) |
| F2 | The scan uses the `security-extended` query suite and a shared config file at `.github/codeql/codeql-config.yml`. | Same workflow job |
| F3 | The config contradicts itself: it excludes `tests/**/*` wholesale by path, then carries a narrower query filter scoped to `tests/**` plus a comment claiming tests are still scanned. **RESOLVED at Clarification Q4: the path exclusion is applied at EXTRACTION time (`--filter exclude:tests/**/*`), so all 393 `tests/` Python files are absent from the database, the query filter is INERT, and the comment is FALSE.** Of the three claims, exactly the first is true. | `.github/codeql/codeql-config.yml` lines 13, 19 to 30; job log of run `30581930915` lines 1480, 1487, 2067 |
| F4 | All 8 historical `tests/` alerts are for one rule, all created on or before the config commit `f9381dc` (2025-11-28). Zero new `tests/` alerts since. This is consistent with EITHER reading of F3 and distinguishes nothing. | Alert API, all states, filtered to `tests/` |
| F5 | Pull request analyses are diff-informed by design and are scoped to changed lines. They routinely report zero results. This is correct behaviour, not a broken gate. | Analyses API: every `refs/pull/*/merge` entry reports 0 results |
| F6 | A green CodeQL check on a pull request is never evidence the repository is clean, only that the changed lines are. | PR #990 was green while 5 alerts were open |
| F7 | Baseline on `refs/heads/main`: 9 results for `/language:python`, of which 5 are open, 15 dismissed and 117 fixed across all history. | Analyses API and alerts API |
| F8 | CodeQL is NOT currently a merge gate. Required status checks on `main` are exactly: `Secrets Scan`, `Lint`, `Run Tests`, `Playwright E2E Tests`. There are zero repository rulesets. Code scanning is in advanced setup, not default setup. | Branch protection API, rulesets API, code-scanning default-setup API |
| F9 | JavaScript and TypeScript need no build for CodeQL. The published language table lists "Not applicable" under compilers for JavaScript, and TypeScript is analyzed by the JavaScript extractor with TypeScript enabled by default. GitHub's own language detection for this repository already names the combined JavaScript/TypeScript identifier. | CodeQL supported-languages reference; `code-scanning/default-setup` API response for this repository |
| F10 | JavaScript and TypeScript surface area: about 47,300 lines. `frontend/src` about 22,300, `frontend/tests` about 19,900, `src/dashboard` about 4,000. No vendored, bundled, or minified JavaScript is committed. | `git ls-files` plus line count |
| F11 | The Python analysis leg completes in about 1 minute. The slowest job in the workflow is the blocking Playwright job at 6 to 7 minutes. | Job timings from the four most recent workflow runs |
| F12 | The workflow also runs on pushes to `main` and to `dependabot/**`, on a weekly schedule, and on manual dispatch. Feature branch pushes alone do not trigger it. | Workflow trigger block |
| F13 | The repository is public. GitHub-hosted standard runners bill at zero for public repositories. The cost of a second matrix leg is therefore wall clock and runner queue, not dollars. The workflow declares no concurrency-cancel group, so rapid pushes stack complete runs rather than superseding each other. | Repository API `visibility: public`; workflow file has no `concurrency:` block |
| F14 | Run volume over the five days to 2026-07-31 was 100 workflow runs: 49 pull request, 25 push (20 on `main`, 5 on `dependabot/**`), 25 manual dispatch, 1 scheduled. Dependabot push traffic is a small minority of the total, not the dominant driver. | Workflow runs API, grouped by event and branch |
| F15 | JavaScript and TypeScript files exist outside the three directories named in F10: six configuration files at the repository root and under `frontend/`, and four contract stub files under `specs/`, about 745 lines combined. One further file, `tests/load/api-load-test.js`, is already covered by the root-anchored exclusion. Scan scope for the new language is therefore "everything except root `tests/`", not "the two dashboards". | `git ls-files` for JavaScript and TypeScript extensions, minus the three named directories |
| F16 | The analysis job is named `Analyze` and its status contexts are generated per matrix value. Adding a second value ADDS `Analyze (javascript-typescript)` and does NOT rename `Analyze (python)`. No workflow or automation in `.github/` matches on any status context name. | Workflow job block; grep across `.github/` for context-name string matches |
| F17 | The analysis job requests `security-events: write` and is triggered by `pull_request`, so it runs on fork-authored pull requests with a downgraded read-only token. No dependency install runs inside that job today. | Job permissions block; workflow trigger block |
| F18 | Dependency vulnerability alerting does cover npm: 82 open npm advisories against 17 open pip advisories. However `dependabot.yml` declares only `pip`, `github-actions`, and `terraform` ecosystems, so npm version updates are not automated. | Dependabot alerts API; `.github/dependabot.yml` |
| F19 | The repository defines exactly two roles, and exactly one account holds push access. "Admin Role (Project Owner: @traylorre)" carries "Respond to security incidents" among its responsibilities. This is the source for every "named role" this spec requires. | `CONTRIBUTING.md` lines 62, 64, 74; `.github/CODEOWNERS` lines 3, 7, 15; collaborators API returning a single `admin` entry |
| F20 | The tech debt registry required by constitution §9 EXISTS, at `docs/reference/TECH_DEBT_REGISTRY.md`, holding `TD-001` through `TD-023`. It was relocated from the flat path by `f8db8d2` (PR #668); §9's path reference at constitution lines 527, 569 and 584 is stale. The highest existing identifier is `TD-023`. **TD identifiers allocate at MERGE time, in merge order, and no feature pre-reserves one**, this one included. The next free value is not `TD-024` by entitlement; it is whatever the registry's highest value is at the moment an entry is written. | `docs/reference/TECH_DEBT_REGISTRY.md`; `git log --diff-filter=D -- docs/TECH_DEBT_REGISTRY.md`; sibling features `001-oauth-provider-taint`, `001-ruff-bump-forward` and `001-ingestion-arn-logging` all converged on merge-time allocation |

### Two dashboards, both unscanned

The repository has two separate dashboards, documented at the top of the project guidance file.
The customer dashboard is the Next.js application under `frontend/`, which is what users
actually see. The admin dashboard is vanilla JavaScript under `src/dashboard/`. Neither is
reachable by the current Python-only matrix. The customer dashboard is the higher-value gap
because it is user facing, but the admin dashboard is small enough that excluding it would
save nothing and would leave an arbitrary hole.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Customer dashboard code is analyzed at all (Priority: P1)

A security reviewer wants to know whether the code users interact with contains taint-flow or
variant-analysis vulnerabilities. Today they cannot know, because no static analysis engine has
ever read that code. After this story, the customer dashboard and the admin dashboard are both
part of every full-tree analysis, and their findings appear in the same alert stream as the
Python findings.

**Why this priority**: This is the entire point of the feature. The gap is total, not partial.
Zero files of about 47,300 lines are analyzed. Every other story in this spec is subordinate to
closing that gap.

**Independent Test**: Land only this story, run a full-tree analysis on the branch reference,
and confirm the analyses record contains an entry categorised for JavaScript/TypeScript with a
recorded results count. Delivers value on its own even if no alert is ever fixed, because it
converts an unmeasured risk into a measured one.

**Which reference proves what** (three references are in play and they are not interchangeable):

| Reference | What it is | What it can prove |
|---|---|---|
| `refs/pull/*/merge` | The pull request check | Nothing about coverage. Diff-informed, routinely zero. Barred as evidence by FR-018. |
| `refs/heads/001-codeql-coverage` | Manual dispatch on the feature branch, before merge | Pre-merge verification only: the leg runs, both dashboards are extracted, wall clock is bounded. Satisfies SC-002, SC-003, SC-007. |
| `refs/heads/main` | The push-triggered run after merge | Post-merge verification and the authoritative baseline. Satisfies SC-001, SC-004, SC-005, and starts the triage clock under A1. |

**Acceptance Scenarios**:

1. **Given** the analysis matrix covers only Python, **When** the matrix is extended to include
   JavaScript/TypeScript and a full-tree analysis runs on a branch reference, **Then** the
   analyses record contains one entry per language and the JavaScript/TypeScript entry reports
   a results count.
2. **Given** the JavaScript/TypeScript leg runs, **When** its job log is inspected, **Then** it
   records extracted source files under both `frontend/` and `src/dashboard/`.
3. **Given** both legs are configured, **When** one leg fails, **Then** the other still completes
   and reports, so a single language failure never blinds the other.
4. **Given** the new leg surfaces alerts, **When** the open alert count rises above the pre-change
   baseline of 5, **Then** this is recorded as expected outcome and does not fail acceptance.

---

### User Story 2 - The scan config says what it does (Priority: P2)

An on-call engineer reading the config to answer "is this file scanned?" gets a straight answer.
Today the file excludes `tests/**/*` by path, carries a query filter scoped to `tests/**` that
may be dead as a result, and carries a comment asserting tests are still scanned. At most one of
those three things is true. The engineer cannot tell which, and neither can anyone else, because
the behaviour has never been probed.

**Why this priority**: A config that lies is worse than a config that is merely narrow, because
it defeats the review step that is supposed to catch narrowness. It ranks below P1 because the
contradiction affects Python test code, while P1 affects all user-facing product code.

**Independent Test**: Run the probe described in FR-007 through FR-009 and produce a recorded
determination. Delivers value even if the config is then left byte-identical, because the
recorded determination is the thing that was missing.

**Acceptance Scenarios**:

1. **Given** the contradiction is unproven, **When** a change to the path or query-filter rules is
   proposed, **Then** the change is blocked until a probe has established actual behaviour.
2. **Given** the probe runs, **When** its analysis reference is a branch reference rather than a
   pull request reference, **Then** its result is admissible. A pull request analysis result is
   inadmissible for this question because it is diff-informed.
3. **Given** the probe returns a conclusive answer, **When** the config is updated, **Then** its
   comments and its rules agree and each retained rule can be traced to the probe record.
4. **Given** the probe returns an inconclusive answer, **When** the config is updated, **Then**
   the update makes intent explicit in wording and removes the contradictory claim, and no rule is
   added or deleted on the strength of a guess about behaviour.

---

### User Story 3 - The new alerts have somewhere to go (Priority: P3)

A maintainer who sees the alert count jump on the day this lands knows what happens next: the
alerts are baselined, triaged, and dispositioned, and the enforcement question is answered rather
than left hanging. Nobody is blocked from merging unrelated work while that happens, and nobody
can quietly let the new findings rot either.

**Why this priority**: Without an intake policy the feature either blocks the whole team on day
one or produces a permanently ignored alert list. Both outcomes waste the coverage that P1 buys.
It is P3 only because it is meaningless until P1 exists.

**Independent Test**: Take the first full-tree JavaScript/TypeScript result set, produce the
baseline record and the dispositions, and confirm every alert in the baseline has exactly one
disposition. Testable without touching any product code. **Baseline membership is keyed on the
(rule identifier, file path) pair, never on the alert number**, because "fix now" dispositions land
inside the triage window and remediating an alert spawns a fresh number at the rewritten line. A
number-keyed baseline would show members vanishing and non-members appearing purely as an artifact
of the fixes the window exists to produce.

**Acceptance Scenarios**:

1. **Given** the first full-tree JavaScript/TypeScript analysis completes, **When** its results are
   captured, **Then** a baseline record exists listing count, rule identifiers, severities, and
   file paths.
2. **Given** the baseline exists, **When** the triage window closes, **Then** every baseline alert
   carries exactly one disposition of fix now, carded follow-up, or dismissed with a recorded
   reason.
3. **Given** triage is complete, **When** the feature is closed out, **Then** an enforcement
   recommendation exists naming a severity threshold, a path scope, and a blocking or non-blocking
   position, backed by the observed alert volume.
4. **Given** the new leg lands, **When** the required status check set on `main` is inspected,
   **Then** it is unchanged in names and count from the four checks recorded in F8.

---

### Edge Cases

- **The probe cannot distinguish.** If a full-tree analysis with the path exclusion removed still
  returns zero results under `tests/`, then Python test code genuinely holds nothing that the
  query suite flags, and the two readings of F3 remain indistinguishable. The resolution path for
  this case is specified in FR-010 and acceptance scenario 2.4: fix the wording, do not guess the
  behaviour.
- **Root-anchored path patterns do not reach nested test directories.** The existing exclusion is
  written against the repository root. It does not match `frontend/tests`. Once JavaScript and
  TypeScript are in the matrix, Python test code would be excluded while about 19,900 lines of
  frontend test code would be scanned. That asymmetry must be a decision with a stated reason, not
  an accident of glob anchoring.
- **Third-party dependencies are absent at scan time.** No dependency install runs before analysis
  and no dependency tree is committed. Findings therefore cover first-party code only. Dependency
  vulnerabilities remain the responsibility of the existing dependency alerting, not this feature.
- **A critical-severity finding lands while enforcement is non-blocking.** Non-blocking is a
  statement about the automated gate, not about triage urgency. FR-015 requires disposition inside
  the window regardless of severity, and a fix-now disposition is the expected route for anything
  at critical or high severity.
- **Alert volume is unmanageably large.** If the baseline exceeds what the triage window can absorb,
  the response is bounded by FR-016a: the window may be extended exactly ONCE, to a new fixed
  calendar date recorded in the baseline record, and never again. An open-ended "adjust the window"
  is not an available response, because a window that can always be extended is not a window. The
  response is never to reduce coverage back down, which would invert the owner directive.
  FR-020's path-class bulk disposition exists so that volume alone does not force an extension.
- **Check-context names are load-bearing, but this change adds rather than renames.** Per F16 the
  job is named `Analyze` and contexts are generated per matrix value, so this change ADDS
  `Analyze (javascript-typescript)` and leaves `Analyze (python)` untouched. No required context
  is renamed and no existing gate can break. The residual hazard is prospective, not present: if
  CodeQL is ever promoted to a required check, the required context string must be pinned per
  matrix value, and any later edit to a matrix value silently retires the context that branch
  protection names. This repository has a documented instance of exactly that failure on the
  Playwright job, which carries an explicit in-file warning. The analysis job carries no such
  warning. FR-022 requires one.
- **Cost multiplies across triggers, but the currency is time, not money.** Per F13 the repository
  is public, so GitHub-hosted runner minutes bill at zero. Per F14 the five-day run volume was 100
  runs, of which only 5 were `dependabot/**` pushes, so the mass-bump traffic is not the dominant
  multiplier that it first appears to be. The real exposures are wall clock on the critical path
  (bounded by SC-007) and runner queue depth, which the absent concurrency-cancel group makes worse
  because rapid pushes stack complete runs.
- **The probe and the baseline can contaminate each other.** The probe under User Story 2 requires
  running the analysis with the path-exclusion rules temporarily mutated. If that run also carries
  the User Story 1 matrix change, a single dispatch produces both the probe result and a
  JavaScript/TypeScript result set under a configuration that is NOT the configuration that lands.
  Capturing that as the baseline would baseline a config that never ships. FR-019 forbids it.
- **A dependency install would create a supply-chain hole.** Per F17 the analysis job requests
  `security-events: write` and is triggered by `pull_request` on a public repository. Adding an
  install step to that job would execute package lifecycle scripts from contributor-authored
  manifests inside a job that holds write access to the security-events surface on non-fork runs.
  Fork runs are downgraded to a read-only token, but branch pushes by any account with write access
  are not. This is the strongest argument for the no-install default in FR-004, and it is stronger
  than the argument A4 originally rested on.
- **The scan scope is wider than the two dashboards.** Per F15, the new leg also reaches root and
  `frontend/` configuration files and four contract stub files under `specs/`. Those stubs are
  specification artifacts that never ship. Alerts against them are real findings against non-shipping
  code, which is a disposition problem, not a coverage problem. FR-020's path classes exist to keep
  them from being mistaken for product findings.

## Requirements *(mandatory)*

### Functional Requirements

**Coverage**

- **FR-001**: The analysis matrix MUST include JavaScript/TypeScript in addition to Python, using
  the combined language identifier that covers both, since TypeScript is analyzed by the
  JavaScript extractor rather than as a separate language.
- **FR-002**: The two legs MUST report independently. A failure in one language MUST NOT cancel or
  suppress the other language's analysis.
- **FR-003**: JavaScript/TypeScript scan scope MUST include the customer dashboard sources under
  `frontend/` and the admin dashboard sources under `src/dashboard/`. Both ship to a human
  audience and neither has ever been analyzed. This is a floor, not the whole scope. Per F15 the
  effective scope is every JavaScript and TypeScript file outside the root-anchored exclusion,
  which additionally reaches build configuration files and contract stub files under `specs/`.
  The scope ceiling MUST be stated explicitly in this feature's artifacts rather than left to be
  discovered from the first result set.
- **FR-004**: The JavaScript/TypeScript leg MUST NOT be blocked on a compilation or build step,
  consistent with F9. If the first run contradicts F9, the prerequisite MUST be stated explicitly
  and provisioned rather than worked around.
- **FR-004a**: Whether to install third-party dependencies before analysis is a separate question
  from FR-004 and MUST be recorded as an explicit decision, not left as an unexamined default. The
  default for this feature is NO install, for two reasons that MUST both be recorded: first, per
  F17, an install step inside a job holding `security-events: write` on a public repository would
  execute contributor-authored package lifecycle scripts inside that job, which is a supply-chain
  exposure created by the scanner rather than found by it; second, the feature is scoped to
  first-party findings. The COST of that default MUST also be recorded rather than assumed away:
  without installed dependencies, type resolution and library modelling degrade, which weakens
  taint tracking through framework boundaries in exactly the first-party code this feature exists
  to cover. The baseline record MUST note whether the job log emitted type-resolution or
  module-resolution warnings, so that revisiting this decision later is evidence-backed.
- **FR-004b**: If FR-004a is ever revisited toward installing dependencies, the install MUST NOT
  be placed in a job that both holds `security-events: write` and is reachable from an untrusted
  reference. That constraint MUST be carried into the enforcement recommendation under FR-017.
- **FR-005**: The JavaScript/TypeScript leg MUST use the same query suite depth as the Python leg,
  so that adding a language does not silently ship a weaker suite for that language.
- **FR-006**: Before the matrix change lands, the shared config file MUST be reviewed for rules
  written with only Python in mind that would begin applying to JavaScript/TypeScript. Every such
  rule MUST be either scoped deliberately or documented as intentionally language-neutral.
- **FR-007**: The treatment of `frontend/tests` MUST be an explicit decision recorded in this
  feature, not a side effect of where a glob happens to be anchored.
- **FR-007a**: That decision MUST additionally address the ASYMMETRY it creates, which FR-007 alone
  does not. Under the current root-anchored exclusion, Python test code is excluded while about
  19,900 lines of frontend test code, more than the 22,300 lines of `frontend/src` it exercises,
  are included. The recorded decision MUST either state a reason why the two test trees are treated
  differently, or record the symmetry question as a carded follow-up. It MUST NOT leave the
  asymmetry undiscussed, because an undiscussed asymmetry is indistinguishable from the glob
  accident that produced it.
- **FR-022**: The analysis job MUST carry an in-file warning, in the same form as the one the
  Playwright job already carries, recording that its status contexts are generated per matrix value
  and that editing or removing a matrix value retires the corresponding context. Adding a language
  without adding that warning leaves the next matrix edit as unguarded as the Playwright rename was.

**Config self-consistency**

- **FR-008**: No change to the path-exclusion or query-filter rules MAY be made until an empirical
  probe has established what those rules currently do.
- **FR-009**: The probe MUST be conducted against a full-tree analysis on a branch reference. A
  pull request check result is inadmissible as probe evidence because pull request analyses are
  diff-informed and scoped to changed lines.
- **FR-009a**: The probe MUST establish a POSITIVE CONTROL before any comparison is treated as
  meaningful. A comparison between two arms that both return zero results under `tests/` proves
  nothing, because zero is the expected output of "the rule no longer fires on this code" as well
  as of "the rule was suppressed". Per F4, six of the eight historical alerts for the filtered rule
  are in the `fixed` state, so the rule may no longer fire on current test code at all. The control
  arm is a full-tree analysis with BOTH the path exclusion and the query filter removed. If the
  control arm returns zero results under `tests/`, the probe is declared INCONCLUSIVE immediately,
  no further arms are run, and FR-011's inconclusive resolution applies. This ordering exists so
  that an unanswerable question is identified in one run rather than three.
- **FR-009b**: **AMENDED at Clarification Q4.** The three-arm design below was written when the
  mechanism was unknown. It is now known, from extraction-level evidence in a `refs/heads/main`
  full-tree job log rather than from any result-count comparison: the path exclusion is passed to the
  extractor as `--filter exclude:tests/**/*`, all 393 `tests/` Python files are absent from the
  database, and the query filter scoped to `tests/**` is therefore INERT. Arms 1 and 2 are ANSWERED
  and MUST NOT be run, because running them would mutate the config to re-derive a settled fact.
  Only the FR-009a control arm survives, and it is now OPTIONAL rather than mandatory: it answers
  only whether `py/incomplete-url-substring-sanitization` still fires on current Python test code,
  which bears on exactly one decision, whether to DELETE the inert query filter as dead or retain it
  against a future narrowing of the path exclusion. If the control arm is not run, that decision MUST
  resolve by RETAINING the filter unchanged, since deleting a rule without evidence is precisely what
  FR-008 forbids.

  *Superseded three-arm design, retained for traceability*: (1) the configuration as it stands today;
  (2) the path exclusion removed, the query filter retained; (3) both removed, the FR-009a control.
- **FR-009c**: If the probe cannot be RUN at all, for example because the manual dispatch permission
  named under Dependencies is unavailable, that MUST be recorded as an inconclusive probe under
  FR-011 rather than as a reason to defer User Story 2 indefinitely or to change the rules anyway.
  FR-008's prohibition on rule changes without a probe holds in that case too.
- **FR-010**: The probe MUST be recorded in this feature's artifacts with enough detail for a second
  person to reproduce it: the analysis identifiers for every arm run, the configuration content of
  each arm, the observed result counts and paths per arm, and the control-arm outcome that
  determined whether the comparison was admissible at all.
- **FR-010a**: Any temporary configuration mutation made to run a probe arm MUST be confined to the
  feature branch and MUST NOT reach `main`. The configuration that lands is the configuration
  determined by FR-011, never a probe arm left in place by accident.
- **FR-011**: The config MUST end in a state where its comments and its rules agree. If the probe
  is inconclusive, the resolution MUST be to make the stated intent explicit and remove the
  contradictory claim, NOT to add or delete a rule on the strength of an assumption.
- **FR-012**: Resolving the contradiction MUST NOT reduce Python analysis coverage relative to the
  `refs/heads/main` baseline in F7, for any rule other than the single rule that is deliberately
  filtered.

**Alert intake and enforcement**

- **FR-013**: The first full-tree JavaScript/TypeScript result set on `refs/heads/main` after merge
  MUST be captured as a baseline record listing count, rule identifiers, severities, and file paths,
  before any triage or remediation begins. Membership in that baseline is identified by the
  (rule identifier, file path) pair. Alert numbers MAY be recorded as a lookup convenience but MUST
  NOT be the identity, because remediation inside the triage window renumbers alerts at rewritten
  lines and a number-keyed baseline would decay as the window does its job.
- **FR-019**: The baseline record MUST be captured from an analysis run under the EXACT configuration
  that lands on `main`. Analyses produced by probe arms under FR-009b MUST be excluded from baseline
  capture by analysis identifier, and the baseline record MUST name the analysis identifier it was
  taken from so that exclusion is checkable. Baselining a probe arm would baseline a configuration
  that never ships.
- **FR-020**: The baseline record MUST partition results into path classes before triage begins, at
  minimum: product code (`frontend/src`, `src/dashboard`), test code (`frontend/tests`), and
  non-shipping artifacts (build configuration files and contract stubs under `specs/`, per F15). A
  single recorded disposition MAY cover an entire path class where the rule identifier and the
  reason are identical across every alert in that class, and that bulk disposition counts as
  satisfying FR-016 for each alert it covers. This exists so that a baseline dominated by test-only
  or stub-only findings does not make FR-016 arithmetically unmeetable, without weakening the
  requirement that nothing is left undispositioned.
- **FR-021**: The baseline record MUST also carry, at the moment of capture: the named accountable
  role for triage, the analysis identifier the baseline was taken from, and the close-out date
  computed from A1. A duration with no start date is not a deadline. Writing the calendar date into
  the record at capture time is what converts it into one. Per F19 the accountable role is
  **Admin Role (Project Owner: @traylorre)**, cited to `CONTRIBUTING.md:64`, whose responsibilities
  already include responding to security incidents. The role MUST be recorded with that citation
  rather than restated as a bare handle, so a later reader can check it against a source.
- **FR-014**: Alerts surfaced by enabling JavaScript/TypeScript MUST be recorded as newly revealed
  pre-existing exposure. They MUST NOT be characterised as a regression introduced by this feature,
  and a rise in the open alert count MUST NOT be treated as a failure condition.
- **FR-015**: The JavaScript/TypeScript leg MUST land in the same non-blocking enforcement state
  that the Python leg occupies today. This feature MUST NOT add a merge gate.
- **FR-016**: Every alert in the baseline MUST receive exactly one disposition within the triage
  window: fix now, carded follow-up, or dismissed with a recorded reason. The window opens at the
  timestamp of the analysis named in FR-019 and closes on the calendar date written into the
  baseline record under FR-021.
- **FR-016a**: The window MAY be extended exactly ONCE, to a new fixed calendar date recorded in the
  baseline record alongside the reason. It MUST NOT be extended a second time. An indefinitely
  extensible window is a deferral wearing a deadline's clothes.
- **FR-016b**: The lapse behaviour MUST be defined rather than left to good intentions. If the
  window closes with any baseline alert undispositioned, then: the undispositioned set is FIRST
  counted and recorded verbatim, because SC-008 is evaluated against that count before any default
  is applied; every undispositioned alert is THEN recorded as `carded follow-up` by default so the
  count never silently drops; the feature is recorded as FAILED CLOSE-OUT rather than quietly
  complete; and a single follow-up item is raised carrying the undispositioned set. Per F20, raising
  that item means a sequential entry in `docs/reference/TECH_DEBT_REGISTRY.md`, per constitution
  §9(a), with the `TD-` identifier allocated AT MERGE TIME against the registry's then-highest value
  and never pre-reserved in this spec. §9(b)'s labelled GitHub issue is NOT raised: the owner has
  directed that the `tech-debt` label not be created, so that half is recorded as outstanding. A requirement with no stated failure mode is a wish. This is the stated failure mode.
- **FR-017**: This feature MUST produce an enforcement recommendation as a deliverable, naming a
  severity threshold, a path scope, and a blocking or non-blocking position, justified by the
  observed alert volume. The gate question MUST be answered, not dropped. The recommendation MUST
  be committed inside this feature's directory, MUST name the role that decides on it, and MUST
  carry a decision-by date. A recommendation with no named recipient is a document, not a decision
  request.
- **FR-017a**: The recommendation MUST also cover the two adjacent questions this feature surfaced
  but does not resolve: the `frontend/tests` symmetry question raised by FR-007a, and the dependency
  install constraint stated in FR-004b.
- **FR-018**: Any claim that JavaScript/TypeScript coverage is live MUST be evidenced from a branch
  reference analysis record or from the alert-state API. A green pull request check MUST NOT be
  accepted as evidence.

**Two-gate acceptance**

- **FR-023**: This feature has TWO acceptance gates and MUST NOT be treated as complete when the
  first one passes. Merging the matrix change satisfies the MERGE gate. It does not satisfy the
  feature. Without this split, every criterion that carries enforcement weight is evaluated after
  the pull request is closed and everyone has stopped looking, which is the exact failure mode that
  turns a coverage feature into a scanner nobody acts on.

  | Gate | Criteria | When |
  |---|---|---|
  | MERGE | SC-001, SC-002, SC-003, SC-005, SC-006, SC-007, SC-009, SC-010, SC-012 | At merge, plus the first `refs/heads/main` run |
  | CLOSE-OUT | SC-004, SC-008, SC-011, SC-013 | On the close-out date recorded under FR-021 |

  The feature's status MUST remain open between the two gates. Closing it at merge is the failure
  mode FR-016b names, reached by a different route.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The code scanning analyses record for `refs/heads/main` contains at least one entry
  categorised for JavaScript/TypeScript, dated after this change lands. Today, every entry across
  the most recent twenty analyses is Python.
- **SC-002**: That JavaScript/TypeScript analysis reports a results count, and the value is written
  into the baseline record. Any value including zero satisfies this criterion; an absent analysis
  does not.
- **SC-003**: The JavaScript/TypeScript job log evidences that source files under both `frontend/`
  and `src/dashboard/` entered the database, rather than only one. Per Clarification Q3 the evidence
  is taken in this order, and the order is load-bearing:

  1. **Per-file lines.** Match `Extracted file` lines for the unanchored substrings `/frontend/` and
     `/src/dashboard/`. The paths in these lines are ABSOLUTE runner paths appearing mid-line, so a
     line-anchored pattern such as `^frontend/` returns zero unconditionally and MUST NOT be used.
  2. **Extractor invocation line.** If tier 1 produces no per-file lines AT ALL for either directory,
     that is a logging-verbosity outcome, not a coverage outcome, because per-file logging is
     extractor-specific and the JavaScript extractor exposes no logging-verbosity option. Fall back
     to the extractor invocation line, which prints the scan root and the active `--filter exclude:`
     set. Both directories being under the scan root and matching no exclusion establishes scope.
  3. **Coverage summary line.** "CodeQL scanned N out of M JavaScript/TypeScript files", reconciled
     against the expected 290 in-scope files at the analyzed commit (`frontend/src` 173,
     `frontend/tests` 101, `src/dashboard` 6, configuration and contract stubs 10). This tier is
     weakest: its tolerance is wider than `src/dashboard`'s 6 files, so it can corroborate but can
     never by itself prove the admin dashboard specifically.

  **Anti-false-negative rule**: absence of evidence at any tier MUST be recorded as SC-003 UNPROVEN
  and carried into the evidence log as an open item. It MUST NOT be recorded as "the admin dashboard
  was not extracted". UNPROVEN does not fail the MERGE gate; asserting a coverage gap that was never
  observed would be worse than admitting the log did not say.
- **SC-004**: The open alert count is measured before and after, against the pre-change baseline of
  5 open alerts, and the delta is published in the baseline record. Acceptance does NOT depend on
  the delta being zero or negative. An increase satisfies this criterion.
- **SC-005**: Python coverage does not REGRESS. The `refs/heads/main` Python analysis reports at
  least 9 results, and no previously open Python alert DISAPPEARS as a side effect of the config
  work. **Identity is the (rule identifier, file path) pair, NOT the alert number.** Alert numbers
  are not stable identities across remediation: closing an alert and rewriting the line spawns a
  fresh number at the same location, so a number-keyed comparison reports a spurious loss. The
  alerts API exposes nothing finer than `path` and line and column offsets under
  `most_recent_instance.location`, so rule plus path is the strongest identity mechanically
  available and this criterion asks for no more. Alert numbers MAY be recorded alongside as a
  convenience for looking an alert up; they MUST NOT be what the comparison turns on. This is
  deliberately a floor and not an equality. If the probe under FR-009b
  shows the path exclusion was suppressing rules other than the single deliberately filtered rule,
  then the correct resolution WIDENS Python scope and the results count rises above 9. An equality
  test would fail the feature for producing exactly the outcome FR-012 is trying to protect.
- **SC-006**: The required status check set on `main` still contains exactly the four contexts from
  F8, unchanged in name and count.
- **SC-007**: The added matrix leg does not push the workflow's total wall clock past its current
  critical path. Measured pre-change totals are 5 to 7 minutes, bounded by the Playwright job, with
  the Python analysis leg at about 1.1 minutes. The bound is therefore: the JavaScript/TypeScript
  leg completes within 8 minutes AND total workflow wall clock stays within 2 minutes of the
  pre-change figure. The earlier "within 10 minutes" wording was internally inconsistent, because a
  10 minute leg against a 6 to 7 minute critical path necessarily breaches the 2 minute total bound.
  If the leg exceeds 8 minutes, the leg bound and the total bound are BOTH reported and the total
  bound governs.
- **SC-012**: The analysis job carries the FR-022 matrix-context warning comment, and the workflow
  contains no other job whose status context is generated per matrix value without one.
- **SC-008**: 100 percent of baseline JavaScript/TypeScript alerts carry exactly one recorded
  disposition when the triage window closes. Zero alerts are left undispositioned. **This is
  measured at window close BEFORE FR-016b's `carded follow-up` default is applied.** Measured after
  the default, every alert carries a disposition by construction and the criterion could never fail,
  which would make it decorative. The undispositioned count at window close is written into the
  close-out record as a number, including when that number is zero.
- **SC-009**: The config file contains no rule whose stated intent contradicts its effect. Every
  retained rule is traceable to a line in the probe record. **AMENDED at Clarification Q4**: since
  FR-009b now makes the surviving control arm OPTIONAL, "a line in the probe record" means EITHER
  an arm line, where the control arm was run, OR the transcribed extraction-level evidence from the
  `refs/heads/main` job log that Q4 records. A retained rule traceable to neither fails this
  criterion. Without this amendment SC-009 would be unsatisfiable on the exact path FR-009b
  permits, while sitting in FR-023's MERGE gate.
- **SC-010**: The probe record is reproducible: a second person, given only the record, can reach
  the same conclusion from the sources the record names. **AMENDED at Clarification Q4** for the
  same reason as SC-009. Where the control arm was run, reproducibility means naming its analysis
  identifier and re-running it. Where it was not run, which FR-009b permits, it means naming the
  run, job and log line numbers of the Q4 extraction evidence and re-reading them. An empty probe
  record satisfies neither form, so the criterion still has teeth.
- **SC-011**: The enforcement recommendation exists as a written artifact committed inside this
  feature's directory, naming a severity threshold, a path scope, a blocking position, the role that
  decides on it, and a decision-by date, and is carried forward as a follow-up item rather than
  being applied inside this feature.
- **SC-013**: The close-out is recorded with an outcome of either COMPLETE or FAILED CLOSE-OUT. A
  close-out with no recorded outcome does not satisfy this criterion, and neither does a feature
  that was marked complete at merge. This is the criterion that makes FR-016b observable rather
  than aspirational.

## Position taken on new-alert intake

**Land coverage non-blocking, baseline it, triage it inside a bounded window, and ship the
enforcement decision as a recommendation rather than as a gate.**

Justification, in order of weight:

1. **Non-blocking is parity, not a concession.** F8 establishes that CodeQL gates nothing today.
   There is no required context for it and no ruleset. Shipping the JavaScript/TypeScript leg
   non-blocking therefore changes no one's merge experience. Shipping it blocking would be a
   brand-new gate smuggled in under a coverage feature, which is a different feature and deserves
   its own argument.
2. **Choosing a blocking threshold before seeing the number is choosing blind.** Nobody knows
   whether the first run yields 3 alerts or 300 across 47,300 lines that have never been analyzed.
   A threshold picked now is a guess dressed as a policy.
3. **A day-one gate on an unknown backlog halts unrelated work.** That cost lands on every
   contributor immediately and buys nothing, because the alerts it would block on are pre-existing
   and were already shipped.
4. **A permanently non-blocking gate is decorative, so the window is time-boxed and the follow-up
   is mandatory.** FR-016 forces disposition of every alert and FR-017 forces a written enforcement
   recommendation. This is a position with a deadline attached, not a deferral. The difference
   between this and punting is that punting produces no artifact and no date.

**The honest limit of point 4.** Nothing in this repository can mechanically enforce a triage
window. There is no automation that fails a build because a disposition is missing. That is a real
weakness and it is stated here rather than papered over. What this feature does instead is remove
every ambiguity that a lapse could hide behind: A1 pins the start to a specific analysis identifier,
FR-021 writes the close-out date into an artifact at capture time, FR-016a caps extensions at one,
FR-016b defines what a lapse produces, FR-023 keeps the feature open past merge, and SC-013 makes
the outcome a recorded value rather than an absence. A lapse then becomes visible and attributable
instead of silent. That is the strongest available guarantee short of adding automation, which would
be a different feature.

This position is consistent with the owner directive. The directive asks for coverage and
acknowledges that more code means more to get passing. It does not ask for the gate to be
tightened in the same stroke.

## Assumptions

- **A1**: The triage window is 10 working days from the FIRST `refs/heads/main` full-tree
  JavaScript/TypeScript analysis after merge, identified by the analysis identifier recorded under
  FR-019. It is explicitly NOT measured from the pre-merge probe or dispatch run, both of which are
  also full-tree JavaScript/TypeScript analyses and would otherwise start the clock early and
  ambiguously. The resulting calendar date is written into the baseline record under FR-021 at
  capture time. The research did not settle a duration. Ten days is long enough to absorb a surprise
  volume and short enough that the backlog does not become permanent.
- **A2**: `frontend/tests` is in scope for scanning. Excluding it preemptively would recreate
  precisely the untested-assumption pattern that User Story 2 exists to fix. If the baseline shows
  the volume is dominated by test-only patterns, that becomes an evidence-backed filter proposal in
  the enforcement recommendation. Two consequences are acknowledged rather than hidden: the volume
  at risk is about 19,900 lines, more than the 22,300 lines of `frontend/src` it exercises, so a
  baseline dominated by test-only findings is a realistic outcome rather than a remote one, and
  FR-020's path-class bulk disposition is what keeps FR-016 meetable if it happens; and the
  resulting asymmetry against excluded Python test code is governed by FR-007a, which requires it to
  be argued rather than inherited from glob anchoring.
- **A3**: F9 holds and no build step is needed. If the first run contradicts it, FR-004 governs.
- **A4**: First-party coverage without installed dependencies is acceptable for this feature. Two
  corrections to the original reasoning. First, the claim that dependency vulnerabilities are
  "already covered elsewhere" is true for ALERTING but only partly true for maintenance: per F18
  there are 82 open npm advisories and the dependency graph does watch npm, but `dependabot.yml`
  declares no npm ecosystem, so npm version updates are not automated. That gap is real, it is
  out of scope here, and FR-017a carries it forward. Second, and more importantly, the cost of
  skipping the install is NOT primarily missed dependency advisories. It is degraded type and
  library resolution, which weakens taint tracking through framework boundaries in first-party
  code. The owner directive names taint analysis specifically, so this cost is directly on the
  thing the feature is for. FR-004a requires it to be measured from the job log rather than assumed
  away, and FR-004b constrains how it may be revisited.
- **A5**: The probe is triggered by manual workflow dispatch on the feature branch, since F12 shows
  feature branch pushes do not trigger the workflow on their own and F5 shows a pull request run
  cannot answer the question. Probe arms mutate the configuration temporarily; FR-010a confines
  those mutations to the branch and FR-019 keeps their analyses out of the baseline. If the dispatch
  permission is unavailable, FR-009c governs.

## Out of Scope

- Remediating the JavaScript/TypeScript alerts this feature surfaces. This feature baselines,
  triages, and dispositions them. Fixes are separate work items.
- Fixing the 5 currently open Python alerts.
- Adding CodeQL to the required status check set, or creating any ruleset or merge protection.
  FR-017 produces the recommendation; applying it is a follow-up.
- Adding any further analysis language beyond JavaScript/TypeScript, including workflow-definition
  scanning.
- Migrating from the current workflow-driven setup to a managed default setup.
- Any change to the other static analysis tooling in this repository.
- Any new cloud resources. This feature creates none.

**Carded, raised with the owner at the enforcement-recommendation step, not resolved here:**

- Promoting CodeQL to a required status check. Adversarial review concluded the case for it is
  strong, because a scanner that gates nothing is a scanner whose output nobody must act on. It
  remains out of scope: it is a new merge gate and deserves its own argument on its own evidence,
  which is exactly what FR-017 is for. Recorded as out of scope, carded, raise with owner at
  Phase 2.
- Adding an `npm` ecosystem to the Dependabot configuration. Per F18, npm advisories are alerted
  on but npm version updates are not automated. Adjacent, real, and not this feature.
- Adding a concurrency-cancel group to the workflow. Per F13 its absence stacks complete runs; the
  second matrix leg makes that slightly worse. Not a security question and not this feature.
- Symmetry between the excluded Python test tree and the included frontend test tree, if FR-007a's
  recorded decision cards it rather than resolving it.
- **DEFERRAL 1 (Clarifications Q2)**: constitution §9 cites `docs/TECH_DEBT_REGISTRY.md` at lines
  527, 569 and 584, but the registry has lived at `docs/reference/TECH_DEBT_REGISTRY.md` since
  `f8db8d2` (PR #668). Amend §9 to the real path, or move the file back? Carried into the FR-017
  enforcement recommendation so it reaches the named decider under that document's decision-by date
  rather than expiring inside a clarifications appendix. Not blocking this feature.
- **DEFERRAL 2 (Clarifications Q5)**: confirm the 10-working-day triage window under A1, or name a
  different number. This one is **blocking for Phase E** rather than merely carded: FR-021 writes
  the computed calendar date into the baseline record at capture time and FR-016a permits exactly
  ONE extension, so an answer arriving after baseline capture would spend that single extension on
  an authoring correction instead of on alert volume. If unanswered at capture time, 10 working
  days is recorded as ASSUMED rather than confirmed, the baseline record says so, and a later owner
  change is treated as the FR-016a extension it is.

## Dependencies

- Permission to trigger a manual workflow run on the feature branch, required by A5 for the probe
  and for the first full-tree analysis. If unavailable, FR-009c governs the probe and User Story 1
  falls back to the post-merge `refs/heads/main` run for all its evidence.
- Read access to the code scanning alerts and analyses APIs for baseline capture and for the
  evidence required by FR-018 and SC-001 through SC-005.
- Write access to this feature's directory for the baseline record, the probe record, and the
  enforcement recommendation. All three are committed artifacts, not chat messages, because FR-021,
  FR-010, and SC-011 are only checkable if the artifacts exist in the repository.

## Adversarial Review #1

**Reviewer**: adversarial reviewer, did not author this spec.
**Date**: 2026-07-30.
**Method**: attack the spec for scope creep, testability, feasibility, internal contradiction,
missing failure modes, security gaps, 3am breakage, six-months-unmaintained decay, and cost.
Every established fact re-verified against live APIs and the working tree rather than taken from
the spec's own table.

### Findings

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| 1 | CRITICAL | **The teeth are evaluated after nobody is looking.** SC-008 and SC-011 cannot be satisfied until 10 working days after merge, but the spec had no concept of the feature staying open past merge. Merge the pull request, close the feature, and the only two criteria carrying enforcement weight are never evaluated. | FIXED. Added FR-023 with an explicit two-gate acceptance table (MERGE gate and CLOSE-OUT gate) and a requirement that feature status stays open between them. Added SC-013 requiring a recorded close-out outcome. |
| 2 | CRITICAL | **Probe and baseline contaminate each other.** The probe requires temporarily mutating the path-exclusion rules. If the probe dispatch also carries the matrix change, one run produces both the probe result and a JavaScript/TypeScript result set under a configuration that never ships. FR-013 would then baseline a fictional config. | FIXED. Added FR-019 requiring the baseline to come from an analysis under the exact configuration that lands, probe analyses excluded by identifier, and the source analysis identifier named in the record. Added FR-010a confining probe mutations to the branch. Added an edge case for it. |
| 3 | HIGH | **The triage window had no start point.** A1 said "10 working days from the first full-tree analysis", but the pre-merge probe run is also a full-tree JavaScript/TypeScript analysis. The clock could start pre-merge, post-merge, or never, and all three readings were defensible. | FIXED. A1 rewritten to pin the start to the first `refs/heads/main` analysis after merge, identified by the analysis identifier in FR-019, and to explicitly exclude pre-merge runs. |
| 4 | HIGH | **The window had no owner, no recorded date, and no lapse behaviour.** FR-016 said "within the triage window" with no accountable role, no calendar date written anywhere, and no consequence if the window passed. The edge case for large volume said "adjust the window", which made it infinitely extensible and therefore not a window at all. | FIXED. FR-021 requires the accountable role, source analysis id, and computed close-out DATE written into the baseline record at capture time. FR-016a caps extensions at exactly one, to a new fixed date. FR-016b defines the lapse: undispositioned alerts default to carded follow-up, the feature is recorded FAILED CLOSE-OUT, one follow-up item is raised. Large-volume edge case rewritten to point at FR-016a and FR-020 instead of open-ended adjustment. |
| 5 | HIGH | **The probe as specified could not answer the question it was for.** FR-010 named "the two configurations compared". Two arms cannot separate "the path exclusion is doing the excluding" from "the query filter is doing the excluding". Worse, per F4 six of the eight historical alerts for the filtered rule are `fixed`, so the rule may no longer fire at all, and a two-arm all-zero result would have been read as a conclusion when it is an artifact. | FIXED. Added FR-009a requiring a POSITIVE CONTROL arm (both rules removed) run FIRST, with immediate inconclusive declaration if it returns zero. Added FR-009b requiring three arms, not two, and forbidding a two-arm probe from being accepted as conclusive. FR-010 extended to require per-arm identifiers, configs, counts, and the control outcome. |
| 6 | HIGH | **SC-005 punished the correct outcome.** It required the Python analysis to "still report 9 results". If the probe showed the path exclusion was suppressing rules beyond the single filtered rule, the correct fix WIDENS Python scope and the count rises above 9, failing SC-005 while succeeding at FR-012, which only bars reduction. An equality test where the requirement specifies a floor. | FIXED. SC-005 restated as a floor ("at least 9 results") with the reasoning recorded so a later reader does not re-tighten it. |
| 7 | HIGH | **SC-007 contradicted itself.** It allowed the new leg 10 minutes while requiring total wall clock within 2 minutes of a pre-change figure bounded by a 6 to 7 minute Playwright job. A 10 minute leg necessarily breaches the 2 minute total bound. Measured pre-change totals are 5 to 7 minutes, Python leg 1.1 minutes. | FIXED. Leg bound tightened to 8 minutes, measured figures written in, and an explicit precedence rule added: if the two bounds disagree, the total bound governs. |
| 8 | HIGH | **A4 justified the no-install decision with the wrong reason and hid the real cost.** It said dependency vulnerabilities are covered elsewhere, which is true for alerting (82 open npm advisories via the dependency graph, F18) but sidesteps the actual cost. Skipping the install degrades type and library resolution, which weakens taint tracking through framework boundaries in first-party code. The owner directive names taint analysis specifically, so the cost lands directly on the feature's purpose. | FIXED. A4 rewritten with both corrections. FR-004 split: FR-004 now covers only the build-step question, FR-004a makes the install a recorded decision with both the real justification and the real cost, and requires the baseline record to note type-resolution and module-resolution warnings from the job log so revisiting is evidence-backed. |
| 9 | HIGH | **A dependency install would open a supply-chain hole, and the spec did not know it.** The analysis job holds `security-events: write` and triggers on `pull_request` on a public repository (F17). An install step there would execute contributor-authored package lifecycle scripts inside a job with write access to the security-events surface. Fork tokens are downgraded, but write-access branch pushes are not. The spec's no-install default was right for reasons it never stated. | FIXED. Added F17. Added FR-004b forbidding a future install in any job that both holds `security-events: write` and is reachable from an untrusted reference, and requiring that constraint to be carried into FR-017. Added an edge case stating it. |
| 10 | HIGH | **FR-003 stated a floor with no ceiling, and the real scope is wider than the two dashboards.** F10 counted three directories. The actual JavaScript and TypeScript surface also includes six build configuration files and four contract stub files under `specs/`, about 745 lines. Contract stubs are specification artifacts that never ship; alerts against them are real findings against non-shipping code and would have been discovered from the first result set rather than from the spec. | FIXED. Added F15 quantifying it. FR-003 now states the ceiling explicitly and requires it recorded. FR-020 adds a non-shipping-artifact path class. Added an edge case. |
| 11 | HIGH | **FR-016 was arithmetically unmeetable at volume.** With about 19,900 lines of frontend test code in scope, more than the 22,300 lines of `frontend/src` it exercises, a baseline dominated by test-only findings would force per-alert disposition on a set nobody can process in 10 days, and the only escape was the open-ended window adjustment killed in finding 4. | FIXED. Added FR-020 requiring path-class partition before triage and permitting one recorded bulk disposition per path class where rule identifier and reason are identical, counting as FR-016 satisfaction for every alert covered. Keeps the "nothing undispositioned" requirement intact while making it reachable. |
| 12 | HIGH | **FR-007 required a decision about `frontend/tests` but was silent on the asymmetry.** Python test code is excluded, frontend test code is included, purely because the exclusion glob is root-anchored. FR-007 could be satisfied by a decision that never mentions the asymmetry, leaving a glob accident indistinguishable from a deliberate policy. | FIXED. Added FR-007a requiring the decision to address the asymmetry explicitly, and to either argue it or card the symmetry question. Carded item added to Out of Scope. A2 rewritten to acknowledge both consequences instead of only the argument in its favour. |
| 13 | HIGH | **FR-017's deliverable had no recipient and no date.** A written recommendation that names no deciding role and no decision-by date is a document that gets filed, not a decision that gets made. It was the second of the two things holding up the entire enforcement position. | FIXED. FR-017 now requires the recommendation to be committed in this feature's directory, to name the deciding role, and to carry a decision-by date. SC-011 updated to match. FR-017a requires it to also cover the two adjacent questions this review surfaced. |
| 14 | MEDIUM | **The analysis job carries no matrix-context warning while the Playwright job does.** Adding a matrix value ADDS `Analyze (javascript-typescript)` and does not rename `Analyze (python)` (F16 verified), so nothing breaks today. But this repository has a documented gate-breakage incident from exactly this shape, and the next matrix edit is as unguarded as that one was. | FIXED. Added F16. Added FR-022 requiring the warning comment in the same form the Playwright job uses, and SC-012 to verify it. Edge case corrected from "creates a new context name" to "adds rather than renames" with the prospective hazard stated separately. |
| 15 | MEDIUM | **The probe had no not-runnable path.** Manual dispatch permission is listed as a Dependency. If it is unavailable, FR-008 forbids changing the rules and nothing else applied, so User Story 2 stalls with no defined outcome. | FIXED. Added FR-009c routing an unrunnable probe to FR-011's inconclusive resolution, with FR-008's prohibition explicitly still holding. Dependencies section updated with the fallback. |
| 16 | MEDIUM | **Three references were in play and the spec used them interchangeably.** US1's Independent Test said "the branch reference", acceptance scenario 1.1 said "a branch reference", SC-001 said `refs/heads/main`, and FR-018 barred pull request references. Verifiable, but only after a reader reconciles it themselves. | FIXED. Added a "Which reference proves what" table to User Story 1 mapping each of the three references to exactly what it can and cannot prove, and to which success criteria it satisfies. |
| 17 | MEDIUM | **Cost framing was directionally wrong in two ways.** The workflow has no concurrency-cancel group, so rapid pushes stack complete runs, which the spec did not mention. Separately, the spec implied Dependabot traffic was a major multiplier; measured, it is 5 of 100 runs over five days. And the repository is public, so runner minutes bill at zero. | FIXED. Added F13 and F14 with measured figures. Cost edge case rewritten: the currency is wall clock and queue depth, not dollars, Dependabot is a minority of traffic, and the missing concurrency group is named. Concurrency group carded as out of scope. |
| 18 | LOW | **The npm ecosystem gap.** Dependabot alerts cover npm (82 open) but `dependabot.yml` declares no npm ecosystem, so npm version updates are not automated. Adjacent to A4's original claim, not caused by this feature. | RECORDED, not fixed. Added F18 and a carded Out of Scope entry. Fixing it here would be scope expansion. |
| 19 | LOW | **The quality checklist self-certifies items that were false at review time.** `requirements.md` marks "Requirements are testable and unambiguous" complete while FR-016 had no owner, no start point, and no lapse behaviour. | RECORDED, not separately fixed. The underlying defects are resolved by findings 3, 4, and 13, which makes the checklist item true rather than aspirational. The checklist file is left as authored. |
| 20 | LOW | **Promoting CodeQL to a required check.** The review concluded the case is strong: a scanner that gates nothing produces data, not enforcement. | RECORDED. Out of scope, carded, raise with owner at Phase 2. It is a new merge gate and belongs to its own feature with its own evidence, which is what FR-017 exists to produce. |

**Counts**: 2 CRITICAL, 11 HIGH, 4 MEDIUM, 3 LOW. Total 20.

### Suspicions the review was asked to verify

| Suspicion | Verdict |
|---|---|
| 1. Delivers nothing enforceable | **PARTIAL, and the enforceable part was smaller than claimed.** The coverage half is genuinely enforceable and binary: SC-001 through SC-003 are API-observable and take the analyzed surface from zero to about 48,000 lines. The intake half was not: findings 1, 3, 4, and 13 confirmed that FR-016 and FR-017 had no owner, no start point, no recorded date, no lapse behaviour, and were scheduled for evaluation after the feature would have been closed. All four are now fixed. The honest residual limit is stated in the Position section: nothing in this repository can mechanically fail a build for a missing disposition. What the fixes buy is that a lapse is now visible and attributable rather than silent. |
| 2. `frontend/tests` drowns the baseline | **CONFIRMED as a risk, REFUTED as unmanageable.** The volume is real: 19,913 lines of frontend test code against 22,295 lines of `frontend/src`. It genuinely could dominate the baseline, and FR-016 was arithmetically unmeetable in that case (finding 11). It is now meetable via FR-020's path-class bulk disposition. The asymmetry against excluded Python tests is confirmed to be a glob accident that A2 rationalized after the fact; FR-007a now forces it to be argued or carded (finding 12). |
| 3. The probe cannot answer the question | **CONFIRMED.** A two-arm probe cannot separate the two readings even in principle, and per F4 the filtered rule may no longer fire at all, so an all-zero result would have been mistaken for a conclusion. Fixed with a mandatory positive-control arm run first (FR-009a) and a three-arm design (FR-009b). The spec already had an inconclusive path in FR-011 and acceptance scenario 2.4; what it lacked was the ability to KNOW it was inconclusive, and a not-runnable path (FR-009c). |
| 4. Cost is understated | **REFUTED on dollars, PARTIAL on the rest.** The repository is public, so GitHub-hosted runner minutes bill at zero. Dependabot traffic is 5 of 100 runs over five days, not a dominant multiplier. What WAS understated: SC-007 contradicted itself (finding 7), and the workflow has no concurrency-cancel group so rapid pushes stack complete runs (finding 16). |
| 5. `Analyze (python)` context renaming | **REFUTED as a live risk, CONFIRMED as a documentation gap.** Verified: the job is named `Analyze` and contexts are generated per matrix value, so adding a language ADDS `Analyze (javascript-typescript)` and leaves `Analyze (python)` untouched. Grep across `.github/` found no automation matching any status context name. Nothing can break today. The gap is that the Playwright job carries an explicit rename warning and this job does not, so the next matrix edit is unguarded. FR-022 and SC-012 close it. |
| 6. Verification relies on a pull request check | **REFUTED.** FR-018 already barred pull request evidence explicitly and SC-001 already targeted `refs/heads/main`. The spec did not make this mistake. The real defect was adjacent: three different references were used interchangeably across US1's Independent Test, acceptance scenario 1.1, and SC-001, with no mapping of which one proves what (finding 16). Now mapped in a table. |

### Not anticipated by the review brief

- **Probe and baseline contamination** (finding 2, CRITICAL). The sequencing hazard between User
  Story 2's config mutation and User Story 3's baseline capture was not on the attack list and was
  the second-most serious defect found.
- **The supply-chain consequence of the install question** (finding 9). The no-install default was
  correct, but for a reason the spec never gave, and the reason it did give would not have survived
  a later argument to add the install.
- **Scan scope reaches `specs/`** (finding 10). Four contract stub files under `specs/` will be
  extracted and can generate alerts against specification artifacts that never ship.
- **SC-005 punished the correct outcome** (finding 6). An equality test guarding a requirement that
  specifies only a floor.

### Does this feature produce a measurable security improvement, or merely data?

Before the review: **mostly data**. The coverage change is real and measurable, but the half of the
spec that converts findings into action had no owner, no start date, no lapse behaviour, and would
have been evaluated after the feature was closed. That combination reliably produces a scanner whose
output nobody must act on.

After the review: **a measurable improvement in what is KNOWN, plus a bounded and attributable
process for acting on it.** The distinction still matters and is stated rather than blurred. Turning
on the scanner does not remove a single vulnerability. It converts about 48,000 lines of unmeasured
risk into measured risk, and the FR-016 and FR-021 machinery is what stops the measurement from
sitting untouched. Whether it becomes enforcement depends on the FR-017 recommendation, which is
correctly out of scope here and now carries a named decider and a date instead of being a document.

### Gate

**0 CRITICAL, 0 HIGH remaining.**

## Clarifications

### Session 2026-07-30

Run non-interactively. Every question below was answered from the working tree, git history, or
read-only GitHub API queries, with the evidence cited inline. Nothing was invented. Two items are
genuinely owner decisions and are marked **DEFERRED**; each is phrased to be answerable in one line.

Primary evidence source used repeatedly below, captured once and referred to as **[LOG]**:
workflow run `30581930915` on `refs/heads/main`, job `Analyze (python)` (job id `91004036909`,
started 2026-07-30T21:05:00Z), full log retrieved via `gh run view --log`. Line numbers are lines
of that retrieved log.

---

**Q1. FR-021 requires the baseline record to carry a "named accountable role" for triage, and FR-017
requires the enforcement recommendation to name the role that decides on it. Is there a source in
this repository for those names, or must the owner supply them?**

**A: SELF-ANSWERED. A source exists; no owner input is needed.**

- `CONTRIBUTING.md:62` states "There are **two roles** in this project".
- `CONTRIBUTING.md:64` names the first: "#### Admin Role (Project Owner: @traylorre)". Its listed
  responsibilities include "Respond to security incidents" (`CONTRIBUTING.md:74`), which is exactly
  the accountability FR-021 is asking to name.
- `.github/CODEOWNERS:15` assigns `* @traylorre` as default owner of the whole tree, and lines 3 and
  7 record that @traylorre is the sole admin and must approve all pull requests.
- Collaborators API for this repository returns exactly one entry:
  `{"login":"traylorre","role_name":"admin","permissions.push":true}`. There is no second account
  with push access and therefore no second candidate.

**Effect on requirements**: FR-021's accountable role and FR-017's deciding role are both
**Admin Role (Project Owner: @traylorre)**, cited to `CONTRIBUTING.md:64`. FR-021 is amended to name
that source so the implementer does not have to derive it.

---

**Q2. Constitution §9 mandates `TD-XXX` entries in `docs/TECH_DEBT_REGISTRY.md`, and `plan.md`
records a DEVIATION on the grounds that the file "does not exist anywhere in this repository". Is
that true, and if not, which of this feature's deferred items are genuine tech debt?**

**A: SELF-ANSWERED, and the premise was false.**

- The registry exists at `docs/reference/TECH_DEBT_REGISTRY.md`: 25479 bytes, holding `TD-001`
  through `TD-023` in the format §9 documents.
- It was relocated from the flat path by commit `f8db8d2` ("feat(docs): Reorganize documentation
  into categorical subdirectories", PR #668). The file was not missing; the constitution's path
  reference is stale, at `.specify/memory/constitution.md` lines 527, 569 and 584.
- Sibling features reached the same finding independently:
  `specs/001-ruff-bump-forward/plan.md:109` and `specs/001-oauth-provider-taint/plan.md:49`.

**Effect on the Constitution Check**: the §9 DEVIATION is **withdrawn**. §9 is satisfiable by
writing into the real registry, so the gate is live rather than blocked, and this feature must
decide which of its deferred items are debt. That triage:

| Deferred item | Registry entry? | Reason |
|---|---|---|
| npm ecosystem absent from `dependabot.yml` while 82 npm advisories are open (F18) | **YES, TD entry** | §9 names "dependency issues requiring future attention" as a trigger. This is exactly that. |
| §10 local-SAST gap: after this lands, CodeQL covers `frontend/` but no local pre-push tier does (`plan.md` recorded gap) | **YES, TD entry** | §9 names "known limitations" as a trigger, and this feature is what widens the gap. |
| Any FR-016b lapse set (baseline alerts undispositioned at window close) | **YES, TD entry**, conditional | §9 names "deferred features or incomplete implementations". This is the "single follow-up item" FR-016b already requires; the TD entry plus a `tech-debt` issue is what raising it means. |
| Promoting CodeQL to a required status check | **NO, carded only** | Not debt this feature incurred. It is a proposed policy change, and FR-017 already delivers it as a committed recommendation with a named decider and a decision-by date, which is stronger than a registry line. A TD entry becomes warranted only if that decision-by date passes undecided. |
| Concurrency-cancel group absent from the workflow (F13) | **NO, carded only** | A queue-depth optimisation that predates this feature and is neither a correctness nor a security shortcut. |
| `frontend/tests` symmetry | **NO, carded only** | Resolved by Q4 below as a deliberately preserved asymmetry with a stated reason. A decision with a rationale is not debt. |

**Identifier collision, flagged and deliberately NOT resolved here**: the next free identifier is
`TD-024`. **Line-number citations to sibling artifacts were removed here because the siblings have
since corrected their own pre-reservations and the citations no longer point at what they claimed.**
The settled cross-feature rule, which all four features in this campaign now share, is that TD
identifiers allocate at MERGE time in merge order and no feature pre-reserves one. `TD-024` appears
in sibling text only as the arithmetic successor to `TD-023`, explicitly not as a claim. This
feature therefore claims
**no identifier at authoring time**. Any TD entry it owes is allocated **at merge time, in merge
order**, against whatever the highest identifier in the registry is at that moment. Pre-reserving an
identifier in a spec is what created the collision.

> **DEFERRED for the owner**: Constitution §9 cites `docs/TECH_DEBT_REGISTRY.md` at lines 527, 569
> and 584, but the registry has lived at `docs/reference/TECH_DEBT_REGISTRY.md` since commit
> `f8db8d2` (PR #668). Amend §9 to the real path, or move the file back to the flat path?

---

**Q3. SC-003 requires the job log to record extracted source files under both `frontend/` and
`src/dashboard/`. Is that evidence guaranteed to exist at default verbosity, and can a logging gap
be mistaken for the admin dashboard not being extracted?**

**A: SELF-ANSWERED. It is not guaranteed, one artifact command is broken as written, and two
fallbacks exist.**

- Per-file logging DOES occur for the Python leg at default verbosity: 152 `Extracted file <path>`
  lines, first at **[LOG]** line 1487. But the paths are ABSOLUTE runner paths
  (`/home/runner/work/sentiment-analyzer-gsk/sentiment-analyzer-gsk/src/...`) appearing mid-line,
  after the `<job name>\t<step>\t<timestamp>` prefix that `gh run view --log` prepends.
- `quickstart.md:108` matches `grep -cE '^frontend/'`, anchored at line start. Against that log
  shape it returns 0 unconditionally, whether or not the directory was extracted. It is a
  **guaranteed false negative** and is corrected to an unanchored `/frontend/` and `/src/dashboard/`
  substring match.
- Per-file logging is extractor-specific, not a CodeQL-wide guarantee. The Python lines originate
  from `python_tracer.py --verbosity 3` (**[LOG]** line 1480). The JavaScript extractor's declared
  options are only `trap` and `skip_types` (**[LOG]** lines 213 to 256); it exposes no
  logging-verbosity option, so its default per-file behaviour cannot be established in advance from
  anything in this repository. This is the residual uncertainty, and it is real.
- Two fallbacks are present in the same log at default verbosity: the extractor invocation line,
  which prints the scan root and the active `--filter exclude:` set (**[LOG]** line 1480), and the
  coverage summary line, "CodeQL scanned 152 out of 154 Python files and 5 out of 5 GitHub Actions
  files in this invocation" (**[LOG]** line 2067).

**Effect on success criteria**: SC-003 is restated with a three-tier evidence ladder and an explicit
anti-false-negative rule, so that "the log did not say" can never be recorded as "the admin
dashboard was not extracted". Denominator for tier 3, computed at `c010178`: **290** JavaScript and
TypeScript files in scope (291 tracked, minus `tests/load/api-load-test.js` which the root-anchored
exclusion removes), of which `frontend/src` 173, `frontend/tests` 101, `src/dashboard` 6, and 10
configuration and contract-stub files. Note the tier-3 tolerance is wider than `src/dashboard`'s 6
files (the Python leg's own count was 154 against 151 git-tracked files), so tier 3 alone can never
prove the admin dashboard specifically. That is why it ranks last and why UNPROVEN is a permitted
outcome.

---

**Q4. F3 records the config contradiction's operational consequence as UNPROVEN, and FR-009b
requires a three-arm probe to settle it. Does conclusive evidence already exist, and does it also
settle the `frontend/tests` asymmetry rationale that FR-007a demands?**

**A: SELF-ANSWERED on both. Evidence already exists, and it required no config mutation.**

From the same `refs/heads/main` full-tree analysis:

- The path exclusion is applied at **extraction** time, not at result-filtering time. The extractor
  is invoked as `python3 -S .../python_tracer.py --verbosity 3 -z all -c <trap_cache> -R <repo root>
  --filter exclude:tests/**/*` (**[LOG]** line 1480).
- Zero of the 152 `Extracted file` lines are under `/tests/`.
- The repository tracks 544 `.py` files at `c010178`: 393 under `tests/`, 151 outside it. CodeQL
  reports "scanned 152 out of 154 Python files" (**[LOG]** line 2067). The 393 test files never
  enter the database at all.

**Therefore, of F3's three claims, exactly the first is true:**

1. `paths-ignore: tests/**/*` (`.github/codeql/codeql-config.yml:19-20`) is what performs the
   exclusion. **TRUE.**
2. The `query-filters` entry scoped to `tests/**` (lines 23 to 29) is **INERT** while that exclusion
   stands. A query filter can only suppress results, and no result can originate from a file that
   was never extracted.
3. The comment "All other security rules apply to tests" (line 13) is **FALSE**. Test code is not
   scanned at all.

This is admissible under FR-009: it comes from a full-tree analysis on `refs/heads/main`, not from a
pull request reference, so F5 and FR-018 do not bar it.

**Effect on requirements**: FR-009b's three arms collapse to at most **one**. Arm 1 versus arm 2
("is the path exclusion what performs the exclusion?") is answered YES. Arm 2 versus arm 3 ("does the
query filter have any effect?") is answered NO. Only the FR-009a control question survives: whether
`py/incomplete-url-substring-sanitization` still fires on current Python test code at all. That
question now matters for exactly one decision, whether to DELETE the inert query filter or retain it
against a future narrowing of the path exclusion, and it is the only reason to mutate the config.

**The `frontend/tests` asymmetry rationale, which FR-007a requires to be argued rather than
inherited**: the asymmetry is larger than glob anchoring alone suggests and it now has a reason. The
Python side is an extraction-level exclusion removing 393 files from the database entirely. The
`frontend/tests` side is 101 files matching no exclusion pattern at all. Narrowing or widening either
side requires editing a rule in the shared config, which FR-008 bars until the surviving control
question above is answered. The asymmetry is therefore **preserved deliberately for this feature's
duration, because resolving it would require exactly the unprobed rule change FR-008 exists to
prevent**, and the symmetry question stays carded (already in Out of Scope), with no TD entry per
the Q2 triage.

---

**Q5. The 10-working-day triage window has no enforcing mechanism. Do the artifacts overstate what
it achieves, is the lapse behaviour complete, and is SC-008 falsifiable?**

**A: SELF-ANSWERED on all three. No overstatement; one hole in the lapse path, now closed; SC-008
was vacuous and is fixed.**

- **No overstatement.** The Position section already states the limit plainly ("Nothing in this
  repository can mechanically enforce a triage window"). Verified independently rather than taken
  from the spec: the only scheduled automation is `nightly-e2e.yml` (`cron: 0 2 * * *`) and the
  weekly security run in `pr-checks.yml` (`cron: 0 9 * * 1`), and neither reads alert dispositions.
  Required status checks on `main` re-queried today return exactly
  `["Secrets Scan","Lint","Run Tests","Playwright E2E Tests"]`, so F8 holds and CodeQL gates
  nothing. `plan.md` and `quickstart.md` make no enforcement claim anywhere.
- **One hole in the lapse path, now closed.** FR-016b required "a single follow-up item is raised"
  without saying where, which is the same shape of gap the adversarial review's finding 13 closed
  for FR-017. Resolved by Q2: the follow-up item is a sequential entry in
  `docs/reference/TECH_DEBT_REGISTRY.md`, per constitution §9(a), with the identifier allocated at
  merge time per the Q2 collision note. §9(b) is recorded as outstanding, per the owner directive
  that the `tech-debt` label not be created.
- **SC-008 was vacuous.** FR-016b makes every undispositioned alert default to `carded follow-up`.
  If SC-008 is evaluated after that default is applied, every alert carries a disposition by
  construction and SC-008 can never fail. A criterion that cannot fail measures nothing. SC-008 is
  restated to be evaluated at window close **before** the FR-016b default is applied, which is what
  makes the COMPLETE versus FAILED CLOSE-OUT distinction in SC-013 mean anything.

> **DEFERRED for the owner**: A1 sets the triage window at 10 working days and the spec records that
> the research did not settle a duration. This repository has exactly one collaborator with push
> access, so that is a commitment by one person against an alert volume nobody has seen yet. Confirm
> 10 working days, or name a different number.

---

### Summary

Five questions raised. **Five self-answered from evidence. Two owner decisions deferred**, both as
sub-questions of a self-answered item (the constitution §9 path in Q2, the window duration in Q5).

Requirements and criteria changed by these answers: **FR-021** (role now named with a source),
**FR-016b** (follow-up destination named), **FR-009b** (three arms collapse to at most one),
**SC-003** (evidence ladder plus anti-false-negative rule), **SC-008** (evaluated before the FR-016b
default). Fact **F3** is replaced, since its "UNPROVEN" status is no longer accurate, and **F19**
and **F20** are added. The §9 DEVIATION in `plan.md` is withdrawn.
