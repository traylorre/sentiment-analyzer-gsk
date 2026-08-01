# Phase 0 Research: Close py/bad-tag-filter and Kill the Dead Suppression

**Feature**: `001-bad-tag-filter-dead-suppression` | **Date**: 2026-07-30

The Technical Context in `plan.md` carries no NEEDS CLARIFICATION markers. That is not because the
questions were waved through: the spec's Adversarial Review #1 resolved one CRITICAL and five HIGH
findings by measurement, and every remaining open question was closed here by running the command
rather than by reasoning about it. Each decision below records what was run and what came back.

---

## Re-verification of inherited claims

The task brief supplied a set of facts and said not to re-derive them. Two of them gate whether
this feature can land green on day one, so they were re-run rather than trusted. Both hold.

### R-0a. RUF100 on the widened path set

```bash
source .venv/bin/activate
ruff check --extend-select RUF100 scripts/          # -> "All checks passed!", exit 0
ruff check --extend-select RUF100 src/ tests/ scripts/  # -> "All checks passed!", exit 0
```

Both clean. The second command is the one the Makefile will actually run, and it is the one that
matters: a per-directory clean result would not rule out a cross-directory interaction. It is
clean under the full configured rule set from `pyproject.toml`, not merely under RUF100 in
isolation, because `--extend-select` adds to the configured selection rather than replacing it.

**Conclusion**: FR-011 can be satisfied immediately. No baseline file, no allowlist, no
grandfathering. The spec's assumption holds.

### R-0b. Bandit on the widened path set

```bash
source .venv/bin/activate
bandit -r scripts/ --ignore-nosec 2>/dev/null | grep -cE "^>>"   # -> 10
bandit -r src/     --ignore-nosec 2>/dev/null | grep -cE "^>>"   # -> 15
```

Ten and fifteen, matching the spec's assumption exactly. Twenty-five total after widening, all
pre-existing, all advisory, none fixed by this feature.

**Conclusion**: FR-012 holds and the spec's warning about the output roughly doubling is accurate.
Anybody reading the target's output after this lands should not read the longer wall as a
regression.

### R-0c. Marker population in the audited path set

```bash
grep -rnE "lgtm\[|codeql\[" src/ tests/ scripts/
# -> scripts/regenerate-mermaid-url.py:82 only
```

Exactly one, which is what SC-004 says. Every other marker in the tree is inside this feature's own
specification directory. Re-measured at the start of Adversarial Review #2: 32 occurrences across
`spec.md` (15), `contracts/dead-suppression-cli.md` (8), `plan.md` (6), `quickstart.md` (2), and
this file (1). Re-measured again after that review's own edits landed: 41, across the same five
files. Two measurements four hours apart, nine apart in value, which is the point. The number only
grows and no criterion may be written against it. The earlier wording named `spec.md` as the only
other holder, which was true when
this file was written and stopped being true the moment the plan and the contract were produced,
which is itself the clearest possible demonstration of why no criterion may count tree-wide. That
asymmetry is the entire justification for scoping the path set to source, and it is measured rather
than asserted.

### R-0d. Required status checks

```bash
gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection \
  --jq .required_status_checks.contexts
# -> ["Secrets Scan","Lint","Run Tests","Playwright E2E Tests"]
```

Four contexts. Neither `Analyze` (CodeQL) nor `Pre-commit Hooks` is among them. This is the fact
FR-018 is built on and it was re-confirmed today rather than inherited.

### R-0e. What the `Lint` job installs

`.github/workflows/pr-checks.yml:52-56`:

```yaml
      - name: Install linting tools
        run: |
          python -m pip install --upgrade pip
          pip install ruff==0.15.14
```

Ruff and nothing else, on top of `setup-python` at 3.13. Bandit is absent. This single fact
decides two things at once: a stdlib-only Python checker costs zero setup time there (FR-019 is
satisfiable), and `make audit-pragma` as a whole cannot be moved there (its bandit half would die
on a missing binary, and installing bandit is the tooling addition FR-019 forbids).

---

## D-1. The rewrite form

**Decision**: `any(line.rstrip().endswith("-->") for line in code.split("\n"))`.

**Rationale**: Two independent differential runs over an 8,057-input corpus put
`split("\n")` at 0 mismatches against `re.search(r"-->\s*$", code, re.MULTILINE)` and
`splitlines()` at 385. The mechanism is understood, not merely observed: `str.splitlines()` breaks
on `\v`, `\f`, `\r`, `\x85`, U+2028, and U+2029, none of which regex `$` treats as a line boundary
under `re.MULTILINE`. Bare `rstrip()` matches `\s` on every code point checked from U+0000 to
U+2FFF, so the default trim is correct and a narrowed `rstrip(" \t")` is not.

