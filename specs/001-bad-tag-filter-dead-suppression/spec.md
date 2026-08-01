# Feature Specification: Close py/bad-tag-filter and Kill the Dead Suppression

**Feature Branch**: `001-bad-tag-filter-dead-suppression`
**Created**: 2026-07-30
**Status**: Draft
**Input**: User description: "Close CodeQL alert 147 (py/bad-tag-filter), delete dead lgtm suppression, extend make audit-pragma"

## Overview

CodeQL alert 147 (`py/bad-tag-filter`, severity high) has been open on `refs/heads/main` since 2026-01-31 against `scripts/regenerate-mermaid-url.py:82`. The flagged line validates Mermaid diagram arrow syntax. It carries a `# lgtm[py/bad-tag-filter]` comment that does nothing at all: the alert is open on the exact line carrying the comment.

This feature does three things. It rewrites the flagged expression so the analyzer has no pattern to complain about, it deletes the decorative comment rather than swapping in another inert form, and it adds a check so a suppression that suppresses nothing is caught the next time somebody writes one.

The third part carries the real design risk and gets the most attention here. The first is a one-line change whose only difficulty is proving behaviour did not shift.

Two facts about this repository shape the whole design and are stated up front because every requirement below depends on them.

**No scanning result blocks a merge here.** The branch protection required checks are exactly four, and none of them is the code scanning analysis. A high-severity alert can sit open on the default branch indefinitely without any check going red, which is precisely how alert 147 survived six months. Closing the alert is therefore an informational outcome, valuable for review honesty, but it carries no enforcement. Only a check that runs inside one of the four required contexts can actually stop the next dead suppression from landing. FR-018 exists because of this.

**The pragma audit target is not currently wired to anything.** It is not a prerequisite of the aggregate validation target, it appears in no continuous integration workflow, and it appears in no commit hook. It runs only when a person types it. Separately, its security-linter portion pipes output into a filter and therefore reports success whether or not findings exist; it exits zero today with fifteen findings outstanding. Adding a new check to that target without addressing either fact would replace a decorative comment with a decorative gate, which is the same defect this feature exists to remove. FR-018 and FR-013 address this directly.

**Scope decision for the reviewer: this feature edits a required status check.** The original request was to rewrite one expression, delete a dead comment, and extend the pragma audit target. FR-018 grows that into adding a step to the `Lint` job, which is one of the four contexts branch protection requires on `main`. The growth follows from the fact above rather than from ambition: the pragma audit target is invoked by nothing, so a check placed only there enforces nothing, and FR-008 through FR-015 would all be satisfiable by an object with the same enforcement power as the comment being deleted. It is stated here so a reviewer accepts or rejects it deliberately instead of meeting it in a diff. If it is rejected, FR-018, FR-019, SC-011, and SC-012 fall with it, US3 reduces to its first five scenarios, and the feature keeps only its informational outcomes. That trade belongs to the reviewer, not to the implementer.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Security reviewer sees a genuinely clean alert list (Priority: P1)

A reviewer opens the repository code scanning list to judge whether the codebase is clean. Today alert 147 sits there at high severity with a suppression comment next to it, so the reviewer cannot tell whether it is handled, ignored, or forgotten. After this change the alert is closed at the branch level and the list reflects reality.

**Why this priority**: This is the reason the work exists. A high-severity alert that has been open for six months is either a real finding or noise that is training people to ignore the list. Both outcomes are bad, and only closing it resolves the ambiguity. Note that no merge is gated on this outcome, so the value is review honesty rather than enforcement.

**Independent Test**: Query the alert state directly from the alert-state API against the branch analysis and confirm no open alert carries the `py/bad-tag-filter` rule at the diagram script's path. Key on path plus rule, not on the number 147, per SC-001. This is verifiable without touching any other part of the feature. The branch analysis only refreshes after the change is on the default branch, so this test is necessarily performed after merge, not before it. See FR-022.

**Acceptance Scenarios**:

1. **Given** an open `py/bad-tag-filter` alert against `scripts/regenerate-mermaid-url.py:82` (numbered 147 today), **When** the arrow check is rewritten without a regular expression literal, **Then** the branch analysis for `refs/heads/main` reports **no open alert whose rule is `py/bad-tag-filter` at that path**. Keyed on path plus rule identifier, never on the number, for the reason recorded in SC-001: remediation demonstrably closes a number and opens a fresh one at the same site, so a **Then** clause written against `147` can be satisfied while the same finding sits there under a new number.
2. **Given** the rewritten arrow check, **When** the diagram validator runs against Mermaid source that ends a line with an arrow and no target, **Then** it still reports "Arrow without target node" exactly as before.
3. **Given** the rewritten arrow check, **When** the validator runs against every input in the differential test corpus, **Then** its verdict matches the previous implementation on every input with zero mismatches.
4. **Given** the sibling thick-arrow check on the following line, **When** this change lands, **Then** that line is untouched and remains free of any alert.

---

### User Story 2 - Maintainer is not misled by a comment that does nothing (Priority: P2)

