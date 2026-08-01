# Quickstart: verifying this feature

**Feature**: `001-bad-tag-filter-dead-suppression`

Half of this feature can be verified before merge and half cannot. The split is a stated property
of the repository, not a gap. Sections 1 through 4 run locally today. Section 5 runs only after the
change is on `main`, possibly on a different day and by a different person, which is why it is
written down here rather than left in somebody's head.

Activate the virtual environment first. A bare `python3` resolves differently per machine, so do
not assume the shell's interpreter is the project's.

```bash
cd /home/zeebo/projects/sentiment-analyzer-gsk
source .venv/bin/activate
python --version   # expect 3.13.x
```

---

## 1. The rewrite preserved behaviour (FR-001, SC-003, SC-009)

```bash
pytest tests/unit/scripts/test_regenerate_mermaid_url.py -v
```

Expect all green, including the differential test over at least 1,500 inputs reporting zero
mismatches against the original expression.

If the differential test fails, read which input diverged before touching anything. The two known
traps both show up as a specific class of input:

- divergence on `\v`, `\f`, `\r`, `\x85`, U+2028, or U+2029 means somebody used `splitlines()`
  instead of `split("\n")`;
- divergence on a non-breaking space or a vertical tab immediately after an arrow means somebody
  used `rstrip(" \t")` instead of a bare `rstrip()`.

## 2. The dead suppression is gone (FR-005, FR-006, SC-004)

```bash
grep -rnE "lgtm\[|codeql\[" src/ tests/ scripts/
```

Expect matches only inside `scripts/check_dead_suppressions.py` and
`tests/unit/scripts/test_check_dead_suppressions.py`. Before this feature the same command
returned one match, in `scripts/regenerate-mermaid-url.py`.

Do not run this tree-wide. `specs/001-bad-tag-filter-dead-suppression/spec.md` alone holds fifteen
markers, because describing a marker requires writing it.

Confirm the control was not disturbed (SC-010):

```bash
git diff main -- scripts/regenerate-mermaid-url.py | grep -- "==>"
```

Expect no output. The thick-arrow line must be byte-identical.

## 3. The checker works (FR-008, FR-014, FR-015, SC-005, SC-006)

Clean run against the real tree:

```bash
python3 scripts/check_dead_suppressions.py; echo "exit=$?"
```

Expect `exit=0` and a non-zero file count in the output. An `exit=2` means zero files were
scanned, which is a broken root rather than a clean tree.

Its own test suite, including the negative test:

```bash
pytest tests/unit/scripts/test_check_dead_suppressions.py -v
```

Manual smoke test of the failure path, if you want to see the message a contributor will get. Note
the fixture goes outside the repository, never inside an audited root:

```bash
mkdir -p /tmp/dsfix
printf 'x = 1  # lgtm[py/some-rule]\n' > /tmp/dsfix/bad.py
DEAD_SUPPRESSION_ROOTS=/tmp/dsfix python3 scripts/check_dead_suppressions.py; echo "exit=$?"
rm -rf /tmp/dsfix
```

Expect `exit=1`, and output naming `bad.py`, line 1, the marker, why the form is inert, and the
dismissal workflow as the supported alternative.

## 4. The audit target (FR-011, FR-012, FR-013, SC-007, SC-008)

```bash
make audit-pragma; echo "exit=$?"
```

Expect `exit=0`. Three labelled sections in the output, two `[BLOCKING]` and one `[ADVISORY]`.

Run this again on the exact tree being merged, after the final rebase, not just once during
implementation (FR-015). The widened unused-pragma path set is clean today, but this worktree is
shared with concurrent work and one `# noqa` landing in `scripts/` in the meantime makes the target
red for everybody on day one. The isolated form is `ruff check --extend-select RUF100 scripts/`.

Two things about that output that are correct and look wrong:

- The bandit wall is roughly twice as long as it used to be. Widening its path set to include
  `scripts/` surfaced ten pre-existing findings on top of the fifteen already there. All
  twenty-five are advisory, all predate this feature, and none is fixed by it. This is recorded in
  the specification's assumptions.
- `make validate` is red on `main` today through the banned-terms scanner, unrelated to this
  feature and carded out of scope. Do not read that as a regression from this change, and do not
  fix it here.

## 5. CI actually enforces it (FR-018, SC-011, SC-012)

Reading the workflow file is not evidence. SC-011 requires an observed check result.

First re-confirm the required contexts, because the whole design rests on them:

