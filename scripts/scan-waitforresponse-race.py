#!/usr/bin/env python3
"""Inventory and classify act-then-wait races in the customer-dashboard E2E suite.

# Target: Customer Dashboard (Next.js/Amplify)

Scanned root: ``frontend/tests/e2e/`` (spec files **and** ``helpers/``). This is the Playwright
suite for the customer dashboard, NOT the admin pytest suite under ``tests/``. Two neighbouring
scripts (``scripts/audit-e2e-skips.py``, ``scripts/check-false-pass-patterns.sh``) default to the
admin suite, and this repository has a documented history of confusing the two dashboards
(see CLAUDE.md, "Two Dashboards").

CLASSIFICATION RULE (verbatim to spec FR-011)
---------------------------------------------
A *call site* is an occurrence of ``page.waitForResponse(...)`` or
``page.waitForEvent('requestfailed'|'response')``. Comment lines are excluded from the call-site
population. Each site is classified as exactly one of:

``RACY``
    An awaited wait whose immediately preceding non-comment, non-blank line performs a triggering
    action: one of ``.fill(``, ``.click(``, ``.press(``, ``.selectOption(``, ``.clear(``,
    ``.goto(``, ``.reload(``, ``.evaluate(``, ``.type(``, ``.check(``, ``.tap(``,
    ``.setInputFiles(``, ``.dispatchEvent(``.

    The listener is registered *after* the request it means to observe was already triggered, so
    the response can arrive in the gap and the wait then blocks until timeout.

``PROMISE-FIRST``
    The wait is assigned to a variable before the triggering action and awaited after it. This is
    the correct shape.

``OTHER``
    Neither. Requires human triage, and is reported under an explicit banner rather than folded
    into the counts alone.

The rule is keyed on the *shape* (adjacency to a triggering action), not on the method name. That
distinction is load-bearing: an earlier method-name-keyed inventory matched only ``waitForResponse``
and silently missed three ``waitForEvent('requestfailed')`` sites.

CONSUMED INTERFACE
------------------
This script is not only a one-off inventory. The dependent regression-guard feature wires it into
a pre-commit hook and into the required CI ``Lint`` job, so its invocation, output and exit codes
are a contract. See ``specs/002-waitforresponse-lint-guard/contracts/detector-cli.md``.

Consequences, each of which has a test in spec 001 T001:

* **Standard library only.** The CI job that enforces this script installs no project
  dependencies, so a single third-party import would put the guard permanently red.
* **Findings go to stdout**, with a five-number summary including files scanned.
* **A scan that examines zero files exits non-zero**, whatever the cause. "No violations found"
  and "no files found" must not share an exit code, or moving the scan root reads as a clean tree.
* **The scan root is fixed and positional arguments are ignored.** The guard's hook runs with
  ``pass_filenames: false`` against untracked files; a file-list-driven detector would never be
  handed the offending file and would report clean.
* **The interpreter floor is asserted below**, because the guard invokes a bare ``python3`` that
  resolves from the committing shell's ``PATH``.

Exit codes:
    0   at least one file scanned, no RACY site found
    1   one or more RACY sites found
    2   zero files scanned (root missing, renamed, or empty), or the interpreter is too old
"""

import sys

# Interpreter floor. Must be the first executable statement: the regression guard invokes this
# script as a bare `python3`, which resolves from the committing shell's PATH and is not
# necessarily the project interpreter. Running the detector under an unvalidated version makes
# its result silently untrustworthy, so fail loudly instead.
# The UP036 suppression below is deliberate. Ruff reads `target-version = py313` as "3.13 is the
# floor" and calls this block dead. That assumption is exactly what fails here: the regression
# guard runs this file under a bare `python3` from the committing shell's PATH, which is 3.12 on
# this machine and 3.10 per CLAUDE.md. The check is unreachable only under the interpreter it is
# not defending against.
if sys.version_info < (3, 13):  # noqa: UP036 - guard runs under a bare python3, not the project 3.13
    sys.stderr.write(
        "scan-waitforresponse-race: requires Python 3.13 or newer, "
        f"got {sys.version_info.major}.{sys.version_info.minor}.\n"
        "The regression guard invokes a bare `python3`; ensure it resolves to 3.13+.\n"
    )
    raise SystemExit(2)

import argparse
import os
import re
from pathlib import Path

# --------------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------------

#: Scan root, relative to the repository root. Fixed by requirement (T001 criterion 12).
DEFAULT_SCAN_ROOT = Path("frontend/tests/e2e")

#: Testing seam for the zero-file branch (T001 criterion 6 asserts it against an empty temporary
#: directory). Deliberately an environment variable rather than a positional argument: pre-commit
#: passes file lists as arguments and never sets env overrides, so this cannot become the
#: narrowing vector criterion 12 exists to close.
SCAN_ROOT_ENV = "WAITFORRESPONSE_SCAN_ROOT"

