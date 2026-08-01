# Contract: dead-suppression checker CLI

**Feature**: `001-bad-tag-filter-dead-suppression` | **Satisfies**: FR-008, FR-009, FR-009a, FR-014, FR-018, FR-019
**Subject**: `scripts/check_dead_suppressions.py`
**Consumers**: the `audit-pragma` recipe in `Makefile`, and the `Lint` job in `.github/workflows/pr-checks.yml`
**Status**: proposed, pinned before implementation

## Why this contract exists

The checker has two independent consumers that will be written at different times, and one of them
lives in a required status check. If the CI step and the Makefile recipe drift apart, the failure
is silent: CI passes, the local target passes, and the gate covers less than either author thinks.

This repository has already paid for that once. The waitForResponse detector needed
`specs/002-waitforresponse-lint-guard/contracts/detector-cli.md` written for exactly this reason,
and pinning the interface surfaced four requirements that contradicted the owning specification.
This document is the same object, one page, and it is a CLI contract rather than an API contract.
There is no API in this feature.

---

## C1. Invocation

```bash
python3 scripts/check_dead_suppressions.py
```

| Property | Requirement |
|---|---|
| Interpreter | Any CPython 3.9 or newer reachable as `python3`. MUST NOT require `.venv`, and MUST NOT use syntax that raises the floor above 3.9. |
| Arguments | None required. The bare invocation scans the full default root set. |
| Positional arguments | Accepted and **ignored**. Parsed with `parse_known_args`, so a pre-commit hook handing over a file list cannot narrow the scan. |
| Working directory | Any. The script resolves the repository root from `Path(__file__).resolve().parent.parent` rather than from the cwd. |
| Imports | **Standard library only.** No import of anything in `requirements.txt`, `requirements-dev.txt`, or `requirements-ci.txt`. |
| Executable bit | Not required. Always invoked through the interpreter. |
| Network, filesystem writes | None. The checker reads and prints. |

The 3.9 floor is deliberately lower than the project's 3.13. The `Lint` job gets 3.13 from
`setup-python`, but the Makefile consumer runs under whatever `python3` the contributor's shell
resolves, and that is not the project interpreter: `/usr/bin/python3` on the reference machine is
3.12.3 while `python3` resolves through a pyenv shim to 3.13.0. Nothing in this design needs a
version-gated feature, so requiring one would fail contributors for no benefit.
`scripts/scan-waitforresponse-race.py:75-81` does carry a hard 3.13 guard. If that pattern is ever
copied here, it MUST NOT exit `2`: C2 assigns `2` to "zero files scanned", and the precedent
already collides on that code, so a wrong-interpreter run there is indistinguishable from a scan
whose roots have vanished.

The stdlib-only rule is not stylistic. `.github/workflows/pr-checks.yml:52-56` installs
`ruff==0.15.14` and nothing else in the `Lint` job. A single third-party import puts a required
check permanently red, and adding an install step to fix it is the tooling addition FR-019 forbids.

Working-directory independence matters because the optional pre-commit hook runs from wherever the
committing shell happens to be, which is not guaranteed to be the repository root.

---

## C2. Exit codes

| Code | Meaning | Consumer behaviour |
|---|---|---|
| `0` | At least one file scanned, no marker found | Makefile continues, CI step passes |
| `1` | One or more markers found | Makefile recipe fails, CI step fails, merge blocked |
| `2` | Zero files scanned, for any reason | Both consumers fail |

Code `2` is separate from `0` deliberately. A scan that examines nothing must not report the same
result as a scan that found nothing, or a moved root reads as a clean tree. The default roots are
three hard-coded directory names, so this is a live risk rather than a theoretical one.

---

## C3. Default root set

```text
src/
tests/
scripts/
```

Resolved relative to the repository root, not the cwd. A root that does not exist contributes zero
files, and if that leaves the total at zero the run exits `2`.

Extension allowlist, case-insensitive:

```text
.py .sh .js .ts .tsx .jsx .html .yml .yaml .tf
```

Skipped unconditionally, at any depth: `__pycache__`, `node_modules`, `.venv`, `.git`,
`.pytest_cache`, `.hypothesis`.

Files are read as UTF-8 with `errors="replace"`, so an undecodable file is scanned harmlessly
rather than raising and taking the gate down.

`.md` and `.txt` are absent from the allowlist on purpose. Prose that describes a marker has to
write it, which is the defect that made the specification's original tree-wide criterion false at
the moment it was written.

---

## C4. Root override

| Property | Requirement |
|---|---|
| Variable | `DEAD_SUPPRESSION_ROOTS` |
| Format | `os.pathsep`-separated paths. Relative paths resolve against the repository root. |
| Effect | Replaces the default root set entirely. Does not extend it. |
| Purpose | Testing only. Neither consumer sets it. |

This exists so the negative test required by SC-006 can point the checker at a `tmp_path`
containing a real marker, without that marker ever existing inside the audited set. It mirrors
`SCAN_ROOT_ENV` in `scripts/scan-waitforresponse-race.py`, which was added for the same reason.

The extension allowlist and the skip list still apply under an override. A test fixture must
therefore be given an allowlisted extension, `.py` being the obvious choice.

---

## C5. Detection rule

A line matches when **both** hold:

1. It contains `lgtm[` or `codeql[`, compared case-insensitively.
2. The marker's position on the line is **after** the first occurrence of a comment introducer:
   `#`, `//`, `<!--`, `/*`, or `--`.

Consequences that consumers and test authors depend on:

- A marker inside a string literal, a docstring, or a URL does not match, because no introducer
  precedes it on that line.
