# Implementation Plan: Close py/bad-tag-filter and Kill the Dead Suppression

**Branch**: `001-bad-tag-filter-dead-suppression` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-bad-tag-filter-dead-suppression/spec.md`

## Summary

Three changes, one of which carries all the design risk.

1. Rewrite the arrow-without-target check at `scripts/regenerate-mermaid-url.py:82` from a
   regular expression into string operations, so the analyzer has no pattern to flag. One line,
   plus a note telling the next author why it is written that way.
2. Delete the `# lgtm[py/bad-tag-filter]` comment and the false-positive note above it. Nothing
   inline replaces them, because no inline form is honoured here.
3. Add a dedicated marker checker, wire it into `make audit-pragma`, and wire it independently
   into the required `Lint` job so it can actually fail a merge. Widen the audit's path set to
   include `scripts/`, and make each half's blocking or advisory status explicit rather than an
   accident of shell pipeline semantics.

The third item is where the plan spends its effort. Parts 1 and 2 are a four-line diff whose only
difficulty is proving behaviour did not shift, which a differential test does.

## Technical Context

**Language/Version**: Python 3.13 for the repository (`requires-python = ">=3.13"`; CI `setup-python` pins 3.13 in the `Lint` job). **The new checker is the exception and targets a 3.9 floor**, per `contracts/dead-suppression-cli.md` C1: its Makefile consumer runs under whatever `python3` the contributor's shell resolves, which is 3.12.3 at `/usr/bin/python3` on the reference machine. See "Reconciling the 3.9 floor with ruff" under Constraints; this is not free and getting it wrong reddens a blocking line.
**Primary Dependencies**: Python standard library only for the new checker (`argparse`, `os`, `pathlib`, `sys`). Existing tooling reused unchanged: ruff 0.15.14 (RUF100 rule), bandit (advisory half of the audit), pytest 7+ with the repository's configured `testpaths = ["tests"]`. No dependency is added to any requirements file.
**Storage**: N/A. The checker reads files and writes nothing.
**Testing**: pytest, collected under `tests/unit/scripts/`. No AWS, no moto, no network. Compliant with the constitution's LOCAL/unit row.
**Target Platform**: Developer shell (`make audit-pragma`) and GitHub Actions `ubuntu-latest` (the `Lint` job).
**Project Type**: Single project. Repository tooling under `scripts/`, tests under `tests/`.
**Performance Goals**: The checker walks roughly 583 source files. It must not measurably lengthen the `Lint` job. A single pass reading each file once is comfortably inside a second.
**Constraints**: The checker MUST import nothing outside the standard library, because the `Lint` job installs only `ruff==0.15.14` (verified at `.github/workflows/pr-checks.yml:52-56`). It MUST NOT require `.venv`. It MUST NOT flag its own source or its own tests, and that exclusion MUST be by exact repository-relative path rather than by filename pattern.

**Reconciling the 3.9 floor with ruff.** These two pull against each other and the collision is
reproducible, not theoretical. `pyproject.toml` sets `target-version = "py313"` and selects `UP`,
so pyupgrade rewrites 3.9-compatible source into 3.10+ source. Run against the pinned ruff
0.15.14, a 3.9-shaped file trips UP035 and UP006 (`typing.List`), UP045 (`Optional[X]` becomes
`X | None`, which is 3.10+ at runtime), and UP036 (any `sys.version_info` guard below 3.13 reads as
dead). This matters because §2 widens `ruff check --extend-select RUF100` to `scripts/`, and
`--extend-select` **adds to** the configured selection rather than replacing it, so the new checker
is linted under the full `E W F I B C4 UP S` set on a **blocking** line of `audit-pragma`. A UP
violation there is exactly the day-one failure FR-015 exists to prevent.

The resolution, and it is the only one that satisfies both:

- Open the checker with `from __future__ import annotations`. Annotations then never evaluate at
  runtime, so PEP 604 syntax (`str | None`) is valid back to 3.7 and UP045 is satisfied at the same
  time. `tests/unit/scripts/test_consolidate_oauth_apply.py:6` and `conftest.py:10` already do this.
- Keep PEP 604 and builtin generics **in annotations only**. Do not use them where they are
  evaluated: no `isinstance(x, str | None)`, no runtime `typing.get_type_hints`.
- Do **not** add a `sys.version_info` interpreter guard. UP036 flags it, the precedent needed
  `# noqa: UP036` to carry one (`scripts/scan-waitforresponse-race.py:70-75`), and C1 forbids
  version-gated syntax anyway. If one is ever added, C1 also forbids reusing exit code `2`.
- The checker and its test file MUST be clean under `ruff check --extend-select RUF100 scripts/`
  and `... tests/` before the widened line is left blocking. No artifact said this and it is not
  implied by "stdlib only".

**Scale/Scope**: One production line rewritten, two comment lines removed, one new checker file, one new test file, one Makefile recipe edited, one CI step added.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution governs the sentiment analyzer service itself: ingestion adapters, inference,
persistence, deployment, the dashboard. This feature touches none of that. It changes a diagram
utility script and the repository's own validation tooling. Most gates are therefore not
applicable rather than passed, and that is recorded honestly below instead of being papered over
with a column of ticks.

| Gate | Applies? | Result |
|---|---|---|
| Functional requirements (ingest, dedup, sentiment output, admin API) | No | Untouched. No service code in the diff. |
| Non-functional (availability, P90 latency, autoscale) | No | No runtime path changes. |
| Security and access control (auth on admin endpoints, TLS, secrets in a managed store) | No | No endpoint, credential, or secret is touched. |
| SQL injection and unsafe DB access | No | No database access anywhere in the diff. |
| Data and model requirements (output schema, model versioning, reproducibility) | No | No model or data schema involved. |
| Deployment (containerised, IaC, Terraform, TFC) | No | No infrastructure change. |
| Observability and monitoring | No | No metrics or logging change. |
| Dashboard and admin controls | No | Neither dashboard is touched. See CLAUDE.md's two-dashboard table: this feature is in neither. |
| **"include SAST/secret scanning and dependency checks in CI"** | **Yes** | **PASS, and strengthened.** The feature closes a high-severity scanning finding and adds a new source scan to a merge-blocking CI context. |
| **"CI/CD pipelines must ... include unit and integration tests, SAST, and IaC linting checks"** | **Yes** | **PASS.** The new checker runs in the required `Lint` job; the new regression test runs in the required `Run Tests` job. |
| **Testing matrix: LOCAL and DEV run ONLY unit tests with mocks** | **Yes** | **PASS.** Every new test is a pure-stdlib unit test with no AWS and no network. No `preprod` marker. |
| **External dependency mocking is mandatory in all environments** | **Yes** | **PASS, vacuously.** The diff has no external dependency to mock. |