Worth spelling out why the two forms agree even though `\s*` can consume newlines: in
`-->\n\n\nfoo`, the regex backtracks `\s*` down to zero characters and `$` then matches at the
position immediately before the first `\n`. The split form sees a line that is exactly `-->` and
matches too. Every path where `\s*` spans a newline has a shorter path where it does not, so the
extra reach never produces a match the split form misses.

**Alternatives considered**:

- `code.splitlines()`. Rejected on 385 measured mismatches. This is the obvious rewrite and it is
  wrong, which is why FR-003 exists as a requirement rather than as a code comment.
- `rstrip(" \t")`. Rejected. Diverges on vertical tab, form feed, and non-breaking space after an
  arrow. Same class of defect as the separator case, one level down, and much easier to miss.
- Keep the regex and add `# codeql[py/bad-tag-filter]`. Rejected by FR-005. No inline form is
  honoured by this repository's scanning setup, so this swaps one decorative comment for another.
  This is precisely what the second round trip did in January.
- Dismiss the alert through the scanning product's own workflow. Not rejected in principle, and
  FR-007 records it as the supported route for a genuine false positive. Rejected here because the
  rewrite is a one-line behaviour-preserving change and dismissal leaves a pattern in the code that
  a future edit can re-flag.

### Why the thick-arrow sibling is not rewritten

`==>` sits on the very next line in the same identical shape and carries no alert. Leaving it
byte-identical (FR-002, SC-010) keeps the control intact: if the analyzer's finding really is
driven by lexical resemblance to an HTML-tag filter, the `-->` form is flagged and `==>` is not,
which is exactly the observed state. Rewriting both would destroy the evidence for that hypothesis
and would widen a four-line diff for no gain. It also means `import re` stays live, so no import
cleanup is warranted.

---

## D-2. Language and location of the checker

**Decision**: `scripts/check_dead_suppressions.py`, standard library only, written to a **3.9
language floor** rather than to the project's 3.13. Corrected by Adversarial Review #2: an earlier
draft of this line said "Python 3.13", which contradicts `contracts/dead-suppression-cli.md` C1.
C1 is normative and its reason is the Makefile consumer, which runs under whatever `python3` the
contributor's shell resolves. The floor is not free, because `pyproject.toml` sets
`target-version = "py313"` and selects `UP`; see "Reconciling the 3.9 floor with ruff" in
`plan.md`'s Technical Context for the constraints that follow. The `Lint` job still gets 3.13 from
`setup-python`, which is why the checker being stdlib-only is what matters there, not its floor.

**Rationale**: FR-009a requires a dedicated file. The three-way choice was bash (following
`check-banned-terms.sh`), Python (following `scan-waitforresponse-race.py`), or an inline Makefile
recipe.

Inline is out by FR-009a: self-exclusion by path only stays narrow if the excluded file is small,
and excluding the Makefile would exempt the one file every contributor edits.

Bash is out on three counts. Exact-path exclusion (FR-009) in grep means comparing output strings,
which is the fragile construction the precedent already got wrong. The FR-014 message needs
structure. And the positional matching rule needs per-line logic that is awkward in a grep
pipeline and readable in Python.

Python is free in the `Lint` job (R-0e) and matches the precedent that FR-018 explicitly cites.

**Alternatives considered**:

- Extend `scripts/check-banned-terms.sh` with the two markers. Rejected. It would inherit that
  script's basename-glob exclusion, which is the F6 defect, and it would couple two unrelated
  gates so that a red banned-terms scan hides a marker finding. Also `make validate` is already
  red through that scanner today, so anything folded into it starts life invisible.
- A ruff or semgrep rule. Rejected under FR-019: semgrep is not installed in the `Lint` job and
  installing it is a tooling addition. A custom ruff rule is not a thing ruff supports.
- A `.gitignore`-style deny list consumed by an existing generic scanner. There is no such generic
  scanner in this repository.

### Underscores in the filename

`scan-waitforresponse-race.py` uses hyphens; `consolidate_oauth_duplicates.py` uses underscores.
Both live in `scripts/`. The underscore form is directly importable
(`tests/unit/scripts/test_consolidate_oauth_apply.py:13` does exactly that, via PEP 420 implicit
namespace packages with the repository root on `sys.path`), which makes the checker's own unit
tests plain function calls instead of `importlib` plumbing. The CLI invocation is identical either
way. Underscores chosen.

This cuts the other way for the script under test: `regenerate-mermaid-url.py` is hyphenated and
cannot be renamed inside this feature's scope (it is referenced by path in documentation), so its
regression test does need `importlib.util.spec_from_file_location`. That cost is one helper
function and is called out in the plan so it is not a surprise.

---