```bash
gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection \
  --jq .required_status_checks.contexts
echo "gh_exit=$?"
```

Expect `gh_exit=0` and `["Secrets Scan","Lint","Run Tests","Playwright E2E Tests"]`. If `Lint` is no
longer in that list, the gate is advisory and FR-018 is unsatisfied regardless of what the workflow
says.

The exit check is not decoration. This endpoint returns a single object rather than a page, so
`--paginate` does not apply, but the failure mode it shares with the alert queries does: a 404, an
expired token, or a permissions change all produce **empty output**, which reads identically to
"branch protection requires nothing". Empty must never be read as an answer here, because the answer
it would imply is the one that invalidates FR-018's entire premise.

Then, on the feature branch, prove the gate bites. Push a scratch commit adding a marker to a
source file:

```bash
printf '\n# lgtm[py/scratch-do-not-merge]\n' >> scripts/regenerate-mermaid-url.py
```

Push it, confirm `Lint` reports failure and names the file and line, then revert the scratch commit
before merging. Confirm `Lint` goes green again on the reverted state.

SC-012 comes free from reading the job log: the new step runs immediately after the waitForResponse
guard with no preceding install step, so it costs no setup time.

---

## 6. After merge: the alert (FR-016, FR-022, SC-001, SC-002)

**This cannot be done before merge.** The branch-level analysis does not refresh until the change
is on `main`, and no scanning result is a required check, so nothing holds the merge while you
wait.

**Never query the alert list without `--paginate`.** The default page size is 30 and this
repository's all-states alert corpus is 137, so an unpaginated read truncates and **truncation
renders as clean**. Measured 2026-07-30: the unpaginated form with a client-side
`select(.state == "open")` returns ZERO open alerts while the paginated form returns FIVE. A
sibling feature in this campaign is expected to raise the open count substantially on purpose, at
which point even a server-side `state=open` filter overflows one page and this section starts
reporting success because the read was cut short rather than because the finding is gone.

Record the open-alert count **before** merging. `--slurp` cannot be combined with `--jq`, so the
pages are written out and filtered separately, which keeps `gh`'s exit status readable instead of
hiding it downstream of a pipe:

```bash
gh api --paginate --slurp \
  "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" \
  > /tmp/alerts-open-before.json
echo "gh_exit=$?"
jq 'add | length' /tmp/alerts-open-before.json
```

After the merge lands and the `Analyze` job has run on `main`:

```bash
gh api --paginate --slurp \
  "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" \
  > /tmp/alerts-open-after.json
echo "gh_exit=$?"
jq 'add | map({n: .number, rule: .rule.id, path: .most_recent_instance.location.path})' \
  /tmp/alerts-open-after.json

# Corpus floor. Pass condition 1 below is an EMPTY result, so the read must independently prove it
# reached the API and saw the whole corpus. Run this both before and after.
gh api --paginate --slurp \
  "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?ref=refs/heads/main&per_page=100" \
  > /tmp/alerts-all.json
echo "gh_exit=$?"
jq 'add | length' /tmp/alerts-all.json
```

Pass conditions, all required:

0. Every `gh_exit` is `0` and the corpus floor is at least 137. A corpus of `0`, or a non-zero
   `gh_exit`, means the read failed, and a failed read proves nothing about condition 1. Emptiness
   is only evidence when the reader has been shown to be working.
1. No open alert has rule `py/bad-tag-filter` at path `scripts/regenerate-mermaid-url.py`.
2. The total open count is exactly one lower than the pre-merge count (SC-002). Exactly one, not
   at most one: a criterion phrased as "no worse than before" is satisfied by the change achieving
   nothing. Caveat: if a sibling feature that changes the analysis matrix merges between the two
   measurements, the total moves for reasons unrelated to this change and condition 2 becomes
   unmeasurable. In that case record both counts, fall back to condition 1 alone, and note why.

**Key on path plus rule id, never on the alert number.** CodeQL demonstrably closes an alert and
opens a fresh number at the same site. A check written against `147` can report success while the
finding is still sitting there under a new number.

**If the alert is still open**, the response is a follow-up change to the same line, not a revert
(FR-022). The rewrite is behaviour-preserving by FR-001, so reverting restores a pattern and buys
nothing. Record the query output either way. It is the evidence FR-016 asks for, and a green pull
request check is explicitly not acceptable in its place, because pull request analysis is
diff-informed and covers only changed lines.
