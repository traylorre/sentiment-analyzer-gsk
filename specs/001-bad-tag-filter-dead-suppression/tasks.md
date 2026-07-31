# Tasks: Close py/bad-tag-filter and Kill the Dead Suppression

**Feature**: `001-bad-tag-filter-dead-suppression`
**Input**: `spec.md`, `plan.md`, `research.md`, `contracts/dead-suppression-cli.md`, `quickstart.md`
**Date**: 2026-07-30

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel. Different files, no dependency on another unfinished task.
- **[Story]**: `US1`, `US2`, `US3`. `[GATE]` additionally marks the owner-rejectable FR-018 block.
- Every task names exact paths. Every verification task names the exact command and the exact pass
  condition.

## Conventions that every verification task inherits

Three of these come from defects this feature exists to remove. They are stated once here and are
binding on every task below.

1. **Never read an exit code from downstream of a pipe.** `Makefile:90` is why this feature exists:
   `bandit ... | grep -E "^(>>|Issue)" || echo "No issues found"` makes the recipe inherit `grep`'s
   status, so the line cannot fail. Any verification command containing a pipe MUST assert on
   `${PIPESTATUS[0]}` (or on the specific element being tested), never on `$?`.
2. **"Empty output" and "exit 0" are not pass conditions on their own.** A check that has never been
   observed failing has not been shown capable of failing. Every gate introduced here has a paired
   red-test: T013 for the differential oracle, T029 for the checker, T040 for the Makefile wiring,
   T044 for the CI step.
3. **Never key an outcome on a code-scanning alert number.** Alert 147 is a locating label. The
   analyzer demonstrably closes a number and opens a fresh one at the same site, so every criterion
   is keyed on **path plus rule id**. This applies to acceptance scenarios and Independent Test
   lines too, not only to the SC block.
4. **`make validate` cannot pass on this tree.** `scripts/check-banned-terms.sh` exits 1 on
   pre-existing matches from concurrent features. No task requires it to be green. Mirror the
   required `Lint` job's individual steps instead (T050).
5. **Run everything under the project virtual environment**: `source .venv/bin/activate` first,
   except where a task deliberately tests a bare `python3` or `sys.executable`.
6. **Never read the code-scanning alert list without `--paginate`, and never accept an absence from
   a read that has not proven itself.** The default page size is 30 and this repository's all-states
   alert corpus is 137, so an unpaginated read truncates and truncation renders as clean. Measured
   2026-07-30: unpaginated returns zero open alerts, paginated returns five. `--slurp` cannot be
   combined with `--jq`, so write the pages out and filter with a separate `jq`; that also keeps
   `gh`'s exit status readable rather than hidden downstream of a pipe. Wherever the pass condition
   is an absence, pair it with an all-states corpus floor, because a failed or truncated read looks
   exactly like a clean repository. This is convention 2 applied to a remote reader.

---

## Phase 1: Pre-flight baselines

**Purpose**: capture the numbers that later criteria are measured against. All five are read-only
and none modifies the tree.

- [ ] **T001** [P] Record the pre-merge open-alert baseline for SC-002 and FR-017.
  - Command:
    ```bash
    gh api --paginate --slurp \
      "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" \
      > /tmp/alerts-open-before.json
    echo "gh_exit=$?"
    jq 'add | {count: length, alerts: map({n:.number, rule:.rule.id, path:.most_recent_instance.location.path, line:.most_recent_instance.location.start_line})}' \
      /tmp/alerts-open-before.json
    echo "jq_exit=$?"

    gh api --paginate --slurp \
      "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?ref=refs/heads/main&per_page=100" \
      > /tmp/alerts-all-before.json
    echo "gh_exit=$?"
    jq 'add | length' /tmp/alerts-all-before.json
    echo "jq_exit=$?"
    ```
  - Pass condition: every `gh_exit=0` and `jq_exit=0`; the all-states corpus count is **at least
    137**; the open set contains exactly one entry whose `rule` is `py/bad-tag-filter` and whose
    `path` is `scripts/regenerate-mermaid-url.py`; and the output is pasted verbatim into the pull
    request description. Record the open `count` as **N**; SC-002 later requires `N - 1`.
  - **`--paginate` is mandatory and this is not defensive padding.** The default page size is 30 and
    the all-states corpus is 137. Measured 2026-07-30: the unpaginated form with a client-side
    `select(.state == "open")` returns **zero** open alerts while the paginated form returns **five**
    (144, 147, 148, 149, 150). Truncation renders as clean. A sibling feature in this campaign
    extends the analysis matrix over tens of thousands of previously unanalyzed lines and is expected
    to raise the open count substantially on purpose, at which point even the server-side
    `state=open` filter overflows one page and SC-001 starts passing because the read was cut short
    rather than because the finding is gone. This is the same defect class as `Makefile:90`: a check
    that structurally cannot report dirty.
  - **`--slurp` cannot be combined with `--jq`.** Write the pages out and filter with `jq`
    separately. That keeps `gh`'s exit status readable rather than hidden downstream of a pipe;
    `gh` failing and `gh` returning nothing are otherwise indistinguishable.
  - **The corpus floor is load-bearing.** SC-001's pass condition is an absence, so the read must
    independently prove it reached the API and saw the whole corpus. A floor of `0` means the read
    failed, and a failed read is evidence of nothing.
  - Note: the rule id is `py/bad-tag-filter`. It is a Python file and the CodeQL Python pack owns
    the finding. Any task or note reading `js/bad-tag-filter` is wrong.

- [ ] **T002** [P] Re-confirm the four required status check contexts (research R-0d, precondition
      for FR-018 and Phase 6).
  - Command:
    ```bash
    gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection \
      --jq .required_status_checks.contexts
    echo "exit=$?"
    ```
  - Pass condition: `exit=0` **and** the output contains `"Lint"`. Both halves are required, in that
    order. This endpoint returns a single object rather than a page, so `--paginate` does not apply,
    but it shares the alert queries' failure mode: a 404, an expired token, or a permissions change
    all produce **empty output**, which reads identically to "branch protection requires nothing".
    Never read empty as an answer here, because the answer it would imply is the one that
    invalidates FR-018's premise. If `Lint` is genuinely absent, Phase 6 cannot satisfy FR-018 as
    designed and the whole phase is blocked pending an owner decision.

- [ ] **T003** [P] Re-confirm the widened unused-pragma path set is clean (research R-0a, FR-011,
      FR-015 baseline).
  - Command:
    ```bash
    source .venv/bin/activate
    ruff check --extend-select RUF100 src/ tests/ scripts/; echo "exit=$?"
    ```
  - Pass condition: `All checks passed!` and `exit=0`. `--extend-select` **adds to** the configured
    `select` in `pyproject.toml` (`E W F I B C4 UP S RUF100`), so this is a full-ruleset result, not
    a RUF100-only one. Re-run at T047 against the merge commit; this measurement is not evidence
    about that commit.

- [ ] **T004** [P] Record the baseline marker population in the audited path set (SC-004 "before"
      state).
  - Command:
    ```bash
    grep -rnE "lgtm\[|codeql\[" src/ tests/ scripts/; echo "exit=$?"
    ```
  - Pass condition: exactly one line of output, `scripts/regenerate-mermaid-url.py:82`, and
    `exit=0`. Do **not** run this tree-wide: this feature's own artifacts contain dozens of marker
    occurrences by necessity, which is FR-021's entire subject.

- [ ] **T005** [P] Record the advisory bandit baseline the widened path set will surface (FR-012,
      spec assumption "Advisory findings stay advisory").
  - Command:
    ```bash
    source .venv/bin/activate
    bandit -r scripts/ --ignore-nosec 2>/dev/null | grep -cE "^>>"; echo "bandit_exit=${PIPESTATUS[0]}"
    bandit -r src/     --ignore-nosec 2>/dev/null | grep -cE "^>>"; echo "bandit_exit=${PIPESTATUS[0]}"
    ```
  - Pass condition: `10` for `scripts/` and `15` for `src/`. Record both. If either differs, the
    spec assumption's count is stale and the difference is recorded in the pull request rather than
    silently absorbed. These findings are pre-existing, advisory, and explicitly out of scope.

---

## Phase 2: Foundational

**Purpose**: pin the one shared fact both new test files depend on. Blocks Phase 3 and Phase 5's
test tasks.

- [ ] **T006** Confirm `tests/unit/scripts/` is the correct home for both new test files, and record
      the collection-time dependency it carries.
  - Both new tests go in `tests/unit/scripts/`. `pyproject.toml:142` sets `testpaths = ["tests"]`,
    and the required `Run Tests` job's ignore list does not cover that directory, so placement alone
    satisfies FR-004's "where the repository's required test check collects it".
  - **Known constraint, must not be restated as an isolation claim**: `tests/unit/scripts/conftest.py`
    imports `boto3` and `moto` at module level, and pytest imports a directory's conftest for every
    test collected in it. Both new files therefore pull `moto` in at collection. This is not a
    breakage (`requirements-ci.txt` pins `moto[all]` and the `Run Tests` job installs it), but the
    new tests are **not** runnable in a bare standard-library environment. `plan.md`'s Technical
    Context "No AWS, no moto" line is inaccurate as written; see Cross-Artifact Analysis F3.
  - Command:
    ```bash
    source .venv/bin/activate
    pytest tests/unit/scripts/ -q --collect-only >/dev/null; echo "exit=$?"
    ```
  - Pass condition: `exit=0`. A collection error naming `boto3` or `moto` means the environment is
    incomplete, not that the placement is wrong.

**Checkpoint**: US1, US2, and US3 core can now proceed.

---

## Phase 3: User Story 1 - Security reviewer sees a genuinely clean alert list (P1)

**Goal**: the arrow-without-target check is no longer a pattern, and behaviour is proven unchanged.

**Independent Test**: `pytest tests/unit/scripts/test_regenerate_mermaid_url.py -v` passes,
including a differential run over at least 1,500 inputs with zero mismatches. The alert-state half
of US1 is measured post-merge in Phase 8, per FR-022.

- [ ] **T007** [US1] Rewrite the arrow-without-target check at `scripts/regenerate-mermaid-url.py:82`
      (FR-001, FR-002, FR-003, FR-020).
  - Replace `if re.search(r"-->\s*$", code, re.MULTILINE):  # lgtm[py/bad-tag-filter]` with:
    ```python
    if any(line.rstrip().endswith("-->") for line in code.split("\n")):
    ```
  - **`code.split("\n")`, never `code.splitlines()`.** This is the single highest-risk line in the
    feature. `str.splitlines()` also breaks on `\v`, `\f`, `\r`, `\x85`, U+2028 and U+2029, none of
    which regex `$` treats as a line boundary under `re.MULTILINE`. Three independent differential
    runs (1,572 / 8,057 / 8,852 inputs) put `split("\n")` at 0 mismatches and `splitlines()` at
    23 / 385 / 194. Worked counterexample: on `"A -->\rB"` the original expression is False, a
    `splitlines()` rewrite is True.
  - **Bare `rstrip()`, never `rstrip(" \t")`.** The narrowed form measured 694 mismatches. Default
    trimming and the expression's `\s` class agree on every code point checked from U+0000 to
    U+2FFF.
  - Add the FR-020 note directly above the line, stating that it is deliberately not a pattern
    match, that no inline suppression form works in this repository's scanning setup, and that
    `split("\n")` and bare `rstrip()` are both load-bearing. The note MUST NOT itself contain a
    marker in bracket form (`lgtm[`, `codeql[`), or the new checker flags the file it just fixed.
  - Do **not** touch the `==>` line on the following line. Do **not** remove `import re`: the
    control line still uses it and an unused-import tidy-up would break the build under ruff's `F`
    rules.
  - Depends on: T006 (nothing else).

- [ ] **T008** [P] [US1] Create `tests/unit/scripts/test_regenerate_mermaid_url.py` with a module
      loader (FR-004, SC-009).
  - The script under test is hyphenated (`regenerate-mermaid-url.py`) and therefore not importable
    by name. Load it with `importlib.util.spec_from_file_location`, resolving the path from the test
    file rather than from the current working directory. Renaming the script is out of scope: it is
    referenced by path in documentation and elsewhere.
  - The file must open with `from __future__ import annotations` and must be clean under
    `ruff check src/ tests/` and `ruff format --check src/ tests/`, both of which are steps in the
    required `Lint` job (`.github/workflows/pr-checks.yml:57-62`). Verified at T037 and T050.
  - Parallel with T007: different file, and the loader does not depend on the rewrite.

- [ ] **T009** [US1] Differential test over at least 1,500 inputs (FR-001, SC-003).
  - Rebuild the original expression as a local oracle inside the test:
    `re.search(r"-->\s*$", code, re.MULTILINE)`. Assert the rewritten check agrees with it on every
    input.
  - Corpus is generated in the test, not committed as a fixture. Build it from exhaustive one, two
    and three element products over an atom set containing at minimum: `-->`, `==>`, `<!--`, `--!>`,
    space, tab, `\r`, `\n`, `\v`, `\f`, `\x85`, U+2028, U+2029, a non-breaking space, and a plain
    letter. Add seeded random four to five element strings under a fixed seed so a failure is
    reproducible, plus the hand-chosen cases from the spec's Edge Cases.
  - The test MUST assert its own corpus size: `assert len(corpus) >= 1500`. Without that assertion
    the criterion is unfalsifiable, since a corpus that silently shrank to 12 inputs still reports
    zero mismatches.
  - On mismatch, the failure message must print the offending input with `repr()`, so an exotic
    separator is visible rather than invisible.
  - Depends on: T007, T008.

