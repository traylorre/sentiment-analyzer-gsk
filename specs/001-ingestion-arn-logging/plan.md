# Implementation Plan: Stop Ingestion Handler Logging Secret ARNs

**Branch**: `001-ingestion-arn-logging` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-ingestion-arn-logging/spec.md`

## Summary

Three logging calls in `src/lambdas/ingestion/handler.py` pass Secrets Manager ARNs into the
logging sink: line 264 interpolates both ARNs into an f-string message that is also reused as a
`RuntimeError` message, and lines 271 and 276 attach an ARN as a structured context value via
`extra=`. CodeQL flags all three under `py/clear-text-logging-sensitive-data` as alerts 148, 149
and 150.

The technical approach is the shape proven by `ebcc2f4` (PR #322): carry no secret-derived value
in the message, in the structured context, or in the raised exception. The source identity at
these three sites is statically known at the call site, so the diagnostic value of each record is
preserved with fixed literal text (`Tiingo`, `Finnhub`) and nothing is read from `config` for
logging purposes. No sanitizer, no helper, no formatter, no filter. The change is a deletion at
all three sites plus a reword at the first one, guarded by a new unit test module that asserts
over both the rendered message and the record's structured attributes.

## Technical Context

**Language/Version**: Python 3.13 (`requires-python = ">=3.13"`; Lambda runtime `python3.13`)
**Primary Dependencies**: Python standard-library `logging` only for the mechanism. `src/lambdas/ingestion/handler.py:119` uses `logging.getLogger(__name__)`, not a structured-logging wrapper, and the handler's logging mechanism is retained unchanged per FR-012. Tests use pytest 8.x with the built-in `caplog` fixture, plus `unittest.mock.patch` and `moto` (`mock_aws`) already present in `tests/unit/lambdas/ingestion/test_handler.py`. No dependency is added, removed or upgraded.
**Storage**: N/A. No data store is read or written by this change.
**Testing**: pytest, `tests/unit/lambdas/ingestion/`, run under the project venv (`source .venv/bin/activate`). Unit tests only; all AWS access is mocked with `moto` and all external APIs with `MagicMock`, per the constitution's LOCAL/DEV row.
**Target Platform**: AWS Lambda (`{env}-sentiment-ingestion`), EventBridge-triggered, logging to CloudWatch Logs.
**Project Type**: Single project. Backend Lambda source under `src/lambdas/`, tests under `tests/`.
**Performance Goals**: N/A. Removing string interpolation from two branches that run at most once per invocation has no measurable effect.
**Constraints**: FR-013 locks the writable file set to `src/lambdas/ingestion/handler.py`, its tests, and this feature's own `specs/001-ingestion-arn-logging/` directory (the directory carve-out was added by Clarification Q4 so that `codeql-logging-convention.md` and, if FR-008a fires, `dismissal-handoff.md` can be written at all). `src/lambdas/shared/secrets.py` must not be touched (alerts 22 through 25 sit there with `fixed_at` null). FR-012 forbids new cloud resources and any logging-framework change. SC-004 forbids loosening or removing any existing assertion; test changes must be additions only.
**Scale/Scope**: 3 log call sites in 1 source file (about 20 lines net), 1 new test module (about 5 tests), 1 convention artifact. No runtime behaviour change beyond message text.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v1.6.

| Constitution clause | Applies | Status | Evidence / note |
|---|---|---|---|
| §3 Security: "do not write raw user-provided text into logs or dashboard fields without redaction" and "Protect logs" | Yes | PASS, this feature is the enforcement | The change removes account topology from the log sink entirely. |
| §6 Observability: "Emit structured logs for requests ... without logging raw input text by default" | Yes | PASS | Records keep their level, their trigger condition and their source identity. Only the ARN leaves. |
| §7 Implementation Accompaniment Rule: every modified module needs unit tests covering happy path and at least one error path | Yes | PASS | New module `tests/unit/lambdas/ingestion/test_handler_arn_logging.py` covers all three failure branches plus the outer exception path. |
| §7 Environment matrix: LOCAL/DEV run unit tests only, all AWS and external APIs mocked | Yes | PASS | `moto` for DynamoDB, `MagicMock` for adapters, `patch` for `get_api_key`. No preprod test is added. |
| §7 Functional Integrity: never make tests pass by weakening fixtures | Yes | PASS | SC-004 already forbids loosening any existing assertion. Test changes are additions only. |
| §7 Deterministic Time Handling | No | N/A | No date or time value appears anywhere in this change. |
| §7 Coverage: 80% minimum for new code | Yes | PASS | The changed lines are exactly the lines the new tests execute. |
| §8 Git Workflow: ruff check, ruff format, GPG-signed commit, feature branch, no `--no-verify` | Yes | PASS, applies at implementation | Standard. Nothing in this feature needs a bypass. |
| §10 Local SAST: bandit pre-commit, `make sast` / `make validate` before push | Yes | PASS | The change deletes a CWE-532 pattern rather than introducing one. `make validate` runs before push as usual. |
| §10 "DO NOT suppress without documented justification" and "DO NOT rename variables just to avoid detection" | Yes | PASS | The fix is removal at source, not suppression and not renaming. FR-003 explicitly forbids the sanitize-in-place shape that would look like detection avoidance. FR-008/FR-009 attach a written justification to any dismissal that remains. |
| §9 Tech Debt Tracking: registry entry for "security shortcuts with documented acceptance criteria". The registry is `docs/reference/TECH_DEBT_REGISTRY.md`; constitution §9 cites the stale flat path `docs/TECH_DEBT_REGISTRY.md`, corrected by commit `f8db8d2` (PR #668) and independently noted by sibling `001-ruff-bump-forward` | Conditionally | **DEVIATION** | Triggers only on the dismissal branch, which is post-merge and therefore unevaluable during implementation. See Complexity Tracking below and Clarification Q1. |

**Initial gate result: PASS with one recorded deviation (§9).**

**Post-design re-check: unchanged. PASS with the same single deviation.** The Phase 1 design adds
no new module, no new dependency, no new resource and no new interface, so no additional clause
comes into play.

## Project Structure

### Documentation (this feature)

```text
specs/001-ingestion-arn-logging/
├── spec.md                        # Input (with Adversarial Review #1 appendix)
├── plan.md                        # This file
├── research.md                    # Phase 0 output: decisions D1 to D7
├── codeql-logging-convention.md   # Phase 1 output: the FR-011 / SC-006 reusable artifact
├── checklists/
│   └── requirements.md            # Existing
├── dismissal-handoff.md           # CONDITIONAL, created at implementation time only if FR-008a fires
└── tasks.md                       # Phase 2 output (/speckit.tasks, NOT created here)
```

### Source Code (repository root)

Only two files **outside this feature's specification directory** are writable under FR-013. Per
Clarification Q4, `specs/001-ingestion-arn-logging/` is itself inside the writable set; everything
else in the repository is not:

```text
src/lambdas/ingestion/
└── handler.py                     # MODIFIED: 3 log sites at lines 258-277 (+ the RuntimeError message)