**Result: PASS. No gate failed. No gate required justification, so Complexity Tracking is empty
and omitted.**

One constitution-adjacent note that is not a gate failure but is worth recording: the constitution
mandates SAST in CI, and the bandit half of `make audit-pragma` reports success unconditionally
today. This feature does not fix that backlog (explicitly out of scope) but FR-013 does force the
recipe to *declare* that half advisory rather than leave a reader to infer it from a pipe. That is
a documentation-honesty improvement against the same clause, not a new gate.

**Post-design re-check: PASS, unchanged.** Phase 1 introduced one new stdlib-only script and one
new unit test file. Neither moves any constitution gate from "not applicable" to "applicable", and
neither weakens a gate that was passing.

## Project Structure

### Documentation (this feature)

```text
specs/001-bad-tag-filter-dead-suppression/
├── spec.md                          # Input (existing, with Adversarial Review #1)
├── plan.md                          # This file
├── research.md                      # Phase 0: the seven decisions with their falsification evidence
├── quickstart.md                    # Phase 1: how to run and verify each half
├── contracts/
│   └── dead-suppression-cli.md      # Phase 1: the checker's CLI contract, two consumers
├── checklists/                      # Existing
└── tasks.md                         # Phase 2 output (/speckit.tasks, NOT created here)
```

**data-model.md is deliberately not produced.** See "Artifacts deliberately skipped" below.

### Source Code (repository root)

```text
scripts/
├── regenerate-mermaid-url.py        # MODIFIED: line 82 rewritten, lines 80-81 replaced
├── check_dead_suppressions.py       # NEW: the marker checker (stdlib only)
├── scan-waitforresponse-race.py     # Reference precedent, untouched
└── check-banned-terms.sh            # Reference precedent for exclusion, untouched

tests/unit/scripts/
├── conftest.py                      # Existing, untouched (moto fixtures for another script)
├── test_regenerate_mermaid_url.py   # NEW: differential + regression tests for the arrow check
└── test_check_dead_suppressions.py  # NEW: checker unit tests including the negative test

Makefile                             # MODIFIED: audit-pragma recipe, lines 85-92
.github/workflows/pr-checks.yml      # MODIFIED: one step appended to the `Lint` job
```

**Structure Decision**: Single project, existing layout, no new directories. The checker goes in
`scripts/` alongside the two scanners it is modelled on. Both new test files go in
`tests/unit/scripts/`, which already exists and already holds tests for another repository script,
and which sits inside the configured `testpaths = ["tests"]` so the required `Run Tests` job
collects them. That last point is FR-004's whole concern and it is satisfied by placement alone.

---

## Design decisions the spec requires this plan to make concrete

The task brief asks for six things to be pinned down. They are pinned here, with the reasoning in
`research.md` and the machine-readable form in `contracts/dead-suppression-cli.md`.

### 1. Where the new check lives

**`scripts/check_dead_suppressions.py`.** A dedicated file, satisfying FR-009a.

Underscores, not hyphens, unlike its `scan-waitforresponse-race.py` sibling. The reason is
testability: `tests/unit/scripts/test_consolidate_oauth_apply.py:13` already does
`import scripts.consolidate_oauth_duplicates as mod`, which works because pytest puts the
repository root on `sys.path` and PEP 420 makes `scripts/` an implicit namespace package. A
hyphenated name would force `importlib.util.spec_from_file_location` gymnastics in every test.
The CLI invocation is `python3 scripts/check_dead_suppressions.py` either way, so the naming
choice costs the consumers nothing.

Python rather than bash, unlike `check-banned-terms.sh`. Three reasons, all concrete. Exact-path
exclusion (FR-009) is a set membership test on `Path.relative_to()` in Python and a fragile string
comparison in `grep`. The precedent's own bash exclusion is the *bug* FR-009 was written to avoid.
The FR-014 output (file, line, marker, why it is inert, what to do instead) is formatting work.
And the `Lint` job already has a 3.13 interpreter from `setup-python`, so Python is free there.

### 2. How the Makefile invokes it

`make audit-pragma` gains a third section and all three sections gain an explicit status label
(FR-013, SC-008). Target shape:

```make
audit-pragma: ## Audit pragma comments (# noqa, # nosec) and dead scanning suppressions
	@echo "$(YELLOW)=== [BLOCKING] Unused # noqa comments (RUF100) ===$(NC)"
	ruff check --extend-select RUF100 src/ tests/ scripts/
	@echo ""
	@echo "$(YELLOW)=== [BLOCKING] Dead inline scanning suppressions ===$(NC)"
	@python3 scripts/check_dead_suppressions.py
	@echo ""
	@echo "$(YELLOW)=== [ADVISORY - never fails this target] # nosec usage (Bandit, suppressions disabled) ===$(NC)"
	@bandit -r src/ scripts/ --ignore-nosec 2>/dev/null | grep -E "^(>>|Issue)" || true
	@echo "$(YELLOW)(the line above is advisory by design; see FR-012)$(NC)"
	@echo ""
	@echo "$(GREEN)✓ Pragma audit complete$(NC)"
```

Three things changed and each maps to a requirement:

- RUF100 path set widened to include `scripts/` (FR-010, FR-011). Verified clean today. It is safe
  to leave blocking on day one **only if** the check is re-run against the exact tree being merged;
  see "Re-verification immediately before merge (FR-015)" under Verification and the merge boundary.
- The new check inserted as an explicitly blocking step (FR-008).
- The bandit line's advisory status made a *declaration* rather than an accident (FR-013). Today
  `... | grep -E "^(>>|Issue)" || echo "No issues found"` swallows failure because the recipe
  inherits grep's exit status, which is a property a reader has to derive from `PIPESTATUS`
  semantics. Replacing the `|| echo` with an explicit `|| true` plus a labelled banner makes the
  contract readable without that derivation, which is exactly what SC-008 asks for. Its path set
  widens to `src/ scripts/` (FR-012), which surfaces ten pre-existing findings that print and
  block nobody, as the spec's assumption already records.

Note that `make audit-pragma` as a whole still is not wired into `make validate` or into CI. That
is deliberate and carded in Out of Scope. Only the marker check reaches CI, and it reaches it
directly rather than through this target.

### 3. How the required `Lint` job invokes it

**This section is the feature's scope growth and it is owner-rejectable.** The original request was
"rewrite an expression, delete a comment, extend `make audit-pragma`" (`spec.md:6`). FR-018 grows
that into editing `.github/workflows/pr-checks.yml`, which carries one of the four contexts branch
protection requires on `main`. The reasoning is in the spec's Overview and is not repeated here.
What the Overview records and this plan previously did not is the fallout if the owner says no, and
it belongs here because tasks are cut from this file:

- **If FR-018 is accepted** (the assumption everything below is written under): this section, the
  CI step, `quickstart.md` section 5, SC-011, and SC-012 all stand.
- **If FR-018 is rejected**: FR-018, FR-019, SC-011, and SC-012 fall, US3 reduces to its first five
  scenarios, this entire section is dropped along with its task, and the feature keeps only its
  informational outcomes. Sections 1, 2, and 4 through 7 are unaffected: the checker still gets
  built, still gets wired into `make audit-pragma`, and still has the same contract. What it loses
  is the property of ever running against a change that is about to land.

Neither outcome may be reached silently. Do not widen the CI footprint beyond the single step below
(no new job, no new required context, no `make validate` prerequisite, all carded out of scope in
the spec), and do not quietly drop the step on the grounds that it is "just tooling".

A new final step in the `lint` job of `.github/workflows/pr-checks.yml`, appended after the
existing waitForResponse guard at line 85-87, following that precedent exactly:

```yaml
      # Dead scanning-suppression guard (001-bad-tag-filter-dead-suppression, FR-018).
      #
      # Why this lives in `Lint` and not in `Pre-commit Hooks`: `Lint` is one of main's
      # required status checks and `Pre-commit Hooks` is not, so this is the only place
      # the guard can actually block a merge. Moving it silently downgrades it to
      # advisory with no symptom until a dead suppression merges green. That is the
      # precise failure this feature exists to delete: alert 147 survived six months
      # behind a comment that could not suppress anything. Required contexts verified
      # 2026-07-30:
      #   gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection \
      #     --jq .required_status_checks.contexts
      #   -> ["Secrets Scan","Lint","Run Tests","Playwright E2E Tests"]
      #
      # No pip install: the checker is stdlib-only and setup-python above already
      # provides 3.13. This job installs only ruff==0.15.14 (FR-019).
      #
      # `if: always()` because steps are fail-fast and this one is last. Without it a
      # ruff failure means the guard never runs and reports nothing.
      - name: Check for dead scanning suppressions
        if: always()
        run: python3 scripts/check_dead_suppressions.py
```

**Why the step is `python3 scripts/check_dead_suppressions.py` and not `make audit-pragma`.**
The `Lint` job installs `ruff` and nothing else. `bandit` is absent, so the target's third section
would fail on a missing binary, and adding bandit to the job is exactly the tooling installation
FR-019 forbids. Invoking the checker directly also means the `Pre-commit Hooks` job's `SKIP`
environment cannot reach it, which is the same reasoning the waitForResponse precedent records
in `.pre-commit-config.yaml:220-228`.

**Optional, and recommended but not required by any FR:** a matching `pre-commit` hook with
`pass_filenames: false, always_run: true`, mirroring `.pre-commit-config.yaml:206-212`. It gives
contributors the failure locally instead of in CI. It is *additive only*. If the two ever
disagree, the CI step is the gate. A task should carry this as explicitly optional so nobody reads
its absence as an FR-018 miss.

### 4. The exclusion mechanism

**Exact repository-relative path membership, never a filename glob** (FR-009).

```python
SELF_EXCLUSIONS = frozenset({
    Path("scripts/check_dead_suppressions.py"),
    Path("tests/unit/scripts/test_check_dead_suppressions.py"),
})
```

A candidate is skipped if and only if it resolves inside the repository root and its
repository-relative path is in that set. Two files, both named, both of which genuinely must
contain the marker strings verbatim.

Do not write that as a bare `path.resolve().relative_to(repo_root())`. Under
`DEAD_SUPPRESSION_ROOTS` the scan walks files outside the repository and `relative_to` raises
`ValueError` on every one of them, which takes the negative test down with it. Use a containment
test and treat "outside the repository" as "not excluded". Same for the reported path, which falls
back to absolute. `contracts/dead-suppression-cli.md` C6 and C7 are normative here, and
`scripts/scan-waitforresponse-race.py:418-423` is the working precedent.

This is deliberately *not* the precedent's mechanism. `check-banned-terms.sh:32` uses
`--exclude=check-banned-terms.sh`, which is a grep basename glob: any file anywhere in the tree
called `check-banned-terms.sh` is exempt. Adversarial Review finding F6 called that out and FR-009
now forbids it. Exact-path membership has no such hole.

Deliberately not done: obfuscating the marker strings inside the checker so it never matches
itself. That would remove the need for an exclusion, and it is the wrong trade. CLAUDE.md's SAST
section says plainly "Do NOT rename variables to avoid detection", and a checker whose own
patterns are assembled from fragments is unreadable to the next maintainer. Two named paths is
cheaper and honest.