- [ ] **T010** [US1] Named regression tests for every Edge Case bullet (FR-004).
  - One named test each, so a failure identifies the case rather than the corpus index: trailing
    spaces after an arrow; trailing tabs after an arrow; a trailing non-breaking space and a
    trailing vertical tab after an arrow; CRLF line endings producing the same verdict as LF; empty
    input; whitespace-only input; input ending in several blank lines; an arrow with a target
    present (must not fire); an arrow with a target on one line and a bare arrow on a later line
    (must fire); the `"A -->\rB"` counterexample (must **not** fire, which is what separates
    `split("\n")` from `splitlines()`).
  - Depends on: T007, T008.

- [ ] **T011** [US1] Control test for the thick-arrow sibling (FR-002, SC-010).
  - Assert the `==>` branch still fires on input ending with a bare `==>`, so the control is
    exercised rather than eyeballed, and assert the validator still reports both messages
    independently.
  - Depends on: T008.

- [ ] **T012** [US1] VERIFY the US1 test module passes.
  - Command:
    ```bash
    source .venv/bin/activate
    pytest tests/unit/scripts/test_regenerate_mermaid_url.py -v; echo "exit=$?"
    ```
  - Pass condition: `exit=0`, zero failures, zero errors, and the differential test present in the
    passing list by name.
  - Depends on: T009, T010, T011.

- [ ] **T013** [US1] VERIFY the differential test can actually fail (red-test for the oracle).
  - A green differential test proves nothing until it has been observed separating a correct
    implementation from the known-incorrect one.
  - Procedure: temporarily change `code.split("\n")` to `code.splitlines()` in
    `scripts/regenerate-mermaid-url.py`, run the command from T012, then revert.
  - Pass condition: the mutated run exits **non-zero** with the differential test failing and the
    failure message showing a `repr()` containing one of `\r`, `\v`, `\f`, `\x85`, ` ` or
    ` `. Then `git diff -- scripts/regenerate-mermaid-url.py` after the revert must show the
    `split("\n")` form restored, and T012 must pass again.
  - Repeat once with `rstrip(" \t")` in place of `rstrip()`: the mutated run must also fail, with
    **some whitespace character other than a space or a tab** visible in the `repr()`. Do **not**
    hold out for a non-breaking space or a vertical tab specifically. Reproduced over a corpus
    built to T009's atom set (6,629 inputs): the narrowed trim produces 441 mismatches, but the
    *first* of them is `'-->\r'`, so a test that reports only the first mismatch shows a carriage
    return, and an operator waiting for a non-breaking space would record a correctly-red red-test
    as not having gone red. See Adversarial Review #3 finding G4. Revert.
  - Depends on: T012.

- [ ] **T014** [US1] VERIFY no pattern literal remains on the arrow-without-target check (FR-002).
  - Command:
    ```bash
    grep -n 're\.search' scripts/regenerate-mermaid-url.py; echo "grep_exit=$?"
    grep -c -- '-->' scripts/regenerate-mermaid-url.py
    ```
  - Pass condition: exactly one `re.search` line remains and it is the `==>` control line. No
    `re.search` line mentions `-->`.
  - Depends on: T007.

**Checkpoint**: US1 is complete and independently verifiable. The alert-state half is deferred to
Phase 8 by FR-022.

---

## Phase 4: User Story 2 - Maintainer is not misled by a comment that does nothing (P2)

**Goal**: the inert suppression and the stale explanatory note are gone, and nothing inline replaces
them.

**Independent Test**: `grep -rnE "lgtm\[|codeql\[" src/ tests/ scripts/` returns matches only inside
the auditor and its test (or nothing at all, if US3 has not landed yet).

- [ ] **T015** [US2] Delete the dead suppression and the stale note in
      `scripts/regenerate-mermaid-url.py` (FR-005, FR-006).
  - Delete the trailing `# lgtm[py/bad-tag-filter]` comment. Do **not** convert it to
    `# codeql[...]` or to any other inline suppression form: no inline form is honoured by this
    repository's scanning setup, and swapping one for the other is exactly what the January
    reintroduction did.
  - Delete or rewrite the adjacent `# CodeQL py/bad-tag-filter: False positive ...` line, which
    describes an expression that no longer exists. In practice it is replaced by the FR-020 note
    written in T007.
  - Same file and same line range as T007. Not parallel with it.
  - Depends on: T007.

- [ ] **T016** [US2] VERIFY the marker is gone from the file and was not replaced (FR-005, FR-006,
      US2 scenarios 1 and 2).
  - Command:
    ```bash
    grep -nE "lgtm\[|codeql\[|False positive" scripts/regenerate-mermaid-url.py; echo "grep_exit=$?"
    ```
  - Pass condition: no output and `grep_exit=1`. `grep_exit=0` means something is still there.
  - Depends on: T015.

- [ ] **T017** [US2] VERIFY the thick-arrow control is byte-identical (SC-010, US1 scenario 4).
  - **Do not use the form in `quickstart.md` section 2.** `git diff main -- <file> | grep -- "==>"`
    prints the control line as a *context* line, because the control sits exactly three lines below
    the changed line and git's default context is three. That command produces output on a
    correct change, so its stated pass condition ("expect no output") is false by construction. See
    Cross-Artifact Analysis F2.
  - Command:
    ```bash
    git diff main -- scripts/regenerate-mermaid-url.py | grep -E '^[+-].*==>'
    echo "git_exit=${PIPESTATUS[0]} grep_exit=${PIPESTATUS[1]}"
    ```
  - Pass condition: `git_exit=0` and `grep_exit=1` (no added or removed line mentions `==>`). Any
    output at all means the control was disturbed.
  - Depends on: T015.

- [ ] **T018** [US2] VERIFY the audited-path marker scan (SC-004, FR-021, US2 scenario 3).
  - Command:
    ```bash
    grep -rnE "lgtm\[|codeql\[" src/ tests/ scripts/; echo "grep_exit=$?"
    ```
  - Pass condition, two states depending on ordering:
    - Run after US2 but **before** US3's checker exists: no output, `grep_exit=1`.
    - Run after US3 has landed: output lines **only** from `scripts/check_dead_suppressions.py` and
      `tests/unit/scripts/test_check_dead_suppressions.py`. No other path may appear.
  - Never run tree-wide. This feature's own artifacts hold dozens of markers and always will.
  - Depends on: T015. Re-run after T036.

**Checkpoint**: US2 is complete. US1 and US2 together are the informational half of the feature and
stand regardless of the Phase 6 owner decision.

---

## Phase 5: User Story 3 core - the checker, its tests, and the local target (P3)

**Goal**: a dedicated, standard-library-only checker that detects inert inline suppression markers,
fails on them with an actionable message, and is wired into `make audit-pragma` with explicit
blocking status.

**Everything in this phase survives a rejection of FR-018.** Only Phase 6 falls.

**Independent Test**: seed a marker into a throwaway file outside the repository, point the checker
at it, and confirm it exits 1 naming file, line and marker. Remove it and confirm exit 0.

**Note on file ordering**: T019 through T025 all edit the same new file
(`scripts/check_dead_suppressions.py`) and are therefore strictly sequential, not parallel. They are
listed separately because each maps to a distinct normative contract clause and each is
independently checkable.

### The checker (contract clauses C1 through C7)

- [ ] **T019** [US3] Create `scripts/check_dead_suppressions.py` satisfying **C1** (invocation) and
      FR-009a (dedicated file).
  - Module docstring stating purpose, the exit codes, and the standard-library-only constraint.
  - **First line of code: `from __future__ import annotations`.** This is not stylistic. See the
    ruff reconciliation block below.
  - Standard library only: `argparse`, `os`, `sys`, `pathlib`. No import of anything from
    `requirements*.txt`. `.github/workflows/pr-checks.yml:52-56` installs `ruff==0.15.14` and
    nothing else in the `Lint` job, so a single third-party import puts a required check
    permanently red.
  - Positional arguments accepted and **ignored**, parsed with `parse_known_args`, so a pre-commit
    hook handing over a file list cannot narrow the scan.
  - Repository root resolved from `Path(__file__).resolve().parent.parent`, never from the current
    working directory. No `.venv` requirement. No executable bit assumed.
  - No network access, no filesystem writes.
  - **Reconciling C1's 3.9 floor with the repository's ruff configuration. This is the feature's
    biggest implementation risk and it has been reproduced, not theorised.** T038 widens
    `ruff check --extend-select RUF100` to `scripts/` on a **blocking** line of `audit-pragma`.
    `--extend-select` adds to `pyproject.toml`'s configured `select` (`E W F I B C4 UP S RUF100`)
    rather than replacing it, and `target-version = "py313"`. A 3.9-shaped file therefore trips
    `UP035`, `UP006`, `UP045` and `UP036` under the pinned ruff 0.15.14, reproduced against a
    purpose-written file. That is the exact day-one failure FR-015 exists to prevent. The binding
    resolution, all four parts:
    1. `from __future__ import annotations` at the top. Annotations then never evaluate at runtime,
       so PEP 604 (`str | None`) is valid back to 3.7 and `UP045` is satisfied at the same time.
    2. PEP 604 unions and builtin generics (`list[Path]`) **in annotations only**. Never where they
       are evaluated: no `isinstance(x, str | None)`, no runtime `typing.get_type_hints`.
    3. **No `sys.version_info` interpreter guard.** `UP036` flags it, the precedent needed
       `# noqa: UP036` to carry one (`scripts/scan-waitforresponse-race.py`), and C1 forbids
       version-gated syntax anyway. If one is ever added later, C1 also forbids it reusing exit code
       `2`, which C2 assigns to "zero files scanned".
    4. The file must be ruff-clean under the full configured set before T038 leaves the widened line
       blocking. Verified at T026.
  - Depends on: T006.

- [ ] **T020** [US3] Implement **C3**: default roots, extension allowlist, skip list, decoding.
  - Roots: `src/`, `tests/`, `scripts/`, resolved against the repository root (FR-010). A root that
    does not exist contributes zero files.
  - Extension allowlist, case-insensitive, exactly: `.py .sh .js .ts .tsx .jsx .html .yml .yaml .tf`.
    `.md` and `.txt` are absent on purpose: prose describing a marker has to write it, which is the
    defect that made the specification's original tree-wide criterion false at the moment it was
    written.
  - Skipped unconditionally at any depth: `__pycache__`, `node_modules`, `.venv`, `.git`,
    `.pytest_cache`, `.hypothesis`. This list is normative in C3 and `plan.md` section 5 carries the
    identical list; they must stay identical.
  - Read files as UTF-8 with `errors="replace"`, so one undecodable file cannot raise and take the
    gate down.
  - Depends on: T019.

- [ ] **T021** [US3] Implement **C4**: the `DEAD_SUPPRESSION_ROOTS` override.
  - `os.pathsep`-separated paths. Relative entries resolve against the repository root. The override
    **replaces** the default set entirely rather than extending it. The extension allowlist and the
    skip list still apply under an override.
  - This is a testing seam and nothing else. Neither consumer sets it (C8).
  - Depends on: T019.

- [ ] **T022** [US3] Implement **C5**: the positional detection rule.
  - A line matches when both hold: it contains `lgtm[` or `codeql[` compared case-insensitively,
    **and** the marker's position is after the first occurrence of a comment introducer on that
    line. Introducers: `#`, `//`, `<!--`, `/*`, `--`.
  - Matching is per line; markers spanning a line break are out of scope by design.
  - `--` is the loosest introducer in the set and matches any line carrying `--` before a marker, an
    arrow included. It is retained deliberately for the `.sql` extension that is **not** currently in
    the allowlist, and is a known false-positive source rather than an oversight.
  - The rule is purely textual. It does not know what a string literal is. That fact is load-bearing
    for T028 and was a falsified claim in an earlier draft of the plan.
  - Depends on: T019.

- [ ] **T023** [US3] Implement **C6**: exact-path self-exclusion.
  - ```python
    SELF_EXCLUSIONS = frozenset({
        Path("scripts/check_dead_suppressions.py"),
        Path("tests/unit/scripts/test_check_dead_suppressions.py"),
    })
    ```
  - A candidate is skipped **if and only if** it resolves inside the repository root **and** its
    repository-relative path is a member of that set. Exactly two members. Adding a third is a
    requirements change.
  - **Do not write a bare `path.resolve().relative_to(repo_root)`.** Under a
    `DEAD_SUPPRESSION_ROOTS` override the scan walks files outside the repository and `relative_to`
    raises `ValueError` on every one of them, which takes the T029 negative test down with it. Use a
    containment test (`Path.is_relative_to`, or `relative_to` inside `try/except ValueError`) and
    treat "outside the repository" as "not excluded".
  - Explicitly **not** the precedent's mechanism: `scripts/check-banned-terms.sh` uses a grep
    basename glob, which exempts any identically named file anywhere in the tree. FR-009 forbids
    that form.
  - Do **not** obfuscate the marker strings inside the checker to avoid matching itself. CLAUDE.md's
    SAST section says plainly not to restructure code to dodge detection.
  - Depends on: T019.

- [ ] **T024** [US3] Implement **C7**: output format, both paths (FR-014, FR-007).
  - Clean run to stdout, stating the roots and **the number of files scanned**, so a root that
    quietly shrank is visible in a passing log rather than only in an exit `2`.
  - Failing run to stdout, per finding: the **file**, the **line number**, the **marker**, and the
    offending source line. Then two blocks: **why the form is inert** (inline `lgtm[...]` and
    `codeql[...]` comments are not honoured by this repository's scanning setup and suppress
    nothing; a high-severity alert sat open on the default branch for six months behind exactly this
    comment, on the exact line the comment was on) and **what to do instead** (change the code so the
    finding does not arise; or dismiss it through the scanning product's own dismissal workflow with
    a recorded reason, which is the only suppression route with any effect here (FR-007); and do not
    swap one marker form for the other, because neither works).
  - Paths printed repository-relative when the file is inside the repository, **absolute when it is
    not**. Same reason as C6's containment test: under an override there is no repository-relative
    path to print, and `relative_to` would raise.
  - Depends on: T020, T022, T023.

