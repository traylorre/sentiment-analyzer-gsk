#!/usr/bin/env python3
"""Detect inline scanning-suppression markers that suppress nothing.

This repository's code scanning setup does not honour inline suppression
comments. A marker written in a comment therefore has no effect at all: it
reads as a decision that was made and enforced, while the finding stays open.
One high-severity alert sat open on the default branch for six months behind
exactly such a comment, on the exact line the comment was on.

This checker walks a fixed set of roots and fails when it finds a marker in a
comment, naming the file, the line, the marker, why the form is inert, and
what to do instead.

Exit codes:
    0   at least one file was scanned and no marker was found
    1   one or more markers were found
    2   zero files were scanned, for any reason

Code 2 is deliberately distinct from 0. A scan that examined nothing must not
report the same result as a scan that found nothing, or a moved root reads as
a clean tree.

Standard library only, and no floor above CPython 3.9. The Makefile consumer
runs under whatever `python3` a contributor's shell resolves, and the CI
consumer installs no packages beyond ruff, so a single third-party import
would put a required check permanently red.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_ROOTS = ("src", "tests", "scripts")

ROOTS_ENV = "DEAD_SUPPRESSION_ROOTS"

# Prose has to write a marker in order to describe one, so documentation
# extensions are deliberately absent from this set.
ALLOWED_EXTENSIONS = frozenset(
    {".py", ".sh", ".js", ".ts", ".tsx", ".jsx", ".html", ".yml", ".yaml", ".tf"}
)

SKIP_DIRECTORIES = frozenset(
    {"__pycache__", "node_modules", ".venv", ".git", ".pytest_cache", ".hypothesis"}
)

MARKERS = ("lgtm[", "codeql[")

COMMENT_INTRODUCERS = ("#", "//", "<!--", "/*", "--")

# Exact repository-relative paths, never basenames or globs. A basename glob
# would exempt any identically named file anywhere in the tree. Exactly two
# members: every addition is a place a real suppression could hide, and the
# point of exact-path exclusion is that the hole stays enumerable.
SELF_EXCLUSIONS = frozenset(
    {
        Path("scripts/check_dead_suppressions.py"),
        Path("tests/unit/scripts/test_check_dead_suppressions.py"),
    }
)


class Finding(NamedTuple):
    """One marker occurrence."""

    path: str
    lineno: int
    marker: str
    source: str


def repo_relative(path: Path) -> Path | None:
    """Repository-relative form of *path*, or None when it is outside.

    Never raises. Under a roots override the scan walks files outside the
    repository, and a bare ``relative_to`` would raise on every one of them.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT)
    except ValueError:
        return None


def display_path(path: Path) -> str:
    """Repository-relative when inside the repository, absolute when not."""
    relative = repo_relative(path)
    return str(relative) if relative is not None else str(path.resolve())


def is_self_excluded(path: Path) -> bool:
    """True only for the two exact repository-relative paths above."""
    relative = repo_relative(path)
    return relative is not None and relative in SELF_EXCLUSIONS


def resolve_roots() -> list[Path]:
    """Default roots, or the override set when the environment names one.

    The override replaces the default set rather than extending it. It is a
    testing seam: neither consumer sets it.
    """
    override = os.environ.get(ROOTS_ENV)
    if override:
        roots = []
        for entry in override.split(os.pathsep):
            if not entry:
                continue
            candidate = Path(entry)
            roots.append(
                candidate if candidate.is_absolute() else REPO_ROOT / candidate
            )
        return roots
    return [REPO_ROOT / name for name in DEFAULT_ROOTS]


def iter_files(roots: Iterable[Path]) -> Iterator[Path]:
    """Yield every allowlisted file under *roots*, skip list applied."""
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRECTORIES)
            for name in sorted(filenames):
                candidate = Path(dirpath) / name
                if candidate.suffix.lower() in ALLOWED_EXTENSIONS:
                    yield candidate


def find_case_insensitive(haystack: str, needle: str) -> int:
    """Index of *needle* in *haystack*, ignoring case, or -1.

    Written as a scan rather than as ``haystack.lower().find(needle)`` because
    lowercasing can change a string's length (U+0130 is the common example),
    which would shift every index computed from it.
    """
    span = len(needle)
    for index in range(len(haystack) - span + 1):
        if haystack[index : index + span].lower() == needle:
            return index
    return -1


