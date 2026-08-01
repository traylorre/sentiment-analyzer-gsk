# Phase 0 Research: Close CodeQL alert 144 (OAuth provider taint)

**Feature**: `001-oauth-provider-taint` | **Date**: 2026-07-30 | **Plan**: [plan.md](plan.md)

This file exists to satisfy User Story 3 and FR-012. Its test is US3's **first** acceptance
scenario: a reader who has never opened this repository's commit history should be able to state,
from this file alone, which approaches were tried against this rule, which one worked, and how that
was verified.

US3 gained a **second** acceptance scenario at Stage 4 clarification (Q1), and this file cannot
satisfy it: a reader who has only the source file in front of them must be warned at the sink
itself. That obligation lives in the code, as **FR-013**, and is discharged by the mandatory inline
comment described in Decision 5 below, not by anything in `specs/`. The comment points back here,
so this file is the destination of that warning rather than a substitute for it.

There were no NEEDS CLARIFICATION markers in the technical context to resolve. spec.md, after
Adversarial Review #1, fixes the approach to a single form and leaves no technology choice open. What
follows is therefore a decision record and an evidence ledger rather than an options study.

---

## Decision 1: Remove every `provider`-derived value from the log `extra` context

**Decision**: Delete the `"provider": safe_provider` entry from the `extra` dict in
`store_oauth_state()`, and delete the `safe_provider` sanitizer assignment that fed it. Substitute
nothing.