- [ ] **T025** [US3] Implement **C2**: exit codes.
  - `0`: at least one file scanned, no marker found.
  - `1`: one or more markers found.
  - `2`: zero files scanned, for any reason.
  - `2` is separate from `0` deliberately. A scan that examined nothing must not report the same
    result as a scan that found nothing, or a moved root reads as a clean tree. The default roots
    are three hard-coded directory names, so this is live rather than theoretical.
  - Depends on: T020, T024.

### Static checks on the checker itself

- [ ] **T026** [P] [US3] VERIFY the real new file is ruff-clean under the full configured rule set.
  - This is the task that closes the 3.9-floor / ruff collision. It runs the real command against
    the real file, not a proxy.
  - Command:
    ```bash
    source .venv/bin/activate
    ruff check --extend-select RUF100 scripts/check_dead_suppressions.py; echo "exit=$?"
    ruff check --extend-select RUF100 src/ tests/ scripts/; echo "exit=$?"
    ```
  - Pass condition: `All checks passed!` and `exit=0` for **both** commands. Any `UP035`, `UP006`,
    `UP045` or `UP036` result means the file was written to the 3.9 floor without the four
    reconciliation rules from T019 and would redden the blocking line T038 introduces.
  - Depends on: T025.

- [ ] **T027** [P] [US3] VERIFY the 3.9 syntax floor and the standard-library-only constraint
      (C1, FR-019).
  - Command:
    ```bash
    source .venv/bin/activate
    python - <<'PY'
    import ast, pathlib, sys
    src = pathlib.Path("scripts/check_dead_suppressions.py").read_text(encoding="utf-8")
    try:
        ast.parse(src, feature_version=(3, 9))
    except SyntaxError as exc:
        sys.exit(f"FAIL: not parseable under 3.9: {exc.msg}")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    extra = mods - set(sys.stdlib_module_names) - {"__future__"}
    if extra:
        sys.exit(f"FAIL: non-stdlib imports: {sorted(extra)}")
    print("PASS: 3.9-parseable, stdlib-only:", sorted(mods))
    PY
    echo "exit=$?"
    ```
  - Pass condition: `exit=0` and a `PASS:` line. Known limitation, stated so it is not oversold:
    `feature_version` catches *syntax* newer than 3.9, not standard-library APIs added after 3.9.
    `Path.is_relative_to` is 3.9, so C6's suggested form is inside the floor.
  - Depends on: T025.

### The checker's tests

- [ ] **T028** [US3] Create `tests/unit/scripts/test_check_dead_suppressions.py`, observing the one
      rule that keeps the gate from going permanently red.
  - Import the checker directly: `import scripts.check_dead_suppressions as mod`. This works because
    pytest puts the repository root on `sys.path` and PEP 420 makes `scripts/` an implicit namespace
    package; `tests/unit/scripts/test_consolidate_oauth_apply.py` already does exactly this. The
    underscore filename was chosen for this reason.
  - **Binding rule, copied literally from `plan.md` section 7: no single source line of this test
    file may contain a comment introducer followed by a marker.** C5 is purely textual and does not
    know what a string literal is, so the natural fixture line
    `fixture.write_text("x = 1  # lgtm[py/some-rule]\n")` **matches C5 as source** and the checker
    flags the test file itself. Build fixtures from separated expressions instead:
    ```python
    INTRODUCER = "#"
    MARKER = "lgtm[py/some-rule]"
    fixture.write_text(f"x = 1  {INTRODUCER} {MARKER}\n")
    ```
    Do the same for the `codeql[` case. The test file must also never carry a marker in a real `#`
    comment: "here is what a bad line looks like" is precisely the well-meaning edit that turns the
    gate permanently red.
  - With that rule observed, the exact-path exclusion and the positional rule are two independent
    mechanisms holding this file. Without it, only the exclusion holds it, and the file is one
    rename away from a permanently red gate.
  - `from __future__ import annotations` at the top. The file lives under `tests/` and is therefore
    linted **and format-checked** by the required `Lint` job (`ruff check src/ tests/` and
    `ruff format --check --diff src/ tests/`).
  - Depends on: T025, T006.

- [ ] **T029** [US3] Negative test: prove the checker fails on a seeded violation (SC-006, US3
      scenarios 1 and 2, C2, C4, C5, C7). **This is the red-test. Without it the checker has never
      been observed failing and is not a check.**
  - Write a fixture file with an allowlisted extension (`.py`) into pytest's `tmp_path`, carrying a
    real marker assembled per T028's rule. Point the checker at `tmp_path` through
    `DEAD_SUPPRESSION_ROOTS`. `tmp_path` is outside the repository, so the fixture never exists
    inside an audited root, no exclusion is needed for it, and pytest destroys it at test end.
  - Assert exit code **1**, and that the output names the fixture file, line **1**, and the marker
    text.
  - Two cases: one for `lgtm[`, one for `codeql[`. Both must exit 1. The `codeql[` case exists
    because that form is honoured only by a command-line path this repository does not use, and
    swapping to it is the obvious wrong workaround.
  - A control case in the same test: the same fixture with the marker but **no** introducer must
    exit `0`, proving the failure came from the rule and not from the file merely existing.
  - Depends on: T028.

- [ ] **T030** [US3] Zero-files test: exit code `2`, not `0` (C2).
  - Point `DEAD_SUPPRESSION_ROOTS` at an empty `tmp_path` directory. Assert exit code is exactly
    `2`. Also assert it is not `0`, with a message explaining that "scanned nothing" must never read
    as "found nothing".
  - Depends on: T028.

- [ ] **T031** [US3] Self-exclusion tests (FR-009, C6).
  - Assert `SELF_EXCLUSIONS` has exactly two members and that they are
    `scripts/check_dead_suppressions.py` and
    `tests/unit/scripts/test_check_dead_suppressions.py`.
  - Assert a file with the **same basename** placed in `tmp_path` and carrying a marker is still
    flagged (exit 1). This is the assertion that would have caught the precedent's basename hole and
    is the whole point of FR-009.
  - Assert the exclusion path does not raise for files outside the repository: a `tmp_path` run must
    complete rather than propagate `ValueError`.
  - Depends on: T028.

- [ ] **T032** [US3] Positional-rule tests (C5).
  - A marker inside a Python string literal with no introducer earlier on the line does not fire.
  - A marker inside a URL with no introducer earlier on the line does not fire.
  - The same marker after `#` fires.
  - The same marker after each of `//`, `<!--`, `/*` and `--` fires.
  - Case-insensitivity: `LGTM[` and `CodeQL[` after an introducer both fire.
  - A file whose extension is not on the allowlist (`.md`) carrying a marker after an introducer
    does **not** fire.
  - Depends on: T028.