### 5. The audited path set

**Roots**: `src/`, `tests/`, `scripts/`. The two audited today plus the one holding the affected
file (FR-010). The spec tree is out of range by construction, which is what makes SC-004
satisfiable at all: this feature's `spec.md` alone holds fifteen marker occurrences, this feature's
own directory holds thirty-two, and exactly one marker in the whole repository sits in source. The
number in the spec tree only grows as planning, contract, and review artefacts are added, which is
why no criterion is allowed to count it.

**Extension allowlist**: `.py`, `.sh`, `.js`, `.ts`, `.tsx`, `.jsx`, `.html`, `.yml`, `.yaml`,
`.tf`. A census of the three roots found `.py` (543), `.sh` (27), `.js` (7), `.html` (5), `.md`
(10), `.txt` (7), `.yaml` (1), plus Dockerfiles and binaries. The allowlist covers every source
language actually present and leaves headroom for the TypeScript that would arrive if a scanner
were ever pointed at `frontend/`.

**`.md` and `.txt` are excluded on purpose.** They are prose, and prose that describes a marker
has to write it. Including them would recreate the F2 defect one directory down: `src/` and
`tests/` between them hold ten markdown files, any of which could legitimately document this very
feature. The exclusion is by extension allowlist rather than by a deny-list so that a new prose
extension does not silently opt itself in.

**Skipped regardless of extension**: `__pycache__`, `node_modules`, `.venv`, `.git`,
`.pytest_cache`, `.hypothesis`, and anything that fails to decode as UTF-8 (read with
`errors="replace"` rather than crashing, so one stray binary cannot take the gate down). That list
is normative in `contracts/dead-suppression-cli.md` C3 and the two must stay identical.

**Roots are overridable** via a `DEAD_SUPPRESSION_ROOTS` environment variable holding
os.pathsep-separated paths, mirroring `SCAN_ROOT_ENV` in the waitForResponse precedent. This
exists for one reason only, and it is the next section.

### 6. Matching rule

Positional, per the spec's "Marker matching is positional" assumption. A line matches when a
marker (`lgtm[` or `codeql[`, case-insensitive) appears **after** a comment introducer on that
same line. Introducers recognised: `#`, `//`, `<!--`, `/*`, `--`. That set covers Python, shell,
YAML, HCL, JS/TS, and HTML, which is every language in the allowlist. `--` is carried for SQL,
which is **not** in the allowlist (no `.sql` extension is scanned) and is the loosest introducer in
the set: any line containing `--` before a marker matches, a `-->` arrow included. It is retained
only so that adding `.sql` later needs no change to the rule, and it is a known false-positive
source rather than an oversight.

The consequence that matters: a marker inside a Python docstring, a URL, or a string literal does
not match, because none of those lines carries an introducer before the marker. That is what keeps
the checker's own *test* file honest even before the exclusion applies, since the test's markers
live in string literals.

The spec permits falling back to a whole-line match if positional proves unreliable. It should not
be needed, and the fallback is worse: `tests/unit/scripts/test_consolidate_oauth_apply.py`-style
files routinely carry bracketed identifiers in string literals. If the positional rule is dropped,
that decision belongs in a spec amendment, not in an implementation shortcut.

### 7. How the negative test materialises a marker without poisoning the audited set

This is the trap the spec's "auditor's own test fixtures" edge case names, and it has a clean
answer.

The test writes a throwaway file carrying a real marker into pytest's `tmp_path`, then points the
checker at `tmp_path` via `DEAD_SUPPRESSION_ROOTS` and asserts the non-zero exit and the reported
file, line, and marker. `tmp_path` is outside the repository entirely, so:

- the fixture never exists inside `src/`, `tests/`, or `scripts/`, so a default-root run never
  sees it and FR-015 is not at risk;
- no exclusion pattern is needed for it, so no hole is opened;
- it is destroyed by pytest when the test ends, satisfying "the fixture must exist only for the
  duration of the test" literally rather than by convention.

**Correction, Adversarial Review #2.** An earlier draft of this section claimed the test file was
protected twice over, by the exact-path exclusion and independently by the positional rule, on the
grounds that its markers "live in Python string literals, not in comment position". That is false
as stated, and the contract is what falsifies it. C5 (`contracts/dead-suppression-cli.md:120-124`)
is a purely textual rule: a line matches when a marker appears anywhere after the **first**
occurrence of a comment introducer on that line. It does not know what a string literal is. The
negative test has to materialise a fixture line carrying an introducer and a marker together, and
`quickstart.md:81` shows the natural shape of it:

```python
fixture.write_text("x = 1  # lgtm[py/some-rule]\n")   # WRONG: this source line matches C5
```

That single source line contains `#` before `lgtm[` and the checker flags it, string literal or
not. So the second mechanism does not exist by default. It has to be built:

```python
INTRODUCER = "#"
MARKER = "lgtm[py/some-rule]"
fixture.write_text(f"x = 1  {INTRODUCER} {MARKER}\n")  # no source line carries both
```

The requirement, which a task must state literally: **no single source line of
`test_check_dead_suppressions.py` may contain a comment introducer followed by a marker.** Split
the introducer and the marker across separate expressions, as above. Do this for the `codeql[`
case too. With that done the belt-and-braces property is real; without it the exact-path exclusion
is the only thing holding the file, and it is one rename away from a permanently red gate.

The test file must also **not** carry a marker in an actual `#` comment. A task should say so,
because "add a comment showing what a bad line looks like" is exactly the well-meaning edit that
turns the gate permanently red.

---

## The rewrite itself

Current, `scripts/regenerate-mermaid-url.py:80-86`:

```python
    # Check for common Mermaid syntax errors (not HTML filtering)
    # CodeQL py/bad-tag-filter: False positive - validates Mermaid arrow syntax, not HTML
    if re.search(r"-->\s*$", code, re.MULTILINE):  # lgtm[py/bad-tag-filter]
        errors.append("Arrow without target node (line ends with -->)")

    if re.search(r"==>\s*$", code, re.MULTILINE):
        errors.append("Thick arrow without target node (line ends with ==>)")
```

Target shape:

```python
    # Check for common Mermaid syntax errors (not HTML filtering)
    # Deliberately not a regex. CodeQL's py/bad-tag-filter fires on any pattern that
    # lexically resembles an HTML-tag filter, and no inline lgtm/codeql comment can
    # suppress it in this repository's scanning setup. Rewriting this back into
    # re.search reopens a high-severity alert that has already made two round trips.
    # split("\n") and bare rstrip() are both load-bearing: splitlines() also breaks on
    # \v \f \r \x85 U+2028 U+2029, which regex $ under MULTILINE does not.
    if any(line.rstrip().endswith("-->") for line in code.split("\n")):
        errors.append("Arrow without target node (line ends with -->)")

    if re.search(r"==>\s*$", code, re.MULTILINE):
        errors.append("Thick arrow without target node (line ends with ==>)")
```

Four things to hold onto:

- `code.split("\n")`, never `code.splitlines()`. The spec records 0 mismatches for the former and
  385 for the latter over an 8,057-input corpus. FR-003 first half.
- Bare `rstrip()`, never `rstrip(" \t")`. Default trimming matches `\s` on every code point
  checked from U+0000 to U+2FFF. FR-003 second half, and the half that is easy to lose because the
  separator argument absorbs all the attention.
- The `==>` line stays byte-identical. It is the control that proves the finding is lexical
  (FR-002, SC-010), and `import re` therefore stays in the file. A task that "tidies up the now
  unused import" breaks the build.
- The note is FR-020 and is the only artefact in this feature addressing the third round trip.
  A behavioural test cannot, because a regex implementation passes it identically.

---

## Testing plan

Two new files, both under `tests/unit/scripts/`, both collected by the required `Run Tests` job.

**`test_regenerate_mermaid_url.py`** (FR-001, FR-004, SC-003, SC-009). Imports the script under
test. Note the filename is hyphenated (`regenerate-mermaid-url.py`) and therefore *not* directly
importable, so this test loads it with `importlib.util.spec_from_file_location`. That is a real
constraint on the task and is called out here so it is not discovered mid-implementation. Renaming
the script to fix it is out of scope: it is referenced by path in docs and the Makefile.

- A differential test rebuilding the original `re.search(r"-->\s*$", code, re.MULTILINE)` as a
  local oracle and asserting agreement over at least 1,500 inputs. The corpus is generated in the
  test, not committed as a fixture: exhaustive products over an atom set containing `-->`, `==>`,
  `<!--`, space, tab, `\r`, `\n`, `\v`, `\f`, `\x85`, U+2028, U+2029, and a non-breaking space,
  plus seeded random strings, plus the hand-chosen cases from Edge Cases. Fixed seed, so a failure
  is reproducible.
- Named regression tests for each Edge Case bullet: trailing whitespace after an arrow, CRLF
  endings, empty input, whitespace-only input, trailing blank lines, arrow with a target, arrow
  with a target on one line and a bare arrow on a later line.
- A guard asserting the thick-arrow branch still fires, so SC-010's control is exercised and not
  merely eyeballed.

**`test_check_dead_suppressions.py`** (FR-008, FR-009, FR-014, SC-006). Imports
`scripts.check_dead_suppressions` directly.

- The negative test described above, via `tmp_path` plus `DEAD_SUPPRESSION_ROOTS`, for both
  `lgtm[` and `codeql[` (US3 scenarios 1 and 2).
- Output assertions: the failure names the file, the line number, the marker, why the form is
  inert, and the supported alternative (FR-014). Assert on substrings, not on exact formatting.
- A positional-rule test: a marker in a string literal and a marker in a URL do not fire; the same
  marker after `#` does.
- A self-exclusion test asserting the checker's own path and its own test path are in
  `SELF_EXCLUSIONS`, and that a *different* file with the same basename in `tmp_path` is still
  flagged. That second assertion is the whole point of FR-009 and the one that would have caught
  the precedent's basename hole.
- A zero-files-scanned test asserting exit code 2, not 0. If a root is ever moved or renamed,
  "scanned nothing" must not read as "found nothing".
- A clean-tree test running the checker against the real default roots and asserting exit 0
  (SC-005, FR-015). This one is a canary: it goes red the day somebody adds a marker, which is the
  behaviour being bought.
- One subprocess test invoking the checker as a CLI to pin the exit-code contract. Use
  `sys.executable`, not a bare `python3`. A bare `python3` resolves differently per machine and per
  shell: on the reference machine `/usr/bin/python3` is 3.12.3 while `python3` reaches 3.13.0
  through a pyenv shim, and CLAUDE.md records 3.10 as the Ubuntu system interpreter.
  `scripts/scan-waitforresponse-race.py:72-74` documents the same spread. The test must pin the
  interpreter it is running under rather than gamble on `PATH`. CI is unaffected either way,
  because `setup-python` puts 3.13 on `PATH` there.

---

## Verification and the merge boundary

The spec is unusually clear that half of this cannot be verified before merge, and the plan
inherits that shape.

**Before merge**, everything except the alert. `make audit-pragma` exits zero. `pytest
tests/unit/scripts/` passes. The `Lint` job runs the new step and passes. A scratch commit adding
a marker to a source file turns `Lint` red, which is SC-011 measured by observation rather than by
reading the recipe. Note that the scratch commit also turns `Run Tests` red, through the clean-tree
canary in the Testing plan. Two red contexts is the expected result, not a second defect.

### Re-verification immediately before merge (FR-015)

FR-015 does not stop at "the audit exits zero against the post-change tree". It requires that
cleanliness to be **re-verified against the exact tree being merged, immediately before the
blocking behaviour lands**, and explicitly forbids inferring it from a measurement taken during
planning. The planning measurement is `research.md` R-0a, taken 2026-07-30. It is not evidence
about the merge commit.