tests/unit/lambdas/ingestion/
├── test_handler.py                # UNCHANGED (SC-004: no existing assertion loosened or removed)
└── test_handler_arn_logging.py    # NEW: the FR-007 regression guard
```

Explicitly not touched: `src/lambdas/shared/secrets.py` (FR-013, SC-005),
`src/lambdas/shared/logging_config.py`, `src/lambdas/shared/logging_utils.py`, any Terraform,
any workflow.

**Structure Decision**: Single project, existing repository layout, no new directory. The feature
is a defect fix inside one existing Lambda handler plus one new sibling test module placed next to
the handler's existing test file. Nothing about this feature motivates a structural change, and
FR-013 forbids one.

## Phase 0: Research

See [research.md](./research.md). No `NEEDS CLARIFICATION` markers were carried into Technical
Context, so Phase 0 resolved no unknowns. It records seven decisions that were already settled by
the spec and its adversarial review, so implementation does not re-derive them:

- **D1** Code shape: strip the value, do not sanitize it (`ebcc2f4` over `0e7a375`).
- **D2** Evidence field: `fixed_at`, never `state`.
- **D3** Why lines 271 and 276 stay in scope even though nothing renders `extra` today.
- **D4** Test assertion surface: the `LogRecord`'s attributes, not `caplog.text`.
- **D5** Forbidden-string enumeration and the fixture ARN chosen to make each component unambiguous.
- **D6** Verification path: default-branch analysis or the alerts API, keyed on path plus rule.
- **D7** Terminal state when dismissal permission is absent.

## Phase 1: Design

### Interface contracts

**Skipped, deliberately.** This feature exposes no interface. It changes no HTTP route, no event
schema, no DynamoDB item shape, no function signature and no module export. `lambda_handler`'s
input event and its returned response dict are byte-identical before and after, which FR-006
requires. Generating a `contracts/` directory here would produce a file describing an unchanged
API, which is padding, so none is written.

### Data model

**Skipped, deliberately.** There are no entities. The only data touched is two environment-sourced
strings that the corrected code stops reading at these sites. Writing a `data-model.md` for a log
statement would be noise.

### Quickstart

**Skipped as a separate file.** The only "getting started" content this feature has is the
verification procedure, which is load-bearing for SC-002, SC-002a and SC-005 and is therefore
recorded inline below rather than in a satellite document a reader might miss.

### Agent context update

**Not run.** `.specify/scripts/bash/update-agent-context.sh claude` writes to the repository-root
`CLAUDE.md`, which is outside this feature's writable scope, and three sibling agents share this
worktree. The script would also have nothing to add: this feature introduces no new technology
(stdlib `logging` and pytest are both long-standing entries).

### Code change design

All three sites are inside the `if not tiingo_adapter and not finnhub_adapter:` region at
`src/lambdas/ingestion/handler.py:256-277`.

**Site 1, lines 259-265 (the definitely-rendered one).** `error_msg` is built by f-string from
both ARNs, passed to `logger.error()`, then reused verbatim as the `RuntimeError` message. Both
uses are sinks. Replace with a fixed literal that names both sources, satisfying FR-002 (this is
the site that currently identifies its sources only through the interpolated key names) and
FR-004 (the exception message is now clean, which is what makes FR-005 hold for the outer
`except` at line 572). The `logger.error` call and the `raise RuntimeError` stay, same level, same
branch, same exception type, per FR-006. Add the FR-010 inline comment naming the rule id.

**Sites 2 and 3, lines 268-277 (the structured-context ones).** Delete the `extra={...}` argument
outright. The message already carries the literal source name, so the record loses nothing an
on-call engineer uses. Add the FR-010 inline comment at each. Do not replace `extra` with a
sanitized value: that is the `0e7a375` shape and FR-003 forbids it.

Net effect on `config`: `config["tiingo_secret_arn"]` and `config["finnhub_secret_arn"]` remain
read exactly once each, at lines 249-250, where they are passed to `get_api_key()`. That is a
legitimate non-logging use and is untouched.

### Test design

New file `tests/unit/lambdas/ingestion/test_handler_arn_logging.py`. Additions only; nothing in
`test_handler.py` is edited, which satisfies SC-004 mechanically.

**Fixture ARNs.** Deliberately richer than the ones in `test_handler.py`'s `env_vars` fixture,
which lack an environment segment and use `us-east-1`, the same region the handler's unrelated
`aws_region` config carries. A region collision would make a region assertion ambiguous, so the
new fixture uses a region that appears nowhere else in the handler's config:

```
arn:aws:secretsmanager:eu-west-2:218795110243:secret:preprod/sentiment-analyzer/tiingo-AbCdEf
arn:aws:secretsmanager:eu-west-2:218795110243:secret:preprod/sentiment-analyzer/finnhub-GhIjKl
```

**Fixture isolation (FR-007, added by Clarification Q3).** The region is not the only value that
can collide. `_get_config()` at `src/lambdas/ingestion/handler.py:585-605` also loads
`sns_topic_arn` and `alert_topic_arn`, both of which legitimately contain an account identifier. If
the fixture put `218795110243` into either of them, a record carrying an SNS ARN would fail the
account assertion for a reason unrelated to the secret ARN, and a passing assertion would stop being
evidence. So the fixture MUST keep every enumerated forbidden string unique to the two secret ARNs:

- `SNS_TOPIC_ARN` keeps the existing fixture's unrelated account (`123456789`) and must not contain
  `218795110243`, `eu-west-2` or `preprod/sentiment-analyzer`.
- `ALERT_TOPIC_ARN` is unset by the existing fixture and defaults to `""`. If the new fixture sets
  it, the same three constraints apply.
- `AWS_REGION` stays `us-east-1`. **`CLOUD_REGION` must be explicitly cleared or pinned to
  `us-east-1` as well**: `_get_config()` reads `CLOUD_REGION` first and only falls back to
  `AWS_REGION` (`handler.py:589-590`), so an inherited `CLOUD_REGION` in the runner's environment
  would silently defeat the region isolation. Neither Q3 nor the existing `env_vars` fixture covers
  this variable.

The single-source cases (2 and 3) are the ones that reach `_get_sns_client` and
`_create_failure_tracker`, so this is where the isolation matters. Case 1 raises at
`handler.py:265` before either is called.

**Forbidden strings (FR-007's enumeration, five classes).** Asserted per record, each on its own:
the full ARN value; the prefix `arn:aws:secretsmanager`; the account identifier `218795110243`
alone; the region `eu-west-2` alone; and the environment or secret path segment
`preprod/sentiment-analyzer` alone. The random suffixes `AbCdEf` and `GhIjKl` are added as a
sixth for completeness. A single-marker check on the prefix would pass while the account
identifier leaked by itself, which is why the enumeration is the operative part of SC-001.

**Assertion surface (FR-007, closes the false-negative edge case).** For each captured record the
haystack is built from `record.getMessage()` **plus every value in `record.__dict__`**, not from
`caplog.text`. Probe result recorded in research.md D4: with the current unfixed code
`caplog.text` does not contain the ARN while `record.tiingo_secret_arn` holds it in full, so a
rendered-text assertion passes against unfixed code and proves nothing. A helper in the test
module builds that haystack once and every test uses it.

**Cases.**

1. Both credentials unavailable: `get_api_key` patched to return `None` for both ARNs. Assert a
   record at `ERROR` exists, that its message contains the literal `Tiingo` and the literal
   `Finnhub` (FR-002), and that it is clean against the full enumeration.
2. Tiingo only unavailable: `get_api_key` given a `side_effect` keyed on the ARN argument so it
   returns `None` for the Tiingo ARN and a key for the Finnhub ARN. Assert the `WARNING` record
   still names Tiingo and is clean against the enumeration, including its structured attributes.
3. Finnhub only unavailable: mirror of case 2.
4. Outer exception path (Acceptance Scenario 4): with both credentials unavailable the
   `RuntimeError` propagates to the `except` at line 572, which logs via
   `get_safe_error_info(e)`. That helper returns `{"error_type": ...}` only, so the record is
   clean by construction, but the test pins it so a future change to either the helper or the
   exception message cannot reintroduce the leak silently.
5. Sweep: assert **every** record captured across the whole invocation in case 1 is clean, not
   just the three targeted ones. Cheap, and it catches a leak that migrates to a fourth site.

**Mechanics.** Follow the existing pattern in `test_handler.py`: `@mock_aws`, the `env_vars`
fixture shape with the new ARNs, `_create_table_with_gsi` plus one active configuration so the
handler reaches line 249, and `patch` on `src.lambdas.ingestion.handler.get_api_key`,
`.TiingoAdapter`, `.FinnhubAdapter`, `._get_sns_client`, `.emit_metrics_batch`. The handler logger
is `src.lambdas.ingestion.handler` with `propagate` left at default, so
`caplog.at_level(logging.WARNING, logger="src.lambdas.ingestion.handler")` captures cleanly. The
`reset_caches` autouse fixture from `test_handler.py` must be duplicated in the new module,
otherwise `_active_tickers_cache` leaks between modules.

### Verification procedure

Local, before push:

```bash
source .venv/bin/activate
pytest tests/unit/lambdas/ingestion/ -v          # new module green, existing module unchanged
make validate                                    # ruff + bandit + semgrep (constitution §10)
```

Closure evidence, after merge, once a default-branch analysis has run on a commit that includes
the change. Keyed on path plus rule, never on the numbers 148, 149, 150:

```bash
gh api "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?state=open&per_page=100" \
  --jq '.[] | select(.rule.id == "py/clear-text-logging-sensitive-data")
        | select(.most_recent_instance.location.path == "src/lambdas/ingestion/handler.py")
        | {number, state, fixed_at, line: .most_recent_instance.location.start_line}'