- [ ] **T033** [US3] Output-content tests (FR-014, C7).
  - On a failing run assert the output contains: the reported path, the line number, the marker
    text, a distinctive phrase from the "why this is inert" block, and a distinctive phrase from the
    "what to do instead" block naming the dismissal workflow (FR-007).
  - On a clean run assert the output states a file count greater than zero.
  - Assert on **substrings only**, never on exact whitespace or a verbatim block, or every wording
    improvement becomes a test failure (C7's closing paragraph).
  - Depends on: T028.

- [ ] **T034** [US3] Subprocess command-line test pinning the exit-code contract (C1, C2).
  - Invoke the checker as a command line with `subprocess.run([sys.executable, "scripts/check_dead_suppressions.py"], ...)`.
  - **Use `sys.executable`, never a bare `python3`.** A bare `python3` resolves differently per
    machine and per shell: on the reference machine `/usr/bin/python3` is 3.12.3 while `python3`
    reaches 3.13.0 through a pyenv shim, and CLAUDE.md records a different number again. The test
    must pin the interpreter it is running under rather than gamble on `PATH`.
  - Assert all three codes through the command-line surface: `0` against the real tree, `1` against
    a seeded `tmp_path` root, `2` against an empty `tmp_path` root.
  - Also assert that passing positional file arguments does **not** narrow the scan (C1, C8): a run
    with a single positional path must scan the same number of files as the bare run.
  - **The `subprocess.run(` call MUST carry `# noqa: S603` with a one-line justification comment
    above it, or this task reddens the required `Lint` job.** `pyproject.toml` selects `S`
    (flake8-bandit) and its `[tool.ruff.lint.per-file-ignores]` entry for `tests/**/*.py` lists
    `S101 S105 S106 S108 S110 S311 E402 C420` and **not** `S603`, so `ruff check src/ tests/`, a
    step in the required `Lint` job, flags every `subprocess.run` under `tests/`. Reproduced:
    `ruff check --select S --ignore-noqa tests/e2e/test_log_visibility.py` reports
    `S603 subprocess call: check for execution of untrusted input`, and the one existing test in
    this repository that shells out (`tests/e2e/test_log_visibility.py:115`) carries exactly that
    suppression plus a two-line justification. That suppression is provably load-bearing rather
    than decorative: `RUF100` is selected too, so if `S603` did not fire the `# noqa` would itself
    be an error and `ruff check src/ tests/` would not be passing today. Put the directive on the
    `subprocess.run(` line and nowhere else, for the same RUF100 reason. `S607` does not apply,
    because `sys.executable` is an absolute path. No other artifact in this feature mentions
    `S603`; see Adversarial Review #3 finding G1.
  - Depends on: T028.

- [ ] **T035** [US3] Clean-tree canary test (SC-005, FR-015).
  - Run the checker against the real default roots and assert exit `0`.
  - This is a canary by design: it goes red the day somebody adds a marker to `src/`, `tests/` or
    `scripts/`, which is exactly the behaviour being bought. It also means a scratch marker commit
    turns **two** required contexts red, `Lint` and `Run Tests`, which is the expected result at
    T044 and not a second defect.
  - **Cross-story dependency, stated rather than hidden**: this test cannot pass until T015 has
    deleted the marker in `scripts/regenerate-mermaid-url.py`. US3 is therefore not fully
    independently testable ahead of US2, contrary to the template's default claim.
  - Depends on: T028, T015.

- [ ] **T036** [US3] VERIFY the checker's test module passes and that it does not flag itself.
  - Command:
    ```bash
    source .venv/bin/activate
    pytest tests/unit/scripts/test_check_dead_suppressions.py -v; echo "exit=$?"
    ```
  - Pass condition: `exit=0`, zero failures, zero errors.
  - Second command, which proves T028's binding rule was actually observed rather than intended. It
    copies the test file outside the repository so the exact-path exclusion cannot apply, leaving
    only the positional rule to hold it:
    ```bash
    TMPD=$(mktemp -d)
    cp tests/unit/scripts/test_check_dead_suppressions.py "$TMPD/copy_of_test.py"
    DEAD_SUPPRESSION_ROOTS="$TMPD" python3 scripts/check_dead_suppressions.py; echo "exit=$?"
    rm -rf "$TMPD"
    ```
  - Pass condition: `exit=0`. An `exit=1` means at least one source line of the test file carries a
    comment introducer followed by a marker, and the file is being held by the exclusion alone.
  - Depends on: T029, T030, T031, T032, T033, T034, T035.

### The local target

- [ ] **T037** [US3] VERIFY both new test files satisfy the required `Lint` job's own steps.
  - The `Lint` job runs `ruff format --check --diff src/ tests/` as well as `ruff check src/ tests/`.
    No artifact in this feature mentions the format step, and a format-dirty new test file reddens a
    required context. See Cross-Artifact Analysis F1.
  - Command:
    ```bash
    source .venv/bin/activate
    ruff format --check --diff src/ tests/; echo "fmt_exit=$?"
    ruff check src/ tests/; echo "lint_exit=$?"
    ```
  - Pass condition: `fmt_exit=0` and `lint_exit=0`.
  - Depends on: T012, T036.

- [ ] **T038** [US3] Rewrite the `audit-pragma` recipe in `Makefile` (FR-010, FR-011, FR-012,
      FR-013, SC-008, C9).
  - Target shape:
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
  - Three changes, each mapped: RUF100 path set widened to include `scripts/` (FR-010, FR-011);
    the new check inserted as an explicitly blocking step (FR-008); the bandit line's advisory status
    turned into a *declaration* rather than an accident of pipeline semantics, with its path set
    widened to `src/ scripts/` (FR-012, FR-013). The existing `|| echo "No issues found"` is
    replaced by `|| true` plus a labelled banner, so a reader does not have to derive the contract
    from `PIPESTATUS` semantics (SC-008).
  - The checker line MUST NOT be piped, wrapped in `|| true`, or otherwise have its status swallowed
    (C8). That would recreate the exact defect this feature exists to remove.
  - **Ordering is load-bearing: this task must come after T026.** Widening the RUF100 line to
    `scripts/` puts the new checker under the full configured rule set on a blocking line. Doing it
    before T026 passes means introducing a day-one failure, which is what FR-015 forbids.
  - `make audit-pragma` as a whole remains unwired from `make validate` and from CI. That is
    deliberate and carded out of scope. Only the marker check reaches CI, and it reaches it directly.
  - Depends on: T026, T036.

- [ ] **T039** [US3] VERIFY the target passes and declares its statuses (SC-005, SC-007, SC-008).
  - Command:
    ```bash
    source .venv/bin/activate
    make audit-pragma; echo "exit=$?"
    ```
  - Pass condition: `exit=0`, and the output contains exactly three section banners, two labelled
    `[BLOCKING]` and one labelled `[ADVISORY`. The bandit wall will be roughly twice as long as
    before (25 findings rather than 15) because the path set widened; that is expected and is not a
    regression this feature caused.
  - Depends on: T038.

- [ ] **T040** [US3] VERIFY the target actually fails on a seeded violation (red-test for the
      Makefile wiring, C8).
  - T039 proves the target can pass. This proves it can fail, which is the property that was missing
    from the bandit half for its entire existence.
  - Procedure:
    ```bash
    source .venv/bin/activate
    printf 'X = 1  %s %s\n' '#' 'lgtm[py/redtest-do-not-commit]' > scripts/_redtest_tmp.py
    make audit-pragma; echo "exit=$?"
    rm -f scripts/_redtest_tmp.py
    make audit-pragma; echo "exit=$?"
    git status --porcelain; echo "status_exit=$?"
    ```
  - Pass condition: the first `make audit-pragma` exits **non-zero** and its output names
    `scripts/_redtest_tmp.py`, line 1, and the marker. The second exits `0`. `git status --porcelain`
    shows no leftover `_redtest_tmp.py`.
  - Note the `printf` form: the marker and the introducer are separate arguments, so no source line
    of any committed file carries both.
  - Depends on: T039.

- [ ] **T041** [P] [US3] VERIFY no consumer swallows the checker's exit status (C8).
  - Command:
    ```bash
    grep -n 'check_dead_suppressions' Makefile .github/workflows/pr-checks.yml .pre-commit-config.yaml
    echo "grep_exit=$?"
    ```
  - Pass condition: every line that invokes the checker is a bare invocation. No line contains
    `|| true`, `| grep`, `| echo`, `|| echo`, or `; true` on the same line as the invocation. The
    `.pre-commit-config.yaml` match is expected only if T043 was done, and is optional.
  - Depends on: T038.

**Checkpoint**: US3's core is complete. The checker exists, is proven able to fail, and blocks the
local target. It does not yet block a merge. That is Phase 6.

---

## Phase 6: FR-018 - making the gate real (OWNER-REJECTABLE, separable)

> **This entire phase is the feature's scope growth and the owner may reject it.**
>
> The original request was "rewrite an expression, delete a comment, extend `make audit-pragma`"
> (`spec.md` Input line). FR-018 grows that into editing `.github/workflows/pr-checks.yml`, which
> carries one of the four contexts branch protection requires on `main`. The reasoning is that
> `make audit-pragma` is invoked by nothing automated: it is not among `make validate`'s seven
> prerequisites (`Makefile:42`), it appears in no workflow, and it appears in no commit hook. A check
> placed only there has never once run against a change that was about to land, which is the same
> category of object as the comment being deleted.
>
> **If the owner rejects FR-018, exactly these tasks die: T042, T043, T044, T045, T046.** With them
> fall FR-018, FR-019, SC-011, SC-012, and US3 acceptance scenario 6. Everything in Phases 1 through
> 5 and 7 through 9 stands unchanged: the checker still gets built, still gets wired into
> `make audit-pragma`, still has the same contract, and still has its red-test. What it loses is the
> property of ever running against a change that is about to land, and the feature keeps only its
> informational outcomes.
>
> Neither outcome may be reached silently. Do not widen the CI footprint beyond the single step in
> T042 (no new job, no new required context, no `make validate` prerequisite, all carded out of
> scope), and do not quietly drop the step on the grounds that it is "just tooling".

- [ ] **T042** [US3] [GATE] Append one step to the `lint` job in `.github/workflows/pr-checks.yml`
      (FR-018, FR-019, C9).
  - Placed after the existing waitForResponse guard step, following that precedent exactly,
    including its explanatory comment block. The step:
    ```yaml
          - name: Check for dead scanning suppressions
            if: always()
            run: python3 scripts/check_dead_suppressions.py
    ```
  - The comment block above it must state: why the guard lives in `Lint` and not in
    `Pre-commit Hooks` (`Lint` is required, `Pre-commit Hooks` is not, so moving it silently
    downgrades the guard to advisory with no symptom until a violation merges green); the command
    that verifies the required contexts and the date it was last run; that there is no `pip install`
    because the checker is standard-library only and `setup-python` already provides an interpreter
    (FR-019); and why `if: always()` is needed (steps are fail-fast and this one is last, so without
    it a ruff failure means the guard never runs and reports nothing).
  - **`python3 scripts/check_dead_suppressions.py`, not `make audit-pragma`.** The `Lint` job
    installs `ruff==0.15.14` and nothing else. `bandit` is absent, so the target's third section
    would fail on a missing binary, and adding bandit is precisely the tooling installation FR-019
    forbids. Invoking directly also means the `Pre-commit Hooks` job's `SKIP` environment cannot
    reach it (C8).
  - No `|| true`, no pipe, no wrapper (C8).
  - Depends on: T002, T038, T040.

- [ ] **T043** [US3] [GATE] **OPTIONAL, not required by any FR**: add a matching local `pre-commit`
      hook.
  - Mirroring the `scan-waitforresponse-race` hook, with `language: system`,
    `pass_filenames: false`, `always_run: true`, `stages: [pre-commit]`.
  - It gives contributors the failure locally rather than in CI. It is **additive only**. If the two
    ever disagree, the CI step is the gate. C8 permits an additive local hook and forbids only the
    required check depending on the hook runner.
  - This task is explicitly optional so that its absence is never read as an FR-018 miss.
  - **MUST come after T044, and this ordering is not cosmetic.** Mirroring the precedent means
    `always_run: true` with `pass_filenames: false` (`.pre-commit-config.yaml:206-212`), so the
    hook runs on **every** commit regardless of what that commit touches. T044 has to commit a
    marker inside an audited root in order to observe the gate biting, and this hook rejects that
    commit locally. `--no-verify` is not an escape: CLAUDE.md forbids it outright and a
    machine-level pre-tool hook denies `git … --no-verify` before it reaches git. If T043 has
    already landed when T044 runs, the only legitimate route is
    `SKIP=check-dead-suppressions git commit -S …`, which pre-commit honours per hook id. Do T044
    first and the question does not arise. See Adversarial Review #3 finding G3.
  - Depends on: T042, T044.

- [ ] **T044** [US3] [GATE] VERIFY SC-011 by observed check result, not by reading the workflow file.
  - Reading the workflow is not evidence. SC-011 requires an observed failure.
  - Procedure, on the feature branch: commit a scratch change adding a marker to a file inside an
    audited root, using the split-argument form so no committed source line of this feature's own
    files carries both an introducer and a marker:
    ```bash
    printf 'X = 1  %s %s\n' '#' 'lgtm[py/scratch-do-not-merge]' > scripts/_gatetest_tmp.py
    git add scripts/_gatetest_tmp.py
    git commit -S -m "scratch: prove the gate bites (reset before merge)"
    git push
    gh pr checks --watch
    ```
    Then remove the scratch commit and push again:
    ```bash
    git reset --hard HEAD~1
    git push --force-with-lease
    ```
  - **Three corrections to the obvious way of doing this, each of which has a concrete failure
    mode.** See Adversarial Review #3 finding G5.
    1. **A throwaway file, not `scripts/regenerate-mermaid-url.py`.** Seeding the marker into the
       very file this feature exists to clean means a botched cleanup silently restores a marker to
       that file. `X = 1  # lgtm[…]` in a throwaway is verified ruff-clean under the repository
       config, so nothing upstream of the checker can fail first and mask the result.
    2. **`git add <path>`, never `git add -A`.** This worktree is shared with concurrent sibling
       features whose `specs/` directories are untracked; `-A` sweeps them into the scratch commit.
    3. **`git reset --hard HEAD~1`, not `git revert`.** A revert leaves the scratch commit in
       history, which makes the stated `git log --oneline` confirmation below unsatisfiable and
       leaves a commit carrying a marker permanently reachable on the branch.
  - Pass condition: on the scratch commit, `Lint` reports **failure** and the job log names
    `scripts/_gatetest_tmp.py` and line 1. **`Run Tests` also reports failure**, through the T035
    clean-tree canary. Two red contexts is the expected result, not a second defect. After the
    reset, both go green.
  - The scratch commit MUST NOT be merged. Confirm with `git log --oneline` that it is gone, and
    with `git status --porcelain` that `scripts/_gatetest_tmp.py` is gone, before Phase 7.
  - Depends on: T042.

- [ ] **T045** [US3] [GATE] VERIFY SC-012 and FR-019 from the job log.
  - **The workflow file is the evidence for FR-019 and for step adjacency; the job log is the
    evidence that no install step actually ran.** They are two different reads and the second one
    needs a **job** id, which `gh run list` does not return.
  - Command:
    ```bash
    grep -n 'pip install' .github/workflows/pr-checks.yml; echo "grep_exit=$?"
    grep -n 'name: Check' .github/workflows/pr-checks.yml; echo "grep_exit=$?"

    RID=$(gh run list --workflow pr-checks.yml --limit 1 --json databaseId --jq '.[0].databaseId')
    JID=$(gh run view "$RID" --json jobs --jq '.jobs[] | select(.name=="Lint") | .databaseId')
    echo "RID=$RID JID=$JID"
    gh run view --job "$JID" --log > /tmp/lint-job.log; echo "log_exit=$?"
    grep -c '' /tmp/lint-job.log
    ```
  - Pass condition: the `lint` job in the workflow file contains exactly one install step and it
    installs `ruff==0.15.14` only; T042 added none; and the new step is the one immediately
    following `Check waitForResponse race ordering` with nothing between them. `log_exit=0` and a
    non-zero line count, so the log read is known to have worked before anything is concluded from
    its contents.
  - **Do not write `gh run view --job "$(gh run list … --json databaseId …)"`.** That is the form
    this task carried before Adversarial Review #3 and it is broken: `gh run list --json databaseId`
    returns a **run** id, `--job` expects a **job** id, and the two id spaces do not overlap.
    Reproduced 2026-07-30 against this repository: run `30597680512` yields
    `failed to get job: HTTP 404: Not Found (…/actions/jobs/30597680512)`, exit 1. The two-step
    resolution above returns job `91053515417` and a 322-line log. A 404 piped into `head -5` with
    `2>/dev/null` prints nothing at all, which an operator reads as "no install steps", which is the
    answer the task wants. A verification that passes by failing. See Adversarial Review #3
    finding G2.
  - Depends on: T042.

- [ ] **T046** [US3] [GATE] Re-confirm the required contexts immediately before merging the CI step.
  - Same command as T002. The precedent's own comment at `.pre-commit-config.yaml` says plainly not
    to trust that list without re-checking.
  - Pass condition: `"Lint"` is still among the returned contexts. If it is not, the step is
    advisory regardless of what the workflow file says, and FR-018 is unsatisfied.
  - Depends on: T044.

---

## Phase 7: Pre-merge re-verification (FR-015)

**Purpose**: FR-015 requires the cleanliness that makes the new blocking behaviour safe to be
re-verified **against the exact tree being merged**, and explicitly forbids inferring it from a
measurement taken during planning. This worktree is shared with concurrent work, and `scripts/` has
never been inside the RUF100 path set before, so a single `# noqa` arriving there between planning
and merge converts FR-011 into a day-one failure for everybody who runs the target.

Run all of Phase 7 on the merge commit, after the final rebase.

- [ ] **T047** [P] Re-run the widened unused-pragma check on the merge commit (FR-011, FR-015,
      SC-007).
  - Command:
    ```bash
    source .venv/bin/activate
    ruff check --extend-select RUF100 src/ tests/ scripts/; echo "exit=$?"
    ```
  - Pass condition: `All checks passed!` and `exit=0`. This supersedes T003; T003 is not evidence
    about this commit.

- [ ] **T048** [P] Re-run the audited-path marker scan on the merge commit (SC-004, FR-021).
  - Command:
    ```bash
    grep -rnE "lgtm\[|codeql\[" src/ tests/ scripts/; echo "grep_exit=$?"
    ```
  - Pass condition: output lines come **only** from `scripts/check_dead_suppressions.py` and
    `tests/unit/scripts/test_check_dead_suppressions.py`. Any other path is a failure. If FR-018 was
    rejected and Phase 6 dropped, this condition is unchanged.

- [ ] **T049** [P] Re-run the local target on the merge commit (FR-015, SC-005, SC-008).
  - Command:
    ```bash
    source .venv/bin/activate
    make audit-pragma; echo "exit=$?"
    ```
  - Pass condition: `exit=0` and three labelled sections.

- [ ] **T050** [P] Mirror the required `Lint` job's steps locally (SC-011 precondition, and the only
      safe substitute for `make validate`).
  - `make validate` cannot pass on this tree: `scripts/check-banned-terms.sh` exits 1 on
    pre-existing matches belonging to other features. Do not require it to be green. Run the `Lint`
    job's own steps instead.
  - Command:
    ```bash
    source .venv/bin/activate
    ruff format --check --diff src/ tests/; echo "fmt_exit=$?"
    ruff check src/ tests/; echo "lint_exit=$?"
    ruff check src/ --select S --output-format=github; echo "sec_exit=$?"
    python3 scripts/scan-waitforresponse-race.py; echo "race_exit=$?"
    python3 scripts/check_dead_suppressions.py; echo "dead_exit=$?"
    ```
  - Pass condition: all five exit `0`. The last line exists only if FR-018 was accepted; if it was
    rejected, run it anyway as a local check, but its result gates nothing.

- [ ] **T051** [P] Run the unit test suite (SC-009).
  - Command:
    ```bash
    source .venv/bin/activate
    pytest tests/unit -q; echo "exit=$?"
    ```
  - Pass condition: `exit=0`, and both new test modules appear in the collected set. SC-009's
    wording is satisfied by this: the diagram script had no prior coverage of any kind, so the
    FR-004 test is the first coverage it has ever had and there is no pre-existing suite for it to
    pass unchanged.

---

## Phase 8: Post-merge verification (FR-016, FR-017, FR-022, SC-001, SC-002)

**Purpose**: the alert half of US1. **This cannot be done before merge.** The branch-level analysis
does not refresh until the change is on `main`, and no scanning result is among the four required
checks, so nothing holds the merge while you wait.

