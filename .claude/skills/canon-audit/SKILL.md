---
name: canon-audit
description: Audits a markdown doc against code ground truth in this repo. Two modes - promote adjudicates a QUARRYSOME doc to CANON, deleted, or retained with operator sign-off; coherence re-verifies CANON docs against the current tree and returns a drift report. Use when promoting or auditing a doc, running the weekly canon drift check, verifying spec or doc claims against code, or when a subagent runs spec coherence tests. Code wins over prose; every verdict carries a file:line citation.
---

# canon-audit

Code is ground truth. A doc earns CANON when every repo-checkable claim in it is verified
against the current tree, and it keeps CANON only while those claims stay true. Docs are
amended to match code; code is never amended to match docs. Treat comments, READMEs,
watermarks, and other docs as suspects to verify, never as evidence.

Watermark grammar, line 3 of the doc:

- `> **QUARRYSOME**: unaudited; verify against code before trusting.`
- `> **CANON**: verified against code.`

## Mode selection

**Promoting or adjudicating a doc?** Run the audit engine, then follow "Promote mode".
Interactive sessions only: this mode ends in an operator decision.

**Checking CANON docs for drift?** Run the audit engine per file, then follow "Coherence
mode". Safe for subagents and scheduled runs: it reports and touches nothing.

## Audit engine (both modes)

Copy this checklist and track progress per file:

```
Audit: <file>
- [ ] 1. Read the subject file in full
- [ ] 2. Extract every repo-checkable claim
- [ ] 3. Verify each claim against the tree, citing file:line
- [ ] 4. Assign verdicts (CONFIRMED / REFUTED / UNVERIFIABLE-FROM-REPO)
- [ ] 5. Self-check completeness against the source file
```