## D-3. The self-exclusion mechanism

**Decision**: a frozenset of exact repository-relative `Path` objects, containing the checker and
its test file. A candidate is skipped if and only if its resolved repository-relative path is a
member.

**Rationale**: FR-009 requires exact-path exclusion after Adversarial Review finding F6 established
that the precedent's `--exclude=check-banned-terms.sh` is a basename glob exempting any
identically named file anywhere in the tree. Set membership on a normalised relative path has no
such hole, and it fails safe: a moved or renamed checker stops being excluded and immediately
flags itself, which is a loud failure rather than a silent one.

**Alternatives considered**:

- Basename exclusion, matching the precedent. Rejected by FR-009 for the reason above.
- A directory-level exclusion such as skipping all of `tests/unit/scripts/`. Rejected. That is the
  "broad pattern exclusion" FR-009 forbids and it would hide a real suppression added to any of the
  other test files in that directory.
- An opt-out comment in the checker's own source, along the lines of a `# audit-exempt` line.
  Rejected as self-defeating: this feature exists because an inline comment claiming to suppress
  something is worthless. Reintroducing the same pattern as the fix would be an unusually direct
  irony.
- Constructing the marker strings by concatenation so the checker never literally contains them.
  Rejected. CLAUDE.md's SAST guidance says not to restructure code to dodge detection, and the
  resulting source is harder to read for a reviewer who wants to know exactly what is matched.

---

## D-4. The audited path set and extension allowlist

**Decision**: roots `src/`, `tests/`, `scripts/`. Extensions `.py .sh .js .ts .tsx .jsx .html .yml
.yaml .tf`. Prose extensions excluded. Roots overridable through `DEAD_SUPPRESSION_ROOTS`.

**Rationale**: FR-010 fixes the roots. The extension allowlist came from a census:

| Root | Extensions found |
|---|---|
| `src/` | 135 `.py`, 8 `.md`, 7 `.txt`, 6 `.js`, 5 `.html`, 1 `.yaml`, 3 Dockerfiles, 1 bootstrap, 1 `.ico` |
| `tests/` | 393 `.py`, 2 `.md`, 1 `.js` |
| `scripts/` | 27 `.sh`, 15 `.py` |

The allowlist covers every source language present and adds the TypeScript extensions for headroom.
`.md` and `.txt` are excluded because prose describing a marker has to write it, which is the F2
defect that made the original SC-004 false at the moment it was written. There are ten markdown
files inside the audited roots, any of which could legitimately document this feature.

An allowlist rather than a deny list, so a new prose extension arriving in `src/` does not silently
opt itself in. Binary and undecodable files are read with `errors="replace"` so one stray file
cannot take the gate down.

**Alternatives considered**:

- Tree-wide scan. Rejected by FR-021 and SC-004. Unsatisfiable on the day it is written: this
  feature's `spec.md` alone holds fifteen markers.
- All files regardless of extension. Rejected. Pulls in `.md`, `.txt`, Dockerfiles, and an `.ico`.
- Adding `frontend/` to the roots. Rejected as scope creep, but the `.ts`/`.tsx` entries in the
  allowlist mean the change would be a one-line edit if somebody later wants it.

---

## D-5. The matching rule

**Decision**: positional. A marker fires only when it appears after a comment introducer (`#`,
`//`, `<!--`, `/*`, `--`) on the same line. Case-insensitive on the marker itself.

**Rationale**: the spec's "Marker matching is positional" assumption prefers this and permits a
whole-line fallback. Positional is achievable in a few lines and its payoff is concrete: markers in
docstrings, URLs, and string literals do not fire, which is what keeps the checker's own test file
clean independently of the exclusion. The introducer set covers every language in the allowlist.

**Alternatives considered**:

- Whole-line substring match. Permitted by the spec as a fallback and rejected here because it is
  not needed. Test files in this repository routinely carry bracketed identifiers inside string
  literals, so the noise is real rather than theoretical. If positional matching is ever abandoned,
  that belongs in a spec amendment, not in an implementation shortcut.
- Full per-language comment parsing, tracking multi-line strings and block comments. Rejected as
  disproportionate. The current match count in the audited set is one. A false negative from a
  marker hidden inside a block comment is an acceptable risk for a check whose job is to catch the
  well-meaning contributor who typed a suppression they believed would work, not to defeat an
  adversary.

---

## D-6. Where the gate is wired

**Decision**: a dedicated step in the `Lint` job of `.github/workflows/pr-checks.yml`, invoking the
checker directly. Optionally, additionally, a `pre-commit` hook.

**Rationale**: FR-018 requires a merge-blocking context, and R-0d shows there are exactly four.
`Lint` is the only one of the four where a text scan belongs. `Run Tests` would work mechanically
but buries a lint concern in pytest; `Secrets Scan` is Gitleaks; `Playwright E2E Tests` is the
customer dashboard suite.