This is not ceremony. This worktree is shared with concurrent work, `scripts/` has never been
inside the RUF100 path set before, and a single `# noqa` arriving there between planning and merge
converts FR-011 into a day-one failure for everybody who runs the target. The same exposure applies
to the checker's own source, which lands in `scripts/` for the first time in this feature and is
linted under the full configured ruleset by the widened line (see Constraints).

Run on the merge commit, after the final rebase, before the target's blocking line is left in:

```bash
source .venv/bin/activate
ruff check --extend-select RUF100 src/ tests/ scripts/   # expect "All checks passed!", exit 0
grep -rnE "lgtm\[|codeql\[" src/ tests/ scripts/         # expect only the two auditor files
make audit-pragma; echo "exit=$?"                        # expect exit=0
```

Scope note, so the exposure is not overstated. This reaches `make audit-pragma` only. The `Lint`
job runs `ruff check src/ tests/` (`.github/workflows/pr-checks.yml:61-62`) and never sees
`scripts/`, so a stray `# noqa` there cannot redden a required check. It can only redden the local
target, which is precisely the "gate that blocks contributors on introduction" FR-015 names.

`research.md`'s "Open items carried forward" item 2 belongs to the same boundary: re-confirm the
required contexts with the R-0d command before merging the CI step. The precedent's own comment at
`.pre-commit-config.yaml:214-229` says plainly not to trust that list without re-checking.
`quickstart.md` section 4 carries the operator-facing form of both.

**After merge**, the alert. Per FR-016 and FR-022, evidence comes from the branch-level analysis,
never from a green pull request check, because pull request analysis is diff-informed.

```bash
# --paginate is MANDATORY. The default page size is 30 and the all-states alert corpus on this
# repository is 137, so an unpaginated read truncates, and truncation renders as CLEAN. Measured
# 2026-07-30: the unpaginated form with a client-side `select(.state == "open")` returns ZERO
# open alerts while the paginated form returns FIVE (144, 147, 148, 149, 150). That unpaginated
# form is step 1 of the mandatory pre-push checklist in CLAUDE.md, and it has been printing a
# clean bill of health over five open alerts, one of which is alert 147. Carded at campaign level.
#
# --slurp cannot be combined with --jq, so the pages are written out and filtered separately.
# That is not a workaround, it is the point: it makes gh's exit status readable instead of
# hiding it downstream of a pipe, which is the same defect class this feature exists to remove.
gh api --paginate --slurp \
  "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" \
  > /tmp/alerts-open.json
echo "gh_exit=$?"
jq 'add | {count: length, alerts: map({n:.number, rule:.rule.id, path:.most_recent_instance.location.path})}' \
  /tmp/alerts-open.json
echo "jq_exit=$?"

# Corpus floor. The pass condition below is an EMPTY result, so the read must independently prove
# it reached the API and saw the whole corpus. Without this, a failed or truncated read is
# indistinguishable from a clean repository.
gh api --paginate --slurp \
  "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?ref=refs/heads/main&per_page=100" \
  > /tmp/alerts-all.json
echo "gh_exit=$?"
jq 'add | length' /tmp/alerts-all.json
```

Key the result on **path plus rule id**, never on the number. CodeQL demonstrably closes an alert
and opens a fresh number at the same site, so `147` is not a stable identifier and a check written
against it can report success while the finding is still there under a new number. The pass
condition is: both `gh_exit=0`, the corpus floor at or above 137, no open alert with rule
`py/bad-tag-filter` at path `scripts/regenerate-mermaid-url.py`, and the total open count down by
exactly one (SC-002). A corpus floor of `0`, or a non-zero `gh_exit`, means the read failed and
proves nothing about the alert.

If the alert is still open after merge, the response is a follow-up change to the same line, not a
revert (FR-022). The rewrite is behaviour-preserving by FR-001, so reverting restores a pattern and
buys nothing.

No scanning result is a required check here, so none of this holds a merge. That is a stated
property of the repository, not a gap in the plan.

---

## Artifacts deliberately skipped

**`data-model.md` is not produced.** The spec's "Key Entities" section lists Alert 147, the inline
suppression marker, the audit path set, and the audit check. None of those is a data structure this
feature designs, persists, or serialises. Alert 147 is a record in a third-party system this
feature only reads. The marker is a substring. The path set is a tuple of directory names, already
pinned above. The audit check is a shell line. Writing a data model for them would produce a page
restating the plan in table form, which is padding, and the task brief asked for it to be named
rather than manufactured.

**`contracts/` is produced, with one file, against the brief's default.** The brief said no API
contracts, and there is no API. But the checker has two independent consumers, the Makefile recipe
and the CI `Lint` step, and its invocation, exit codes, and root-override variable are a real
interface between them. This repository has already been burned by exactly that gap: the
waitForResponse detector needed
`specs/002-waitforresponse-lint-guard/contracts/detector-cli.md` written for the same reason, and
that document records four requirements that turned out to contradict the owning spec. A CLI
contract here is the same object, not an API contract, and it is one page.

**`quickstart.md` is produced** and is short. It is the runbook for the post-merge verification,
which happens on a different day from the implementation and possibly by a different person.

**The agent-context update script is not run.** `.specify/scripts/bash/update-agent-context.sh`
writes to `CLAUDE.md` at the repository root, which is outside this task's write scope
(`specs/001-bad-tag-filter-dead-suppression/` only) and is shared with three sibling agents in the
same worktree. There is also nothing to add: this feature introduces no technology. Python 3.13 is
already listed many times over, and the checker imports only the standard library.

---

## Adversarial Review #2

Reviewer did not author the spec or the plan. This is not a re-run of Adversarial Review #1, which
gated at 0 CRITICAL / 0 HIGH on `spec.md` alone. The subject here is **drift**: Stage 4 clarify
writes answers into `spec.md` and revisits nothing else, so `plan.md`, `research.md`,
`contracts/`, and `quickstart.md` were checked against the five clarification answers and against
each other. Every claim below was reproduced with a command before being written down. Line
references were taken with `grep -n` on 2026-07-30, before the fixes in this section were applied.

