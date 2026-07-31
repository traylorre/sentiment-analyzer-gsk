# Convention: handling CodeQL `py/clear-text-logging-sensitive-data`

**Owner**: feature `001-ingestion-arn-logging` | **Date**: 2026-07-30
**Satisfies**: FR-011, SC-006. Written to be cited by `001-oauth-provider-taint` and by any later
feature working this rule, so nobody re-derives it.

This document is self-contained on purpose. A reader who has never seen the feature should get the
decision rule, the dismissal wording, and the verification caveat from this file alone.

---

## 1. Decision rule: rewrite or dismiss

Work the list in order and stop at the first branch that applies.

**Step 1. Is the flagged value's meaning knowable at the call site without reading it?**

If the site is `if not tiingo_adapter:` then yes, the author already knows the source is Tiingo.
Write the literal and drop the value entirely. This is the preferred outcome and it is what
`001-ingestion-arn-logging` did at all three of its sites. No helper, no sanitizer, no truncation.

**Step 2. If not, can the record carry a non-derived discriminator instead?**

A counter, an enum, an error type, an index into a fixed list. Anything that identifies the failing
case without being a function of the sensitive value. Prefer this over any transformation of the
value.

**Step 3. Only if neither works, sanitize.**

Be aware this shape has failed in this repository. `0e7a375` (PR #321, 2025-12-09) introduced an
intermediate sanitized variable and CodeQL still flagged it. `ebcc2f4` (PR #322, same day) removed
every secret-derived value from the log context and that is the shape that took. Read the outcome
from `fixed_at`: alerts 22 through 25 are the four sanitize-in-place sites and their `fixed_at` is
null to this day; alerts 26 and 27 are the two stripped sites and both carry a non-null `fixed_at`.
A sanitized value is still a value derived from the sensitive one, so expect the alert to survive
and expect to land in step 4.

**Step 4. Alert survives a genuine remediation. Now dismiss, with the wording in section 2.**

Never suppress with an inline comment as a first move (constitution §10), and never rename a
variable to dodge the detector. Both read as detection avoidance, and neither is a fix.

**Always**, whichever branch you land on: leave an inline comment at the site naming the rule id and
the reason the value was removed. Unconditionally, including on sites where the fix worked cleanly.
Without it, a later refactor reintroduces the interpolation and nothing objects.

---

## 2. Dismissal wording pattern

Three elements. All three are required.

1. **What the value actually is.** State that it is a resource identifier, not a credential value.
   Name it.
2. **Which convention was applied.** Name the shape used: value stripped from message, context and
   exception; or discriminator substituted; or sanitized to a bare name.
3. **Why CodeQL still reports the flow.** This element is new. None of the seven existing dismissals
   of this rule in this repository states it, and their silence is exactly what makes them
   impossible to re-evaluate later. Say what the engine is still seeing: the taint source reaching a
   sink through a path the remediation did not sever, an inter-procedural flow through a helper, a
   dataflow the engine models conservatively.

Template:

> The value reaching this sink is `<name>`, an AWS resource identifier (`<what it identifies>`), not
> a credential value. It contains no secret material; possessing it does not grant access to
> anything. Convention applied per `specs/001-ingestion-arn-logging/codeql-logging-convention.md`:
> `<step 1 / 2 / 3 shape, stated concretely>`. CodeQL continues to report the flow because
> `<concrete reason: e.g. the engine models the whole return value of get_secret() as tainted and
> the remaining reference is inside the same dataflow path, regardless of what is now logged>`.
> Re-evaluate this dismissal if `<the condition that would make it wrong>`.

Do not paste the template as-is. The third element and the re-evaluation trigger must be specific to
the site, otherwise the dismissal is no better than the seven that came before it.

---

## 3. Verification caveats

Three traps. Each has burned somebody in this repository.

**Trap 1: `state` is not `fixed_at`.** Dismissal is sticky and survives a later genuine repair, so
`state` conflates "a human dismissed this" with "the code was fixed". Alerts 26 and 27 read
`dismissed` and carry a non-null `fixed_at`, meaning repaired. Alerts 22 through 25 also read
`dismissed` and have `fixed_at` null, meaning never repaired. Key every claim about repair on
`fixed_at`, and require it to be dated at or after the change.

**Trap 2: alert numbers are not stable identities.** CodeQL can close a number as fixed and open a
brand new number at the same location in the same run. Alert 117 on
`src/lambdas/shared/auth/oauth_state.py` carries `fixed_at` `2026-01-20T22:34:56Z` and alert 144 on
the same file was created at that identical timestamp. Alerts 107, 110 and 111 spawned and closed
within hours during the 2025-12-09 secrets remediation. Therefore: **key success on path plus rule
id, never on the alert number**. "Alert N is no longer open" is not the criterion. "Zero open alerts
of this rule at this path" is.

**Trap 3: a green PR CodeQL check is not evidence.** CodeQL runs diff-informed analysis on pull
requests here. PR runs report `results_count: 0` while the corresponding `refs/heads` run reports 9;
PR #990 was green with five alerts open. Read closure from the default-branch analysis or from the
code scanning alerts API, on a commit that includes the change. The useful inverse: when the change
edits the exact flagged lines, the diff-scoped PR result is directly informative, so a survivor there
is a real survivor.

Query shape:

```bash
gh api "repos/<owner>/<repo>/code-scanning/alerts?state=open&per_page=100" \
  --jq '.[] | select(.rule.id == "py/clear-text-logging-sensitive-data")
        | select(.most_recent_instance.location.path == "<path>")
        | {number, state, fixed_at, line: .most_recent_instance.location.start_line}'
```

Empty output is the pass condition. Drop `state=open` and read `fixed_at` per number to distinguish
repaired from dismissed.

---

## 4. Blast radius rule

Do not edit a file that carries alerts of this rule unless that file is your feature's target.
Editing lines that hold a live-behind-dismissal finding (`state: dismissed`, `fixed_at: null`) can
re-fingerprint it into a fresh open alert. That is what happened to `src/lambdas/shared/secrets.py`
on 2025-12-09, and it is why `001-ingestion-arn-logging` refused to reuse that file's sanitizing
helper even though reuse looked like the tidier option.

Known live-behind-dismissal sites as of 2026-07-30: alerts 22, 23, 24 and 25 on
`src/lambdas/shared/secrets.py`. Treat that file as off limits unless it is your target.

---

## 5. Two states that are neither done nor failed

### 5a. You cannot yet verify: `PENDING-BRANCH-ANALYSIS`

This is the normal ending, not an edge case. Closure is read from the default-branch analysis
(section 3, trap 3), and no such analysis can exist while the change sits on a feature branch. So at
the end of implementation the feature is not `DONE` (closure unevaluated), not `DONE (dismissed)` (no
survivor observed yet), and not blocked on permission (nothing has been attempted).

Terminate in `PENDING-BRANCH-ANALYSIS` when the code change and its regression tests are complete
and green but no qualifying analysis exists. Record the exact verification query from section 3,
filled in with your own path, so the check is mechanical the moment the analysis lands. Report it as
neither done nor failed.

### 5b. You cannot dismiss: `BLOCKED-ON-OWNER`

**Check the permission with a read-only probe. Never establish it by attempting a dismissal**, which
mutates alert state and cannot be cleanly reverted.

The probe is the token's scope list read together with the repository's visibility and the actor's
repository permissions:

```bash
gh auth status                                  # token scopes
gh api repos/<owner>/<repo> --jq '{visibility, permissions}'
```

**A missing `security_events` scope is not by itself a blocker.** GitHub's
update-code-scanning-alert endpoint requires `security_events` only on **private** repositories. On a
**public** repository `public_repo` suffices, and the `repo` scope includes `public_repo`. This
repository is public, so a token carrying `repo` plus a repository role of push or above can dismiss.
Probed on 2026-07-30 the local environment satisfies exactly that, which means
`BLOCKED-ON-OWNER` is **not** the expected outcome here. Reading `gh auth status` alone and
concluding "no `security_events`, therefore blocked" is the specific mistake this paragraph exists to
prevent; `001-ingestion-arn-logging` made it once and corrected it in its Clarification Q2.

If the probe genuinely shows the permission absent, do not leave the feature hanging and do not
report it failed. Terminate in `BLOCKED-ON-OWNER` and write a handoff artifact into your feature's
directory carrying: the exact alert numbers observed at the path, the exact justification text for
each (section 2), and the exact API call or UI steps to apply them. The code change is independently
complete and mergeable at that point. Only the dismissal is outstanding.

The two states are distinct. `PENDING-BRANCH-ANALYSIS` means no observation is possible yet.
`BLOCKED-ON-OWNER` means a survivor has already been observed and permission to dismiss it is
absent.