- [ ] **T052** Query the branch-level alert state after the `Analyze` job has run on `main`
      (FR-016, SC-001).
  - Command (identical shape to T001, and `--paginate` plus the corpus floor are mandatory for the
    reasons recorded there):
    ```bash
    gh api --paginate --slurp \
      "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100" \
      > /tmp/alerts-open-after.json
    echo "gh_exit=$?"
    jq 'add | {count: length, alerts: map({n:.number, rule:.rule.id, path:.most_recent_instance.location.path})}' \
      /tmp/alerts-open-after.json
    echo "jq_exit=$?"

    gh api --paginate --slurp \
      "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?ref=refs/heads/main&per_page=100" \
      > /tmp/alerts-all-after.json
    echo "gh_exit=$?"
    jq 'add | length' /tmp/alerts-all-after.json
    echo "jq_exit=$?"
    ```
  - Pass condition, in this order and all required: every `gh_exit=0` and `jq_exit=0`; the
    all-states corpus count is **at least 137**; and only then, **no** returned entry has `rule`
    equal to `py/bad-tag-filter` at `path` `scripts/regenerate-mermaid-url.py`.
  - **The order is the point.** This criterion is satisfied by an absence, and an absence produced
    by a truncated or failed read looks exactly like an absence produced by a fixed finding. The
    corpus floor is what separates them. Without it, this task is a check that cannot report dirty,
    which is the defect the whole feature exists to remove.
  - **Keyed on path plus rule id, never on the number.** The analyzer demonstrably closes a number
    and opens a fresh one at the same site, so a check written against `147` can report success
    while the same finding sits there under a new number. This applies to US1 acceptance scenario 1
    as well, whose wording still names the number; treat that wording as narrative identification
    and measure it this way.
  - A green pull request check is **not** acceptable as evidence (FR-016). Pull request analysis is
    diff-informed and covers only changed lines; a recent pull request in this repository passed its
    scanning check with five alerts open.
  - Depends on: merge, and the `Analyze` job completing on `main`.

- [ ] **T053** VERIFY the open-alert count dropped by exactly one (SC-002, FR-017).
  - Pass condition: `count` from T052 equals **N - 1**, where N is the baseline recorded at T001.
    Exactly one lower, not at most one lower: a criterion phrased as "no worse than before" is
    satisfied by the change achieving nothing, and "exactly one" simultaneously confirms the old
    finding closed and that no new finding was introduced in its place.
  - **Both counts must come from paginated reads whose corpus floor passed.** Comparing a paginated
    baseline against a truncated post-merge read produces a drop that is an artefact of the read.
  - **Known campaign-level confound.** A sibling feature extends the analysis matrix over previously
    unanalyzed source and is expected to raise the open-alert count deliberately. If it merges
    between T001 and T052, the total moves for reasons unrelated to this change and SC-002 becomes
    unmeasurable as literally phrased. In that case: record both counts and the sibling's merge
    commit, fall back to SC-001 (T052's path-plus-rule condition) as the operative criterion, and
    say so explicitly rather than reporting a pass. Do not silently reinterpret "exactly one lower"
    as "no worse than before"; that reinterpretation is the exact weakening Adversarial Review #1
    finding F7 removed from this spec.
  - Depends on: T052.

- [ ] **T054** Record the outcome and, if the alert is still open, take the named response (FR-022).
  - Paste the T052 output into the pull request or the follow-up issue either way. It is the
    evidence FR-016 asks for.
  - If an open alert with rule `py/bad-tag-filter` remains at that path, the response is a
    **follow-up change to the same line, not a revert**. The rewrite is behaviour-preserving by
    FR-001, so reverting restores a pattern and buys nothing.
  - Depends on: T052.

---

## Phase 9: Traceability and close-out

- [ ] **T055** [P] VERIFY FR-021 across everything this feature added.
  - Every command in `tasks.md` and `quickstart.md` that counts marker occurrences must be scoped to
    `src/ tests/ scripts/` and never to the tree.
  - Command:
    ```bash
    grep -n 'grep -r' specs/001-bad-tag-filter-dead-suppression/tasks.md \
                      specs/001-bad-tag-filter-dead-suppression/quickstart.md
    echo "grep_exit=$?"
    ```
  - Pass condition: every recursive **marker** scan listed (any line containing `lgtm\[` or
    `codeql\[` as a pattern) ends in `src/ tests/ scripts/`. None scans `.`, the repository root, or
    `specs/`. A tree-wide count can never reach zero, because describing a
    marker requires writing it, and any criterion phrased that way is unsatisfiable on the day it is
    written.

- [ ] **T056** [P] VERIFY no inline suppression form was introduced anywhere in the diff (FR-005,
      FR-007).
  - Command:
    ```bash
    git diff main --unified=0 -- . ':(exclude)specs/**' | grep -nE '^\+.*(lgtm\[|codeql\[)'
    echo "diff_exit=${PIPESTATUS[0]} grep_exit=${PIPESTATUS[1]}"
    ```
  - Pass condition: `diff_exit=0`, and the only added lines matching are inside
    `scripts/check_dead_suppressions.py` (its own pattern constants) and
    `tests/unit/scripts/test_check_dead_suppressions.py`. Nothing else may add a marker. Note that
    the checker's own constants are added lines and will appear here; check the file each hit
    belongs to rather than requiring `grep_exit=1`.

- [ ] **T057** Walk `quickstart.md` end to end as the operator would, and record any step whose
      stated pass condition does not hold.
  - Pass condition: every section from 1 through 4 runs as written and produces the stated result,
    **with one known exception already identified**: section 2's control check
    (`git diff main -- ... | grep -- "==>"`, "expect no output") is false by construction, because
    the control line falls inside the diff's default three-line context window and prints as a
    context line. Use T017's corrected form. Section 5 applies only if FR-018 was accepted. Section
    6 is Phase 8.

- [ ] **T058** Card the adjacent defects found during this feature. **Do not fix any of them here.**
  - They are listed in the Cross-Artifact Analysis below under "Adjacent defects". Each is outside
    this feature's scope and belongs on the board, not in this diff.

---

## Dependencies and execution order

### Phase order

1. **Phase 1 (baselines)**: no dependencies, all five parallel.
2. **Phase 2 (foundational)**: after Phase 1. Blocks the test tasks in Phases 3 and 5.
3. **Phase 3 (US1)** and **Phase 5 (US3 core)**: can proceed in parallel by different people, with
   one caveat below.
4. **Phase 4 (US2)**: T015 depends on T007 (same lines of the same file).
5. **Phase 6 (FR-018 gate)**: after Phase 5 and after T002. **Owner-gated. May be dropped entirely.**
6. **Phase 7 (pre-merge re-verification)**: after every preceding phase, on the merge commit.
7. **Phase 8 (post-merge)**: after merge, after `Analyze` runs on `main`.
8. **Phase 9**: T055 and T056 any time after Phase 5; T057 after Phase 7; T058 last.

### Cross-story dependencies (stated, not hidden)

The template's default claim that stories are independently testable does not fully hold here:

- **T035 (US3 clean-tree canary) depends on T015 (US2)**. Until the marker in
  `scripts/regenerate-mermaid-url.py` is deleted, the canary fails against the real roots. US3
  cannot be fully green before US2 lands.
- **T018 (US2 marker scan) has two valid pass states** depending on whether US3 has landed, and both
  are written into the task.
- **T038 (Makefile widening) depends on T026 (checker ruff-clean)**. Reversing that order introduces
  a day-one blocking failure, which is exactly what FR-015 forbids.
- **T042 (CI step) depends on T040 (Makefile red-test)**. Wiring a gate into a required context
  before it has been observed failing is how the original defect happened.

### Parallel opportunities

`[P]` tasks: T001, T002, T003, T004, T005, T008, T026, T027, T041, T047, T048, T049, T050, T051,
T055, T056. Sixteen of fifty-eight.

T019 through T025 all edit `scripts/check_dead_suppressions.py` and are strictly sequential.
T028 through T035 all edit `tests/unit/scripts/test_check_dead_suppressions.py` and are strictly
sequential. T007 and T015 edit the same three lines of `scripts/regenerate-mermaid-url.py` and are
sequential.

---

## Requirement coverage

### Functional requirements

| FR | Subject | Implementing task(s) | Verifying task(s) |
|---|---|---|---|
| FR-001 | Identical verdict, proven by differential test | T007 | T009, T012, T013 |
| FR-002 | Not expressed as a pattern; control unchanged | T007 | T011, T014, T017 |
| FR-003 | Newline-only split; full whitespace trim | T007 | T009, T010, T013 |
| FR-004 | Regression test in the collected test root | T008, T010 | T006, T012, T051 |
| FR-005 | Delete the marker, do not substitute another form | T015 | T016, T048, T056 |
| FR-006 | Remove or rewrite the stale explanatory comment | T015, T007 | T016 |
| FR-007 | Dismissal workflow is the supported route | T024 | T033 |
| FR-008 | Detect both marker forms and fail on them | T022, T025 | T029, T040 |
| FR-009 | Narrow, exact-path self-exclusion | T023 | T031, T036 |
| FR-009a | Dedicated file, not inline in the recipe | T019 | T026, T041 |
| FR-010 | Widen the audited path set to include `scripts/` | T020, T038 | T039, T047 |
| FR-011 | Unused-pragma check stays blocking, widened | T038 | T003, T039, T047 |
| FR-012 | Security-linter half stays advisory | T038 | T005, T039 |
| FR-013 | Blocking or advisory status explicit and accurate | T038 | T039, T041 |
| FR-014 | Failure names file, line, marker, why, what instead | T024 | T029, T033, T040 |
| FR-015 | Exits zero on the tree as it lands, re-verified at merge | T038 | T035, T047, T048, T049 |
| FR-016 | Closure evidenced from branch analysis, not a PR check | (verification only) | T052, T054 |
| FR-017 | Open-alert count must not increase | (verification only) | T001, T053 |
| FR-018 | Marker check executes in a merge-blocking context | **T042** [GATE] | **T044, T046** [GATE] |
| FR-019 | No new tooling installation in that context | **T042** [GATE] | **T027, T045** [GATE] |
| FR-020 | Note on the line saying it is deliberately not a pattern | T007 | T014, T057 |
| FR-021 | Counting criteria scoped to the audited path set | T020 | T004, T018, T048, T055 |
| FR-022 | Closure gathered post-merge; named failure response | (verification only) | T052, T054 |

No FR is uncovered. FR-016, FR-017 and FR-022 have no implementing task by their nature: they
constrain how evidence is gathered, not what is built.

### Success criteria

| SC | Subject | Task(s) |
|---|---|---|
| SC-001 | No open alert with that rule at that path, post-merge | T052 |
| SC-002 | Open count exactly one lower | T001, T053 |
| SC-003 | Differential test, >= 1,500 inputs, zero mismatches | T009, T012, T013 |
| SC-004 | Audited-path marker scan clean but for the auditor | T004, T018, T048 |
| SC-005 | Audit exits zero on the post-change tree | T035, T039, T049 |
| SC-006 | Audit exits non-zero on a seeded marker, names file and line | T029, T040 |
| SC-007 | Unused-pragma check runs on the widened set and passes | T039, T047 |
| SC-008 | Recipe declares status for every check | T038, T039 |
| SC-009 | Unit suite passes including the net-new regression test | T012, T051 |
| SC-010 | Thick-arrow control byte-identical | T011, T017 |
| SC-011 | A marker-adding change turns a required check red | **T044** [GATE] |
| SC-012 | Reachable from the blocking context with no extra tooling | **T027, T045** [GATE] |

No SC is uncovered.

### Contract clauses

`contracts/dead-suppression-cli.md` is normative. The contract carries **nine** clauses, C1 through
C9, not eight.

| Clause | Subject | Implementing task | Verifying task(s) |
|---|---|---|---|
| C1 | Invocation, interpreter floor, stdlib only, ignored positionals | T019 | T026, T027, T034 |
| C2 | Exit codes 0 / 1 / 2 | T025 | T029, T030, T034, T040 |
| C3 | Default roots, extension allowlist, skip list, decoding | T020 | T032, T036, T039 |
| C4 | `DEAD_SUPPRESSION_ROOTS` override | T021 | T029, T030, T036 |
| C5 | Positional detection rule | T022 | T032, T036 |
| C6 | Exact-path self-exclusion, no raise outside the repository | T023 | T031, T036 |
| C7 | Output, both paths, relative with absolute fallback | T024 | T033, T029, T040 |
| C8 | What consumers must not do | T038, T042 | T034, T041 |
| C9 | Consumer wiring, verbatim | T038, T042 | T039, T041, T045 |

Every clause has both an implementing task and at least one verifying task. Every exit code in C2
has a dedicated assertion: `0` at T034 and T035, `1` at T029 and T040, `2` at T030 and T034.

---

## Cross-Artifact Analysis

Scope: `spec.md`, `plan.md`, `research.md`, `contracts/dead-suppression-cli.md`, `quickstart.md`,
and this `tasks.md`. Every claim below was reproduced with a command on 2026-07-30 before being
written down. This is a consistency pass, not a re-run of Adversarial Review #1 (which gated on
`spec.md`) or #2 (which gated on drift between the spec's clarifications and the design artifacts).

### Findings