### Findings

| Sev | ID | Finding | Resolution |
|---|---|---|---|
| HIGH | D1 | **FR-015 drift.** Clarify Q2 turned "re-check the widened path set before it becomes blocking" from a `research.md` planning note into an FR, and wrote the operator step into `quickstart.md:97-100`. `plan.md` was never revisited. Worse, `plan.md:163` already pointed forward at "the re-verification section below" and no such section existed: verified against the file's complete heading list. The plan therefore promised a step it did not contain, and tasks are cut from the plan. | FIXED. New "Re-verification immediately before merge (FR-015)" subsection under Verification and the merge boundary, with the three commands, the shared-worktree reason, the scope note that the exposure is `make audit-pragma` only, and the R-0d re-confirmation. `plan.md`'s §2 bullet repointed at it. |
| HIGH | D2 | **Q4 drift, plus an implementability collision nobody caught.** Clarify Q4 relaxed contract C1 to a **3.9 floor** and forbade version-gated syntax (`contracts/dead-suppression-cli.md:30,38-46`). `plan.md:25` still declared "Python 3.13" and `research.md:132` still read "**Decision**: ... Python 3.13, standard library only", contradicting a normative contract clause. The collision underneath is the real finding: `pyproject.toml` sets `target-version = "py313"` and selects `UP`, and §2 widens `ruff check --extend-select RUF100` to `scripts/` on a **blocking** line, with `--extend-select` adding to the configured selection rather than replacing it. Reproduced against the pinned ruff 0.15.14: 3.9-shaped source trips UP035, UP006, UP045, and UP036. A checker written to C1's floor reddens the blocking line on day one, which is the exact failure FR-015 exists to prevent. No artifact recorded the reconciliation. | FIXED. `plan.md` Technical Context rewritten to name the 3.9 floor as the checker's exception, plus a new "Reconciling the 3.9 floor with ruff" block under Constraints giving the four rules that satisfy both (`from __future__ import annotations`; PEP 604 in annotations only; no `sys.version_info` guard; checker and its test must be ruff-clean under the full configured set before the widened line is left blocking). `research.md` D-2 decision line corrected. |
| HIGH | D3 | **A load-bearing claim, falsified against the contract.** `plan.md:314-317` and `research.md:309-313` asserted the negative test is protected twice over, by the exact-path exclusion and independently by the positional rule, because its markers "live in Python string literals, not in comment position". C5 (`contracts/dead-suppression-cli.md:120-124`) is a purely textual rule and does not know what a string literal is: a line matches when a marker appears after the first comment introducer on it. The negative test must materialise a fixture line carrying both, and `quickstart.md:81` shows the natural shape, `printf 'x = 1  # lgtm[py/some-rule]\n'`. Written as one source line, that line matches. The second mechanism did not exist. Same shape as the AR#1 F5 finding: a confident claim drawn from cases that could only confirm it. | FIXED. `plan.md` §7 now carries the correction, the wrong and right forms side by side, and a literal requirement a task can copy: no single source line of the test file may contain a comment introducer followed by a marker, for `lgtm[` or `codeql[`. `research.md` D-7 corrected to match. |
| HIGH | D4 | **`spec.md` keys its primary outcome on an unstable identifier, and the plan forbids exactly that.** SC-001 read "Alert 147 reports a state other than open", and Key Entities calls that state "the feature's primary outcome measure". `plan.md:441-443` and `quickstart.md:168-170` both say the opposite in terms: "Key the result on path plus rule id, never on the number ... a check written against `147` can report success while the finding is still there under a new number." Remediation demonstrably closes a number and opens a fresh one at the rewritten line. SC-002 and `quickstart.md`'s pass condition 1 give defence in depth, but the criterion the spec calls primary was keyed the one way the plan bans. | FIXED. SC-001 rekeyed onto rule plus path, with the number demoted to a locating label and the reason stated. US1's Independent Test rekeyed to match. US1 scenario 1 and Key Entities still name 147; left alone deliberately, as narrative identification rather than measurement. |
| MEDIUM | D5 | **Stale census.** `plan.md:262` gave `.py` (563) for the three roots. Measured: 543 (`src` 135, `tests` 393, `scripts` 15), which is what `research.md:212-214` records and what makes the 583 allowlisted total in `plan.md:31` and `contracts/dead-suppression-cli.md:184` arithmetically correct (543+27+7+5+1). The 563 was the only outlier. | FIXED, single line. |
| MEDIUM | D6 | **Phase 1 self-invalidation.** `research.md:56` read "Tree-wide the only other file holding markers is this feature's own `spec.md`". True when written, false the moment `plan.md`, the contract, and `quickstart.md` were produced. Measured across the feature directory: 32 occurrences at review start, in five files. This is FR-021's own thesis demonstrating itself inside the artifact that argues for it. | FIXED, one paragraph, with the per-file breakdown and a note that the number only grows. |
| MEDIUM | D7 | **Q1 drift.** Clarify Q1 recorded the scope growth into a required status check as an owner-rejectable decision and put the fallout in `spec.md:22`. `plan.md` §3 presented the CI step as settled and carried none of it. Tasks are cut from the plan, so a rejection would have had no plan-level landing point, and the campaign constraint is that the growth is neither silently expanded nor silently retracted. | FIXED. `plan.md` §3 now opens with the accept/reject fallout, names exactly what falls (FR-018, FR-019, SC-011, SC-012, US3 scenarios beyond the fifth, this section and its task), states that sections 1, 2, and 4 through 7 are unaffected, and forbids widening the CI footprint beyond the single step. |
| MEDIUM | D8 | **Inaccurate isolation claim.** `plan.md:28` says the new tests are "No AWS, no moto, no network" and `plan.md:102` lists `tests/unit/scripts/conftest.py` as "Existing, untouched". That conftest imports `boto3` and `moto` at module level (`tests/unit/scripts/conftest.py:12-16`), and pytest imports a directory's conftest for every test collected in it. Both new files therefore pull moto in at collection. Not a breakage: `requirements-ci.txt:50` pins `moto[all]==5.2.2` and the `Run Tests` job installs it. But the Constitution Check row at `plan.md:57` rests on a claim that is inaccurate as written, and the tests are not runnable in a bare stdlib environment. | RECORDED, not fixed. Needs a wording call rather than a one-line correction, and no gate result changes. |
| LOW | D9 | `plan.md:287` claimed the introducer set covers "Python, shell, YAML, HCL, JS/TS, HTML, and SQL, which is every language in the allowlist". `.sql` is not in the allowlist (`contracts/dead-suppression-cli.md:85`). `--` is the loosest introducer in the set and matches any line with `--` before a marker, a `-->` arrow included. | FIXED, single edit: SQL dropped from the coverage claim, `--` retained with its false-positive cost stated. |
| LOW | D10 | Four artifacts cite four different line ranges for the same `.pre-commit-config.yaml` comment block: `spec.md:238` says 214-225, `spec.md:259` says 214-229, `plan.md:211` says 220-228, `research.md:287` says 214-228. Measured, the block spans 214-229. All four land inside it, so nothing is misdirected. | RECORDED, not fixed. Four edits across three files for zero behavioural gain. |
| LOW | D11 | `quickstart.md:126-134` tells the verifier to push a scratch marker commit and "confirm `Lint` reports failure". It also turns `Run Tests` red, through the clean-tree canary the plan mandates in the Testing plan. A verifier seeing two red contexts should not go hunting for a second defect. | FIXED opportunistically, one sentence in `plan.md`'s "Before merge" paragraph. `quickstart.md` left alone. |

