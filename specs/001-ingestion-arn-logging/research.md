# Phase 0 Research: Stop Ingestion Handler Logging Secret ARNs

**Feature**: `001-ingestion-arn-logging` | **Date**: 2026-07-30 | **Plan**: [plan.md](./plan.md)

No `NEEDS CLARIFICATION` marker was carried into the plan's Technical Context, so this phase
resolved no open unknowns. Its purpose is different: the spec and its Adversarial Review #1 settled
seven questions that are expensive to re-derive and easy to get wrong. They are recorded here so
implementation cites them instead of rediscovering them, and so a reviewer can check the reasoning
without reading GitHub.

---

## D1: Code shape is "strip the value", not "sanitize the value"

**Decision**: At all three sites, carry no secret-derived value at all. Not in the message, not in
`extra`, not in the raised exception message.

**Rationale**: The repository has run this experiment already, on the same CodeQL rule, two weeks
apart on the same file.

- `0e7a375` (PR #321, 2025-12-09) broke the taint flow with an intermediate sanitized variable and
  kept the sanitized name inside the log context. CodeQL still flagged it.
- `ebcc2f4` (PR #322, 2025-12-09) removed every secret-derived value from the log context. That
  worked.

The empirical read, from `fixed_at` and not from `state` (see D2): alerts 22, 23, 24 and 25 are the
four sites that kept a sanitized value inside `extra`, and their `fixed_at` is null to this day.
Alerts 26 and 27 are the two sites rewritten to exception-message-only, and both carry a non-null
`fixed_at`.

**Alternatives considered**:

- *Call the existing `_sanitize_secret_id_for_log()` helper from the three sites.* Rejected. This is
  the `0e7a375` shape, it has already failed here, and FR-003 forbids it. It would also mean
  importing from or touching `src/lambdas/shared/secrets.py`, which FR-013 forbids for an unrelated
  and stronger reason (D6 tail).
- *Keep the ARN and add a redacting `logging.Filter` or formatter.* Rejected by FR-012. It also does
  not remove the flow at source, so the alert would likely survive and the repository would carry a
  new logging mechanism for three lines.
- *Suppress with a `# nosec` or CodeQL inline suppression.* Rejected by constitution §10 ("DO NOT
  suppress without documented justification", "DO NOT rename variables just to avoid detection") and
  by the fact that a real fix is available and cheap.

**Why no sanitizer is needed here at all**: in `src/lambdas/shared/secrets.py` the identifier
arrives as a runtime argument, so identifying which secret failed genuinely requires deriving
something from that argument. At these three ingestion sites the source identity is statically known
at the call site. `"Tiingo"` and `"Finnhub"` are literals the author can type. Nothing is lost by
dropping the value entirely, which is what makes FR-004 stricter than its own precedent without
costing any diagnostic power.

---

## D2: Read `fixed_at`, never `state`

**Decision**: Every judgement about whether a site was repaired keys on the `fixed_at` field of the
code scanning alert. `state` is not evidence.

**Rationale**: Dismissal is sticky and can predate a later genuine repair, so `state` conflates "a
human dismissed this" with "the code was fixed". In this repository:

- Alerts 26 and 27 read `dismissed` and both carry a non-null `fixed_at`. Repaired.
- Alerts 22 through 25 also read `dismissed` and have `fixed_at` null. Never repaired.

A reviewer reading `state` alone would put all six in the same bucket and draw the opposite
conclusion about which code shape works. That is exactly the error Adversarial Review #1 caught in
the spec's own first draft.

**Alternatives considered**: reading `state` only (rejected, above); reading the alert's `html_url`
timeline by hand (rejected, not scriptable and not reproducible in CI or in a report).

---

## D3: Lines 271 and 276 stay in scope even though nothing renders `extra` today

**Decision**: Fix all three sites. Do not narrow the change to line 264 on the grounds that the
other two do not currently reach CloudWatch.

**Rationale**: `configure_lambda_logging()` in `src/lambdas/shared/logging_config.py` is a
level-setter only. Its own docstring says it "never attaches handlers or formatters". The root
handler installed by the Lambda runtime renders `record.getMessage()`, so a value passed only via
`extra=` is currently attached to the record and not printed. Line 264 interpolates directly into
the message string and therefore definitely leaks today.

Three reasons the other two stay in:

1. The value is passed to the sink. Whether the sink prints it is a property of the currently
   installed formatter, not of the code.
2. It arms itself the moment any structured or JSON formatter is attached, which is a change one
   line long that nobody would think of as security-relevant.
3. CodeQL flags the flow regardless of rendering, so leaving them means leaving two open alerts,
   which fails SC-002 outright.

**Alternatives considered**: fixing only line 264 and dismissing 149 and 150 as non-rendering.
Rejected. It trades a two-line deletion for two permanent dismissals plus a latent leak, and the
dismissal justification would be false the day someone adds a formatter.

---

## D4: Tests assert over the `LogRecord`, not over `caplog.text`

**Decision**: The forbidden-string assertions run against `record.getMessage()` plus every value in
`record.__dict__`. `caplog.text` is not an acceptable assertion surface for this feature.

**Rationale**: Probe result against the current unfixed code: `arn:aws:` is absent from
`caplog.text`, while `record.tiingo_secret_arn` holds the full ARN. A test written against rendered
text passes today against two of the three unfixed sites. It would be a permanent false negative and
would not satisfy FR-007. Adversarial Review #1 raised this as a HIGH finding for exactly that
reason.

Scanning all of `record.__dict__` rather than a hand-listed set of extra keys is deliberate: it
catches `msg`, `args`, and any future `extra` key without the test needing to know its name.

**Alternatives considered**:

- Asserting on `record.__dict__` keys by name (`assert not hasattr(record, "tiingo_secret_arn")`).
  Rejected: it passes if someone renames the key.
- Installing a JSON formatter inside the test so `caplog.text` becomes representative. Rejected: it
  is more machinery than the direct read, and it makes the test depend on a formatter the production
  code does not have.

---

## D5: The forbidden-string enumeration, and why the fixture ARN is not the existing one

**Decision**: Six explicit forbidden strings per record, and a fixture ARN with a region and an
environment path that appear nowhere else in the handler's configuration:

```
arn:aws:secretsmanager:eu-west-2:218795110243:secret:preprod/sentiment-analyzer/tiingo-AbCdEf
arn:aws:secretsmanager:eu-west-2:218795110243:secret:preprod/sentiment-analyzer/finnhub-GhIjKl
```

Forbidden: the full value; `arn:aws:secretsmanager`; `218795110243`; `eu-west-2`;
`preprod/sentiment-analyzer`; and the random suffix.

**Rationale**: FR-007 requires the enumeration rather than a single marker because an assertion on
the ARN prefix alone would pass while the account identifier leaked by itself, and the account
identifier is the highest-value component of the disclosure.

The existing `env_vars` fixture in `tests/unit/lambdas/ingestion/test_handler.py` uses
`arn:aws:secretsmanager:us-east-1:123456789:secret:tiingo`. Two problems for this feature: it has no
environment or secret path segment, so one of the five required classes has nothing to assert
against; and its region `us-east-1` is also the value of `AWS_REGION`, which the handler legitimately
logs elsewhere, so a region assertion could fail for an innocent reason or pass for the wrong one.
Choosing `eu-west-2` makes any region match unambiguous evidence of an ARN leak.

**Alternatives considered**: reusing the existing fixture and dropping the region and path
assertions. Rejected: it drops two of the five classes FR-007 names.

---

## D6: Closure evidence comes from the default-branch analysis or the alerts API, keyed on path plus rule

**Decision**: Success is "zero open alerts for rule `py/clear-text-logging-sensitive-data` whose
location path is `src/lambdas/ingestion/handler.py`", read after a default-branch analysis on a
commit containing the change. Never keyed on the numbers 148, 149, 150.

**Rationale**: two independent traps.

*Alert numbers are not stable identities.* CodeQL can close a number as fixed and open a fresh number
at the same location in the same run. Documented here: alert 117 on
`src/lambdas/shared/auth/oauth_state.py` has `fixed_at` `2026-01-20T22:34:56Z` and alert 144 on the
same file was created at that identical timestamp. During the 2025-12-09 secrets remediation, alerts
107, 110 and 111 were created and closed within hours at lines a remediation attempt had just
rewritten. A criterion asking only whether three numbers stopped being open is satisfiable while the
disclosure sits open under three fresh numbers.

*A green PR check is not evidence.* CodeQL runs diff-informed analysis on pull requests in this
repository. PR #990 was green with all five of its alerts still open; PR runs report
`results_count: 0` while `refs/heads` runs report 9. The one useful inverse: because this change
edits the exact flagged lines, the diff-scoped PR result is directly informative here, so an alert
surviving the PR run is a genuine survivor.

**Related constraint on blast radius**: SC-005 requires alerts outside the handler to be unchanged in
both count and `fixed_at`. This is the reason FR-013 forbids editing `src/lambdas/shared/secrets.py`
even to reuse its helper: alerts 22 through 25 sit on lines in that file with `fixed_at` null,
meaning live findings behind a dismissal, and editing those lines risks re-fingerprinting them into
fresh open alerts. That is precisely what happened to that file on 2025-12-09.

**Alternatives considered**: waiting for a required-check signal. Rejected, because there is none.
CodeQL is not a required status check on this repository; the required contexts are exactly
`Secrets Scan`, `Lint`, `Run Tests` and `Playwright E2E Tests`. Nothing blocks a merge on a CodeQL
result, which is why the spec defines its own completion gate.

---

## D7: Two terminal states exist that are neither done nor failed

**Decision**: The feature has two non-terminal-looking but defined endings, and they are different
things.

*`PENDING-BRANCH-ANALYSIS` (FR-008b).* The code change and the FR-007 tests are complete and green
but no default-branch CodeQL analysis containing the change exists yet. This is the expected ending
of implementation, not an edge case, because SC-002 and SC-002a are keyed to a default-branch
analysis (D6) which cannot exist while the change sits on a feature branch. Reaching it requires the
plan's verification query to be on record so the check is mechanical when the analysis lands.

*`BLOCKED-ON-OWNER` (FR-008a).* A survivor alert exists and a read-only capability probe shows the
implementing agent cannot dismiss it. Then `dismissal-handoff.md` is written into this feature's
directory. Reported as blocked, never as done and never as failed.

**The permission claim this decision originally got wrong.** The first draft of D7 said dismissal
requires `security-events: write`. That is false for this repository. GitHub's
update-code-scanning-alert endpoint requires `security_events` only on **private** repositories; on a
public repository `public_repo` suffices, and the `repo` scope includes `public_repo`. This
repository is public and the actor holds push or above, so dismissal is available and
`BLOCKED-ON-OWNER` is **not** the expected path. Corrected by Clarification Q2.

**The probe is mandatory and must be read-only.** Establishing the permission by attempting a
dismissal and reading the failure is not acceptable: a dismissal that succeeds mutates alert state,
cannot be cleanly reverted, and SC-005 treats unintended alert-state change as a breach. The probe is
`gh auth status` (scopes) read together with `gh api repos/<owner>/<repo>` (visibility and the
actor's permissions).

**Rationale**: FR-008a and FR-008b. Without these states the feature is permanently incomplete
whenever the agent cannot dismiss or cannot yet verify, with no deliverable and no way to tell a
blocked feature from a failed one. The handoff artifact carries the observed alert numbers, the exact
justification text per alert, and the exact API call or UI steps to apply them, so the owner's action
is mechanical. The code change is independently complete and mergeable in both states.

**Alternatives considered**: leaving the alert open and unexplained (rejected by FR-008); marking the
feature failed (rejected, it misreports a complete and correct code change); collapsing the two
states into one (rejected, they call for different owner actions, one is "wait for the analysis" and
the other is "apply this dismissal").

---

## Cross-references

- The reusable convention distilled from D1, D2 and D6, for the sibling feature
  `001-oauth-provider-taint`, lives in [codeql-logging-convention.md](./codeql-logging-convention.md)
  as FR-011 and SC-006 require.
- The concrete code and test design derived from these decisions is in [plan.md](./plan.md).
