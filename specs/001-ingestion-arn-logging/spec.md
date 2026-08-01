# Feature Specification: Stop Ingestion Handler Logging Secret ARNs

**Feature Branch**: `001-ingestion-arn-logging`
**Created**: 2026-07-30
**Status**: Draft
**Input**: User description: "Stop `src/lambdas/ingestion/handler.py` from writing full AWS Secrets Manager ARNs into CloudWatch logs. Closes CodeQL alerts 148, 149, 150 (`py/clear-text-logging-sensitive-data`) at handler.py lines 264, 271, 276."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnose a missing API key without leaking account topology (Priority: P1)

An on-call engineer sees the ingestion job return no articles. They open the ingestion log group and need to know which upstream credential is unavailable, Tiingo or Finnhub or both. Today the log tells them by printing the full Secrets Manager ARN, which also hands any log reader the AWS account ID, the region, the environment name, the secret path, and the random AWS suffix. The engineer needs the same diagnostic answer without the log carrying that extra topology.

**Why this priority**: This is the actual defect. The disclosure is real and CloudWatch log access is broader than Secrets Manager access. Severity is low and recon grade, not a credential leak, but the fix is cheap.

Precision on blast radius, because the three sites are not equivalent. One site interpolates both ARNs directly into the message string, so it is rendered by any formatter and definitely reaches CloudWatch. The other two attach the ARN as a structured context value rather than putting it in the message text, and whether a structured context value is rendered depends on the formatter active at runtime. The handler configures log levels only and installs no formatter of its own, so the spec does not assert that those two are emitted today. They are still in scope and still must be fixed: the value is passed to the logging call, it is reachable the moment a formatter that serialises structured context is introduced, and the analysis engine flags the flow regardless of rendering.

**Independent Test**: Force each of the three conditions (both adapters unavailable, Tiingo only unavailable, Finnhub only unavailable), capture the emitted log records, and confirm each record still names the affected source while carrying no ARN component in either its rendered message or its structured context.

**Acceptance Scenarios**:

1. **Given** both credentials are unavailable, **When** the ingestion handler runs, **Then** the error record names Tiingo and Finnhub as fixed literal text, and neither its rendered message nor its structured context contains the account identifier, the region, the environment or secret path, the random AWS suffix, or the ARN prefix.
2. **Given** only the Tiingo credential is unavailable, **When** the ingestion handler runs, **Then** the degraded-mode warning still says Tiingo is the unavailable source, and its structured context carries no value derived from the configuration ARN.
3. **Given** only the Finnhub credential is unavailable, **When** the ingestion handler runs, **Then** the degraded-mode warning still says Finnhub is the unavailable source, and its structured context carries no value derived from the configuration ARN.
4. **Given** both credentials are unavailable, **When** the raised failure propagates to the handler's outer exception path, **Then** the record written there still carries no ARN component in message or structured context.

---

### User Story 2 - Prove closure from branch state, not from a PR check (Priority: P2)

A security reviewer needs to confirm that the three flagged sites in `src/lambdas/ingestion/handler.py` are genuinely free of open findings for rule `py/clear-text-logging-sensitive-data`, and to see a written justification for any finding that remains open by decision rather than by oversight.

**Why this priority**: Two separate traps make the naive check wrong.

First, a green CodeQL check on the pull request is not evidence. CodeQL runs diff-informed analysis on pull requests in this repository, so a pull request check only reasons about changed lines. PR #990 was green with all five of its alerts still open. Closure has to be read from the `refs/heads` branch analysis or from the GitHub code scanning alerts API.

Second, and more dangerous, alert numbers are not stable identities. When a flagged line is rewritten, the engine can close the old number as fixed and open a brand new number at the same location in the same run. This is documented in this repository, not hypothetical. Alert 117 on `src/lambdas/shared/auth/oauth_state.py` carries `fixed_at` of `2026-01-20T22:34:56Z`, and alert 144 on the same file was created at that identical timestamp. During the 2025-12-09 remediation of the shared secrets module, alerts 107, 110 and 111 were all created and then closed within hours at lines a remediation attempt had just rewritten. A criterion that asks only whether three specific numbers stopped being open can therefore be fully satisfied while the disclosure sits open under three fresh numbers.

The same trap applies to reading alert `state`. Dismissal is sticky and survives a later genuine fix, so `state` conflates "a human dismissed this" with "the code was repaired". Alerts 26 and 27 read `dismissed` but both carry a non-null `fixed_at`. Alerts 22, 23, 24 and 25 also read `dismissed` and have `fixed_at` null to this day, meaning those four sites were never repaired. `fixed_at` is the load-bearing field, not `state`.

**Independent Test**: After the default branch analysis completes on a commit that includes the change, query the GitHub code scanning alerts API for every alert of this rule whose location path is `src/lambdas/ingestion/handler.py`, in any state, and confirm the set of open ones is empty regardless of alert number.

**Acceptance Scenarios**:

1. **Given** the change has landed on the default branch and its CodeQL analysis has completed on a commit that includes the change, **When** the GitHub code scanning alerts API is queried for all alerts of this rule located in `src/lambdas/ingestion/handler.py`, **Then** no alert at that path is in the open state, whether or not its number is 148, 149 or 150.
2. **Given** alerts 148, 149 or 150 have moved out of the open state, **When** a new alert number for this rule appears at the same path, **Then** the change is classified as not yet successful and the new alert is worked as a survivor, not treated as an unrelated finding.
3. **Given** an alert for this rule at this path ends in the dismissed state, **When** its GitHub dismissal record is read, **Then** it carries a justification that names the value logged, the convention applied, and why CodeQL still reports it.
4. **Given** only the pull request CodeQL check is green, **When** closure is claimed on that basis alone, **Then** the claim is rejected as insufficient evidence.
5. **Given** a claim that the site was repaired, **When** the evidence offered is an alert reading `dismissed` or `closed`, **Then** the claim is rejected unless that alert also carries a non-null `fixed_at` dated at or after the change.

---

### User Story 3 - Leave a convention the next feature can reuse (Priority: P3)

The next feature working CodeQL rule `py/clear-text-logging-sensitive-data`, namely `001-oauth-provider-taint`, needs a single written convention to follow instead of re-deriving one. This repository already carries seven dismissals of this rule, and their reasoning lives only in GitHub dismissal comments.

**Why this priority**: Value is real but deferred. The fix stands on its own without it. Skipping it means the next feature repeats the same investigation.

**Independent Test**: A reader who has never seen this feature can find, in one place, the decision rule for when to rewrite the log site and when to dismiss, plus the wording pattern for the dismissal.

**Acceptance Scenarios**:

1. **Given** a new site is flagged by `py/clear-text-logging-sensitive-data`, **When** an engineer consults the recorded convention, **Then** it tells them which code shape to attempt first and what to do if the alert survives.

---

### Edge Cases