A maintainer reading the diagram script sees a suppression comment and an explanatory note claiming the finding is a false positive. Both suggest somebody assessed and handled this. Neither is true in any operational sense, because the suppression form has no effect on the scanning pipeline. After this change the misleading comments are gone rather than replaced with a different inert marker.

**Why this priority**: Independent of whether the alert closes, a comment that claims to suppress something it cannot suppress is worse than no comment. It cost this repository six months of a stale high-severity alert. It ranks below P1 only because the alert closure is the outcome people are actually waiting on.

**Independent Test**: Scan the audited source directories for inline scanning-suppression comments and confirm none remain outside the auditor that implements the check. The scan is scoped to source, not to the whole tree, because specification and review prose necessarily quotes the marker strings in order to describe them.

**Acceptance Scenarios**:

1. **Given** the `# lgtm[py/bad-tag-filter]` comment on the flagged line, **When** this change lands, **Then** that comment is deleted and is not replaced by a `# codeql[...]` comment or any other inline suppression form.
2. **Given** the adjacent comment describing the finding as a false positive, **When** the regular expression it refers to no longer exists, **Then** that comment is removed or rewritten so it does not describe code that is gone.
3. **Given** the audited source directories, **When** they are scanned for `lgtm[` and `codeql[` markers, **Then** the only matches are inside the auditor implementation and its own tests. Documentation and specification files are out of this scan's scope by design, since describing the markers requires writing them.

---

### User Story 3 - The gate catches the next dead suppression automatically (Priority: P3)

Somebody adds an inline scanning-suppression comment believing it will silence a finding. Today nothing objects and the repository accumulates another decorative marker plus a permanently open alert. After this change the pragma audit fails on that comment and explains why the form does not work.

**Why this priority**: This is the durable part of the fix and the reason the same defect will not recur. It is P3 only because it prevents future instances rather than resolving the current one.

**Independent Test**: Introduce a throwaway file carrying an inline suppression comment, run the pragma audit, and confirm it fails and names the file, line, and offending marker. Remove the file and confirm the audit passes. Then confirm the same check is reachable from a merge-blocking context, because a check reachable only by typing a command by hand prevents nothing.

**Acceptance Scenarios**:

1. **Given** a file anywhere in the audited paths carrying a `# lgtm[...]` comment, **When** the pragma audit runs, **Then** it exits non-zero and identifies the file, the line number, and the marker.
2. **Given** the same situation with a `# codeql[...]` comment, **When** the pragma audit runs, **Then** it also exits non-zero, because that form is honoured only by a CLI path this repository does not use.
3. **Given** the repository as it stands immediately after this feature lands, **When** the pragma audit runs, **Then** it exits zero, so the new gate does not block anybody on the day it is introduced.
4. **Given** the audited path set, **When** the pragma audit runs, **Then** it covers the diagram script's directory in addition to the two directories it covers today.
5. **Given** the auditor's own source, which necessarily contains the literal marker strings it searches for, **When** the pragma audit runs, **Then** the auditor does not flag itself.
6. **Given** a pull request that adds an inline suppression marker to a source file, **When** the required checks run on that pull request, **Then** at least one required check reports failure. Without this scenario the preceding five are satisfied by a target nothing invokes.

---

### Edge Cases

- **Exotic line separators.** The obvious string-method rewrite splits input into lines using the general line-splitting behaviour, which treats vertical tab, form feed, carriage return, and several Unicode separators as line breaks. The original expression treated only the newline character as a line break. On input such as an arrow followed by a bare carriage return and more text, the two disagree: the general form reports an error where the original did not. The rewrite MUST split on the newline character only, so behaviour is preserved exactly. This case is not hypothetical and is covered by FR-003.
- **Carriage-return line endings.** Diagram source saved with CRLF endings must produce the same verdict as the same source with LF endings, and the same verdict the original produced.
- **Empty and whitespace-only input.** Empty diagram source, source that is only whitespace, and source ending in several blank lines must all produce no arrow error, matching current behaviour.
- **Trailing whitespace after an arrow.** An arrow followed by spaces or tabs to end of line must still be reported as an error.
- **The trailing-whitespace character class.** This is the same trap as the line-separator case, one level down, and it is easy to miss because the line-separator case gets all the attention. The original expression's trailing-whitespace match accepts the full whitespace class, which includes vertical tab, form feed, and non-breaking space. A rewrite that trims only spaces and tabs disagrees with the original on an arrow followed by any of those characters. The rewrite MUST trim the full whitespace class. This was verified during review: the language's default trimming behaviour and the expression's whitespace class agree on every code point checked, so the default is correct and a narrowed trim set is not. Covered by FR-003.
- **Arrow that is not at end of line.** An arrow with a target after it must not be reported, including when a later line does end with a bare arrow.
- **Suppression markers in non-code positions.** A marker appearing inside a documentation string, a URL, or prose is not a real suppression. The audit must not produce noise that pushes people toward blanket exclusions. See FR-009 and the assumption on comment-position matching.
- **Markers in specification and review prose.** Any document that describes this feature has to quote the marker strings in order to name them. This specification alone contains fifteen occurrences across both markers, and its plan, tasks, and review artefacts will add more. A scan defined as repository-wide can therefore never come back clean, no matter how the code is written. The audited path set is source directories only, and every criterion that counts markers is scoped to that set rather than to the tree. Covered by FR-021 and SC-004.
- **The auditor's own test fixtures.** The negative test required by SC-006 has to materialise a file carrying a real marker in order to prove the check fires. If that fixture is written to a path inside the audited set and left there, the audit fails permanently; if it is excluded by a broad pattern, the exclusion becomes a hole a real suppression can hide in. The fixture must exist only for the duration of the test.
- **The auditor matching itself.** Any implementation of the marker check contains the marker strings verbatim. Without explicit self-exclusion the gate fails permanently the moment it is introduced. This is the same trap the existing banned-terms scanner already solves by excluding its own filename.
- **Pre-existing findings surfaced by the widened path set.** Widening the scanned paths can reveal findings that predate the change. A gate that fails the moment it lands blocks every contributor. FR-010 through FR-013 resolve this explicitly.
- **Alert reopening, for the third time.** This alert has already made one full round trip. A change in January deleted the expression and closed it; a change eleven days later re-added the expression "with proper lgtm suppression comment" and reopened it. The second author believed they were handling the finding. Because the analyzer flags this construct on lexical resemblance, any future edit that reintroduces an arrow-like literal into an expression reopens the alert, and the regression test required by FR-004 does not prevent that, since a regular expression and a string rewrite both satisfy the same behavioural tests. The marker gate blocks only the dead-suppression response, not the reintroduction itself. FR-020 addresses the reintroduction with the cheapest thing that has any chance of working: a note on the line telling the next author why it is written the way it is.