#: Actions that trigger a network request. Keyed on shape, not on method name.
#: `.evaluate(` is not hypothetical: error-visibility-search.spec.ts triggers a request with
#: `retryButton.evaluate((el) => el.click())`. A list stopping at `.reload(` would miss it.
TRIGGER_TOKENS = (
    ".fill(",
    ".click(",
    ".press(",
    ".selectOption(",
    ".clear(",
    ".goto(",
    ".reload(",
    ".evaluate(",
    ".type(",
    ".check(",
    ".tap(",
    ".setInputFiles(",
    ".dispatchEvent(",
)

#: `page.waitForResponse(...)` in any form.
WAIT_FOR_RESPONSE_RE = re.compile(r"\bpage\s*\.\s*waitForResponse\s*\(")

#: `page.waitForEvent('requestfailed')` / `('response')` only. Other events are not request waits.
WAIT_FOR_EVENT_RE = re.compile(
    r"""\bpage\s*\.\s*waitForEvent\s*\(\s*['"](requestfailed|response)['"]"""
)

#: `const x = ` / `let x = ` / `var x = ` immediately preceding the wait call.
ASSIGNMENT_RE = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*$")

#: Enclosing test or function, for the OTHER triage banner.
ENCLOSING_RE = re.compile(
    r"""^\s*(?:export\s+)?(?:
          (?:async\s+)?function\s+(?P<fn>[A-Za-z_$][\w$]*)
        | test(?:\.\w+)*\s*\(\s*['"`](?P<test>[^'"`]+)['"`]
        | describe\s*\(\s*['"`](?P<desc>[^'"`]+)['"`]
        | (?:const|let|var)\s+(?P<arrow>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(
    )""",
    re.VERBOSE,
)

RACY = "RACY"
PROMISE_FIRST = "PROMISE-FIRST"
OTHER = "OTHER"


# --------------------------------------------------------------------------------------------
# Source inspection helpers
# --------------------------------------------------------------------------------------------


def is_comment(line: str) -> bool:
    """True for `//`, `/*` and continuation `*` lines.

    Comment lines are excluded from the call-site population entirely. A naive grep over the
    scan root returns more matches than there are real sites, and the difference is prose
    describing the pattern, not code performing it.
    """
    stripped = line.strip()
    return (
        stripped.startswith("//")
        or stripped.startswith("/*")
        or stripped.startswith("*")
    )


def is_blank(line: str) -> bool:
    return not line.strip()


def find_wait(line: str) -> bool:
    """True if this line opens a request-wait call."""
    return bool(WAIT_FOR_RESPONSE_RE.search(line) or WAIT_FOR_EVENT_RE.search(line))


def preceding_code_line(lines: list[str], index: int) -> str | None:
    """The nearest preceding line that is neither blank nor a comment.

    This is the adjacency the classification rule turns on. Skipping comments matters: several
    racy sites in this suite are preceded by a comment explaining the wait, and a rule that
    stopped at the comment would classify every one of them as OTHER.
    """
    for i in range(index - 1, -1, -1):
        if is_blank(lines[i]) or is_comment(lines[i]):
            continue
        return lines[i]
    return None


def performs_trigger(line: str | None) -> bool:
    if line is None:
        return False
    return any(token in line for token in TRIGGER_TOKENS)


def enclosing_name(lines: list[str], index: int) -> str:
    """Nearest enclosing test or function name, for the triage banner."""
    for i in range(index, -1, -1):
        match = ENCLOSING_RE.match(lines[i])
        if match:
            for key in ("test", "desc", "fn", "arrow"):
                if match.group(key):
                    return match.group(key)
    return "<module scope>"


def awaited_later(lines: list[str], start: int, variable: str) -> bool:
    """True if `variable` is awaited after `start`, with a triggering action in between.

    This is what separates PROMISE-FIRST from a promise that is created and then dropped. A wait
    assigned to a variable that is never awaited is not the correct shape; it is a floating
    promise, and it is reported as OTHER for human triage.
    """
    await_re = re.compile(rf"\bawait\s+{re.escape(variable)}\b")
    seen_trigger = False
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if is_comment(line):
            continue
        if performs_trigger(line):
            seen_trigger = True
        if await_re.search(line):
            return seen_trigger
    return False


# --------------------------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------------------------


class Site:
    """One classified call site."""

    def __init__(
        self, path: Path, line_no: int, classification: str, text: str, context: str
    ):
        self.path = path
        self.line_no = line_no
        self.classification = classification
        self.text = text
        self.context = context

    def __str__(self) -> str:
        return f"{self.path}:{self.line_no} {self.classification}"


def classify_site(lines: list[str], index: int) -> str:
    """Classify the call site opening at `lines[index]`."""
    line = lines[index]

    # PROMISE-FIRST: assigned to a variable, then awaited after a triggering action. The
    # assignment may be on the same line (`const p = page.waitForResponse(`) or, for a wrapped
    # call, on the line above.
    match = re.search(
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?=.*waitFor)", line
    )
    variable = match.group(1) if match else None
    if variable is None and index > 0:
        prev = ASSIGNMENT_RE.search(lines[index - 1].rstrip())
        if prev:
            variable = prev.group(1)
    if variable is not None:
        return PROMISE_FIRST if awaited_later(lines, index, variable) else OTHER

    # RACY: awaited inline, immediately after a triggering action.
    if re.search(r"\bawait\b", line):
        if performs_trigger(preceding_code_line(lines, index)):
            return RACY
        return OTHER

    return OTHER


