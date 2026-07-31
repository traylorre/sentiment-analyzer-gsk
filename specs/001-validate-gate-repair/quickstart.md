# Quickstart: Validation Gate and Legacy-Term Checker

**Feature**: `001-validate-gate-repair` | **Date**: 2026-07-30

## Terminology Note *(inherited)*

Retired framework names are never written in this repository's specification artifacts. They are
called **legacy terms**. The authoritative list lives in one place, the checker module. Examples
below use `<TERM>` as a stand-in.

---

## Run the gate

```bash
source .venv/bin/activate
make validate
```

Allow at least five minutes. Every stage runs now, so a failing run costs the same as a passing one.
That is a deliberate trade: one run surfaces every failure, replacing the previous pattern where each
run surfaced one failure and hid the rest behind it.

Read the summary block at the end rather than scrolling for the first red line:

```text
================ validate summary ================
  format check          BLOCKING   PASS
  lint                  BLOCKING   PASS
  dependency audit      ADVISORY   reported
  static analysis       BLOCKING   PASS
  legacy terms          BLOCKING   FAIL
  test target headers   BLOCKING   PASS
  e2e race guard        BLOCKING   PASS
==================================================
```

**ADVISORY means the stage cannot fail the gate.** The dependency audit reports findings from the
open dependency-alert backlog and is tracked by a separate feature. It is labelled rather than hidden
so that its silence is never mistaken for a clean result.

Individual stages still run on their own:

```bash
make lint
make check-banned-terms
make check-test-target-headers
```

---

## The gate blocked me on a legacy term. What now?

The failure names the file, the line, the term, and a remedy. Which remedy depends on what the line
actually is, and the distinction is the whole point of the checker:

**Is the line asserting the framework is current?** Then it is a real violation. Remove the
reference. This covers application source, infrastructure, configuration, and any specification whose
present tense claims the project runs on the retired stack.

**Is the line recording that the framework was retired, or discussing it as prior art?** Then it is a
legitimate record and gets an exemption. Add a marker on the same line:

```markdown
The dashboard previously ran on <TERM>. <!-- legacy-term-ok: records the pre-migration runtime -->
```

The marker is `legacy-term-ok:` followed by a real justification. It works in any file format,
because the checker looks for the token anywhere on the line and does not care what comment syntax
wraps it:

| Format | Form |
|---|---|
| Markdown, HTML | `<!-- legacy-term-ok: reason -->` |
| Python, YAML, shell, Make | `# legacy-term-ok: reason` |
| TypeScript, JavaScript | `// legacy-term-ok: reason` |

**The justification is enforced, not decorative.** A marker with nothing after the colon does not
exempt anything. Write the reason a reviewer would need, not the word "needed".

If this reads like the existing `# pragma: allowlist secret` convention, that is intentional. Same
shape, same review posture.

### Correct or exempt is not the whole rule

Those two cover most lines and they covered barely half of the original corpus. The remaining kinds
have dispositions of their own, and a reviewer who knows only the first two reaches the wrong answer
on them: an example in a template reads as "not asserting anything, so exempt it", which leaves the
template generating fresh matches forever. The full rule, one row per kind actually encountered:

| The line | Disposition | Why not something else |
|---|---|---|
| asserts the framework is current | correct it | It is simply false. This is the only kind that is a defect in the ordinary sense. |
| records the retirement, or discusses it as prior art | exempt it | Correcting it would delete the record. This is what the marker is for. |
| names the framework without asserting anything: a heading, a research question, a code sample | rewrite so the sentence stays true with the name removed | Do not substitute the current stack here. A superseded research document that suddenly reports findings about a framework nobody researched is worse than the stale name it replaced. |
| is an example or a placeholder in a template | scrub the example | Exempting hides it; the template keeps emitting the term into every document generated from it. Fix the source, then the copies. |
| documents this policy and reproduces the terms in order to discuss them | reword to describe rather than reproduce | An exemption would work and is the wrong habit: a document about banned terms that spells them out is the most copy-pasted place in the repository. |
| is a path recorded inside a generated file | rename the path | Covered below. There is no exemption mechanism for generated files, deliberately. |

Where a line is genuinely two of these at once, the earlier row wins: an assertion that also happens
to be a heading is still an assertion.

---

## When not to use an inline marker

**Machine-generated files.** If a tool rewrites the file, an inline marker is destroyed on the next
regeneration and the gate goes red again with no obvious cause. There is no exemption mechanism for
these, deliberately. Fix the cause instead:

> Determine whether the legacy term is in the file's **content**, or merely in a **path** the file
> records. If it is a path, rename the path.

That distinction is not academic. Every generated-file match this repository has ever had was the
second kind: a secrets baseline recording the path of a badly named directory, in a file whose
contents held no legacy term at all. A whole second exemption mechanism was designed to accommodate
those three matches before anyone checked which kind they were. Renaming the directory removed them
and the mechanism together.

If you find a legacy term genuinely present in generated **content**, that is a case this project has
not seen. It needs FR-013 amended to re-add a path-scoped mechanism, which is a spec change, not a
config edit.

**Application source. The checker refuses these.** A marker under `src/`, `infrastructure/`, or
`frontend/src/` is an error in itself, and the failure names the marker rather than the term:

```text
  ERROR: exemption markers are not permitted under src/.
  remedy: remove the reference. Exemptions record that a framework was
          retired; this tree holds code, not records.
```

This is not a checker bug and there is no syntax that makes it work. Under the adjudication rule
those trees hold code rather than records of a retirement, so no legitimate exemption can exist in
them. If you are reaching for a marker in `src/`, the answer is to remove the reference.

---

## Audit the exemptions

```bash
make audit-exemptions
```

Lists every exemption in the repository with its justification, plus a total. Mirrors the existing
`make audit-pragma`.

Check this in review when a change adds one. Exemptions are meant to be rare, and a climbing count
means the adjudication rule is being applied loosely rather than that the count needs accepting.

---

## Adding a new E2E test

Every file matching `frontend/tests/e2e/*.spec.ts` or `tests/e2e/test_*.py` must declare its target
in a `Target:` line near the top. Three declarations are sanctioned:

```typescript
// Target: Customer Dashboard (Next.js/Amplify)
```

```python
# Target: Admin Dashboard (Lambda HTMX)
```

```python
# Target: Infrastructure (WAF rule set, not either dashboard UI)
```

The third exists because several tests exercise a firewall, an identity provider, a content delivery
network, or log groups, none of which belongs to a dashboard. Before this feature the guard demanded
one of the first two on every file, so those tests could only pass by declaring something untrue.

One caveat on the gate itself: **`make -n validate` no longer tells you the truth** unless the
dry-run guard is in place. The driver recipe runs under `-n` because it invokes sub-makes, and `-n`
propagates to them, so every stage dry-runs, returns success, and the summary reports a clean pass
without having run anything. Treat a dry-run summary as meaningless.

**Pick the accurate one.** This repository has confused its two dashboards in four separate
incidents, which is why the declaration is mandatory. A firewall test labelled as a dashboard test is
worse than no label, because it is the exact confusion the guard exists to prevent.

---

## Common situations

| Situation | What is happening | What to do |
|---|---|---|
| Gate passed locally, failed in CI on legacy terms | The check now runs in the required lint job. It was previously enforced nowhere. | Run `make check-banned-terms` locally and fix. The CI output is identical. |
| A term appears in a file I did not touch | Most likely the plan template placeholder, or a superseded spec. | Find its row in "Correct or exempt is not the whole rule" above. Those two are not the only dispositions, and a template placeholder in particular is neither. |
| Marker added and the checker still fails | The justification is empty, or the marker is on a different line from the match. | Same line, non-empty reason after the colon. |
| Checker reports a configuration failure | It is failing closed on an unusable configuration rather than reporting a false pass. | Read the named cause. Do not work around it: a checker that passes when it cannot see is the defect this feature removed. |
| New spec is red immediately after `/speckit.plan` | Should no longer happen. The template placeholder that caused this was the root cause fixed by this feature. | If it recurs, the template has regained an example value naming a legacy term. Fix the template, not the generated plan. |

---

## For maintainers of the checker

- Term list is authoritative in the checker module and nowhere else. The module excludes its own file
  from the scan for that reason.
- Terms are matched case-insensitively as patterns, not literals. One existing term contains
  characters that behave as wildcards. This is documented at the array and preserved deliberately.
- Exclusions compare against normalised repository-relative paths only, never against file content.
  The previous version filtered the formatted output line, so any file mentioning an excluded path in
  its text suppressed its own finding. Keep path and content as separate values and that bug cannot
  return.
- An empty exclusion list must never produce a pass. The previous version reported success on a
  repository with seventeen violations when the list was emptied.
- Tests live in `tests/unit/scripts/test_check_banned_terms.py`. The checker runs in a required CI
  job and fails closed, so a defect in it blocks every merge in the repository. Do not change
  matching or exclusion behaviour without a test.