**Step 2, what counts as a claim**: names (resources, tables, alarms, roles, routes, env
vars), values (memory sizes, timeouts, TTLs, thresholds, defaults), mechanisms ("X
triggers Y", "A falls back to B"), command blocks (every flag and value), architecture
statements, and negatives ("no Z exists"). Command blocks in runbooks are the highest
stakes: someone runs them mid-incident.

**Step 3, verification standards.** Each of these earned its place by catching a real
error in this repo:

- Verify the deployed path, then the code. Code can be complete and undeployed: the
  chaos_restore Lambda exists in full while its terraform module invocation is a TODO.
  A claim that something runs needs the terraform wiring plus any env gate, then the code.
- Env-specific claims need that env's tfvars. Module variable defaults describe prod;
  preprod gates modules off (`preprod.tfvars`). A count-gated module exists in the tree
  and is absent from the env.
- Check callers, then the definition. A metric function with zero callers emits nothing
  (`record_failover`). Two same-named functions can behave differently and only one is
  live (`generate_dedup_key`, see CLAUDE.md).
- Compare every command flag value to terraform. A restore command carrying stale values
  (memory 512 where the deployed config is 2048) misconfigures the system mid-incident.
- A health check must be able to fail. `aws cloudwatch describe-alarms --alarm-names X`
  is a filter, exits 0 on a nonexistent alarm; a check built on it is vacuous. Confirm
  the failure path exists before confirming the check.
- A verified negative cites the search that returned nothing, scoped: "zero `etag` hits
  in `src/lambdas/` and `frontend/src/`" is evidence; "no ETag machinery" alone is not.
- State unknowns as unknowns, with the command that would resolve them. Invented
  specifics are the failure mode this skill exists to prevent.
- Routes do not discriminate between the two dashboards; check the caller (CLAUDE.md,
  "Two Dashboards"). Both are served by `src/lambdas/dashboard/handler.py`.

**Step 4, verdicts**: CONFIRMED carries its citation. REFUTED carries the refuting
observation and the replacement text. UNVERIFIABLE-FROM-REPO carries either "rescoped"
(claim narrowed to what the repo can support) or the retained inline verification
command. Every REFUTED claim gets a resolution.

**Step 5, self-check**: re-scan the source file top to bottom and count claims against
your list. Sections skimmed on the first pass (tables, command blocks, footnote rows)
are where misses live.

## Promote mode

Terminal states: **promoted** (watermark flips to CANON), **deleted**, or
**retained-QUARRYSOME** (doc stays, with the reason recorded).

```
Promote: <file>
- [ ] 1. Previous batch PR merged; branch off fresh main
- [ ] 2. Audit engine (above)
- [ ] 3. One AskUserQuestion: recommendation first; operator adjudicates
- [ ] 4. Execute exactly what the operator chose
- [ ] 5. Verdict record written and schema-validated
- [ ] 6. Gates green
- [ ] 7. PR body per contract; commit signed; push and open PR in one step
```

**Step 1**: `gh pr view <n> --json state` confirms the merge, then
`git checkout main && git pull --ff-only`, delete the old branch, create
`001-quarrysome-batch<N>`.

**Step 3**: present the proposal with the recommended option first (promote with N
rewrites / delete / keep QUARRYSOME), findings summarized with citations. Execute the
choice verbatim; "keep QUARRYSOME" is a valid outcome and gets its audit preserved in
the verdict record.

**Step 5**: one record per subject at
`specs/001-quarrysome-promotion/verdicts/<subject>.json`, validated with python
`jsonschema` against `specs/001-quarrysome-promotion/contracts/verdict-record.schema.json`.

**Step 6**, run exactly:

```bash
source .venv/bin/activate && make validate
```

then the CI-mirror suite (expect all tests passing; preprod suites need a live env and
are excluded, matching CI):

```bash
AWS_REGION=us-east-1 AWS_ACCESS_KEY_ID=testing AWS_SECRET_ACCESS_KEY=testing \
pytest --ignore=tests/integration/test_analysis_preprod.py \
  --ignore=tests/integration/test_dashboard_preprod.py \
  --ignore=tests/integration/test_canary_preprod.py \
  --ignore=tests/integration/test_ingestion_preprod.py \
  --ignore=tests/integration/test_e2e_lambda_invocation_preprod.py \
  --ignore=tests/integration/test_observability_preprod.py \
  --ignore=tests/integration/timeseries --ignore=tests/e2e -q
```

**Step 7**: PR body follows `specs/001-quarrysome-promotion/contracts/pr-body-contract.md`
(7 numbered sections; a section with nothing to report says so). Defects found during the
audit go in body section 5. Commit with `-S`, message states why, then push and open the
PR in one Bash call with a 600000ms timeout (the pre-push hook runs pytest):

```bash
git push -u origin HEAD && gh pr create --title "..." --body-file <path>
```

## Coherence mode

Scope: every file carrying the CANON watermark, or the file list the caller passes.

```bash
grep -rln '^> \*\*CANON\*\*' --include='*.md' . | grep -v node_modules
```

**Triage first** when time-boxed: rank files by how recently their subject code changed
relative to the doc (`git log -1 --format=%ci -- <doc>` vs the same for the source dirs
the doc cites). Audit the widest-gap files first; a doc untouched since its subject
system was rewritten is the likeliest drift site.

Run the audit engine per file. The report is the artifact: return it as the final
message, or write it to the path the caller names. Report template:

```markdown
# Canon coherence report

Scope: <N> files audited | Clean: <n> | Drifted: <n>

## <file> - DRIFTED
| Locus | Claim | Reality | Severity | Proposed rewrite |
|---|---|---|---|---|
| <doc>:<line> | <claim> | <evidence, file:line> | dangerous/misleading/stale-pointer | <replacement text> |

## <file> - CLEAN
<claim count> claims re-verified.
```

Severity: **dangerous** (following the doc causes harm: wrong runbook values, wrong
safety claims), **misleading** (wrong mechanism or ownership; reader designs against
fiction), **stale-pointer** (dead file:line references, renamed identifiers). Order
findings by severity.

Coherence mode reports only. Fixes happen in a follow-up the operator approves, per the
standing rule that every md amendment needs owner sign-off.

## Traps

These are standing negatives. Each pairs with a positive rule above.

- Never treat the doc's own cross-references, header comments, or watermarks as evidence;
  header strings lie (`HTMX` appears in dozens of files and the admin dashboard has none).
- Never create new tracking cards, labels, or tables; defects go in the PR body, or as an
  append to an existing card that already covers the finding.
- Never present a REFUTED claim without its replacement text; a bare refutation forces
  re-derivation later.
- Never run `make -n validate` (refused by design) and never read pip-audit green as
  evidence (advisory stage, `|| true`).
- Never let a doc grow without stating why honest promotion required it.
- Never soften a rule-bearing doc with an exception clause during a rewrite.
- Never skip the merge check before branching; the pre-push branch-collision hook is the
  backstop, not the plan.