| Sev | ID | Finding | Disposition |
|---|---|---|---|
| HIGH | F1 | **An unmentioned required-check step can redden `Lint` on day one.** The `Lint` job runs `ruff format --check --diff src/ tests/` as its first check, before `ruff check`. Both new test files land under `tests/`. No artifact in this feature mentions the format step: `plan.md`'s Constraints block requires the checker and its test to be clean under `ruff check --extend-select RUF100`, and `research.md` R-0e quotes only the install step. A format-dirty new test file turns a required context red for a reason no artifact predicts. | COVERED by T037 and T050, which run the format check explicitly. Recorded here because the plan's Constraints block is incomplete as written. |
| HIGH | F2 | **`quickstart.md` section 2's control check is false by construction.** It says to run `git diff main -- scripts/regenerate-mermaid-url.py \| grep -- "==>"` and "expect no output". The control line sits exactly three lines below the changed line, and git's default context is three, so the control prints as a context line on a correct change. The command therefore fails a correct implementation, and its status is read from downstream of a pipe on top of that. | COVERED by T017, which pins the corrected form (`grep -E '^[+-].*==>'` with `PIPESTATUS`). `quickstart.md` itself is left unedited; T057 records the discrepancy for the operator. |
| MEDIUM | F3 | **`plan.md` Technical Context overstates the new tests' isolation.** It reads "Testing: pytest, collected under `tests/unit/scripts/`. No AWS, no moto, no network." That directory's `conftest.py` imports `boto3` and `moto` at module level, and pytest imports a directory's conftest for every test collected in it, so both new files pull moto in at collection. The Constitution Check's "LOCAL and DEV run ONLY unit tests with mocks" row rests on the inaccurate sentence. Not a breakage: `requirements-ci.txt` pins `moto[all]` and the `Run Tests` job installs it. `plan.md`'s own Adversarial Review #2 recorded this as D8 and left it unfixed pending a wording call. | RECORDED. T006 states the constraint accurately and verifies collection. No gate result changes. |
| MEDIUM | F4 | **`spec.md` US1 acceptance scenario 1 and Key Entities still key the primary outcome on an alert number.** Scenario 1's **Then** clause reads "the branch analysis for `refs/heads/main` reports alert 147 as no longer open", and Key Entities says the state of alert 147 "is the feature's primary outcome measure". Adversarial Review #2 finding D4 rekeyed SC-001 and US1's Independent Test onto path plus rule but deliberately left these two, calling them narrative identification. Scenario 1's **Then** clause is not narrative: it is the acceptance condition, and it is keyed the one way `plan.md` and `quickstart.md` both forbid in terms. | COVERED by T052, which measures path plus rule and states explicitly that the scenario's wording is to be treated as narrative. Left in `spec.md` unedited; the measurement is unambiguous. |
| MEDIUM | F5 | **This briefing's own framing carried two errors.** (a) The alert is stated as "`js/bad-tag-filter` class". The live alert is `py/bad-tag-filter`, confirmed against the alert-state API: alert 147, rule `py/bad-tag-filter`, severity high, `scripts/regenerate-mermaid-url.py:82`. Every artifact in the feature has it right. (b) The contract is described as having clauses "C1 through C8". It has nine, C1 through C9, and C9 (Consumer wiring, verbatim) is the clause that pins the two consumer invocations the feature actually edits. Verifying only C1 through C8 would leave the Makefile and CI wiring text unverified against the contract. | FIXED in this document. The coverage table runs C1 through C9 and T001 records the correct rule id. |
| MEDIUM | F6 | **Cross-story dependency contradicts the tasks template's independence claim.** US3's clean-tree canary (SC-005, FR-015) asserts exit `0` against the real default roots, which cannot hold until US2 has deleted the marker in the diagram script. So US3 is not independently deliverable ahead of US2, though the spec presents the three stories as independently testable. Similarly SC-004's post-state depends on both US2 and US3. | RECORDED and made explicit in T035, T018 and the Cross-story dependencies section, rather than left for an implementer to hit. |
| LOW | F7 | **C1's 3.9 floor has no runtime enforcement and no interpreter available to test it.** The contract sets a 3.9 floor, `plan.md` forbids a `sys.version_info` guard (because `UP036` flags it), and no 3.9 interpreter exists on the reference machine. So nothing would catch a 3.10-only construct until a contributor on an old interpreter hit it. | MITIGATED by T027, which uses `ast.parse(..., feature_version=(3, 9))`. Stated limitation: this catches syntax newer than 3.9, not standard-library APIs added after 3.9. `Path.is_relative_to` is 3.9, so C6's suggested form is inside the floor. |
| LOW | F8 | **C7's example output is already arithmetically stale.** It shows "Scanned 583 files." A census over the three roots and the ten allowlisted extensions returns 583 today, but this feature adds two allowlisted files, so the real first clean run prints 585. | RECORDED, not fixed. The example is illustrative and C7's normative requirement is only that a count be printed. T033 asserts "greater than zero", not a literal. |
| LOW | F9 | **`plan.md`'s Adversarial Review #2 cites its own line numbers inaccurately in D8.** It points at "`plan.md:57`" for the Constitution Check row and "`plan.md:102`" for the conftest listing; the actual lines are 82 and 126. All the substance is correct and locatable; only the labels drifted, which is the same class as D10's four different citations of one comment block. | RECORDED, not fixed. Four edits for zero behavioural gain, and every citation still lands in the right document. |
| LOW | F10 | **`make audit-pragma`'s advisory bandit section becomes unreachable when a blocking section fails.** Make stops at the first failing recipe line, and the new checker sits above the bandit line. A contributor whose run fails on a marker never sees the advisory output. | RECORDED, not fixed. It is the correct behaviour for a blocking gate and the advisory half is explicitly not this feature's product. |
| CRITICAL | F11 | **The feature's own closure query is a check that cannot report dirty.** Every code-scanning query in this feature's artifacts was written without `--paginate`: `plan.md`'s post-merge block, `quickstart.md` section 6 (twice), and three sites in this document. GitHub's default page size is 30 and this repository's all-states alert corpus is 137. Measured 2026-07-30: the unpaginated form with a client-side `select(.state == "open")` returns **zero** open alerts while the paginated form returns **five** (144, 147, 148, 149, 150). Truncation renders as clean. A server-side `state=open` filter masks this only while fewer than 30 alerts are open, and a sibling feature in this campaign extends the analysis matrix over tens of thousands of previously unanalyzed lines with the deliberate intent of raising that count. The moment it lands, SC-001's pass condition, an absence, starts being satisfied by a truncated read, and this feature can be marked complete by a blind query. This is precisely the defect the feature exists to remove, in a third costume: `Makefile:90` cannot fail, the `lgtm[...]` comment cannot suppress, and this query cannot report dirty. | FIXED. All six sites rewritten to `gh api --paginate --slurp ... --per_page=100` with the pages written out and filtered by a separate `jq`, an explicit `gh_exit` check at every site, and an all-states corpus floor of 137 wherever the pass condition is an absence. `--slurp` cannot be combined with `--jq`, which is why the filter is separated; that separation is also what makes the exit status readable instead of hiding it downstream of a pipe. |
| MEDIUM | F12 | **SC-002 is confounded by the same sibling feature.** "The count of open alerts after this change is exactly one lower than the count before" assumes nothing else moves the total between the two measurements. A sibling feature in this campaign is expected to raise the open count deliberately. If it merges between T001 and T052, SC-002 becomes unmeasurable as literally phrased, through no fault of this change. | FIXED in T053, which names the confound, requires both counts and the sibling's merge commit to be recorded, and falls back to SC-001 as the operative criterion rather than silently weakening "exactly one lower" into "no worse than before". That weakening is what Adversarial Review #1 finding F7 removed from the spec. |

Counts: 1 CRITICAL, 2 HIGH, 5 MEDIUM, 4 LOW. The CRITICAL and both HIGH findings are closed inside
this document. F11 was surfaced by a campaign-level correction, independently reproduced here
against the live API before being applied, and the same evidence produced F12.

### Requirement coverage gaps

None. All 23 functional requirements (FR-001 through FR-022, including FR-009a) and all 12 success
criteria map to at least one task, per the tables above. FR-016, FR-017 and FR-022 are
verification-only by construction and are marked as such rather than being given a fabricated
implementing task.

### Contract clauses with no implementing or verifying task

None, across C1 through C9. Every exit code in C2 has a dedicated assertion in at least two tasks.
C8's four prohibitions are each covered: status-swallowing at T041, `pre-commit run` from the
blocking context at T042 and T041, positional narrowing at T034, and override-setting by consumers
at T041 (the grep would surface any consumer line setting `DEAD_SUPPRESSION_ROOTS`).

### Tasks with no requirement behind them

Three, each justified rather than removed:

- **T013** (red-test for the differential oracle) traces to no FR. It exists because SC-003's zero
  mismatches is unfalsifiable until the corpus has been observed separating the correct
  implementation from the known-incorrect one. Without it, a corpus that quietly stopped containing
  exotic separators still reports success.
- **T036**'s second command (scanning a copy of the test file from outside the repository) traces to
  `plan.md` section 7 rather than to an FR. It is the only way to prove the "no source line carries
  both an introducer and a marker" rule was observed rather than intended.
- **T043** (local pre-commit hook) is explicitly optional and is marked as required by no FR, so
  that its absence is never read as an FR-018 miss.

### Ordering hazards

Four, all made explicit in the Dependencies section:

1. **T038 before T026** would put a checker that has not been proven ruff-clean onto a blocking line
   linted under the full configured rule set. This is the feature's single most likely
   self-inflicted failure and is the exact day-one break FR-015 exists to prevent.
2. **T042 before T040** would wire an unproven gate into a required context.
3. **T035 before T015** fails for a reason that looks like a checker bug and is not.
4. **T044's scratch commit** turns two required contexts red, not one. An operator expecting one
   will hunt for a second defect. Stated in the task.

### Unfalsifiable pass conditions

Four were found and all four are corrected in this document:

- `quickstart.md` section 2's `git diff | grep` control check (F2). Corrected in T017.
- Any "differential test passes" condition without a corpus-size assertion. T009 requires
  `assert len(corpus) >= 1500` inside the test, and T013 requires the test to have been observed
  failing.
- Any "`make audit-pragma` exits 0" condition standing alone. The whole feature exists because
  `Makefile:90` exits 0 unconditionally. T040 pairs T039 with a seeded-violation red-test, and every
  piped command in this document reads `${PIPESTATUS[0]}`.
- **Any alert-absence condition read from an unpaginated query (F11).** An absence produced by a
  truncated or failed read is indistinguishable from an absence produced by a fixed finding. T001
  and T052 now require `--paginate`, an explicit `gh_exit` check, and an all-states corpus floor of
  137 evaluated *before* the absence is read. The general rule, which generalises past this feature:
  **when the pass condition is emptiness, the reader must independently prove it was working.**

### Contradictions between artifacts

- **F1** (format check unmentioned) and **F3** (moto isolation claim) are the two live ones.
- **F4** is a residual internal contradiction inside `spec.md` between US1 scenario 1 and SC-001,
  both post-Adversarial-Review-#2.
- `plan.md`'s skip list and C3's skip list were checked character by character and are identical
  (`__pycache__`, `node_modules`, `.venv`, `.git`, `.pytest_cache`, `.hypothesis`).
- `plan.md`, `research.md`, `spec.md`, `quickstart.md` and this document all specify
  `split("\n")` and reject `splitlines()`. No artifact recommends the incorrect form anywhere.
- The 3.9 floor is now consistent across `contracts/` C1, `plan.md` Technical Context and
  `research.md` D-2, after Adversarial Review #2's D2 fix.

### Independent re-verification performed for this analysis

| Claim under test | Method | Result |
|---|---|---|
| The alert's rule id and location | `gh api --paginate --slurp ".../code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100"`, filtered with a separate `jq` | Alert 147, `py/bad-tag-filter`, high, `scripts/regenerate-mermaid-url.py:82`. Five open alerts (144, 147, 148, 149, 150), so SC-002's target is four |
| An unpaginated alert query truncates, and truncation renders as clean | Ran `gh api ".../code-scanning/alerts" --jq '[.[] \| select(.state=="open")] \| length'` against the paginated form | Unpaginated: `0`. Paginated: `5`. All-states corpus: `137`, against a default page size of 30 |
| `--slurp` can carry the `--jq` filter | `gh api --paginate --slurp ... --jq ...` | Refused: "the `--slurp` option is not supported with `--jq` or `--template`". Pages must be written out and filtered separately, which is also what keeps `gh`'s exit status readable |
| Widened unused-pragma set is clean | `ruff check --extend-select RUF100 src/ tests/ scripts/` | `All checks passed!`, exit 0 |
| Marker population in the audited roots | `grep -rnE "lgtm\[\|codeql\[" src/ tests/ scripts/` | Exactly one line, `scripts/regenerate-mermaid-url.py:82` |
| Allowlisted-file census | `find` over the ten allowlisted extensions across the three roots | 583, matching `plan.md` and C7 |
| The 3.9-floor / ruff collision is real | Wrote a 3.9-shaped file, ran the pinned ruff 0.15.14 with the repo config plus `--extend-select RUF100` | 4 errors: UP035, UP006, UP045, UP036 |
| The reconciliation actually works | Same command against a file opening with `from __future__ import annotations` and using PEP 604 in annotations only | `All checks passed!`, exit 0 |
| `--extend-select` adds rather than replaces | `pyproject.toml` `[tool.ruff.lint] select` | `E W F I B C4 UP S RUF100`, `target-version = "py313"` |
| Advisory bandit counts | `bandit -r scripts/ --ignore-nosec \| grep -cE "^>>"` and the same for `src/` | 10 and 15, matching the spec assumption |
| `Lint` job contents | `.github/workflows/pr-checks.yml` steps 52 onward | Installs `ruff==0.15.14` only; runs `ruff format --check --diff src/ tests/`, `ruff check src/ tests/`, `ruff check src/ --select S`, then the waitForResponse guard with `if: always()` |
| `audit-pragma` is invoked by nothing | `grep -rn audit-pragma` excluding `specs/` | `Makefile:1` (PHONY), `Makefile:85` (the target), `CLAUDE.md:243` (prose), plus archived docs. Absent from `make validate`'s prerequisites, from every workflow, from the hook config |
| The control line falls inside the diff context window | Line positions in `scripts/regenerate-mermaid-url.py`: change at 80-82, control at 85, git default context 3 | Control prints as a context line. `quickstart.md` section 2's check is false by construction |
| `ast.parse(feature_version=(3, 9))` discriminates | Parsed a `match` statement and a future-annotated PEP 604 file | `match` raises "only supported in Python 3.10 and greater"; the annotated file parses. Usable as a floor check |
| Test collection home | `tests/unit/scripts/` contents and `pyproject.toml testpaths` | `__init__.py`, `conftest.py` importing `boto3`/`moto` at module level, two existing test modules; `testpaths = ["tests"]` |
| Banned terms in this document | Case-insensitive scan for all seven | Clean |