The precedent is followed deliberately and completely, including the explanatory comment. The
waitForResponse guard sits in `Lint` at lines 69-87 with a comment stating that moving it to
`Pre-commit Hooks` would silently downgrade it to advisory. That comment exists because the
downgrade has no symptom until a violation merges green, which is the same failure mode as the
comment this feature is deleting. Repeating the note is cheap insurance against a future tidy-up.

`if: always()` matters here for a reason that is easy to miss: steps are fail-fast, this step is
last, and without it any ruff failure means the guard silently does not run. The job still goes
red either way, so the flag costs nothing and buys both failures being visible in one run.

**Alternatives considered**:

- Invoke `make audit-pragma` from the `Lint` job. Rejected on R-0e: bandit is not installed there
  and installing it violates FR-019. Also drags in a 25-finding advisory wall on every PR.
- Add `audit-pragma` to `make validate`'s prerequisites. Rejected, and carded in the spec's Out of
  Scope. `make validate` is already red on `main` through the banned-terms scanner, so a gate added
  there starts life invisible, which is the exact failure being fixed.
- Pre-commit hook only. Rejected by FR-018. `Pre-commit Hooks` is not a required context, verified
  at R-0d, and `.pre-commit-config.yaml:214-228` already documents that in a comment.
- A new dedicated CI job. Rejected. A new job is a new context, and a context that is not in the
  required list is advisory. Adding it to the required list is a branch protection change, which
  the spec cards as out of scope.

---

## D-7. The negative test without a persistent fixture

**Decision**: write the marker-carrying fixture into pytest's `tmp_path` and point the checker at
it through `DEAD_SUPPRESSION_ROOTS`.

**Rationale**: the spec's "auditor's own test fixtures" edge case sets two constraints that look
contradictory. The fixture must be real enough to prove the check fires, and it must not persist
inside the audited set nor be exempted by a broad pattern. `tmp_path` satisfies both by putting the
fixture outside the repository entirely: a default-root run never sees it, no exclusion is needed,
and pytest destroys it at test end, so "exists only for the duration of the test" is literally
true rather than a convention somebody has to remember.

The root override variable exists for this and only this. It mirrors `SCAN_ROOT_ENV` in the
waitForResponse precedent, which was introduced for the same testing reason.

One rule for the test file that a task should state explicitly, **corrected by Adversarial Review
#2**: no single source line may contain a comment introducer followed by a marker. The earlier
wording ("its marker strings live in Python string literals, never in a `#` comment") was too weak,
and the reasoning attached to it was wrong. The D-5 positional rule is textual and does not know
what a string literal is, so the obvious fixture line
`fixture.write_text("x = 1  # lgtm[py/some-rule]\n")` has `#` before the marker and **does** fire.
The introducer and the marker must be assembled from separate expressions, and only then is the
positional rule a second mechanism independent of the exact-path exclusion. `plan.md` §7 carries
the worked form. The well-meaning edit that adds "here is what a bad line looks like" as a real
comment is still the one that turns the gate permanently red.

**Alternatives considered**:

- A committed fixture under `tests/fixtures/`. Rejected. `tests/` is an audited root, so the
  fixture would fail the audit permanently unless excluded, and excluding it opens a hole.
- A fixture written into the repository and deleted in a teardown. Rejected. A crashed or
  interrupted test leaves a marker in the tree and the gate red for everyone.
- Feeding the checker a string rather than a file. Rejected as insufficient: SC-006 requires the
  output to name the file and the line, which only a real filesystem walk exercises.

---

## D-8. Exit codes and the zero-files case

**Decision**: 0 clean, 1 marker found, 2 zero files scanned.

**Rationale**: taken directly from the waitForResponse precedent, whose contract records the
reasoning: "No violations found" and "no files found" must not share an exit code, or moving the
scan root reads as a clean tree. That failure is not hypothetical for this checker, whose roots are
three hard-coded directory names that a future repository reorganisation could move.

Full detail in `contracts/dead-suppression-cli.md`.

---

## Open items carried forward

Nothing blocks implementation. Two things are worth a task-time re-check rather than a plan-time
assumption:

1. **Re-run R-0a immediately before making the RUF100 line blocking on the widened set.** It is
   clean today. A sibling agent working in this shared worktree could land a `# noqa` in `scripts/`
   between now and then, and FR-015 turns that into a day-one failure. Cheap to re-run, expensive
   to discover in CI.
2. **Re-confirm the required contexts before merging the CI step.** The plan's comment block
   asserts them and the precedent's comment says plainly not to trust the list without re-checking.
   Same command as R-0d.