- The configuration value is a bare secret name or a slash separated path rather than an ARN, which happens in local and development setups. Because the corrected design derives nothing from the configuration value for logging purposes, the log output is identical in that case and no shape handling is required. This edge case is closed by the design, not handled at runtime.
- The configuration value is absent entirely. Configuration loading already fails earlier in that case, so the log sites must not be written as though a well formed ARN is guaranteed. Again, the corrected design does not read the value at these sites at all.
- Only one of the two sources is degraded. Both single source paths must remain distinguishable in the logs.
- Line numbers shift as the file changes, so CodeQL may report a finding at a new line for the same site. Verification must key on the file path and the rule id, not on the line number.
- **CodeQL closes 148, 149 and 150 and opens fresh numbers at the same file.** This is the failure mode most likely to produce a false claim of success, and it is documented in this repository (alert 117 closing and alert 144 opening at the same timestamp on the same file; alerts 107, 110 and 111 spawning during the 2025-12-09 secrets remediation). It counts as not yet successful.
- **The default branch analysis has not re-run, or the result predates the change.** A result whose commit does not include the change decides nothing. Classification must wait.
- **A test asserts on rendered log text only.** Structured context values attached to a logging call are not rendered into the formatted message under the default formatter, so an assertion that only inspects rendered text passes today against two of the three unfixed sites. Any test written that way is a false negative and does not satisfy FR-007.
- **The dismissal step cannot be performed by the implementing agent.** Permission to dismiss may be absent. The feature must have a defined terminal state in that case rather than hanging indefinitely.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ingestion handler MUST NOT write a full Secrets Manager ARN, or any of its account identifier, region, environment path, secret path or random suffix components, into any log record. This covers both the rendered message and the structured context attached to the logging call, since the second is a sink whether or not the active formatter renders it.
- **FR-002**: Each affected log record MUST still identify which upstream source is unavailable, using fixed literal text chosen at the call site. The two degraded mode warnings already carry literal source names and MUST keep them. The both keys missing error currently identifies the sources only through the interpolated configuration key names, so it MUST be reworded to name Tiingo and Finnhub as literal text. Deriving the source label from the configuration value in any way is prohibited by FR-004.
- **FR-003**: No new sanitizing helper may be introduced, and the repository's existing ARN to bare name convention MUST NOT be called from any of the three sites. The source identity at these sites is statically known at the call site, unlike the shared secrets module where the identifier arrives as a runtime argument, so no sanitizing is required to satisfy FR-002. A sanitized value is still a value derived from the ARN and is therefore prohibited by FR-004; this is precisely the shape that failed in the `0e7a375` precedent below.
- **FR-004**: No value derived from the configuration ARN may appear in the log message, in the structured context, or in the raised exception message. This is stricter than the closest precedent, which retained a sanitized name in the exception message only because the identifier there was a runtime argument. Here nothing is lost by dropping it entirely, and dropping it removes the taint flow at its source. The two commits that establish the precedent: `0e7a375` (PR #321, 2025-12-09) tried breaking the taint flow with an intermediate sanitized variable and CodeQL still flagged it, then `ebcc2f4` (PR #322, 2025-12-09) removed every secret derived value from the log context. Read the evidence via the `fixed_at` field, not via `state`, because dismissal is sticky and survives a later genuine repair: the two sites rewritten to drop the value from the log context are alerts 26 and 27, which both carry a non-null `fixed_at` despite still reading `dismissed`, whereas the four sanitize in place sites are alerts 22, 23, 24 and 25, whose `fixed_at` is null to this day.
- **FR-005**: The failure raised when both credentials are missing MUST NOT reintroduce the ARN into logs through any downstream handler, including the outer exception path. Since FR-004 keeps the ARN out of the exception message entirely, this holds regardless of what a downstream handler chooses to log.
- **FR-006**: Runtime behaviour MUST be otherwise unchanged, scoped precisely as: the same conditions trigger the same log levels at the same three sites, the same exception type is raised from the same branch, and the same response is returned. The text of the messages themselves is explicitly permitted to change, and FR-002 requires it to change on the both keys missing path. FR-006 does not override FR-002.
- **FR-007**: Automated tests MUST cover all three paths by capturing emitted log records and asserting, for each record, that no ARN component appears in either the rendered message or the record's structured context attributes. Asserting only on rendered text is insufficient and MUST NOT be accepted: structured context values are not rendered into the formatted message under the default formatter, so such a test passes today against two of the three unfixed sites and proves nothing. The forbidden strings MUST be enumerated rather than represented by a single marker: the full ARN fixture value, the ARN prefix, the account identifier alone, the region alone, and the environment or secret path segment alone. An assertion on the ARN prefix alone would pass while the account identifier leaks by itself. The test module's own environment fixture MUST additionally keep every enumerated string unique to the two secret ARNs: no other environment value the fixture sets, in particular `SNS_TOPIC_ARN`, `ALERT_TOPIC_ARN` and `AWS_REGION`, may contain the account identifier, the region or the path segment being asserted. Without that isolation a record that legitimately carries one of those unrelated values fails the assertion for the wrong reason, and a passing assertion stops being evidence about the ARN. See Clarification Q3.
- **FR-008**: If any alert for `py/clear-text-logging-sensitive-data` remains open at `src/lambdas/ingestion/handler.py` after the code change and after a completed default branch analysis, that alert MUST be dismissed in GitHub as a false positive with a written justification, and MUST NOT be left open and unexplained. This applies to any alert number at that path, not only to 148, 149 and 150.
- **FR-008a**: If the implementing agent lacks permission to dismiss, the feature MUST reach the defined terminal state `BLOCKED-ON-OWNER` rather than remaining indefinitely incomplete. Reaching that state requires delivering, in this feature's directory, a handoff artifact containing the exact alert numbers observed at the path, the exact dismissal justification text for each, and the exact API call or UI steps needed to apply them. The code change is independently complete and mergeable at that point; only the dismissal is outstanding. A feature blocked this way MUST NOT be reported as done, and MUST NOT be reported as failed. Whether the permission is present MUST be determined by a read-only capability probe before any dismissal is attempted, never by attempting a dismissal and observing the result: a dismissal that succeeds cannot be cleanly undone and would itself mutate alert state. The probe is the token's scope list read together with the repository's visibility and the actor's repository permissions. See Clarification Q2.
- **FR-008b**: The feature MUST also have a defined terminal state for the case where the code change is complete and locally verified but no default-branch CodeQL analysis containing the change exists yet, which is the normal state at the end of implementation because SC-002 and SC-002a are only evaluable after the change reaches the default branch. That state is `PENDING-BRANCH-ANALYSIS`. Reaching it requires the code change and the FR-007 tests to be complete and green, and requires the exact verification query from the plan to be recorded so the check is mechanical when the analysis lands. Like `BLOCKED-ON-OWNER`, it MUST NOT be reported as done and MUST NOT be reported as failed. It is distinct from `BLOCKED-ON-OWNER`, which is about permission to dismiss a survivor that has already been observed.
- **FR-009**: Each dismissal justification MUST state three things: that the logged value is a resource identifier and not a credential value, which convention is applied, and why CodeQL still reports the flow. The first two elements match the wording on the seven existing dismissals of this rule in the repository; the third element is new and is deliberately stronger, because none of the existing seven states it and their silence on that point is what made them impossible to re-evaluate later.
- **FR-010**: All three sites MUST carry an inline comment naming the rule id `py/clear-text-logging-sensitive-data` and the reason the value was removed, regardless of whether the resulting alerts end fixed or dismissed. Restricting the comment to dismissed sites would leave the successful path unmarked and let a later refactor silently reintroduce the interpolation.
- **FR-011**: The wording pattern used for the dismissal justification, together with the decision rule for when to rewrite versus when to dismiss and the `fixed_at` versus `state` caveat, MUST be recorded in this feature's artifacts so `001-oauth-provider-taint`, which works the same CodeQL rule, can cite it instead of inventing its own.
- **FR-012**: No new cloud resources may be introduced, and the handler's existing logging mechanism is retained. No logging framework migration, no new filter or formatter.
- **FR-013**: No file outside `src/lambdas/ingestion/handler.py`, its tests, and this feature's own `specs/001-ingestion-arn-logging/` directory may be modified. The directory carve-out is explicit because FR-011 and SC-006 require a convention artifact there and FR-008a requires a handoff artifact there, and a literal reading of the earlier wording forbade writing either. Nothing in the carve-out relaxes the prohibition on source, test, infrastructure or documentation files elsewhere in the repository. See Clarification Q4. In particular `src/lambdas/shared/secrets.py` MUST NOT be edited. Four dismissed alerts (22 through 25) sit on lines in that file whose `fixed_at` is null, meaning the findings are still live behind a dismissal. Editing those lines risks re-fingerprinting them into fresh open alerts, which is exactly what happened to that file on 2025-12-09, and would breach SC-005.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across all three failure paths, zero captured log records contain any of the enumerated forbidden strings from FR-007, checked against both the rendered message and the record's structured context attributes. The enumeration is the operative part: a check for the ARN prefix alone is not sufficient evidence for this criterion.
- **SC-002**: The count of open alerts for rule `py/clear-text-logging-sensitive-data` whose location path is `src/lambdas/ingestion/handler.py` is zero, read from the `refs/heads` default branch CodeQL analysis or the GitHub code scanning alerts API after an analysis whose commit includes the change has completed. This criterion is keyed to the path and the rule, never to the numbers 148, 149 and 150, because the engine can close those three and open fresh numbers at the same path in the same run. A passing pull request CodeQL check is explicitly not accepted as evidence, because CodeQL runs diff-informed analysis on pull requests and PR #990 was green with five alerts open. The one useful inverse: because this change edits the exact lines flagged today, the diff scoped pull request result is directly informative here, and an alert that survives it is a genuine survivor.
- **SC-002a**: For each of alerts 148, 149 and 150 that is reported as repaired rather than dismissed, `fixed_at` is non-null and dated at or after the change. A `state` of `dismissed` or `closed` with a null `fixed_at` does not satisfy this criterion, because dismissal is sticky and can mask a site that was never repaired, as alerts 22 through 25 demonstrate.
- **SC-003**: Every alert for this rule at this path that ends dismissed rather than repaired has a non-empty GitHub dismissal comment containing all three elements required by FR-009. If the dismissal is pending an owner action under FR-008a, this criterion is satisfied instead by the handoff artifact containing the exact text that will be applied, and the feature status reads `BLOCKED-ON-OWNER` rather than complete.
- **SC-004**: The existing ingestion test suite passes with no assertion loosened or removed, the only test change being additions.
- **SC-005**: Alerts for `py/clear-text-logging-sensitive-data` outside `src/lambdas/ingestion/handler.py` are unchanged in both count and `fixed_at` value. In particular alert 144 on `src/lambdas/shared/auth/oauth_state.py`, owned by feature `001-oauth-provider-taint`, stays untouched, and alerts 22 through 25 on `src/lambdas/shared/secrets.py` remain dismissed with `fixed_at` null. Any new alert number appearing on `src/lambdas/shared/secrets.py` is a breach of this criterion and of FR-013.
- **SC-006**: A reader can locate the dismissal wording pattern, the decision rule, and the `fixed_at` versus `state` caveat in a single artifact under this feature's directory, without reading dismissal comments in GitHub.

## Assumptions

- The configuration values are populated with full ARNs in the deployed environments, because infrastructure wires the secret ARN outputs straight into them. Non-ARN forms occur locally. Neither shape matters to the corrected design, because nothing derived from the value reaches a log or an exception message.
- The existing sanitizing helper is private to its module and stays that way. It is not called from the ingestion handler and is not promoted, wrapped or otherwise touched. See FR-003 and FR-013.
- Dismissing a CodeQL alert requires write access to code scanning alerts. On this repository, which is public, that is satisfied by a token carrying `public_repo` (which `repo` includes) together with a repository role of push or above; the `security_events` scope is what a private repository would require. Probed on 2026-07-30 the local environment satisfies this, so `BLOCKED-ON-OWNER` is not the expected path. It remains the defined terminal state under FR-008a if the implementing agent's environment differs. See Clarification Q2.
- CodeQL is not a required status check on this repository. The required contexts are `Secrets Scan`, `Lint`, `Run Tests` and `Playwright E2E Tests`. Nothing therefore prevents this change from merging while alerts remain open. The completion definition in this spec is the only gate, which is why FR-008a defines a terminal state instead of relying on a merge block.
- Best case is that the code change alone clears the site with no dismissal needed. The spec covers the dismissal path because the repository's own history shows this rule surviving a sanitize in place fix, not because dismissal is the expected outcome. Attempting the real fix is the primary path.

## Out of Scope

- Alert 144 on `src/lambdas/shared/auth/oauth_state.py`, the other open `py/clear-text-logging-sensitive-data` alert. That belongs to sibling feature `001-oauth-provider-taint`.
- The seven existing dismissals of `py/clear-text-logging-sensitive-data` on the shared secrets and errors modules, alerts 1 and 22 through 27. They are not re-litigated here.
- Migrating the ingestion handler to a different logging library, or adding a redacting filter or formatter anywhere.
- Building a repository wide registry of CodeQL dismissals. The wording pattern is recorded in this feature's artifacts only.
- Changing what infrastructure injects into the environment, or the shape of the secrets themselves.
- Any change whatsoever to `src/lambdas/shared/secrets.py`, including the sanitizing helper's truncation behaviour on hyphenated names and its visibility. Forbidden by FR-013.
- Other account topology values handled near these sites, such as the SNS topic ARN and the alert topic ARN. They carry the same account identifier but are not flagged by this rule and are not part of this feature. Carded for separate triage.
- Making CodeQL a required status check, or adding a lint rule that blocks ARN interpolation into logging calls repository wide. The FR-007 test is the regression guard for these three sites only. A repository wide guard is carded.

## Adversarial Review #1

Reviewer did not author the spec. Every claim below was checked against the code at
`src/lambdas/ingestion/handler.py`, `src/lambdas/shared/secrets.py`,
`src/lambdas/shared/logging_config.py`, `src/lib/metrics.py`, and against the live GitHub code
scanning alerts API on `refs/heads/main`.

### Findings

| Severity | Finding | Resolution |
|---|---|---|
| CRITICAL | SC-002 was keyed to alert numbers 148, 149 and 150. CodeQL can close those three and open fresh numbers at the same lines in the same run, so the criterion was satisfiable while the disclosure stayed open. Proven in this repository: alert 117 carries `fixed_at` `2026-01-20T22:34:56Z` and alert 144 was created at that exact timestamp on the same file; alerts 107, 110 and 111 spawned and closed within hours during the 2025-12-09 secrets remediation. | Fixed. SC-002 rewritten to require zero open alerts of this rule at path `src/lambdas/ingestion/handler.py`, any number. New acceptance scenario 2 in User Story 2 classifies a fresh number at the same path as not yet successful. New edge case added. |
| HIGH | FR-003 and FR-004 contradicted each other. FR-003 required source identification to reuse the existing ARN to bare name sanitizer; FR-004 forbade carrying any secret derived value in the log message or context. A sanitized value is still ARN derived, so the two could not both hold in the log path. | Fixed. FR-003 inverted: the sanitizer MUST NOT be called from these three sites, because the source identity is statically known at the call site here, unlike the shared secrets module where it arrives as a runtime argument. FR-004 tightened to exclude the exception message too, which removes the taint at source and makes the helper unnecessary anywhere in the handler. |
| HIGH | Assumption 2 authorised promoting or wrapping the private helper in `src/lambdas/shared/secrets.py`. That file holds alerts 22 through 25, which read `dismissed` but have `fixed_at` null, meaning the findings are still live behind a dismissal. Editing those lines risks re-fingerprinting them into fresh open alerts, the exact churn that file suffered on 2025-12-09, breaching SC-005. | Fixed. New FR-013 forbids editing any file other than the handler and its tests, naming `src/lambdas/shared/secrets.py` explicitly. Assumption rewritten. Out of Scope extended. SC-005 strengthened to check `fixed_at` and to treat any new alert on that file as a breach. |
| HIGH | FR-007 and SC-001 were satisfiable by a test that passes against unfixed code. Structured context values attached to a logging call are not rendered into the formatted message under the default formatter, so an assertion over rendered text alone passes today against the two sites at lines 271 and 276. Verified by probe: rendered text does not contain the ARN, the record attribute does. | Fixed. FR-007 now requires assertion over both the rendered message and the record's structured context attributes, and explicitly rejects rendered-text-only tests. SC-001 follows. New edge case added. |
| HIGH | FR-007 and SC-001 said "no ARN marker" without defining it. Asserting absence of the ARN prefix alone would pass while the account identifier leaked by itself, which is the highest value component of the disclosure. | Fixed. FR-007 now enumerates five required forbidden strings: the full fixture value, the ARN prefix, the account identifier alone, the region alone, and the environment or secret path segment alone. |
| HIGH | FR-002 required the both keys missing error to name its sources, but that message currently names them only through the interpolated configuration key names, so satisfying FR-002 requires adding literal text. FR-006 said "the same conditions trigger the same error and warnings", readable as forbidding that text change. Contradiction between a requirement and its own compatibility clause. | Fixed. FR-002 now states which sites already carry literals and which must gain them. FR-006 scoped precisely to log level, branch, exception type and response, with message text explicitly permitted to change and FR-002 declared to win. |
| HIGH | FR-004's precedent citation inverted part of its own evidence and rested on the wrong field. It cited "alerts 22 through 26" as the surviving sanitize in place sites. Alert 26 carries `fixed_at` `2025-12-03`, so it is a repaired site and is evidence for the preferred shape, not against it. More broadly, `state` conflates dismissal with repair: alerts 26 and 27 read `dismissed` while carrying non-null `fixed_at`, and dismissal predates the fix by two weeks. | Fixed. FR-004 corrected to 22 through 25, and rewritten to key on `fixed_at` rather than `state`. New SC-002a rejects a `dismissed` or `closed` state with null `fixed_at` as evidence of repair. New acceptance scenario 5 in User Story 2. |
| HIGH | The dismissal handoff had no terminal state. FR-008, SC-003 and Assumption 3 together left the feature permanently incomplete whenever the implementing agent lacked `security-events: write`, with no defined deliverable and no way to distinguish a blocked feature from a failed one. | Fixed. New FR-008a defines terminal state `BLOCKED-ON-OWNER`, requires a handoff artifact carrying the observed alert numbers, the exact justification text and the exact steps, and states the code change is independently mergeable. SC-003 amended to accept the artifact when dismissal is pending. |
| MEDIUM | FR-009 claimed its three element wording "follows the pattern already used on the seven existing dismissals". It does not. All seven existing comments carry two elements (the value is not a credential, a sanitizing convention is applied) and none states why CodeQL still reports the flow. | Fixed. FR-009 now claims only the first two elements as precedent and states the third is deliberately new, with the reason. |
| MEDIUM | User Story 1 asserted the disclosure "is written on every degraded run". True for the site that interpolates into the message string, unverified for the two that attach the ARN as structured context, since the handler installs no formatter and only sets levels. Over-claiming impact weakens the spec against a reviewer who checks. | Fixed. User Story 1 now separates the three sites by rendering certainty and keeps all three in scope on the correct grounds: the value is passed to the sink, it becomes reachable the moment a serialising formatter is introduced, and the engine flags the flow regardless. |
| MEDIUM | No regression guard on the success path. FR-010 required the inline comment only on sites behind a dismissed alert, so if the fix worked cleanly all three sites would end unmarked and a later refactor could reintroduce the interpolation silently. | Fixed. FR-010 made unconditional across all three sites regardless of outcome. Repository wide guard recorded as out of scope and carded. |
| LOW | Adjacent account topology values are handled a few lines away and carry the same account identifier: `sns_topic_arn`, `alert_topic_arn`. Not flagged by this rule, not surveyed by the spec. | Out of scope, carded. Recorded in Out of Scope. |
| LOW | CodeQL is not a required status check here, so nothing mechanically prevents merging with all three alerts open. The spec's completion definition is the only gate. | Out of scope, carded. Recorded as an assumption so the reliance is explicit, and mitigated by FR-008a defining a terminal state rather than depending on a merge block. |

Counts: 1 CRITICAL, 7 HIGH, 3 MEDIUM, 2 LOW. All CRITICAL and HIGH resolved by edit. All MEDIUM
resolved by edit because each was a wording fix inside existing scope. Both LOW carded without fix.

### Edits made

1. User Story 1 rationale rewritten to separate the one definitely-rendered site from the two whose
   rendering depends on the active formatter, without weakening the case for fixing all three.
2. User Story 1 independent test and all four acceptance scenarios rewritten to cover the structured
   context, not only the rendered message, and to name the disclosure components explicitly.
3. User Story 2 rewritten around two traps rather than one: diff-informed pull request analysis, and
   alert number instability. Both documented with in-repository evidence.
4. User Story 2 acceptance scenarios expanded from three to five, adding the fresh-number case and
   the `fixed_at` versus `state` case.
5. Edge cases: two sanitizer shape cases retired as closed by design, four added covering alert
   renumbering, stale analysis, rendered-text-only tests, and the missing dismissal permission.
6. FR-001 extended to name the structured context as a sink in its own right.
7. FR-002 rewritten to require fixed literal source names and to state which site must gain them.
8. FR-003 inverted from "reuse the sanitizer" to "do not call the sanitizer", with the reason.
9. FR-004 tightened to exclude the exception message, corrected from "22 through 26" to
   "22 through 25", and re-keyed onto `fixed_at`.
10. FR-005 given its reason now that the exception message is clean.
11. FR-006 scoped to control flow, level, exception type and response; message text change permitted.
12. FR-007 rewritten to require structured context assertions and to enumerate five forbidden strings.
13. FR-008 re-keyed from three alert numbers to any alert at the path.
14. FR-008a added: `BLOCKED-ON-OWNER` terminal state plus handoff artifact contents.
15. FR-009 provenance claim corrected.
16. FR-010 made unconditional across all three sites.
17. FR-011 extended to record the decision rule and the `fixed_at` caveat, not just the wording.
18. FR-013 added: file scope lock, with `src/lambdas/shared/secrets.py` named.
19. SC-001 re-keyed onto the FR-007 enumeration and the structured context.
20. SC-002 re-keyed onto path plus rule, never onto alert numbers.
21. SC-002a added: `fixed_at` must be non-null and dated at or after the change.
22. SC-003 amended to accept the handoff artifact when dismissal is pending.
23. SC-005 strengthened to check `fixed_at` and to treat any new alert on the shared secrets module
    as a breach.
24. SC-006 extended to require the `fixed_at` caveat be recorded.
25. Assumptions: sanitizer promotion assumption struck and replaced with a prohibition; blocked
    completion assumption re-pointed at FR-008a; new assumption recording that CodeQL is not a
    required check.
26. Out of Scope: shared secrets module edits, adjacent topology ARNs, and a repository wide lint
    guard all added.

### Gate

**0 CRITICAL, 0 HIGH remaining.**

## Clarifications

### Session 2026-07-30

Four questions were raised. All four were answered from the repository, the constitution, the live
GitHub API and git history. **None is deferred to the owner.** The count is four rather than five
because the spec's adversarial review and planning pass had already closed the rest; a fifth
question would have been manufactured.

---

**Q1: Constitution §9 requires a `TD-XXX` registry entry when a security finding is accepted by
dismissal. Is this feature blocked by that requirement, and what is the minimal correct response?**

**A: Not blocked. The premise that the registry does not exist is wrong, the obligation is
conditional and post-merge, and the correct response is a carded follow-up at the corrected path.**

Three findings, in order of importance.

First, the registry exists. It is `docs/reference/TECH_DEBT_REGISTRY.md`, not
`docs/TECH_DEBT_REGISTRY.md`. Constitution §9(a) at `.specify/memory/constitution.md:527` cites the
flat path, and §9's Acceptance Criteria at line 569 repeats it, but the file was moved under
`docs/reference/` by commit `f8db8d2` ("feat(docs): Reorganize documentation into categorical
subdirectories", PR #668), planned at `specs/1210-documentation-reorganization/plan.md:71`. The
constitution was never updated. Sibling feature `001-ruff-bump-forward` reached the same conclusion
independently and recorded it as its adversarial finding F3 at `plan.md:109`. Sibling feature
`001-codeql-coverage` did not, and states at its `plan.md:59` that the file "does not exist in this
repository", which is false. This spec's own `plan.md` Constitution Check row and Complexity
Tracking row both carried the stale path and have been corrected.

Second, the obligation is conditional, and the condition cannot be evaluated during implementation.
§9's trigger list at constitution lines 553 to 558 includes "Security shortcuts with documented
acceptance criteria". A dismissal under FR-008 is such a shortcut. A clean repair under FR-001 is
not, and creates no debt at all. Which of the two occurs is only knowable after a default-branch
CodeQL analysis, which is post-merge (see Q2). So no registry entry can be authored during
implementation even if the file were writable.

Third, FR-013 keeps the registry outside the writable set, and that reason survives the path
correction. The registry is a shared, append-only, single-source-of-truth file, and sibling feature
`001-ruff-bump-forward` already has task T016 queued to add "the next sequential TD entry" to it.
The highest existing identifier is `TD-023`, so both features would claim `TD-024` and collide.
Three sibling agents share this worktree, which makes that collision likely rather than theoretical.

**Minimal correct response**: no change to scope. The §9 deviation already recorded in
`plan.md`'s Complexity Tracking stands, with its path corrected to
`docs/reference/TECH_DEBT_REGISTRY.md` and its rationale restated as conditional-and-post-merge
rather than file-does-not-exist. The acceptance remains documented in two places under this
feature's own directory (FR-009 dismissal text, FR-011 convention artifact), so it is discoverable.
The registry entry itself is carded for the owner, to be written at the next free identifier at the
time it is written, not pre-reserved as `TD-024`.

*Evidence*: `docs/reference/TECH_DEBT_REGISTRY.md` (exists, `TD-001` through `TD-023`);
`.specify/memory/constitution.md:527,553-558,569`; commit `f8db8d2`;
`specs/1210-documentation-reorganization/plan.md:71`; `specs/001-ruff-bump-forward/plan.md:109` and
`tasks.md:36`; `specs/001-codeql-coverage/plan.md:59`.

---

**Q2: FR-008a defines `BLOCKED-ON-OWNER` for the case where the implementing agent cannot dismiss.
Does that fully cover the case?**

**A: No. Two holes. One is a missing detection procedure, the other is a missing terminal state for
a different and far more likely blocker. Both are now closed in the spec.**

*Hole 1, no capability probe.* FR-008a as written told the agent what to do when it "lacks
permission to dismiss" but never said how to establish that. The obvious method, attempting the
dismissal and reading the failure, is unacceptable here: a dismissal that succeeds mutates alert
state and cannot be cleanly reverted, and SC-005 makes unintended alert-state change a breach.
A read-only probe exists and was run. `gh auth status` reports the active token's scopes as `gist`,
`read:org`, `repo`, `workflow`, with no `security_events`. On its own that reads as blocked, and
the spec's Assumption 3 said exactly that. It is wrong. GitHub's update-code-scanning-alert endpoint
requires `security_events` only for private repositories; `public_repo` suffices for public ones,
and `repo` includes `public_repo`. This repository is public:
`gh api repos/traylorre/sentiment-analyzer-gsk` returns `"private": false`, `"visibility":
"public"`, and permissions `admin: true, maintain: true, push: true`. Read access is already
demonstrated: the alerts API returns the four open alerts of this rule (148, 149, 150 at
`src/lambdas/ingestion/handler.py` lines 264, 271 and 276, plus 144 at
`src/lambdas/shared/auth/oauth_state.py:104`, which is the sibling feature's and stays untouched
per SC-005). So on this environment dismissal is available and `BLOCKED-ON-OWNER` is not the
expected outcome. FR-008a now names the probe, and Assumption 3 has been rewritten from the false
`security-events: write` claim to the actual requirement.

*Hole 2, and this is the larger one: nothing covered "cannot yet verify".* SC-002 and SC-002a are
both keyed to a default-branch CodeQL analysis on a commit that includes the change. Such an
analysis cannot exist while the change sits on a feature branch, so at the end of implementation
the feature is neither `DONE` (SC-002 unevaluated), nor `DONE (dismissed)` (no survivor observed
yet), nor `BLOCKED-ON-OWNER` (permission is present and no dismissal is pending). The plan's
Terminal States section lists exactly those three. This is not an edge case, it is the normal
ending, and it is made certain here because this agent tree performs no git operations at all. The
spec's edge case "The default branch analysis has not re-run" said only "Classification must wait",
which is not a terminal state and reproduces precisely the ambiguity that FR-008a was added to
remove.

**Resolution**: new **FR-008b** adds terminal state `PENDING-BRANCH-ANALYSIS`, reached when the code
change and the FR-007 tests are complete and green but no qualifying analysis exists. Like
`BLOCKED-ON-OWNER` it is reported as neither done nor failed, and it is explicitly distinguished
from it: `BLOCKED-ON-OWNER` is about permission to dismiss a survivor already observed,
`PENDING-BRANCH-ANALYSIS` is about no observation being possible yet.

*Evidence*: `gh auth status` scope list, 2026-07-30; `gh api repos/traylorre/sentiment-analyzer-gsk`
visibility and permissions; `gh api .../code-scanning/alerts?state=open` returning 148, 149, 150 and
144; spec SC-002, SC-002a; `plan.md` "Terminal states".

---

**Q3: The plan uses a richer local fixture instead of the shared `env_vars` fixture. Does any other
test depend on the values chosen, and is each forbidden string actually assertable against it?**

**A: No other test depends on them. Each string is assertable, but only under an isolation
constraint the plan stated for the region and omitted for the account identifier. FR-007 now carries
that constraint.**

*Dependency sweep, all clean.* `eu-west-2` appears in exactly one test module,
`tests/unit/test_dynamodb_helpers.py`, which sets its own region and shares no fixture with the
ingestion tests. `218795110243` appears in `tests/unit/test_sentiment.py` at lines 748, 803, 843 and
906, always as the S3 bucket name `sentiment-analyzer-models-218795110243`, again a different module
with no shared fixture. `preprod/sentiment-analyzer` appears in no test at all; its only
non-specification occurrence is a comment in `infrastructure/terraform/ci-user-policy.tf:285`. The
existing `env_vars` fixture at `tests/unit/lambdas/ingestion/test_handler.py:42-68` is not modified
and not shared, so SC-004 is unaffected.

*On using the real account identifier.* `218795110243` is this project's real AWS account. It is
already committed to the repository in `CLAUDE.md` and in `tests/unit/test_sentiment.py`, so the
fixture introduces no disclosure that is not already public in a public repository, and no secret
scanner treats it as a finding. Keeping it is therefore acceptable and matches existing test
precedent. A synthetic identifier would work equally well and is the tidier choice if the
implementer prefers it; nothing in FR-007 or SC-001 depends on the value being real.

*Assertability, one string at a time, against the handler's actual configuration.* The full ARN,
the suffixes `AbCdEf` and `GhIjKl`, and the path segment `preprod/sentiment-analyzer` are unique to
the two secret ARNs by construction; the fixture's `ENVIRONMENT` is `test`, so `preprod` does not
collide. The prefix `arn:aws:secretsmanager` is safe because the only other ARN in the
configuration is `SNS_TOPIC_ARN`, which is `arn:aws:sns`; note that a bare `arn:aws:` assertion
would have collided and must not be used. `eu-west-2` is safe only because `AWS_REGION` stays
`us-east-1`, which the plan states. The account identifier is the gap: `_get_config()` at
`src/lambdas/ingestion/handler.py:585-605` also loads `sns_topic_arn` and `alert_topic_arn`, and
both legitimately contain an account identifier. If the new fixture reused `218795110243` in either
of those, a record carrying an SNS ARN would fail the account assertion for a reason that has
nothing to do with the secret ARN, and conversely a passing assertion would stop being evidence.
The existing fixture already uses `123456789` for `SNS_TOPIC_ARN`, so keeping that separation is
sufficient. FR-007 now states the constraint for all three of `SNS_TOPIC_ARN`, `ALERT_TOPIC_ARN`
and `AWS_REGION` rather than for the region alone.

*One non-issue checked and cleared.* The plan's sweep case, which asserts every record from the
both-keys-missing invocation is clean, cannot trip over the SNS or alert topic ARN, because that
path raises at `handler.py:265` before `_get_sns_client` and `_create_failure_tracker` are reached.
The single-source cases do run that code, which is why the fixture isolation matters there.

*Evidence*: `tests/unit/test_dynamodb_helpers.py`; `tests/unit/test_sentiment.py:748,803,843,906`;
`tests/unit/lambdas/ingestion/test_handler.py:42-68`; `src/lambdas/ingestion/handler.py:256-277` and
`585-605`; `infrastructure/terraform/ci-user-policy.tf:285`; `CLAUDE.md`.

---

**Q4: FR-013 forbids modifying any file outside the handler and its tests. FR-011, SC-006 and
FR-008a all require artifacts under `specs/001-ingestion-arn-logging/`. Which wins?**

**A: A real contradiction, not a reading quibble. FR-013 has been given an explicit carve-out for
this feature's own specification directory.**

As written, FR-013 forbade writing `codeql-logging-convention.md`, which FR-011 and SC-006 require
and which already exists, and forbade writing `dismissal-handoff.md`, which FR-008a requires as the
sole deliverable of the `BLOCKED-ON-OWNER` state. An implementing agent obeying FR-013 literally
would refuse to produce the one artifact that distinguishes a blocked feature from a failed one,
which is the exact failure FR-008a was added to prevent. The plan already assumed the carve-out, at
`plan.md:65-74`, without the spec granting it.

The carve-out is narrow on purpose. FR-013's real target is source, test, infrastructure and shared
documentation files, and above all `src/lambdas/shared/secrets.py`, whose alerts 22 through 25 read
`dismissed` with `fixed_at` null and would re-fingerprint into fresh open alerts if their lines were
touched. A specification directory carries no CodeQL alerts and is owned solely by this feature, so
writing in it cannot breach SC-005. The `docs/reference/TECH_DEBT_REGISTRY.md` exclusion from Q1 is
unaffected: that file is shared and contended, and stays outside the writable set.

*Evidence*: spec FR-011, FR-008a, SC-006, SC-005; `plan.md:65-74`;
`specs/001-ingestion-arn-logging/codeql-logging-convention.md` (already written).

---

### Requirements and criteria changed by this session

| Item | Change | Driven by |
|---|---|---|
| FR-007 | Added the fixture-isolation constraint covering `SNS_TOPIC_ARN`, `ALERT_TOPIC_ARN` and `AWS_REGION`. The enumeration itself is unchanged. | Q3 |
| FR-008a | Added the read-only capability probe, and the prohibition on establishing permission by attempting a dismissal. | Q2 |
| FR-008b | **New requirement.** Terminal state `PENDING-BRANCH-ANALYSIS`. | Q2 |
| FR-013 | Scope widened to include `specs/001-ingestion-arn-logging/`. All other prohibitions unchanged. | Q4 |
| Assumption on dismissal permission | Rewritten. The `security-events: write` claim was factually wrong for a public repository. | Q2 |

No success criterion was changed. SC-002 and SC-002a keep their wording; FR-008b names the state
that exists before they become evaluable rather than altering what they measure.