## Requirements *(mandatory)*

### Functional Requirements

#### Closing the alert

- **FR-001**: The arrow-without-target validation MUST produce an identical verdict to the current implementation for all diagram source inputs, demonstrated by a differential test rather than asserted.
- **FR-002**: The arrow-without-target validation MUST NOT be expressed as a regular expression pattern, so the analyzer has no pattern to evaluate. The sibling thick-arrow check MUST be left unchanged, since it carries no alert and serves as the control that proves the finding is driven by lexical resemblance.
- **FR-003**: The replacement MUST treat only the newline character as a line boundary, and MUST match trailing whitespace using the full whitespace character class rather than a narrowed set such as spaces and tabs. General-purpose line splitting is prohibited here because it recognises additional separators and changes the verdict on those inputs. Narrowing the trailing-whitespace class is prohibited for the same reason one level down. Both halves of this requirement are load-bearing and both were falsified empirically before being written, not assumed.
- **FR-004**: A regression test MUST cover the arrow-without-target validation, including the trailing-whitespace, empty-input, multi-line, and carriage-return cases named in Edge Cases, so a future rewrite cannot silently change behaviour. That test MUST be placed where the repository's required test check collects it. A test that lives beside the script but outside the collected test root runs nowhere and protects nothing, and the diagram script has no existing test suite to inherit this from.

#### Removing the dead suppression

- **FR-005**: The `# lgtm[...]` comment on the flagged line MUST be deleted. It MUST NOT be converted to `# codeql[...]` or any other inline suppression form, because no inline form is honoured by the scanning pipeline this repository runs.
- **FR-006**: The adjacent explanatory comment that describes the flagged expression as a false positive MUST be removed or rewritten, so no comment describes code that no longer exists.
- **FR-007**: If a finding genuinely warrants suppression in future, the supported route is the scanning product's own dismissal workflow, recorded with a reason. The specification records this so the deletion is not read as "suppression is forbidden", only as "this inline form does not work".

#### Extending the pragma audit

- **FR-008**: The pragma audit MUST detect inline `lgtm[...]` and `codeql[...]` suppression comments and MUST fail when any is present, treating them as unsupported and inert.
- **FR-009**: The marker detection MUST NOT flag the auditor's own implementation or its tests, which necessarily contain the marker strings. Self-exclusion MUST be explicit and narrow, scoped to the auditor's own files rather than achieved by broad path or pattern exclusions, and MUST be expressed as an exact path rather than a bare filename pattern that would silently exempt any identically named file anywhere in the tree.
- **FR-009a**: The marker detection MUST live in a dedicated file of its own rather than inline in the build recipe. Two reasons, both concrete. Self-exclusion by path is only narrow if there is a small file to exclude; excluding the build recipe wholesale would exempt the one file every contributor edits. And the check has to be invocable from the merge-blocking context required by FR-018 without dragging the rest of the audit target's tooling in with it, which the existing precedent in this repository already does for the same reason.
- **FR-010**: The audited path set MUST include the directory containing the diagram script, in addition to the two directories audited today. The current path set is why this defect went unnoticed for six months: the affected file was never scanned.
- **FR-011**: The unused-pragma check MUST remain a blocking check and MUST apply to the widened path set. This is safe to make blocking immediately, because the widened path set currently reports clean.
- **FR-012**: The security-linter portion of the audit MUST remain advisory and MUST NOT gain blocking behaviour as a side effect of widening its path set. It reports findings for human attention and does not fail the build today, and this feature does not change that contract.
- **FR-013**: The audit recipe MUST make each check's blocking or advisory status explicit and intentional, and that declaration MUST be accurate rather than aspirational. Today the advisory behaviour of the security-linter portion is an accident of how its output is piped, which means a routine edit to that line could silently turn it into a blocking gate carrying pre-existing findings. It also means the target as a whole reports success unconditionally on that half. Verified during review: the target exits zero with fifteen findings outstanding.
- **FR-014**: When the audit fails, its output MUST name the offending file, the line number, and the marker found, and MUST state both why the form is inert and what the supported alternative is. A failure that only says "found a bad comment" will be worked around rather than fixed.
- **FR-015**: The pragma audit MUST exit zero against the repository as it stands immediately after this feature lands, so the gate does not block contributors on introduction. That cleanliness MUST be re-verified against the exact tree being merged, immediately before the blocking behaviour lands, and not inferred from a measurement taken during planning. The widened unused-pragma path set is clean today, but this worktree is shared with concurrent work and a single `# noqa` arriving in the newly audited directory between planning and merge converts FR-011 into a day-one failure for everybody who runs the target.