def first_introducer_index(line: str) -> int:
    """Index of the earliest comment introducer, or -1 when there is none.

    The introducers are caseless, so this searches the line as written.
    """
    positions = [line.find(token) for token in COMMENT_INTRODUCERS]
    found = [position for position in positions if position >= 0]
    return min(found) if found else -1


def marker_in_comment(line: str) -> str | None:
    """The marker text when this line carries one in a comment, else None.

    Purely textual: it does not know what a string literal is. A marker with
    no introducer earlier on the same line does not match, which is what keeps
    URLs, docstrings and this checker's own constants out of the results.
    """
    introducer = first_introducer_index(line)
    if introducer < 0:
        return None
    hits = [find_case_insensitive(line, marker) for marker in MARKERS]
    positions = [position for position in hits if position > introducer]
    if not positions:
        return None
    start = min(positions)
    end = line.find("]", start)
    return line[start : end + 1] if end >= 0 else line[start:].rstrip()


def scan_file(path: Path) -> list[Finding]:
    """Every marker occurrence in *path*, at most one per line."""
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = []
    for lineno, line in enumerate(text.split("\n"), start=1):
        marker = marker_in_comment(line)
        if marker is not None:
            findings.append(Finding(display_path(path), lineno, marker, line.strip()))
    return findings


WHY_BLOCK = (
    "Why this is a problem:",
    "  Inline lgtm[...] and codeql[...] comments are NOT honoured by this",
    "  repository's code scanning setup. They suppress nothing. A high-severity",
    "  alert sat open on the default branch for six months behind exactly this",
    "  comment, on the exact line the comment was on.",
)

WHAT_BLOCK = (
    "What to do instead:",
    "  - Preferred: change the code so the finding does not arise.",
    "  - If the finding is genuinely a false report, dismiss it through the code",
    "    scanning product's own dismissal workflow, with a recorded reason. That",
    "    is the only suppression route that has any effect here.",
    "  - Do not swap lgtm[...] for codeql[...]. Neither of them works.",
)


def report(roots: list[Path], scanned: int, findings: list[Finding]) -> None:
    """Print the run, clean or failing, to stdout."""
    print("=== Dead Suppression Scanner ===")
    print("Roots: " + ", ".join(display_path(root) + "/" for root in roots))
    print(f"Scanned {scanned} files.")

    if not findings:
        print("PASS: no inline scanning-suppression markers found.")
        return

    noun = "marker" if len(findings) == 1 else "markers"
    print()
    print(f"FAIL: {len(findings)} inline scanning-suppression {noun} found.")
    print()
    for finding in findings:
        print(f"  {finding.path}:{finding.lineno}")
        print(f"    marker: {finding.marker}")
        print(f"    line:   {finding.source}")
    print()
    for line in WHY_BLOCK:
        print(line)
    print()
    for line in WHAT_BLOCK:
        print(line)


def main(argv: list[str] | None = None) -> int:
    """Scan and return the exit code."""
    parser = argparse.ArgumentParser(
        description=(
            "Detect inline scanning-suppression markers, which this "
            "repository's code scanning setup does not honour."
        )
    )
    parser.add_argument(
        "files",
        nargs="*",
        help=(
            "Accepted and ignored. A pre-commit hook handing over a file list "
            "must not be able to narrow the scan."
        ),
    )
    parser.parse_known_args(argv)

    roots = resolve_roots()
    scanned = 0
    findings: list[Finding] = []
    for path in iter_files(roots):
        if is_self_excluded(path):
            continue
        scanned += 1
        findings.extend(scan_file(path))

    if scanned == 0:
        print("=== Dead Suppression Scanner ===")
        print("Roots: " + ", ".join(display_path(root) + "/" for root in roots))
        print("Scanned 0 files.")
        print(
            "ERROR: the scan examined nothing. A scan that examined nothing is "
            "not a clean tree. Check that the roots above still exist."
        )
        return 2

    report(roots, scanned, findings)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