```

Empty output satisfies SC-002. Any number returned, including one that did not exist before, is a
survivor under Acceptance Scenario 2 and is worked, not dismissed as unrelated.

For SC-002a, re-query without the `state` filter and read `fixed_at` on each of 148, 149 and 150.
Non-null and dated at or after the change means repaired. `state` of `dismissed` or `closed` with
`fixed_at` null does not count.

For SC-005, run the same query filtered to `src/lambdas/shared/secrets.py` and to
`src/lambdas/shared/auth/oauth_state.py` before and after, and diff. Alert 144 must be untouched;
alerts 22 through 25 must still read `dismissed` with `fixed_at` null; no new number may appear on
`secrets.py`.

Do not accept a green PR CodeQL check as closure evidence (SC-002). The useful inverse still
holds: because this change edits the exact flagged lines, the diff-informed PR result is directly
informative, so an alert that survives the PR run is a genuine survivor worth investigating
immediately rather than waiting for the branch analysis.

### Terminal states

- **DONE**: tests green, zero open alerts of the rule at the handler path on the default-branch
  analysis, SC-005 diff clean.
- **DONE (dismissed)**: a survivor exists, is dismissed as a false positive with the FR-009
  three-element justification from `codeql-logging-convention.md`, SC-003 satisfied by the
  dismissal comment.
- **PENDING-BRANCH-ANALYSIS** (FR-008b): the code change and the FR-007 tests are complete and
  green, but no default-branch CodeQL analysis on a commit containing the change exists yet. This is
  the **expected ending of implementation**, not an edge case, because SC-002 and SC-002a are only
  evaluable after the change reaches the default branch and this agent tree performs no git
  operations. Reaching this state requires recording the exact verification query above (the `gh api`
  block under "Closure evidence") so the check is mechanical when the analysis lands; the query in
  this plan satisfies that, and no separate artifact is required. Per FR-008b this is reported as
  neither done nor failed.
- **BLOCKED-ON-OWNER** (FR-008a): a survivor exists **and** a read-only capability probe shows the
  implementing agent cannot dismiss it. The probe is mandatory and must run before any dismissal is
  attempted, because a dismissal that succeeds mutates alert state and cannot be cleanly reverted,
  which SC-005 treats as a breach. The probe is `gh auth status` (token scopes) read together with
  `gh api repos/traylorre/sentiment-analyzer-gsk --jq '{visibility, permissions}'`. **A missing
  `security_events` scope alone does not establish the block**: that scope is required only for
  private repositories, this repository is public, and `public_repo` (which `repo` includes) plus a
  push-or-above role suffices. Probed 2026-07-30 the local environment satisfies this, so
  `BLOCKED-ON-OWNER` is not the expected outcome. If the probe does show the permission absent,
  write `specs/001-ingestion-arn-logging/dismissal-handoff.md` carrying the observed alert numbers,
  the exact justification text per alert, and the exact `gh api` call to apply each. The code change
  is independently complete and mergeable at that point. Per FR-008a this is reported as blocked,
  never as done and never as failed.

`PENDING-BRANCH-ANALYSIS` and `BLOCKED-ON-OWNER` are distinct: the first means no observation is
possible yet, the second means a survivor has already been observed and permission to act on it is
absent.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Constitution §9 requires a `docs/reference/TECH_DEBT_REGISTRY.md` entry for a security finding accepted with documented criteria. If FR-008 fires and an alert ends dismissed rather than repaired, that is such an acceptance, and no registry entry will be written. | The registry exists (`TD-001` through `TD-023`); the constitution's flat path is stale. Two reasons the entry is not written here. First, the trigger is conditional on the dismissal branch, which is only knowable after a default-branch analysis, so it cannot be evaluated during implementation (FR-008b). Second, FR-013 locks the writable set to `src/lambdas/ingestion/handler.py`, its tests and this feature's spec directory; the shared registry is outside it, sibling `001-ruff-bump-forward` task T016 already claims the next sequential identifier, and three sibling agents share this worktree. | Writing the registry entry anyway breaches FR-013 and races the sibling for `TD-024`. The mitigation kept: the justification is recorded twice, in the GitHub dismissal comment (FR-009, SC-003) and in `codeql-logging-convention.md` under this feature's directory (FR-011, SC-006), so the acceptance is documented and discoverable, just not in the central registry. A follow-up registry entry is carded for the owner and is a one-line addition once the alert outcome is known. |

## Carded, not done here

Recorded so they are not silently lost. All are already in the spec's Out of Scope.

- Adjacent account topology values near these sites (`sns_topic_arn`, `alert_topic_arn`) carry the
  same account identifier and are not flagged by this rule. Separate triage.
- A repository-wide lint rule blocking ARN interpolation into logging calls. The FR-007 test
  guards these three sites only.
- Making CodeQL a required status check. Today the required contexts are exactly `Secrets Scan`,
  `Lint`, `Run Tests` and `Playwright E2E Tests`.
- The `docs/reference/TECH_DEBT_REGISTRY.md` entry described in Complexity Tracking, if the
  dismissal path fires. The identifier is allocated when the entry is written, never pre-reserved
  here.

## Adversarial Review #2

Reviewer did not author any artifact under review and did not participate in Adversarial Review #1
or in the clarification session. Scope of this pass is **post-clarification drift** and
**cross-artifact consistency**, not a re-run of AR#1. Every claim below was checked against
`src/lambdas/ingestion/handler.py`, `src/lambdas/shared/logging_utils.py`,
`src/lambdas/shared/logging_config.py`, `tests/unit/lambdas/ingestion/test_handler.py`,
`docs/reference/TECH_DEBT_REGISTRY.md`, `scripts/check-banned-terms.sh`, and against the live GitHub
code scanning alerts API on 2026-07-30.

### The structural cause

The clarify stage writes its answers into `spec.md` only. It does not revisit `plan.md`,
`research.md`, `codeql-logging-convention.md` or `checklists/requirements.md`. Clarifications Q2,
Q3 and Q4 each changed a requirement that those four documents had already encoded, so each left a
stale copy behind. Q2 is the worst case: its own answer text quotes the plan's Terminal States
section as evidence of the gap and then does not fix it, so the plan was left literally documenting
the state the clarification was raised to remove.

### Findings

| # | Severity | Finding | Caused by | Stale artifact | Correction |
|---|---|---|---|---|---|
| C1 | **CRITICAL** | `codeql-logging-convention.md:132` asserted "Dismissing requires `security-events: write`." That is false for this repository and it directly contradicts the spec, which was corrected: `spec.md:114` (Assumption) and `spec.md:270-280` (Q2) both establish that `security_events` is a **private**-repository requirement and that `public_repo`, which `repo` includes, suffices here. This is the one document feature `001-oauth-provider-taint` inherits by citation, and its token carries the same scope list (`gist`, `read:org`, `repo`, `workflow`, no `security_events`). Following section 5 as written, feature B reads its own scope list, concludes it is blocked, and terminates in `BLOCKED-ON-OWNER` while holding the permission it needs. The convention would have propagated the exact error the spec caught and corrected. | Q2 | `codeql-logging-convention.md:132` vs `spec.md:114,270-280` | **Fixed.** Section 5 rewritten. The scope claim is corrected, the "missing `security_events` alone does not establish the block" trap is stated explicitly, and the read-only probe (`gh auth status` plus repository visibility and permissions) is made mandatory with the reason a dismissal-attempt probe is unacceptable. |
| H1 | **HIGH** | `plan.md` Terminal States listed exactly three states and omitted `PENDING-BRANCH-ANALYSIS`. FR-008b is therefore a spec requirement with **no reachability from the plan at all**, and the plan asserted a closed set of endings that excludes the one the implementation will actually hit. Q2's own answer names this section as the evidence for the gap. | Q2 | `plan.md:255-266` vs `spec.md:91` (FR-008b) | **Fixed.** `PENDING-BRANCH-ANALYSIS` added as a first-class terminal state, marked as the expected ending, with the FR-008b recording obligation pointed at the plan's existing `gh api` block so no new artifact is implied. A closing sentence distinguishes it from `BLOCKED-ON-OWNER`. |
| H2 | **HIGH** | `plan.md:262` keyed `BLOCKED-ON-OWNER` on lacking `security-events: write` and carried no capability probe. Same false premise as C1, plus the omission of FR-008a's hard requirement that the permission be determined by a read-only probe and never by attempting a dismissal. An implementer following the plan alone would either self-block wrongly or probe by attempting, which SC-005 makes a breach. | Q2 | `plan.md:262` vs `spec.md:90` (FR-008a) and `spec.md:114` | **Fixed.** Rewritten with the mandatory probe, the two concrete commands, the public-repository correction, and the note that `BLOCKED-ON-OWNER` is not the expected outcome on this environment. |
| H3 | **HIGH** | `research.md` D7 carried the same false `security-events: write` premise, described only one terminal state, and mentioned no probe. Research is the document the plan cites to avoid re-deriving decisions, so a stale D7 re-arms C1 and H2 even after they are fixed downstream. | Q2 | `research.md:187-197` vs `spec.md:90,91,114` | **Fixed.** D7 retitled and rewritten to cover both states, to record the corrected permission model explicitly as a decision that was gotten wrong and why, and to state the read-only probe constraint. |
| H4 | **HIGH** | Q4 widened FR-013 to carve out `specs/001-ingestion-arn-logging/`. `plan.md` was left internally contradictory: `plan.md:31` (Constraints) and `plan.md:78` ("Only two files are writable under FR-013") kept the pre-Q4 two-file reading, while `plan.md:272` (Complexity Tracking) already used the widened form. An implementer reading the narrow statement refuses to write `dismissal-handoff.md`, which is precisely the failure Q4 was raised to close, and the plan contradicts itself about it. | Q4 | `plan.md:31` and `plan.md:78` vs `plan.md:272` and `spec.md:96` (FR-013) | **Fixed.** Both sites restated with the directory carve-out and a pointer to Q4. |
| H5 | **HIGH** | Q3 added a fixture-isolation constraint to FR-007 covering `SNS_TOPIC_ARN`, `ALERT_TOPIC_ARN` and `AWS_REGION`. The plan's Test design, which is the operative instruction the implementer follows, justified **only** the region choice and never stated the account-identifier constraint. The plan then told the implementer to follow "the `env_vars` fixture shape" (`plan.md:210`), which does not set `ALERT_TOPIC_ARN` at all. A fixture that sets `ALERT_TOPIC_ARN` using account `218795110243` makes every account-identifier assertion fail for a reason unrelated to the secret ARN, and a passing assertion stops being evidence. | Q3 | `plan.md` Test design (fixture paragraph) vs `spec.md:88` (FR-007) | **Fixed.** A "Fixture isolation" subsection added stating the constraint per variable, plus the note that case 1 raises at `handler.py:265` before the SNS path and cases 2 and 3 are where it matters. |
| H6 | **HIGH** | `codeql-logging-convention.md` had no terminal state for "cannot yet verify". Q2 called that hole "the larger one" for this feature; the convention passes the identical hole to feature B, whose closure criteria are keyed to the same default-branch analysis and which will finish implementation in exactly the same unclassifiable position. | Q2 | `codeql-logging-convention.md` section 5 vs `spec.md:91` (FR-008b) | **Fixed.** Section 5 split into 5a `PENDING-BRANCH-ANALYSIS` and 5b `BLOCKED-ON-OWNER`, written generically so feature B can cite it without substitution beyond its own path. |
| M1 | MEDIUM | `research.md:130` gave the second fixture ARN as `...:secret:finnhub-GhIjKl` followed by a prose arrow, missing the `preprod/sentiment-analyzer/` path segment. It contradicts `plan.md:175` and defeats D5's own stated rationale at `research.md:141-145`, which is that the existing fixture is rejected precisely because it "has no environment or secret path segment, so one of the five required classes has nothing to assert against". | Pre-existing, surfaced by cross-artifact comparison | `research.md:130` vs `plan.md:175` | **Fixed** (single line). Full path restored, prose arrow removed. |
| M2 | MEDIUM | `plan.md:284` (Carded) used the stale flat path `docs/TECH_DEBT_REGISTRY.md`, contradicting `plan.md:272` and Clarification Q1, which established the file is at `docs/reference/TECH_DEBT_REGISTRY.md` and that the constitution's flat path is the stale one. Q1 corrected the Constitution Check and Complexity Tracking rows and missed the Carded list. | Q1 | `plan.md:284` vs `plan.md:272` and `spec.md:219-228` | **Fixed** (single line). Path corrected and a no-pre-reservation clause added. |
| M3 | MEDIUM | `checklists/requirements.md:53` stated FR-013 as "the ingestion handler and its tests", pre-Q4. The checklist is the quality-gate record for the spec, so a stale scope statement there is a false attestation, not just a stale note. The checklist also carries no note at all about the clarification session or FR-008b. | Q4 | `checklists/requirements.md:53` vs `spec.md:96` | **Partly fixed** (single line). Scope statement corrected. The missing clarification-session note is left recorded, not written, since the checklist is a Stage 1 artifact and adding sections to it is out of this pass's remit. |
| M4 | MEDIUM | Q3's isolation reasoning, and therefore FR-007's constraint list, omits `CLOUD_REGION`. `_get_config()` at `handler.py:589-590` reads `CLOUD_REGION` first and only falls back to `AWS_REGION`, so an inherited `CLOUD_REGION` in the runner's environment silently defeats the region isolation that Q3 relies on. The existing `env_vars` fixture does not set or clear it. | Q3 (incomplete answer, not drift) | `spec.md:88` (FR-007 names three variables) | **Fixed in the plan only** (the plan's new Fixture isolation subsection requires `CLOUD_REGION` be cleared or pinned). FR-007's enumeration in `spec.md` still names three variables rather than four. Recorded, not edited, because `spec.md` is the clarification stage's output and amending its requirement text is the owner's call. |
| M5 | MEDIUM | FR-008b (`spec.md:91`) requires "the exact verification query from the plan to be recorded" without saying **where**. Read literally it implies a new artifact; read loosely it is already satisfied by the plan. Ambiguity in the reaching-condition of a terminal state is the same defect class FR-008a was added to fix. | Q2 | `spec.md:91` | **Resolved in the plan** by stating that the plan's own `gh api` block satisfies the recording obligation and no separate artifact is required. The spec wording is left as-is. |
| L1 | LOW | `spec.md:240` (Q1) says "both features would claim `TD-024`". Three sibling specs currently contain `TD-024`: `001-oauth-provider-taint`, `001-codeql-coverage` and (per Q1's own citation of task T016) `001-ruff-bump-forward`. The contention is worse than stated, which strengthens rather than weakens Q1's conclusion. | Q1 | `spec.md:240` | Recorded, not fixed. The conclusion is unaffected. |
| L2 | LOW | `research.md:125` says "Six explicit forbidden strings", `plan.md` says five classes plus a sixth for completeness, and FR-007 enumerates five. All three are reconcilable (the suffix is the sixth) but three phrasings of one enumeration invite an implementer to assert the wrong count. | Pre-existing | `research.md:125` vs `plan.md:178-183` vs `spec.md:88` | Recorded, not fixed. No behavioural difference. |

### Checks run that found nothing

Recorded so a later reviewer does not repeat them.

- **Banned terms in this feature's directory**: clean. No occurrence of any term on the
  `scripts/check-banned-terms.sh` list under `specs/001-ingestion-arn-logging/`.
- **`plan.md` line 21 placeholder**: not applicable here. This plan's Technical Context begins at
  line 22 with `Primary Dependencies` filled in at line 25, so the template's seeded placeholder was
  never inherited.
- **Success criteria keyed on alert numbers**: SC-002 and the plan's verification query are keyed on
  path plus rule id, correctly. SC-002a names 148, 149 and 150 but only as a companion
  anti-fraud check on `fixed_at`; it cannot be used to claim success on its own. No violation.
- **Tests that would pass on unfixed code**: the plan's assertion surface is
  `record.getMessage()` plus every value in `record.__dict__`, not `caplog.text`. Correct, and D4
  records the probe that proves it matters. One implementation note for the implementer, not a
  finding: `record.__dict__` holds non-string values, so the haystack builder must coerce with
  `str()` or the membership test will raise.
- **Overstated `extra` impact**: none found. `spec.md:16`, `research.md` D3 and the plan all
  correctly separate the definitely-rendered site 1 from the two latent `extra` sites, and none
  claims the latter reach CloudWatch today.
- **Tech-debt id pre-reservation by this feature**: none. Both mentions of `TD-024` in this
  feature's artifacts are arguments for *not* claiming it.
- **Live alert state**, queried 2026-07-30: alerts 148 (line 264), 149 (271) and 150 (276) open at
  `src/lambdas/ingestion/handler.py`, all with `fixed_at` null; alert 144 open at
  `src/lambdas/shared/auth/oauth_state.py:104`. Matches every artifact's claim.
- **Handler line references**: `error_msg` at 259-265, `raise` at 265, warnings at 269-272 and
  274-277, `_get_sns_client` at 280, outer `except` at 572 with its `logger.error` at 573. All plan
  references check out.
- **`get_safe_error_info` returns type only**: confirmed at
  `src/lambdas/shared/logging_utils.py:106-131`. The plan's case 4 reasoning holds.
- **Logger propagation**: `handler.py:119-120` uses `logging.getLogger(__name__)` with `propagate`
  at its default, and `configure_lambda_logging` sets levels only. `caplog` captures cleanly, as the
  plan states.

### Gate

**GATE: 0 CRITICAL, 0 HIGH remaining.**

1 CRITICAL and 6 HIGH found, all fixed by edit. 5 MEDIUM found: M1, M2 and M3 fixed as single-line
corrections, M4 fixed in the plan with the spec-side gap recorded, M5 resolved in the plan with the
spec wording left as-is. 2 LOW recorded without fix.