#### Making the gate real

- **FR-018**: The marker detection MUST execute in a context that can fail a merge. Today the pragma audit target satisfies none of the three ways that could happen: it is not a prerequisite of the aggregate validation target, it appears in no continuous integration workflow, and it appears in no commit hook. It runs only when a person chooses to type it. Satisfying FR-008 through FR-015 while leaving that unchanged produces a check that has never once run against a change that was about to land, which is the same category of object as the comment this feature is deleting. This repository already has a precedent for exactly this problem and its resolution: an earlier guard was deliberately placed inside a required check rather than a commit-hook job, with an in-file note explaining that moving it would silently downgrade it to advisory with no symptom until a violation merged green. The same reasoning applies here and the same placement is expected.
- **FR-019**: The wiring required by FR-018 MUST NOT introduce new tooling installation into the merge-blocking context. The check is a text scan over source files; it requires nothing that is not already available where it will run. This constraint exists so that satisfying FR-018 cannot be argued down on the grounds that it slows the required checks or adds a dependency.
- **FR-020**: The rewritten arrow check MUST carry a short note stating that it is deliberately not a pattern match and why. The behavioural regression test required by FR-004 cannot enforce this, because a pattern-based implementation passes exactly the same tests. This alert has already made one full round trip through delete and reintroduce, and the reintroduction was performed by somebody who believed they were handling the finding properly. The note is the only thing in this feature that speaks to the author of the third round trip.
- **FR-021**: Every requirement and criterion that counts marker occurrences MUST be scoped to the audited source path set, never to the whole tree. Specification, planning, and review documents necessarily quote the markers in order to describe them, so a tree-wide count can never reach zero and any criterion phrased that way is unsatisfiable on the day it is written.

#### Verifying closure

- **FR-016**: Closure of alert 147 MUST be evidenced from the branch-level analysis or the alert-state API. A green pull request check MUST NOT be accepted as evidence, because pull request analysis is diff-informed and covers only changed lines. A recent pull request in this repository passed its scanning check with five alerts open.
- **FR-017**: The change MUST NOT increase the total count of open alerts. The rewrite is verified not to introduce a new finding in place of the old one.
- **FR-022**: The closure evidence required by FR-016 MUST be gathered after the change reaches the default branch, and the specification MUST name the outcome if it fails there. The branch analysis does not refresh until the change is on the branch, and no scanning result is a required check, so there is no point before merge at which closure can be confirmed and no check that would hold the merge if it were not. If the alert remains open after merge, the response is a follow-up change to the same line, not a revert, because the rewrite is behaviour-preserving by FR-001 and reverting would restore a pattern for no gain.

### Key Entities