def scan_file(path: Path, display: Path) -> list[Site]:
    """Classify every call site in one file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Never swallow a read failure into a clean result. An unreadable file under the scan
        # root means the scan is incomplete, and an incomplete scan must not read as a pass.
        raise SystemExit(
            f"scan-waitforresponse-race: cannot read {display}: {exc}"
        ) from exc

    lines = text.splitlines()
    sites: list[Site] = []
    for index, line in enumerate(lines):
        if is_comment(line) or not find_wait(line):
            continue
        sites.append(
            Site(
                path=display,
                line_no=index + 1,
                classification=classify_site(lines, index),
                text=line.strip(),
                context=enclosing_name(lines, index),
            )
        )
    return sites


# --------------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------------

REMEDIATION = """\
How to fix a RACY site
----------------------
Register the listener BEFORE the action that triggers the request, then await it after:

    // WRONG - the response can arrive before the listener exists
    await searchInput.fill('AAPL');
    await page.waitForResponse('**/api/v2/tickers/search**');

    // RIGHT - promise-first
    const searchPromise = page.waitForResponse('**/api/v2/tickers/search**');
    await searchInput.fill('AAPL');
    await searchPromise;

Await the promise on the success path so a timeout surfaces as a test failure rather than an
unhandled rejection. Where this suite searches for a ticker, prefer the shared helper
`searchAndAwaitResponse()` in frontend/tests/e2e/helpers/search-helpers.ts, which encapsulates
the promise-first ordering so it cannot be reintroduced one call site at a time."""


def report(sites: list[Site], files_scanned: int) -> int:
    """Print findings to stdout and return the exit code."""
    for site in sites:
        print(site)

    counts = {
        RACY: sum(1 for s in sites if s.classification == RACY),
        PROMISE_FIRST: sum(1 for s in sites if s.classification == PROMISE_FIRST),
        OTHER: sum(1 for s in sites if s.classification == OTHER),
    }

    others = [s for s in sites if s.classification == OTHER]
    if others:
        # A shape the classifier cannot place must be visible, or it is counted as clean by
        # omission. Name the enclosing test so triage does not start with a line-number hunt.
        print()
        print("=" * 78)
        print("OTHER sites - requires human triage")
        print("=" * 78)
        for site in others:
            print(f"  {site.path}:{site.line_no}  (in: {site.context})")
            print(f"      {site.text}")

    print()
    print(
        f"SUMMARY: RACY {counts[RACY]} / PROMISE-FIRST {counts[PROMISE_FIRST]} "
        f"/ OTHER {counts[OTHER]} / total {len(sites)} / files scanned {files_scanned}"
    )

    if files_scanned == 0:
        print()
        print(
            "ERROR: zero files scanned. The scan root is missing, renamed, or empty.\n"
            "       This is not a clean result - the scan examined nothing."
        )
        return 2

    if counts[RACY] > 0:
        print()
        print(REMEDIATION)
        return 1

    return 0


# --------------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------------


def repo_root() -> Path:
    """Repository root, derived from this file's location rather than the CWD.

    The regression guard invokes this script from a pre-commit hook, whose working directory is
    not guaranteed to be the repository root.
    """
    return Path(__file__).resolve().parent.parent


def resolve_scan_root() -> Path:
    override = os.environ.get(SCAN_ROOT_ENV)
    if override:
        return Path(override)
    return repo_root() / DEFAULT_SCAN_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="scan-waitforresponse-race",
        description=(
            "Classify act-then-wait races in the CUSTOMER DASHBOARD Playwright suite at "
            "frontend/tests/e2e/ (spec files and helpers/). This is not the admin pytest "
            "suite under tests/."
        ),
        epilog=(
            "The scan root is fixed; positional arguments are ignored, so this is safe to run "
            "from a pre-commit hook with pass_filenames: false. Exit codes: 0 clean, 1 RACY "
            "sites found, 2 zero files scanned."
        ),
    )
    # parse_known_args, not parse_args: pre-commit may pass a file list, and this scanner
    # deliberately ignores it rather than letting it narrow the scan (T001 criterion 12).
    parser.parse_known_args()

    scan_root = resolve_scan_root()
    root = repo_root()

    sites: list[Site] = []
    files_scanned = 0
    if scan_root.is_dir():
        for path in sorted(scan_root.rglob("*.ts")):
            files_scanned += 1
            try:
                display = path.relative_to(root)
            except ValueError:
                display = path
            sites.extend(scan_file(path, display))

    return report(sites, files_scanned)


if __name__ == "__main__":
    raise SystemExit(main())