Counts: 0 CRITICAL, 4 HIGH, 4 MEDIUM, 3 LOW. All four HIGH fixed by direct edit. D5, D6, D9, and
D11 were single-line or single-paragraph and were fixed opportunistically. D8 and D10 are recorded
unfixed.

### Verification performed

| Claim under test | Method | Result |
|---|---|---|
| `plan.md` contains a re-verification section | Full heading extraction, `grep -n "^#\+ "` | Absent. 17 headings, none of them it. `plan.md:163` pointed at nothing |
| Contract C1's 3.9 floor is reachable under the repo's ruff config | Wrote a 3.9-shaped file, ran the pinned ruff 0.15.14 with `--select UP,F --target-version py313` | 4 errors: UP035, UP006, UP045, UP036. Floor reachable only via `from __future__ import annotations` |
| `--extend-select` adds to the configured selection | `pyproject.toml` `[tool.ruff.lint] select` read directly | `E W F I B C4 UP S RUF100`. The widened blocking line lints the new checker under all of it |
| The precedent needed a UP036 suppression for a version guard | `scripts/scan-waitforresponse-race.py:70-81` | `# noqa: UP036` present, with the same reasoning in a comment |
| C5 fires on an introducer inside a string literal | Read C5 against the `quickstart.md:81` fixture line | Matches. `#` precedes `lgtm[` on that line; the rule is textual |
| `.py` census across the three roots | `find src tests scripts -name '*.py' -not -path '*/__pycache__/*' \| wc -l` | 543, not 563 |
| Allowlisted-file total | `find` over the ten allowlisted extensions | 583. Confirms `plan.md:31` and contract C7 |
| Marker population, audited roots | `grep -rnE "lgtm\[\|codeql\[" src/ tests/ scripts/` | Exactly one, `scripts/regenerate-mermaid-url.py:82`. SC-004 holds |
| Marker population, feature directory | Per-file count across the five artifacts | 32: spec 15, contract 8, plan 6, quickstart 2, research 1 |
| `Makefile` audit-pragma line range | `sed -n '82,95p' Makefile` | 85-92. `plan.md:105` correct |
| `make validate` prerequisites | `Makefile:42` | Seven, `audit-pragma` absent. Confirmed |
| Required contexts asserted in-repo | `.pre-commit-config.yaml:214-229` | `["Secrets Scan","Lint","Run Tests","Playwright E2E Tests"]`, with "do not trust that list" |
| `Lint` job installs | `.github/workflows/pr-checks.yml:52-55` | `ruff==0.15.14` only. FR-019 satisfiable |
| waitForResponse guard placement | `.github/workflows/pr-checks.yml:67-87` | Comment 67-84, step 85-87. `plan.md` §3 correct |
| `Lint` job's ruff scope | `.github/workflows/pr-checks.yml:61-62` | `ruff check src/ tests/`. `scripts/` never linted by a required check |
| `Run Tests` can collect the new tests | `pyproject.toml` `testpaths`, `pr-checks.yml:119-127`, `requirements-ci.txt` | `testpaths = ["tests"]`, no ignore covering `tests/unit/scripts/`, moto and boto3 present |
| Coverage gate reaches `scripts/` | `[tool.coverage.run] source` | `["src"]`. The new checker is not measured, `--fail-under=80` unaffected |
| The import precedent works as claimed | `tests/unit/scripts/test_consolidate_oauth_apply.py:13`, absence of `scripts/__init__.py` | `import scripts.consolidate_oauth_duplicates as mod`, PEP 420. `plan.md` §1 correct |
| `split("\n")` appears everywhere the rewrite is specified | Read all five artifacts | Consistent. No `splitlines()` recommended anywhere; it appears only as the rejected form |
| Differential corpus floor stated at >= 1,500 | spec SC-003, `plan.md` Testing plan, `quickstart.md:27` | Present in all three |
| Subprocess test pins `sys.executable` | `plan.md` Testing plan, final bullet | Present, with the corrected per-machine reason |
| Banned terms in the feature directory | Case-insensitive scan for all seven | Clean |
| `plan.md` line 21 is a real value | `sed -n '21p'` | Prose, no template placeholder |

### Gate

**GATE: 0 CRITICAL, 0 HIGH remaining.**