- **The `py/bad-tag-filter` finding at `scripts/regenerate-mermaid-url.py`**: the open high-severity alert this feature exists to close, numbered 147 at the time of writing. **Its identity is path plus rule identifier.** The number is a locating label with a shorter life than the finding: remediation closes a number and opens a fresh one at the same site, so anything that treats the number as the identity can report success over a finding that never moved. Its state on the branch analysis, read that way, is the feature's primary outcome measure.
- **Inline suppression marker**: A source comment of the form `lgtm[rule]` or `codeql[rule]`. Has no effect on this repository's scanning pipeline. The audit's job is to make its presence a failure rather than a silent no-op.
- **Pragma audit path set**: The set of directories the audit walks. Currently excludes the directory holding the affected file, which is the root cause of the six-month blind spot.
- **Audit check**: A single check within the audit, carrying an explicit blocking or advisory status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When the alert-state API is queried against the branch analysis after the change is on the default branch, **no open alert exists with the `py/bad-tag-filter` rule at the diagram script's path**, and the query output is recorded as the evidence. The criterion is keyed on path plus rule identifier, never on the alert number: remediation demonstrably closes a number and opens a fresh one at the same site, so a criterion written against `147` can report success while the same finding sits there under a new number. The number is a label for locating the finding today, not the thing being measured. This criterion is measured after merge, not before it, and no required check enforces it.
- **SC-002**: The count of open alerts after this change is exactly one lower than the count before, confirming both that alert 147 closed and that nothing new was introduced. A criterion phrased as less than or equal would be satisfied by the change achieving nothing at all.
- **SC-003**: A differential test comparing old and new arrow validation over a corpus of at least 1,500 generated and hand-chosen inputs reports zero mismatches. The corpus includes arrows with trailing whitespace, arrows at end of input, multi-line input, empty input, CRLF endings, the exotic line separators named in Edge Cases, and the non-newline whitespace characters named in the trailing-whitespace-class edge case. An 8,057-input differential run during review reported zero mismatches for the newline-only split and 385 mismatches for the general-purpose split, so the corpus is known to be capable of separating a correct implementation from the obvious incorrect one.
- **SC-004**: A scan of the audited source path set for `lgtm[` and `codeql[` markers returns matches only inside the auditor implementation and its tests. Before this change the same scan returns one match, in the diagram script. The scan is deliberately not tree-wide: this specification alone contains fifteen marker occurrences because describing a marker requires writing it, and a tree-wide criterion would be false at the moment of writing.
- **SC-005**: The pragma audit exits zero against the post-change tree.
- **SC-006**: The pragma audit exits non-zero when a file carrying an inline suppression marker is added, and its output names that file and line. This negative test is automated, not performed by hand once.
- **SC-007**: The pragma audit's unused-pragma check runs against the widened path set and passes.
- **SC-008**: The audit recipe declares a blocking or advisory status for every check it runs, verifiable by reading the recipe without inferring behaviour from shell pipeline semantics.
- **SC-009**: The repository's unit test suite passes, including the net-new regression test required by FR-004. The diagram script has no pre-existing test suite of its own, so there is nothing there to pass unchanged and the FR-004 test is the first coverage the script has ever had. Any criterion asserting an existing suite for this script would be unmeasurable.
- **SC-010**: The thick-arrow sibling check is byte-identical to its pre-change form, confirming the control was not disturbed.
- **SC-011**: A change that adds an inline suppression marker to a source file causes at least one required status check to report failure. Measured by observing the check result, not by reasoning about the recipe. Without this, SC-005 through SC-008 are all satisfiable by a target that no automated process invokes, and the feature ships a gate with the same enforcement power as the comment it removes: none.
- **SC-012**: The marker check is reachable from the merge-blocking context without installing tooling that is not already present there, so wiring it costs no additional setup time in the required checks.

## Assumptions

- **Advisory findings stay advisory, and there are ten of them.** Widening the security-linter path set surfaces pre-existing findings in the newly scanned directory. The count was measured during review: ten, on top of the fifteen already reported for the existing path set. Because that check does not fail the build today, all twenty-five print for attention and block nobody. Anybody running the target after this lands sees a longer wall of output than before and should not read it as a regression. This feature deliberately does not convert them into a blocking gate, and does not fix them. Making that check blocking, with its existing backlog, is a separate decision with a separate cost.
- **The unused-pragma check can be blocking immediately.** The widened path set was checked during review and reports clean under the full configured rule set, not merely under the unused-pragma rule in isolation, so no grandfathering mechanism, baseline file, or allowlist is needed for it. If that assumption fails at implementation time, the fallback is to fix the findings rather than to introduce a baseline, since the count is small.
- **"Blocking" and "runs" are different properties, and the audit target has only the first.** The unused-pragma check does fail the target when it finds something. The target is invoked by nothing automated, so that failure has never once reached a change under review. This is stated separately because the phrase "blocking check" appears throughout the requirements above and would otherwise be read as meaning enforced. It means enforced only once FR-018 is satisfied.
- **Marker matching is positional.** Detection targets markers appearing in comment position rather than anywhere in a line, to avoid flagging prose and URLs. If the implementation cannot do this reliably, the simpler whole-line match is acceptable given the current match count in the audited path set is one, but the noise risk moves to Edge Cases as a known limitation. Either way the path set is source only, so the largest source of prose false positives, the specification tree, is out of range before the positional question is even reached.
- **No supported inline suppression exists here.** The audit treats every inline suppression form as inert. If the scanning configuration later adopts a path where an inline form is honoured, this gate becomes wrong and must be revisited. The scanning setup is driven by a configuration file rather than a workflow this repository maintains, so that change could arrive without a visible diff in this repository at all.
- **The rewrite closes the alert.** This is strongly evidenced rather than certain: a prior change that deleted the same expression closed this same alert, and the analyzer's own message complains specifically about the pattern's handling of comment-end syntax. Confirmation comes from SC-001 and arrives only after merge, per FR-022. The diff-scoped pull request analysis is corroborating rather than sufficient here, and is never accepted as the evidence FR-016 requires, even though the change touches the exact flagged line.

## Out of Scope