### Verdict

**PASS with one CRITICAL and two HIGH findings, all closed inside this document rather than
deferred.**

The CRITICAL (F11) is the one worth reading twice. This feature's own post-merge closure query could
not report dirty, for the same structural reason `make audit-pragma` cannot fail and the same
structural reason a `lgtm[...]` comment cannot suppress. Three costumes, one defect: a check whose
negative result is indistinguishable from a check that did not run. Every alert query in the feature
now carries `--paginate`, an exit-code assertion, and a corpus floor.

Coverage is complete: 23 of 23 functional requirements, 12 of 12 success criteria, 9 of 9 contract
clauses, each with at least one implementing and one verifying task where both apply. Every gate this
feature introduces has a paired red-test, so none of them ships in the "structurally unable to fail"
state that produced the defect in the first place. The FR-018 block is separable and named, so an
owner rejection removes exactly five tasks and leaves the rest standing.

The single largest implementation risk is ordering: T038 before T026 puts a checker written to a 3.9
floor onto a blocking line linted under a `py313` ruleset, which is a reproducible day-one failure
rather than a theoretical one.

### Adjacent defects, outside this feature's scope. Card, do not fix

1. **`make audit-pragma`'s bandit half has been structurally unable to fail since it was written**
   (`Makefile:90`). This feature makes the advisory status a *declaration* but does not fix the
   backlog or convert the check. The 25 findings remain unaddressed. Already carded in Out of Scope.
2. **`make validate` is red on `main`** through `scripts/check-banned-terms.sh`, which exits 1 on 17
   pre-existing matches from other features. That is one reason nobody noticed `audit-pragma` was
   missing from its prerequisite list. Already carded.
3. **`scripts/scan-waitforresponse-race.py` collides on exit code 2**: it uses `2` both for "zero
   files scanned" and for "interpreter too old", so a wrong-interpreter run is indistinguishable
   from a vanished scan root. The new checker deliberately avoids the collision; the precedent still
   has it.
4. **`scripts/check-banned-terms.sh` excludes itself by grep basename glob**, exempting any
   identically named file anywhere in the tree. Adversarial Review finding F6 identified it; FR-009
   forbids the form for the new checker but the existing script is untouched.
5. **`scripts/` is linted by no required check.** The `Lint` job runs `ruff check src/ tests/`. After
   this feature, `scripts/` is linted only by `make audit-pragma`, which nothing invokes
   automatically. The new checker's own source is therefore never linted by CI.
6. **Three `py/clear-text-logging-sensitive-data` alerts, all high severity, sit open on
   `src/lambdas/ingestion/handler.py`** (lines 264, 271, 276), plus one on
   `src/lambdas/shared/auth/oauth_state.py:104`. Four of the five open alerts. Explicitly out of
   scope here.
7. **The code scanning configuration contradicts itself**: a path exclusion for the test tree is
   followed by a query filter whose comment states the test tree is still scanned. One of the two is
   dead. Already carded.
8. **`bandit` is installed in CI via `requirements-ci.txt` but invoked by no workflow step**, per
   `docs/cleanup/validator-inventory.md`. A binary shipped to CI and never run.
9. **The mandatory pre-push security check in `CLAUDE.md` is an unpaginated alert query and has been
   reporting a clean bill of health over five genuinely open alerts.** Step 1 of the Pre-Push
   Checklist runs `gh api repos/{owner}/{repo}/code-scanning/alerts --jq '.[] | select(.state ==
   "open") | ...'` with no `--paginate`. Reproduced 2026-07-30: it returns nothing while five alerts
   are open, three of which belong to another feature in this campaign. Every contributor and agent
   following that checklist has been getting a false all-clear. **Already carded and routed at
   campaign level; deliberately not touched by this feature.** Recorded here because it is the same
   defect as F11 and because this feature's artifacts inherited the query shape from it.

---

## Adversarial Review #3

Final gate before implementation. The reviewer authored none of these artifacts. Every claim below
was **run**, not read, on 2026-07-30 under `.venv` (ruff 0.15.14, gh 2.89, Python 3.13). Where a
finding contradicts an earlier review, the earlier text is left standing: prior appendices are
history and are not rewritten.

The question this gate answers is narrower than "is the design right". It is: **can an implementer
execute this task list start to finish without getting stuck, misled, or silently passing?** Three
places the answer was no.

### Findings

| Sev | ID | Finding | Disposition |
|---|---|---|---|
| HIGH | G1 | **T034's subprocess test reddens the required `Lint` job, and no artifact says so.** `pyproject.toml` selects `S` (flake8-bandit) and its `per-file-ignores` entry for `tests/**/*.py` lists `S101 S105 S106 S108 S110 S311 E402 C420`, with **no** `S603`. `ruff check src/ tests/` is a step in the required `Lint` job, and T034 mandates a `subprocess.run([sys.executable, …])` call in a file under `tests/`. Reproduced: `ruff check --select S --ignore-noqa tests/e2e/test_log_visibility.py` reports `S603 subprocess call: check for execution of untrusted input`, exit 1. The suppression on that precedent line is provably load-bearing, not decorative: `RUF100` is also selected, so an unnecessary `# noqa: S603` would itself be an error and `ruff check src/ tests/` would not be passing today. This is the same class as Cross-Artifact F1 (unmentioned `ruff format` step) and is graded the same way: an artifact-invisible cause of a red required context on day one. | **FIXED** in T034, which now requires `# noqa: S603` on the `subprocess.run(` line with a justification comment, states why it must be on exactly that line (RUF100), and records that `S607` does not apply because `sys.executable` is absolute. |
| HIGH | G2 | **T045, a `[GATE]` verification task, cannot execute, and its failure mode is to report the answer it was looking for.** The command was `gh run view --job "$(gh run list … --json databaseId --jq '.[0].databaseId')" --log 2>/dev/null \| head -5`. `gh run list --json databaseId` returns a **run** id; `--job` requires a **job** id. Reproduced: run `30597680512` gives `failed to get job: HTTP 404: Not Found (…/actions/jobs/30597680512)`, exit 1. With `2>/dev/null` and `head -5`, that 404 prints **nothing**, and nothing is exactly what "no extra install step" looks like. A verification of SC-012 that passes when it fails, inside a feature whose entire thesis is that such objects are worse than nothing. | **FIXED** in T045: two-step id resolution (`gh run view "$RID" --json jobs --jq '.jobs[] \| select(.name=="Lint") \| .databaseId'`), verified working against this repository (job `91053515417`, 322 log lines), plus an explicit `log_exit` and line-count check before anything is read from the log, and the workflow-file read named as the authoritative evidence for step adjacency. |
| HIGH | G3 | **T043 can make T044 unexecutable, and nothing ordered them.** Both declared only `Depends on: T042`. T043 mirrors the precedent hook, which is `always_run: true` with `pass_filenames: false` (`.pre-commit-config.yaml:206-212`), so it runs on every commit whatever it touches. T044 must commit a marker inside an audited root to observe the gate biting, and that hook rejects the commit. The hook-bypass flag is not available either: CLAUDE.md forbids it and a machine-level pre-tool hook denies it before git sees it. An implementer doing the optional task first hits a wall with no documented way through. | **FIXED**: T043 now declares `Depends on: T042, T044`, states the mechanism, and names `SKIP=check-dead-suppressions` on the commit as the only legitimate route if the ordering is inverted anyway. |
| MEDIUM | G4 | **T013's second red-test would be recorded as not having gone red.** It required "a non-breaking space or vertical tab visible in the failure output" after mutating to `rstrip(" \t")`. Reproduced over a corpus built to T009's atom set (6,629 inputs): the narrowed trim produces **441** mismatches, but the first one is `'-->\r'`. A test that reports the first mismatch shows a carriage return. The red-test goes red correctly and its stated pass condition says it did not. | **FIXED**: T013 now requires "some whitespace character other than a space or a tab", with the reproduction recorded. |
| MEDIUM | G5 | **T044's mechanics carried three separate hazards.** (a) `git add -A` in a worktree shared with concurrent sibling features sweeps their untracked `specs/` directories into the scratch commit; four such directories are untracked right now. (b) "revert the scratch commit … confirm with `git log --oneline` that it is gone" is self-contradictory: a revert leaves the commit in history, so the stated confirmation can never pass, and a commit carrying a marker stays reachable. (c) The marker was appended to `scripts/regenerate-mermaid-url.py`, the one file this feature exists to clean, so a botched cleanup restores a marker to it. | **FIXED**: T044 now seeds a throwaway `scripts/_gatetest_tmp.py` (verified ruff-clean under the repository config, so nothing upstream can fail first and mask the result), stages it by path, signs the commit, and removes it with `git reset --hard HEAD~1` plus a lease-checked force push. |
| MEDIUM | G6 | **`spec.md` was still alert-number-keyed in two places, contradicting this document's own binding convention 3**, which says in terms that the path-plus-rule rule "applies to acceptance scenarios and Independent Test lines too, not only to the SC block". US1 acceptance scenario 1's **Then** clause read "reports alert 147 as no longer open" and Key Entities named the entity "Alert 147" and identified it "by number, rule, file path, line, and state". Cross-Artifact F4 saw this and left it, calling the measurement unambiguous. That is true of T052 and false of the scenario, which is the acceptance condition a reader checks the feature against. | **FIXED by direct edit to `spec.md`.** Scenario 1's **Then** is now "no open alert whose rule is `py/bad-tag-filter` at that path", with the number kept only as a locator. Key Entities is now keyed on path plus rule with the number named as a label. Cross-Artifact F4's disposition line ("Left in `spec.md` unedited") is now stale and is deliberately not rewritten. |
| LOW | G7 | **T027's heredoc does not survive being copied out of the raw file.** The fenced block sits at four spaces of list indentation and the `PY` terminator carries them, so bash never closes the here-document. Reproduced by extracting the block verbatim and running it: `warning: here-document at line 1 delimited by end-of-file (wanted 'PY')`, then `IndentationError: unexpected indent` from the interpreter. A markdown renderer strips the list indentation, so this bites an implementer working from the raw file and not one working from a rendered view. | RECORDED, not fixed. De-indenting one fence would leave it inconsistent with every other fence in the document. Implementer note: if T027 hangs or reports an indentation error, strip the leading four spaces from the block. |
| LOW | G8 | **`--extend-select RUF100` adds nothing, and FR-011 is doing less work than it reads as doing.** `RUF100` is already a member of `pyproject.toml`'s `select`. Every statement the artifacts make about the flag is accurate ("adds to the configured select"), but the flag itself is a no-op, and a reader can come away thinking the unused-pragma check is otherwise off. The operative consequence: the required `Lint` job's `ruff check src/ tests/` **already** enforces RUF100 over `src/` and `tests/`, so the only coverage FR-011's widening actually buys is `scripts/`, inside a target that nothing automated invokes. | RECORDED, not fixed. No command changes; removing the flag would be a gratuitous diff and keeping it is harmless. Worth a sentence in the pull request so the widening is not oversold. |
| LOW | G9 | **`plan.md`'s Constraints block names the wrong path set for the test file.** It requires "the checker and its test file MUST be clean under `ruff check --extend-select RUF100 scripts/`". The test file lives under `tests/`, which that command never reaches. | RECORDED, not fixed. T026 runs `src/ tests/ scripts/` and closes the gap. Same class as Cross-Artifact F9: a citation drift with no behavioural consequence. |
| LOW | G10 | **The corpus-floor `jq` had no exit check** at the last site in T001 and in T052, while both pass conditions read "every `gh_exit=0` and `jq_exit=0`". The floor read is the one whose silent failure matters most, since the whole point of the floor is to prove the reader was working. | **FIXED**: `echo "jq_exit=$?"` added at both sites. |
| LOW | G11 | **T014's second command has no pass condition.** `grep -c -- '-->' scripts/regenerate-mermaid-url.py` is run and its output is never given a criterion. After T007 the count is necessarily non-zero (the rewritten check and the FR-020 note both contain the arrow), so it can neither pass nor fail. | RECORDED, not fixed. The first command carries the whole criterion and is sufficient. |

Counts: 3 HIGH, 3 MEDIUM, 5 LOW, 0 CRITICAL. All three HIGH and all three MEDIUM are closed by
direct edit in this feature directory. No LOW was fixed.

### The four red-tests: does each actually go red?