**Rationale**: This is the only shape with in-repo evidence of closing
`py/clear-text-logging-sensitive-data`. Commit `ebcc2f4` (PR #322, merged 2025-12-09 22:18:14Z)
states the finding in its own message: the analyzer "traces taint through function calls, so
intermediate variables still trigger alerts. The only solution is to avoid using ANY value derived
from `secret_id` in the `logger.info()` extra context." Alerts 110 and 111 both carry
`fixed_at = 2025-12-09T22:19:20Z`, one minute after that merge.

**Alternatives considered and rejected**:

| Alternative | Why rejected |
|---|---|
| Sanitize in place (`str(x).replace(...)[:200]`) | Already applied to this exact line by `8424cbd` and it relocated the finding rather than clearing it (see Ledger B). It cannot work in principle: in the analyzer's Python dataflow model, `replace()` and slicing propagate taint rather than removing it, as this repo's own `sanitize_for_log()` docstring states. It also addresses a different rule, `py/log-injection`. |
| Route through an intermediate variable | Tried by `0e7a375` (PR #321) and refuted the same day; see Ledger A. |
| Substitute a literal chosen by an allowlist membership check | Deleted for cause by Adversarial Review #1 (CRITICAL 2). Its sole rationale was preserving a Google-versus-GitHub distinction in the logs, and that distinction does not exist (Decision 2). Unproven at a cost: `ebcc2f4` proved that *removing* a derived value closes the rule, never that *a literal selected by branching on the tainted value* counts as removal. If the analyzer models implicit or control-flow taint here, that form still flags, and trying it first means editing this sink twice. |
| Inline **suppression** comment (`# nosec`, `# noqa`, `# lgtm`, a CodeQL pragma), rule-level suppression, severity downgrade, file exclusion | Forbidden by FR-010. Note this is not the same artefact as the mandatory **documentation** comment required by FR-013; see Decision 5, which states the disjointness. |
| Do nothing and dismiss immediately | Forbidden by FR-007 and by the sibling convention. A proven in-repo remedy must be exhausted before a dismissal is recorded. |

**One honest caveat about the precedent.** `ebcc2f4` did not delete its value outright. It relocated
the sanitized identifier into a raised exception message, a sink the analyzer tolerates.
`store_oauth_state()` has no raise anywhere on its path (it is `put_item`, log, return), so there is
no equivalent relocation target and the deletion here is strictly more aggressive than the precedent
it cites. Given Decision 2 and Decision 3, that costs nothing.

---

## Decision 2: The removed value has no operational consumer, so nothing is substituted

**Decision**: Treat the deletion as lossless. Do not add a replacement key, a boolean, or a counter.

**Rationale**: `oauth_state.py` logs through the standard library logger
(`logging.getLogger(__name__)`). No handler or formatter in this repository renders `extra` keys.
`src/lambdas/shared/logging_config.py` is documented and implemented as a level-setter and by its own
docstring "never attaches handlers or formatters". The root handler is the Lambda runtime's default,
which formats `record.getMessage()` and nothing else.

Captured production output confirms it rather than merely predicting it. The post-deploy evidence at
`specs/001-lambda-log-visibility/evidence/post-deploy/logshape-dashboard.json` records three real
emissions of this exact call on 2026-07-27, and every one is bare:

```text
[INFO]	2026-07-27T16:54:55.291Z	ccc0f079-351f-464c-85ec-7082529fbe36	OAuth state stored
```

No `provider`, no `has_user_id`, no `ttl_seconds`. **The logs do not today distinguish a Google
authorize from a GitHub authorize on this line, and never have.** Any requirement to preserve that
distinction would be protecting a capability that does not exist.

Independently: no metric filter, alarm, dashboard or runbook consumes this line. The repository's
only log metric filter is `dashboard_import_errors`
(`infrastructure/terraform/modules/monitoring/main.tf:30`).

**Standing assumption this rests on**: no consumer of the `extra` dict is introduced concurrently. If
a structured-JSON formatter were ever attached to the root handler, the provider distinction would
still be absent from this line, and restoring it would be a new feature with its own analysis of
this rule.

---

## Decision 3: The information is not lost from the system

**Decision**: Accept the value's absence from the log without compensating storage.

**Rationale**: `provider` is written into the DynamoDB item at `oauth_state.py:87`, inside the
`put_item` call eight lines above the log site, and FR-003 freezes that write. It is also carried on
the returned `OAuthState`. Anyone who needs to know which provider a state belongs to reads the item,
which is where they would have had to look anyway given Decision 2.

---

## Decision 4: Anchor success on the path and the rule id, never on numbers

**Decision**: Key success on **zero open findings for rule
`py/clear-text-logging-sensitive-data` at path `src/lambdas/shared/auth/oauth_state.py`**. Never on
alert 144 disappearing, never on a line window, and not on a function either. Function attribution is
performed on a survivor only, to decide ownership, with the function's line bounds resolved fresh at
the analyzed commit.

**Why not function-scoped, which an earlier draft of the gate assumed.** The code scanning alerts API
exposes no function field: `most_recent_instance.location` carries `path`, `start_line`, `end_line`,
`start_column` and `end_column`. Any function attribution is therefore derived from a `start_line`,
which drags the line instability of the next two bullets back into the criterion through the side
door. Path plus rule id is the strongest identity the API mechanically supports, and it is what the
inherited convention independently settled on
(`specs/001-ingestion-arn-logging/codeql-logging-convention.md` §3, Trap 2: "Zero open alerts of this
rule at this path"). Attribution still earns its keep, just not as the gate: `validate_oauth_state()`
carries the same sanitize-in-place shape at lines 253 to 258 and is frozen by FR-004, so a survivor
there is reported rather than dismissed (FR-006a).

**Rationale for rejecting the two number-based alternatives**: both are provably wrong on this file's
own history.

- **Alert numbers**: `8424cbd` closed alert 117 and opened alert 144 in the same analysis run. A
  disappearing alert number is compatible with the disclosure surviving.
- **Line numbers**: the respawn moved the finding from line 95 to line 104, a gap of nine lines. An
  adjacency window of 99 to 109 drawn around the current sink would have missed the very precedent it
  was written to catch. This feature also deletes four lines from the middle of the function, which
  shifts every line below 99.

**Consequence for the gate**: a new alert number appearing on this path for this rule classifies as
**Refuted**, not as success. If it attributes to `store_oauth_state()` it routes to the dismissal
branch with a note that a respawn occurred; if it attributes elsewhere in the file it is reported,
not dismissed.

---

## Decision 5: Mark the sink in the source, unconditionally

**Decision**: The `logger.info()` call keeps a documentation comment naming the rule id
`py/clear-text-logging-sensitive-data` and stating why no `provider`-derived value may be added back.
It is written on every branch of the decision gate, including the branch where the fix worked
cleanly. This is **FR-013**, promoted from a plan-level choice at Stage 4 clarification (Q1).

**Rationale**: it is the only part of this feature that survives in the place the next author will
actually be reading. The failure mode US3 exists to prevent is a later refactor reintroducing the
key, and whoever writes that refactor is looking at `oauth_state.py`, not at `specs/`. This file has
already been through one such cycle: `8424cbd` re-touched this exact sink in January, apparently
unaware of the December `0e7a375` and `ebcc2f4` results recorded in Ledger A, and relocated the
finding rather than closing it. An unmarked sink is what made that possible. The obligation is not
this feature's invention either: it is the unconditional closing clause of
`specs/001-ingestion-arn-logging/codeql-logging-convention.md` §1, consumed via FR-008.

**Why it is not the thing FR-010 forbids**, which is a real question and not a rhetorical one. FR-010
forbids "an inline suppression comment as a substitute for FR-007", meaning a pragma that hides the
finding instead of dismissing it through the reviewable path. The FR-013 comment carries no
`# nosec`, no `# noqa`, no `# lgtm` and no CodeQL pragma. It changes no analyzer behaviour, hides
nothing, and substitutes for no part of the dismissal path. The two requirements partition cleanly:
FR-010 forbids suppressing the finding, FR-013 requires explaining it.

---

## Ledger A: what the repository has already tried against this rule

Every row is anchored on `most_recent_instance.commit_sha` and on `fixed_at`, not on calendar dates
and not on `state`. Both of those weaker fields have already produced a wrong conclusion in this
feature's own drafting history.

| Commit | Shape attempted | Outcome | Evidence |
|---|---|---|---|
| `0e7a375` (PR #321, merged 2025-12-09 21:40:15Z) | Route the sensitive value through an intermediate sanitized variable before logging it | **Failed**, instructively | Alerts 110 and 111 created 2025-12-09T21:38:16Z, both pinned by the API to `0e7a3752aaba49c502d0403a11544965911b8262`, at the lines that commit had just rewritten (`secrets.py:230` and `:243`) |
| `ebcc2f4` (PR #322, merged 2025-12-09 22:18:14Z) | Remove every derived value from the `extra` context; relocate the sanitized identifier into a raised exception message | **Worked** | Alerts 110 and 111 both carry `fixed_at = 2025-12-09T22:19:20Z` |
| `8424cbd` (2026-01-20) | Inline CRLF sanitization on this exact line in `oauth_state.py` | **Relocated the finding**, which is worse than no progress | See Ledger B |

**Correction on the record**: an earlier draft attributed alert 107 to `0e7a375`. It is pinned to
commit `a245d1d9` and was created 2025-12-09T08:47:23Z, roughly 13 hours before `0e7a375` was
committed. Only 110 and 111 carry `0e7a375`'s SHA. The error came from reasoning on calendar dates,
which is why this ledger cites `commit_sha`.

### Why `fixed_at` and not `state`

Dismissal is sticky and survives a later genuine repair, so `state` conflates "a human dismissed
this" with "the code was repaired". The split is causal, not circumstantial:

| Site shape | Alerts | `fixed_at` |
|---|---|---|
| Derived value removed from `extra` (`ebcc2f4`) | 26, 27, 106, 107, 110, 111 | all set |
| Sanitizer call left inside `extra` (`secrets.py:171, 186, 198, 210`) | 22, 23, 24, 25 | **null to this day**, 8 months on |

Alerts 26 and 27 read `dismissed` only because the dismissal (2025-11-24) predates the fix by two
weeks. They carry `fixed_at` regardless. The four sites that kept a sanitizer call inside `extra`
were never fixed, only annotated. That is also why the blast radius rule at
`specs/001-ingestion-arn-logging/codeql-logging-convention.md` **§4** forbids editing
`src/lambdas/shared/secrets.py`, a prohibition this feature inherits via FR-008: those four findings
are still live behind a dismissal and re-fingerprint into fresh open alerts on touch. The citation
anchors on the convention document's section rather than on a sibling requirement number, as FR-008
requires, because the sibling can renumber and this feature would not notice.

---

## Ledger B: this file has already produced a respawn

| Alert | Path:line | Created | Fixed |
|---|---|---|---|
| 117 | `oauth_state.py:95` | 2026-01-10T19:25:14Z | **2026-01-20T22:34:56Z** |
| 144 | `oauth_state.py:104` | **2026-01-20T22:34:56Z** | null |

The same analysis run closed 117 and opened 144, nine lines further down, for the same rule in the
same function. `8424cbd` did not fix this finding; it moved it, producing the appearance of progress
while the reported disclosure survived. This is the decisive precedent behind Decision 4, and it is
exact rather than merely same-day: the two timestamps are identical to the second.

---

## What remains genuinely unknown

Recorded so no later reader mistakes confidence in the remedy for confidence in the diagnosis.

1. **Why the engine classifies this value as "password".** The alert message reads "This expression
   logs sensitive data (password) as clear text." The only non-constant input is `provider`, whose
   two production call sites pass the string literals `"google"` and `"github"`. No secret, token,
   credential or user input reaches the expression. The REST API returns `code_flows` of length **0**
   for alert 144, so the taint path cannot be inspected. This feature makes no claim about the cause
   and no requirement depends on discovering it. The prior art raises confidence in the remedy; it
   does not explain the diagnosis.
2. **Whether the analyzer models implicit or control-flow taint on this sink.** Unresolved, and
   deliberately left that way: the chosen form removes the value entirely, so the question does not
   need an answer. It would have needed one under the rejected allowlist form, which is part of why
   that form was rejected.

## What a CodeQL result is worth on this repository

CodeQL is not a required status check. The required contexts are exactly `Secrets Scan`, `Lint`,
`Run Tests` and `Playwright E2E Tests`, and the rulesets API returns `[]`. No CodeQL result blocks a
merge today. The `codeql` job lives inside `.github/workflows/pr-checks.yml` (job id `codeql`, name
`Analyze`, category `/language:python`) and runs on `push` to `main` as well as on pull requests, so
default-branch analyses are produced automatically on merge.

The alert is worth closing because it is a standing open high-severity finding on the default branch,
not because it gates anything. Correspondingly, a green `Analyze` job is not evidence of closure;
only the alerts API is (FR-009).