- Fixing the pre-existing advisory security-linter findings in any directory, including those newly surfaced by the widened path set.
- Converting the advisory security-linter check into a blocking gate.
- The four other open alerts in this repository.
- Any change to the diagram script beyond the flagged arrow check and its comments, including the thick-arrow check, which is the control.
- Retiring or replacing the security linter itself.
- Changing the scanning workflow configuration, its query pack selection, or its trigger conditions.
- Adopting a dismissal workflow for any current finding.
- Adding the scanning analysis to the branch protection required checks. This would give SC-001 real enforcement, but it is a branch protection change affecting every contributor and carrying the existing open-alert backlog. Out of scope, carded.
- Wiring the pragma audit target as a whole into the aggregate validation target or the required checks. FR-018 requires only the marker check to reach a merge-blocking context, not the target's other halves, because the security-linter half carries a twenty-five finding backlog and the aggregate validation target has its own pre-existing failure. Out of scope, carded.
- Repairing the pre-existing failure in the banned-term scanner, which makes the aggregate validation target red on the default branch today and is one reason nobody noticed the pragma audit was missing from it. Unrelated to this feature. Out of scope, carded.
- Reconciling the scanning configuration file's internal contradiction, where a path exclusion for the test tree is followed by a query filter whose comment states the test tree is still scanned. One of the two is redundant. Out of scope, carded.

## Adversarial Review #1

Reviewer did not author the spec. Every claim below was reproduced locally before being written down. Nothing was taken from the prior agent's notes on trust.

### Findings

| Sev | Finding | Resolution |
|---|---|---|
| CRITICAL | F1: The pragma audit target is invoked by nothing automated. It is absent from the aggregate validation target's prerequisite list, absent from every continuous integration workflow, and absent from the commit hook configuration. Separately its security-linter half pipes into a filter and reports success unconditionally: verified exit zero with fifteen findings outstanding. US3 and FR-008 through FR-015 therefore specified a gate with the same enforcement power as the comment being deleted. | FIXED. New FR-018 requires the marker check to execute in a merge-blocking context, citing the in-repository precedent where an earlier guard was deliberately placed in a required check for exactly this reason. New FR-019 forbids that wiring from adding tooling installation, removing the usual argument against it. New US3 scenario 6, new SC-011 and SC-012 measure it by observed check result rather than by reading the recipe. New assumption separates "blocking" from "runs". Overview states both facts up front. |
| HIGH | F2: SC-004 was already false when written. A tree-wide scan for the two markers returns fifteen matches inside this specification file alone, because naming a marker requires writing it. Plan, tasks, and this review add more. The criterion could never reach its stated state. | FIXED. SC-004, US2 independent test, and US2 scenario 3 rescoped to the audited source path set. New FR-021 makes the scoping rule general so the next criterion is not written the same way. New edge case records the cause. |
| HIGH | F3: SC-009 required "the diagram script's own test suite" to pass unchanged. No such suite exists. There is no test file anywhere referencing the script. The criterion was unmeasurable and it concealed that FR-004's regression test is net-new, with no established home. | FIXED. SC-009 rewritten to state the script has no prior coverage. FR-004 extended to require the new test live where the required test check collects it, since the collected test root is configured and a test outside it runs nowhere. |
| HIGH | F4: Closure evidence is obtainable only after merge, and no scanning result is a required check. SC-001 could not gate anything and the spec did not say so, nor what happens if the alert stays open post-merge. | FIXED. New FR-022 states the post-merge timing and names follow-up rather than revert as the failure response, with the reason. SC-001 and US1 amended. Overview states plainly that no scanning result blocks a merge here. |
| HIGH | F5: FR-003 constrained the line-boundary character but said nothing about the trailing-whitespace character class. The original expression accepts the full whitespace class; a rewrite trimming only spaces and tabs diverges on vertical tab, form feed, and non-breaking space. Identical in kind to the defect FR-003 was written to prevent, one level down, and invisible because the line-separator case absorbs all the attention. | FIXED. FR-003 now constrains both. New edge case documents it. SC-003's corpus now required to include those characters. Verified during review that the default trimming behaviour and the expression's whitespace class agree on every code point from U+0000 to U+2FFF, so the default is correct and only a narrowed set is dangerous. |
| HIGH | F6: FR-009's self-exclusion was underspecified. The cited precedent excludes by bare filename, which exempts any identically named file anywhere in the tree. And the spec never said where the check lives; hosted inline in the build recipe, self-exclusion would mean exempting the single file every contributor edits. | FIXED. FR-009 now requires exact-path exclusion rather than a filename pattern. New FR-009a requires the check to live in a dedicated file, with both reasons stated. New edge case covers the negative test's fixture, which must not persist inside the audited set nor be exempted by a broad pattern. |
| MEDIUM | F7: SC-002 read "less than or equal to the count before", which is satisfied by the change accomplishing nothing. | FIXED. Now requires the count to drop by exactly one, with the reason for the change recorded in the criterion. |
| MEDIUM | F8: FR-016 forbade accepting a pull request check as evidence while the closing assumption called the same analysis "meaningful here", which reads as a licence to accept it. | FIXED. Assumption reworded to corroborating rather than sufficient, and cross-referenced to FR-022. |
| MEDIUM | F9: Widening the security-linter path set adds ten pre-existing findings, unquantified in the spec. The target's output roughly doubles and a reader could mistake that for a regression this feature caused. | FIXED. Count measured and recorded in the assumption alongside the existing fifteen. |
| MEDIUM | F10: Nothing prevented a third round trip. FR-004's behavioural test passes identically for a pattern-based and a string-based implementation, so it cannot stop reintroduction. The second round trip was performed by somebody who believed they were handling the finding. | FIXED. New FR-020 requires a short note on the line stating it is deliberately not a pattern match. Edge case rewritten with the full round-trip history and an explicit statement that the regression test does not cover this. |
| LOW | F11: The scanning configuration file excludes the test tree by path and then carries a query filter whose comment asserts the test tree is still scanned. One of the two is dead. | Out of scope, carded in Out of Scope. |
| LOW | F12: The banned-term scanner is red on the default branch today, so the aggregate validation target already fails. Relevant only as the likely reason nobody noticed the pragma audit is not one of its prerequisites. | Out of scope, carded in Out of Scope. |