| Red-test | Verdict | Evidence |
|---|---|---|
| **T013** (differential oracle, two mutations) | **YES, both.** The pass condition for the second mutation was wrong and is fixed (G4) | Independently rebuilt the oracle and the corpus to T009's specification: 6,629 inputs (exhaustive 1, 2 and 3 element products over the 15 atom set, 3,000 seeded random 4 to 5 element strings, 14 hand-chosen). `split("\n")` with bare `rstrip()`: **0 mismatches**. `splitlines()`: **134**, first `'-->\r==>'`. `rstrip(" \t")`: **441**, first `'-->\r'`. Direction matches all three prior runs; the counts differ because the corpora differ |
| **T029** (checker exits 1 on a seeded fixture) | **YES by design, conditional on T023** | Cannot be run before the checker exists. The mechanism was checked end to end and holds: `.py` is on the C3 allowlist, `tmp_path` is outside the repository so the fixture never enters an audited root, `DEAD_SUPPRESSION_ROOTS` replaces the root set, and the C6 containment test is what stops `relative_to` raising on every file under that override. The one way this goes wrong is a bare `path.resolve().relative_to(repo_root)` in the exclusion check, which T023 forbids in terms. The no-introducer control case is what makes it a real red-test rather than "the file exists" |
| **T040** (`make audit-pragma` non-zero on a marker seeded into `scripts/`) | **YES, and the reason it works is not obvious** | The seeded line matters. `make` stops at the first failing recipe line, and the widened `ruff check --extend-select RUF100 src/ tests/ scripts/` runs **above** the checker. Ran the exact T040 line through the real configuration: `X = 1  # lgtm[py/redtest-do-not-commit]` gives `All checks passed!` and `1 file already formatted`, so control reaches the checker and the failure output names the file. Had the seeded line been ruff-dirty, the target would still have exited non-zero, T040's pass condition ("names the file, line 1, and the marker") would have failed, and the operator would have been hunting a checker bug that was not there |
| **T044** (observed `Lint` failure) | **YES on mechanism, and the two-red-contexts prediction is correct. Executability was the problem** | `Lint` is required, confirmed live: `["Secrets Scan","Lint","Run Tests","Playwright E2E Tests"]`, exit 0. `Run Tests` does collect `tests/unit/scripts/` (`testpaths = ["tests"]`, and the job's seven ignore flags cover `tests/integration/*preprod*`, `tests/integration/timeseries` and `tests/e2e`, none of them this directory), so T035's canary reddens the second context exactly as the task predicts. What did not hold was the procedure: G3 (a local hook can block the scratch commit) and G5 (`git add -A`, revert versus reset, and seeding the feature's own file). All three fixed |

### The 3.9-floor / ruff collision: reproduced

Ran both halves against the real configuration with the pinned ruff 0.15.14.

| Input | Command | Result |
|---|---|---|
| 3.9-shaped: `from typing import List, Optional`, `Optional[str]` and `List[int]` in annotations, a `sys.version_info < (3, 9)` guard | `ruff check --config pyproject.toml --extend-select RUF100 <file>` | **4 errors: UP035, UP045, UP006, UP036.** Exit 1 |
| `from __future__ import annotations`, PEP 604 (`str \| None`) and builtin generics (`list[Path]`) in annotations only, no version guard | same command | **`All checks passed!`** Exit 0 |
| `pyproject.toml` `[tool.ruff.lint]` | read directly | `select = E W F I B C4 UP S RUF100`, `target-version = "py313"`, `required-version = "==0.15.14"` |

**T019's four reconciliation rules are correct and sufficient**, and each of the four is load-bearing
against a specific rule: rule 1 against `UP045` (and it is what makes rule 2 safe), rule 2 against
`UP035` and `UP006`, rule 3 against `UP036`, rule 4 is the verification. **The T038-after-T026
ordering is justified and is the single most important line in the dependency section.** T038 puts
`scripts/` on a blocking line linted under a `py313` ruleset; a checker written to C1's 3.9 floor
without the four rules produces exactly the four errors above, on a line that fails the target for
everybody, on day one. That is the failure FR-015 exists to prevent, and it is reproducible rather
than hypothetical.

One caveat on rule 2 that is implicit in T019 and worth making explicit for the implementer: PEP 604
in annotations is only safe because `from __future__ import annotations` stops them evaluating.
`isinstance(x, str | None)` and any runtime `typing.get_type_hints` call would still break on 3.9,
and neither ruff nor T027's `ast.parse(feature_version=(3, 9))` would catch it, because both are
valid 3.9 *syntax*. T027's own "known limitation" note covers the general case; this is the specific
instance most likely to be written by accident.

### The `ruff format` ordering (Cross-Artifact F1): closed

Read the required job directly. `.github/workflows/pr-checks.yml` `lint` job, in order: checkout,
`setup-python`, install (`pip install ruff==0.15.14`, one step, nothing else),
**`ruff format --check --diff src/ tests/`**, `ruff check src/ tests/`,
`ruff check src/ --select S --output-format=github`, then `Check waitForResponse race ordering` with
`if: always()`. The format check is indeed first, and both new test files land under `tests/`.

T037 and T050 both run `ruff format --check --diff src/ tests/` explicitly, so F1 is closed. Two
notes the implementer should not have to rediscover. First, T037 depends on T012 and T036, so the
format check runs only after both test modules are complete, which is the right place. Second,
`scripts/` is **not** format-checked by anything, so the new checker's own formatting is
unconstrained; only its lint cleanliness matters, and only through T026 and the widened
`audit-pragma` line.

### FR-018 separability: holds

Traced every reference to Phase 6 from outside it. T042 through T046 are the only tasks that touch
`.github/workflows/pr-checks.yml` or depend on a task that does. Outside Phase 6, three tasks mention
the CI step and all three are written to survive its absence: T041's grep spans three files and still
exits 0 on the `Makefile` match alone; T050's fifth command is explicitly marked as gating nothing if
FR-018 is rejected; T057 scopes quickstart section 5 to the accepted case. T048's pass condition is
stated as unchanged either way. The coverage tables isolate the casualties correctly: FR-018, FR-019,
SC-011, SC-012, US3 scenario 6. **Rejecting FR-018 removes exactly five tasks and nothing else
breaks.**

One labelling wrinkle, not worth an edit: the coverage tables mark **T027** with `[GATE]` under
FR-019 and SC-012, but T027 lives in Phase 5, is not marked `[GATE]` at its definition, and survives
a rejection. It is a verification of C1's stdlib-only property that happens to also evidence FR-019.
Reading the table alone, an implementer might drop T027 along with Phase 6. Do not.

### Highest-risk task, and the most likely source of rework

**Highest risk: T019.** It is the only task where getting it wrong produces a failure that looks like
somebody else's problem. It writes a file to a 3.9 floor that will be linted under a `py313` ruleset
on a blocking line, and all four reconciliation rules have to be right at once. Three of the four are
invisible in the finished file: a reader sees `from __future__ import annotations` and reads it as
house style rather than as the thing holding `UP045` off, and the absence of a version guard reads as
an omission rather than as a decision. The failure surfaces at T026 or, if the ordering slips, at
T038 as a target that fails for every contributor. T007 is the more famous line and it is
better protected: it has a 6,629-input differential test and two mutation red-tests standing over it.

**Most likely source of rework: T028, the checker's test file.** It is the one place where three
constraints collide and each of them is discovered by a red required check rather than by reasoning.
It has to satisfy C5 as *source* (no single line carrying a comment introducer followed by a marker,
or the checker flags the file it is testing), `ruff format --check --diff src/ tests/`, and
`ruff check src/ tests/` with `S` selected and `S603` unignored. G1 was exactly this and was invisible
to every artifact until it was run. Expect at least one round trip here, and expect it to arrive as
a red `Lint` job rather than as a failing test.

### What was RUN (not read)

| Command | Result |
|---|---|
| `gh api --paginate --slurp ".../code-scanning/alerts?ref=refs/heads/main&state=open&per_page=100"` then `jq add` | `gh_exit=0`, **5 open**: 150/149/148 `py/clear-text-logging-sensitive-data` on `src/lambdas/ingestion/handler.py`, **147 `py/bad-tag-filter` on `scripts/regenerate-mermaid-url.py:82`**, 144 on `src/lambdas/shared/auth/oauth_state.py:104` |
| the same query, all states | **137**. T001's and T052's corpus floor is exact, not padded |
| `gh api --paginate --slurp … --jq length` | Refused: "the `--slurp` option is not supported with `--jq` or `--template`", exit 1. Convention 6 is correct |
| `gh api …/branches/main/protection --jq .required_status_checks.contexts` | `["Secrets Scan","Lint","Run Tests","Playwright E2E Tests"]`, exit 0 |
| `ruff check --extend-select RUF100 src/ tests/ scripts/` (T003) | `All checks passed!`, exit 0. FR-011's premise holds today |
| `grep -rnE "lgtm\[\|codeql\[" src/ tests/ scripts/` (T004) | Exactly one line, `scripts/regenerate-mermaid-url.py:82` |
| `bandit -r scripts/ --ignore-nosec \| grep -cE "^>>"` and the same for `src/` (T005) | **10** and **15**, matching the spec assumption exactly |
| `pytest tests/unit/scripts/ -q --collect-only` (T006) | exit 0 |
| `make audit-pragma` on the current tree | **exit 0**, with 15 bandit findings printed. The recipe's structural inability to fail is real |
| `find` census over the three roots and the ten allowlisted extensions | **583**, matching C7's example and `plan.md` |
| `ruff check --select S --ignore-noqa tests/e2e/test_log_visibility.py` | `S603`, 1 error, exit 1. Basis of G1 |
| `ruff check --config pyproject.toml --extend-select RUF100` on `X = 1  # lgtm[py/redtest-do-not-commit]` | `All checks passed!`, `1 file already formatted`. T040's seeded line reaches the checker |
| Differential oracle, 6,629 inputs, three implementations | 0 / 134 / 441 mismatches (see the red-test table) |
| `rstrip()` versus regex `\s`, every code point U+0000 to U+2FFF | **0 divergences.** The bare-`rstrip()` half of FR-003 is confirmed independently |
| T027's heredoc, extracted verbatim from the fence | Unterminated here-document plus `IndentationError`. Basis of G7 |
| `gh run view --job "$(gh run list … databaseId)" --log` | `HTTP 404: Not Found (…/actions/jobs/30597680512)`, exit 1. Basis of G2 |
| `gh run view "$RID" --json jobs --jq '.jobs[] \| select(.name=="Lint") \| .databaseId'` then `gh run view --job "$JID" --log` | job `91053515417`, 322 lines, exit 0. The corrected form |
| `import scripts.<module>` from a test under `tests/unit/scripts/` | Confirmed by precedent at `tests/unit/scripts/test_consolidate_oauth_apply.py:12`. `__init__.py` present at `tests/`, `tests/unit/`, `tests/unit/scripts/`; absent at `scripts/`, which is the PEP 420 namespace package T028 relies on |
| `.github/workflows/pr-checks.yml` `lint` and `test` jobs | Read directly. Step order as recorded above; `Run Tests` ignores nothing covering `tests/unit/scripts/` |
| `Makefile` `validate` prerequisites | Seven: `fmt lint security sast check-banned-terms check-test-target-headers check-waitforresponse-race`. `audit-pragma` absent, as every artifact says |

What was **read** and not run: `plan.md`, `research.md`, `quickstart.md`, `checklists/requirements.md`,
`.pre-commit-config.yaml`, `pyproject.toml`, `scripts/regenerate-mermaid-url.py`.

### Errors found in the briefing that commissioned this review

1. **The fuzz counts do not reproduce, and cannot.** The briefing cites `splitlines()` at
   "23/385/194" and `rstrip(" \t")` at "694". This review's independent corpus gives **134** and
   **441**. The direction and the mechanism are identical and the conclusion is unchanged, but those
   numbers are properties of a corpus, not of the code, and quoting them without the corpus invites
   an implementer to treat a different count as a discrepancy worth investigating. Any future
   citation should say "many mismatches for both mutations, zero for the specified form" and name
   the counterexample `"A -->\rB"` instead, which is stable: the original expression is False on it,
   a `splitlines()` rewrite is True, and the specified rewrite is False. Verified again here.
2. **The briefing's own corrections were accepted rather than re-derived, and both check out.** The
   rule is `py/bad-tag-filter` and the contract has nine clauses, both re-confirmed here against the
   live API and the contract file rather than taken on trust. Cross-Artifact F5 already carries both.
   Nothing to change, recorded so the verification is on the record.

Nothing else in the briefing was falsified. `make validate` is red, `Makefile:90` cannot fail,
`audit-pragma` is invoked by nothing, `tests/unit/scripts/conftest.py` imports `boto3` and `moto` at
module level, the system interpreter is 3.12.3, and the canonical alerts query behaves exactly as
described, all confirmed above.

### Adjacent defects found outside this feature's scope. Card, do not fix

The nine already listed under Cross-Artifact Analysis stand. Two more, both surfaced by G1:

10. **`[tool.ruff.lint.per-file-ignores]` for the test tree omits `S603` and `S607`**, so every test
    in this repository that shells out needs a hand-written `# noqa`, and the requirement is recorded
    nowhere. Exactly one test does it today (`tests/e2e/test_log_visibility.py:115`), this feature
    will add the second, and the third author will rediscover it from a red required check. Either
    add the ignore with a scoping comment or write the convention down. Not this feature's diff.
11. **`ruff format` covers `src/` and `tests/` but not `scripts/`**, while `ruff check` covers
    `scripts/` only through `make audit-pragma`, which nothing invokes. So `scripts/` is
    format-unconstrained and, after this feature, lint-constrained only by a target no automated
    process runs. This sharpens existing card 5 rather than replacing it: the new checker's own
    source is neither linted nor formatted by any required check.

### Verdict

Three HIGH findings existed and all three were executability defects rather than design defects: a
required-check rule nobody had named (G1), a `[GATE]` verification command that returns 404 and reads
as a pass (G2), and an optional task that can lock the implementer out of a mandatory one (G3). All
three are closed by direct edit, along with three MEDIUM. Five LOW are recorded and left.

The design underneath survived every test put to it. The rewrite is equivalent over 6,629
independently generated inputs and both mutations of it are not. The ruff collision is real,
reproduced, and correctly reconciled by four rules each of which earns its place. Every gate this
feature introduces has a red-test that goes red. The FR-018 block is genuinely separable: five tasks,
no hidden dependents.

**READY FOR IMPLEMENTATION**, with two conditions that are execution conditions rather than open
questions. First, the FR-018 scope growth into the required `Lint` job is still owner-rejectable and
has not been accepted; Phase 6 must not be started until it is decided, in either direction, and
neither outcome may be reached by drifting into it. Second, the ordering constraints are binding:
T038 must not precede T026, T042 must not precede T040, and T043 must not precede T044.