- A marker after `#` matches regardless of what else is on the line, so a real suppression appended
  to a line of code is caught.
- Matching is per line. Markers spanning a line break are not detected, which is accepted: the
  target is the contributor who typed a suppression they believed would work, not an adversary.

---

## C6. Self-exclusion

Exclusion is by **exact repository-relative path**, never by basename or glob:

```python
SELF_EXCLUSIONS = frozenset({
    Path("scripts/check_dead_suppressions.py"),
    Path("tests/unit/scripts/test_check_dead_suppressions.py"),
})
```

A candidate is skipped if and only if it resolves inside the repository root **and** its
repository-relative path is a member of that set. A candidate that resolves outside the repository
root is never excluded, and computing its relative path MUST NOT raise.

That second sentence is load-bearing, not pedantry. Under a `DEAD_SUPPRESSION_ROOTS` override the
scan walks files outside the repository, and
`Path("/tmp/x/bad.py").resolve().relative_to(repo_root)` raises
`ValueError: '/tmp/x/bad.py' is not in the subpath of ...`. A naive `relative_to` in the exclusion
test therefore crashes the checker on every file the SC-006 negative test creates. Use a
containment test (`Path.is_relative_to`, or `relative_to` inside `try/except ValueError`) and treat
the outside case as "not excluded".

This is explicitly **not** the mechanism `scripts/check-banned-terms.sh:32` uses.
`--exclude=check-banned-terms.sh` is a grep basename glob and exempts any identically named file
anywhere in the tree. FR-009 forbids that form after Adversarial Review finding F6.

The set MUST have exactly the two members above. Adding a third is a requirements change: every
addition is a place a real suppression can hide, and the whole point of exact-path exclusion is
that the hole is enumerable.

Fails safe. A renamed or relocated checker stops being excluded and immediately flags itself,
which is loud rather than silent.

---

## C7. Output

### Clean run

Goes to stdout. Must state the number of files scanned, so a root that quietly shrank is visible
in a passing log rather than only in a `2`.

```text
=== Dead Suppression Scanner ===
Roots: src/, tests/, scripts/
Scanned 583 files.
PASS: no inline scanning-suppression markers found.
```

### Failing run

Paths are printed repository-relative when the file is inside the repository, and absolute when it
is not. The fallback is required for the same reason as C6's containment test, and it is what
`scripts/scan-waitforresponse-race.py:418-423` already does.

Goes to stdout. Per FR-014 every finding names the **file**, the **line number**, and the
**marker**, and the run states both **why the form is inert** and **what the supported alternative
is**. A failure that only says "found a bad comment" gets worked around instead of fixed, which is
how the repository ended up here.

```text
=== Dead Suppression Scanner ===
Roots: src/, tests/, scripts/
Scanned 583 files.

FAIL: 1 inline scanning-suppression marker found.

  scripts/regenerate-mermaid-url.py:82
    marker: lgtm[py/bad-tag-filter]
    line:   if re.search(r"-->\s*$", code, re.MULTILINE):  # lgtm[...]

Why this is a problem:
  Inline lgtm[...] and codeql[...] comments are NOT honoured by this repository's
  code scanning setup. They suppress nothing. A high-severity alert sat open on main
  for six months behind exactly this comment, on the exact line the comment was on.

What to do instead:
  - Preferred: change the code so the finding does not arise.
  - If the finding is genuinely a false positive, dismiss it through the code
    scanning product's own dismissal workflow, with a recorded reason. That is the
    only suppression route that has any effect here.
  - Do not swap lgtm[...] for codeql[...]. Neither works.
```

Assertions in tests SHOULD target substrings such as the path, the line number, the marker text,
and a distinctive phrase from each explanatory block. They MUST NOT target exact whitespace or the
full block verbatim, or every wording improvement becomes a test failure.

---

## C8. What consumers MUST NOT do

- MUST NOT wrap the invocation in anything that swallows the exit status. That includes
  `|| true`, piping into `grep`, and piping into `echo`. The bandit half of `audit-pragma` is
  advisory precisely because of a pipe, and FR-013 exists because that was an accident rather than
  a decision. Repeating the accident here would recreate the whole defect.
- MUST NOT reach the checker through `pre-commit run` **from the merge-blocking context**. The
  `Pre-commit Hooks` CI job sets `SKIP` and is not a required context, so the `Lint` step invokes
  the script directly for both reasons. This does not forbid a local pre-commit hook: an additive
  one is permitted and recommended, and the precedent carries all three wirings at once, a hook at
  `.pre-commit-config.yaml:206-212`, a direct `Lint` step at `.github/workflows/pr-checks.yml:85-87`,
  and a `make validate` prerequisite at `Makefile:42`. What is forbidden is the required check
  depending on the hook runner.
- MUST NOT pass positional file lists expecting the scan to narrow. They are ignored by design.
- MUST NOT set `DEAD_SUPPRESSION_ROOTS`. It is a testing seam.

---

## C9. Consumer wiring, verbatim

**`Makefile`**, inside `audit-pragma`:

```make
	@echo "$(YELLOW)=== [BLOCKING] Dead inline scanning suppressions ===$(NC)"
	@python3 scripts/check_dead_suppressions.py
```

**`.github/workflows/pr-checks.yml`**, final step of the `lint` job:

```yaml
      - name: Check for dead scanning suppressions
        if: always()
        run: python3 scripts/check_dead_suppressions.py
```

Both are the bare invocation. Neither passes arguments, neither sets the override, neither
swallows the status.