Counts: 1 CRITICAL, 5 HIGH, 4 MEDIUM, 2 LOW. All CRITICAL and HIGH resolved by direct edit. Both LOW carded without fixing, since fixing either means touching files this feature does not own.

### Verification performed

| Claim under test | Method | Result |
|---|---|---|
| Audit target cannot fail on its security-linter half | Ran the target, captured exit status | Exit 0 with 15 findings printed. Confirmed |
| Audit target is wired into the aggregate validation target | Read the prerequisite list | Absent. Seven prerequisites, none of them the audit |
| Audit target is wired into continuous integration | Searched the workflow tree | Zero occurrences |
| Audit target is wired into commit hooks | Searched the hook configuration | Zero occurrences |
| Unused-pragma check is clean on the widened path set | Ran it against the new directory under the full rule set | Clean. FR-011 assumption holds |
| Security-linter findings in the new directory | Ran it against the new directory | 10 |
| Marker count, tree-wide | Two searches across the tree | 9 for one marker, 7 for the other, 15 of the 16 inside the spec itself |
| The script has an existing test suite | Searched for any file referencing it | None outside specification documents |
| Newline-only split is equivalent to the original expression | Independent differential run, 8,057 inputs | 0 mismatches |
| General-purpose split is not equivalent | Same run, same corpus | 385 mismatches |
| Default trimming matches the expression's whitespace class | Compared both across U+0000 to U+2FFF | 0 divergences |

The differential corpus was built from exhaustive one, two, and three element products over a twenty element atom set containing both arrow forms, the comment-end form the analyzer complains about, spaces, tabs, carriage return, newline, vertical tab, form feed, file separator, next line, and the Unicode line separator, plus three thousand random four to five element strings under a fixed seed, plus fourteen hand-chosen cases. This is an independent construction, not a rerun of the prior corpus. It agrees with the prior result in direction and mechanism: the general-purpose split fails on exotic separators, the newline-only split does not. The mismatch counts differ because this corpus is denser in exotic separators, which is why it produces 385 rather than 23.

### Gate

**0 CRITICAL, 0 HIGH remaining.**

## Clarifications

### Session 2026-07-30

Five questions raised, five self-answered from the codebase, artifacts, and git history. None
deferred and none put to the owner as an open question, though Q1 records a decision the owner
still has to accept or reject at review. Evidence is a file and line, a commit, or the output of a
command that was actually run.

- **Q: This started as "rewrite a regex, delete a comment, extend a make target" and now edits a required status check. Is that recorded as a scope decision the owner can reject, or does it only appear in the diff? → A: It was not recorded. Now stated in the Overview as an explicit scope decision, with what falls if it is rejected.**
  - Evidence that the growth is real: the Input line of this spec (line 6) names only the alert, the dead comment, and `make audit-pragma`. `plan.md:106` and `plan.md:179-204` add a step to `.github/workflows/pr-checks.yml`.
  - Evidence that `Lint` is required: `gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection --jq .required_status_checks.contexts` returns `["Secrets Scan","Lint","Run Tests","Playwright E2E Tests"]`, recorded at `research.md:61-67` and re-asserted in `.pre-commit-config.yaml:214-225`.
  - Evidence that the target is unwired: `Makefile:42` lists seven prerequisites for `validate` and `audit-pragma` is not among them; a repository-wide search for `audit-pragma` outside `specs/` returns only `Makefile:1`, `Makefile:85`, and `CLAUDE.md:243`.
  - Changed: the Overview gained a third bold paragraph. No requirement text changed. FR-018 already carried the technical reasoning; what was missing was the framing that lets a reviewer say no.

- **Q: FR-015 rests on the widened unused-pragma path set being clean. Do the artifacts require re-checking that immediately before the check becomes blocking, or only at planning time? → A: Only at planning time, and at research level. Now a requirement.**
  - Current state re-measured: `ruff check --extend-select RUF100 scripts/` and `ruff check --extend-select RUF100 src/ tests/ scripts/` both print "All checks passed!" and exit 0 (run 2026-07-30 under `.venv`, ruff 0.15.14). `grep -rnE "lgtm\[|codeql\[" src/ tests/ scripts/` returns exactly one line, `scripts/regenerate-mermaid-url.py:82`.
  - The re-check instruction existed only at `research.md:341-350` ("Open items carried forward"), which is a planning note, not a requirement, and is not reproduced in `spec.md` or `quickstart.md`.
  - Changed: FR-015 now requires re-verification against the exact tree being merged. `quickstart.md` section 4 gained the matching step. Scope note: the exposure is `make audit-pragma` only, since the `Lint` job runs `ruff check src/ tests/` (`.github/workflows/pr-checks.yml:61-62`) and never sees `scripts/`, so a stray `# noqa` there cannot redden a required check.

- **Q: The negative test points the checker at `tmp_path`, which is outside the repository. Does the contract's exclusion and output handling survive a root that has no repository-relative path? → A: No. `relative_to` raises, and both C6 and C7 needed the fallback the precedent already uses.**
  - Reproduced: `Path("/tmp/dsfix/bad.py").resolve().relative_to(Path("/home/zeebo/projects/sentiment-analyzer-gsk"))` raises `ValueError: '/tmp/dsfix/bad.py' is not in the subpath of ...`. As written, C6's "skipped if and only if its resolved repository-relative path is a member" would crash the checker on every file the SC-006 negative test creates, and C7's repo-relative output has nothing to print.
  - The precedent already solved this: `scripts/scan-waitforresponse-race.py:418-423` wraps `path.relative_to(root)` in `try/except ValueError` and falls back to the absolute path for display.
  - Changed: `contracts/dead-suppression-cli.md` C6 now specifies a containment test that returns false for out-of-repo paths rather than raising, and C7 specifies the display fallback. No spec requirement changed; SC-006 and the "auditor's own test fixtures" edge case were both unsatisfiable against the contract as written, and are now satisfiable.

- **Q: The plan's `importlib` and `sys.executable` constraints, and the contract's "any CPython 3.13 reachable as python3" line. Spec-level or plan-level, and is the stated reason accurate? → A: Plan-level, both. The reason given was wrong and the contract's interpreter requirement was too strong.**
  - `importlib.util.spec_from_file_location` is forced by the hyphen in `regenerate-mermaid-url.py`, which this feature cannot rename. That is a test mechanic with no observable behaviour attached, so it stays in `plan.md` (Testing plan, "test_regenerate_mermaid_url.py") and needs no requirement.
  - The stated reason for `sys.executable` was "the repository's system interpreter is 3.10" (`plan.md` Testing plan, subprocess-test bullet, and `quickstart.md:10`). Measured on this machine: `/usr/bin/python3` is 3.12.3 and `python3` resolves through `/home/zeebo/.pyenv/shims/python3` to 3.13.0. The conclusion still holds and is in fact stronger, because a bare `python3` resolves differently per machine and per shell. `scripts/scan-waitforresponse-race.py:72-74` already records the same discrepancy in a comment.
  - Contract C1 required "any CPython 3.13 reachable as `python3`". Nothing in the design needs 3.13, and the Makefile consumer runs under whatever `python3` the contributor has, which is demonstrably 3.12 on a stock path here. Changed: C1 now states a 3.9 floor and forbids version-gated syntax. If a runtime interpreter guard is ever added in imitation of the precedent, which exits 2 at `scan-waitforresponse-race.py:75-81`, it MUST NOT reuse exit code 2, because C2 assigns that to "zero files scanned" and the precedent has that collision today.
  - Changed: `plan.md` and `quickstart.md` corrected to the accurate reason. Contract C1 relaxed. No FR or SC changed.

- **Q: Contract C8 forbids reaching the checker through `pre-commit run`, and the plan recommends an optional pre-commit hook. Which is it? → A: Both, once C8 is scoped to the merge-blocking consumer, which is what it was written about.**
  - The prohibition's actual target is the CI step: the `Pre-commit Hooks` job sets `SKIP` and is not a required context, so a required check must never route through it. That reasoning is at `.pre-commit-config.yaml:214-229`.
  - The precedent carries all three wirings simultaneously: a pre-commit hook at `.pre-commit-config.yaml:206-212`, a direct step in the required `Lint` job at `.github/workflows/pr-checks.yml:85-87`, and a `make validate` prerequisite at `Makefile:42` and `Makefile:45-47`. A local hook alongside a direct CI step is the established pattern, not a violation of it.
  - Changed: C8's bullet now says the merge-blocking invocation must not route through `pre-commit run`, and that an additive local hook is permitted. The plan's "optional and recommended" wording at `plan.md:213-217` stands unchanged. No FR or SC changed.

Line references into `plan.md` above point at section headings and quoted phrases where the exact
line could drift; references into repository files were taken with `grep -n` on 2026-07-30.

Also corrected without spending a question, since both are clerical rather than decisions: `plan.md`'s
skip list omitted `.pytest_cache` and `.hypothesis`, which `contracts/dead-suppression-cli.md` C3
lists, and the two are now identical.
