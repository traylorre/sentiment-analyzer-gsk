#!/usr/bin/env python3
"""Scan the repository for references to retired framework terms.

Replaces ``scripts/check-banned-terms.sh`` (feature 001-validate-gate-repair).

WHY THIS IS PYTHON AND NOT SHELL
--------------------------------
The shell version could not be unit tested: its filename was not importable, and three
of the feature's success criteria are assertions about behaviour under filesystem states
that must be constructed and torn down. The project constitution's Implementation
Accompaniment Rule requires unit tests for implementation code. Tests live in
``tests/unit/scripts/test_check_banned_terms.py``.

THE TWO BUGS THIS REWRITE EXISTS TO KILL
----------------------------------------
1. The shell version applied path exclusions to grep's whole ``path:lineno:content``
   output line. Any file whose *content* mentioned an excluded path suppressed its own
   finding. Here ``path`` and ``line_text`` are separate values and exclusions only ever
   see the path.
2. An empty exclusion list produced an empty ``grep -Ev`` pattern, which matched every
   line, discarded every finding, and printed PASS on a repository with 17 violations.
   An empty list here filters nothing, so the dangerous direction is unreachable rather
   than guarded. ``_validate_config`` records it as an intended property anyway.

A third, subtler defect: exclusions only worked because GNU grep emits a ``./`` prefix.
Changing the scan root would have silently disabled every exclusion at once. Every path
here is canonicalised before any comparison, so nothing depends on incidental spelling.

EXIT CODES
----------
0  every occurrence is absent or carries a sanctioned exemption
1  at least one unexempted occurrence, OR the configuration is unusable

Exit 1 covers both deliberately. A checker that cannot determine the answer must not
report success, and a caller able to pass on "the checker is broken" defeats the point.
The two cases are distinguished by the message, never by the exit code.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Authoritative term list. This is the ONLY place these strings are enumerated.
#
# Terms are matched case-insensitively as regular expressions, not as literals.
# One entry ("lambda.web.adapter") contains dots that behave as wildcards, so it
# also matches underscore and hyphen spellings. That is preserved deliberately:
# altering the term list is out of scope for this feature, and the wildcard
# behaviour appears intentional. Any term added later that contains regex
# metacharacters will match more, or less, than its author expects.
#
# Because this file enumerates the terms, it excludes itself from the scan by
# resolved path. See _is_self().
# ---------------------------------------------------------------------------
BANNED_TERMS: tuple[str, ...] = (
    "fastapi",
    "mangum",
    "uvicorn",
    "starlette",
    "lambda.web.adapter",
    "LambdaAdapterLayer",
    "AWS_LWA",
)

# Directory names skipped at any depth. Scan scoping, not exemption.
#
# ".claude" holds git-ignored subagent handoff output. Without it the gate measures its
# own output: any agent that quotes a failure line from this checker raises the count for
# whoever commits next, and every commit and `make validate` on a machine that has run
# subagents fails. CI never saw it because a fresh clone has no .claude/handoff.
EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        ".pytest_cache",
        ".hypothesis",
        ".ruff_cache",  # absent from the shell version; caches can hold anything
        ".claude",  # git-ignored agent handoff output; see below
    }
)

# Path prefixes skipped entirely, compared against canonical repo-relative paths.
#
# These are SCAN SCOPING rules and carry no exemption semantics. They decide what is
# searched, not what is forgiven. Conflating the two is what made the shell version's
# exclusion list read as a list of things that had been permitted, when it was really a
# list of places nobody had looked. The sanctioned exemption set is exactly one
# mechanism, the inline marker below.
EXCLUDED_PATH_PREFIXES: tuple[str, ...] = (
    "specs/archive/",
    "docs/archive/",
    "docs/archived-specs/",
    "specs/1217-web-framework-infra-purge/",
    ".specify/",
)

# Filename prefixes skipped. Widened from the shell version's "CONTEXT-CARRYOVER-*",
# which did not match "CONTEXT-CARRYOVER.md.loaded" (no dash). With this checker wired
# into a required CI job and failing closed, one such file containing a term would block
# every merge in the repository.
EXCLUDED_FILENAME_PREFIXES: tuple[str, ...] = ("CONTEXT-CARRYOVER",)

# Trees where an exemption marker is itself an error (FR-028).
#
# These hold code, and the adjudication rule exempts records that a framework was
# retired. No legitimate exemption can exist here, so refusing markers costs nothing and
# removes a bypass. Stated as explicit paths rather than as the phrase "application
# source" because that phrase is ambiguous at two boundaries: infrastructure/ contains a
# documentation subtree where a record could legitimately live, and frontend/ contains a
# test subtree that is not source.
MARKER_REFUSED_PREFIXES: tuple[str, ...] = ("src/", "infrastructure/", "frontend/src/")
MARKER_REFUSED_EXCEPTIONS: tuple[str, ...] = ("infrastructure/docs/",)

# THE SANCTIONED EXEMPTION SET IS EXACTLY ONE MECHANISM: the inline marker below.
#
# A path-scoped mechanism was considered and found unnecessary. The only occurrences that
# would have needed one were filename keys inside .secrets.baseline, a generated file.
# Renaming the four legacy-named directories and two files removed them at the source, so
# nothing survives that a path scope would have had to forgive. FR-017 forbids an
# exemption mechanism that requires editing generated files, and it is therefore satisfied
# by elimination rather than by construction. That is why no task implements it, and this
# note exists so the absence reads as deliberate rather than as an oversight.
#
# If a generated file ever comes to contain a legacy term in its CONTENT rather than in a
# path, this reasoning expires: FR-013 must be amended to re-add a path-scoped mechanism.
# Treat that as an amendment to the requirement, not as a gap in the implementation.
#
# Syntax-agnostic on purpose: the checker tests for this token as a substring and never
# parses comment syntax, so the same rule serves Markdown, HTML, Python, YAML, shell,
# TypeScript, and formats nobody has used yet.
#
# Named *_TOKEN, so two scanners read it as a credential: ruff's S105 and
# detect-secrets' Secret Keyword plugin. The two suppressions below cover ruff and
# detect-secrets.
#
# The pragma is deliberate in preference to a .secrets.baseline entry: the baseline is a
# register of audited secrets, and a misclassified marker token is not one.
MARKER_TOKEN = "legacy-term-ok:"  # noqa: S105  # pragma: allowlist secret

_TERM_PATTERNS = tuple((t, re.compile(t, re.IGNORECASE)) for t in BANNED_TERMS)
_MARKER_PATTERN = re.compile(re.escape(MARKER_TOKEN) + r"\s*(?P<why>.*)", re.IGNORECASE)


@dataclass(frozen=True)
class Match:
    """One occurrence of one term at one line.

    ``path`` and ``line_text`` are separate fields and never share a representation.
    That separation IS the fix for the content-matched-exclusion bug: the class of
    defect it eliminates is not "a filter was written wrong" but "a filter was applied
    to the wrong thing", and it cannot recur while these stay distinct.
    """

    path: str  # canonical: repo-relative, forward slashes, no leading "./"
    line_number: int  # 1-indexed
    term: str
    line_text: str

    @property
    def justification(self) -> str | None:
        """Exemption justification on this line, or None if absent or empty."""
        found = _MARKER_PATTERN.search(self.line_text)
        if not found:
            return None
        why = found.group("why").strip()
        # Comment syntax is not part of the justification. A terminator ENDS the
        # justification wherever it appears, so the earliest one wins and everything
        # after it is discarded.
        #
        # Two earlier shapes of this were both wrong. rstrip("-->") takes a character
        # SET, not a suffix, so it also ate a justification's own trailing hyphens and
        # angle brackets. Replacing it with an endswith() suffix strip fixed that but
        # only handled markers at end of line: inside a Markdown table cell the comment
        # is followed by " |", nothing is stripped, and the closing syntax lands in the
        # justification. Cutting at the terminator handles both without a special case.
        cut = min(
            (i for i in (why.find(t) for t in ("-->", "*/", "#}", "?>")) if i != -1),
            default=-1,
        )
        if cut != -1:
            why = why[:cut].strip()
        return why or None

    @property
    def has_marker(self) -> bool:
        return _MARKER_PATTERN.search(self.line_text) is not None

    @property
    def marker_is_refused(self) -> bool:
        """True when a marker sits in a tree where none can be legitimate (FR-028)."""
        if not self.has_marker:
            return False
        if any(self.path.startswith(p) for p in MARKER_REFUSED_EXCEPTIONS):
            return False
        return any(self.path.startswith(p) for p in MARKER_REFUSED_PREFIXES)

    @property
    def is_exempt(self) -> bool:
        return self.justification is not None and not self.marker_is_refused


def repo_root() -> Path:
    """Repository root, derived from this file's location, never from the caller's cwd."""
    return Path(__file__).resolve().parent.parent


def canonical(path: Path, root: Path) -> str:
    """Repo-relative, forward-slashed, no leading prefix.

    Every comparison in this module runs against this form. Nothing depends on how a
    path happened to be spelled by whatever produced it, which is what made the shell
    version's exclusions accidentally correct and one refactor away from silently
    disabling themselves.
    """
    return path.resolve().relative_to(root.resolve()).as_posix()


# This file enumerates the banned terms in order to search for them. A checker that
# reported its own term list would fail permanently and for no useful reason.
#
# A second entry listed the shell predecessor while both checkers coexisted on disk,
# between the Makefile repoint and the script's deletion. Without it the corpus could
# not reach zero, because the cleanup phase ran before the deletion phase. The script is
# gone now and the entry went with it: kept, it would be dead configuration implying a
# shell checker still exists.
CHECKER_SELF_PATHS: tuple[str, ...] = ("scripts/check_banned_terms.py",)


def _is_self(rel_path: str) -> bool:
    """These files enumerate the terms, so they must not report themselves."""
    return rel_path in CHECKER_SELF_PATHS


def _is_excluded(rel_path: str) -> bool:
    if _is_self(rel_path):
        return True
    if any(rel_path.startswith(p) for p in EXCLUDED_PATH_PREFIXES):
        return True
    name = rel_path.rsplit("/", 1)[-1]
    return any(name.startswith(p) for p in EXCLUDED_FILENAME_PREFIXES)


def _validate_config() -> list[str]:
    """Reasons the configuration is unusable. Empty list means usable.

    FR-009: the checker must fail closed. An empty term list cannot detect anything,
    which is not the same as finding nothing, and reporting success would be the most
    dangerous possible direction to fail in.
    """
    problems = []
    if not BANNED_TERMS:
        problems.append("the term list is empty")
    if not MARKER_TOKEN:
        problems.append("the exemption marker token is empty")
    return problems


def iter_files(root: Path):
    """Yield canonical paths of scannable files under root."""
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if any(
            part in EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts[:-1]
        ):
            continue
        rel = canonical(path, root)
        if _is_excluded(rel):
            continue
        yield path, rel


def scan(root: Path) -> list[Match]:
    """Every match in the tree, in one pass. Never stops at the first (FR-012)."""
    matches: list[Match] = []
    for path, rel in iter_files(root):
        try:
            text = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            # Binary, undecodable, or unreadable. The repository contains a SQLite
            # coverage database and editor swap files; an unguarded text read raises on
            # the first one, and a crash in a fail-closed required job is a
            # repository-wide merge outage.
            continue
        if "\x00" in text:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for term, pattern in _TERM_PATTERNS:
                if pattern.search(line):
                    matches.append(Match(rel, lineno, term, line))
    return matches


def _remedy(match: Match) -> str:
    if match.marker_is_refused:
        return (
            f"    ERROR: exemption markers are not permitted under {match.path.split('/')[0]}/.\n"
            "    remedy: remove the reference. Exemptions record that a framework was\n"
            "            retired; this tree holds code, not records, so no exemption\n"
            "            applies here. See FR-028."
        )
    if any(match.path.startswith(p) for p in MARKER_REFUSED_PREFIXES):
        return (
            "    remedy: this is application source. Remove the reference. Exemptions are\n"
            "            for records that the framework was retired, not for code that uses it."
        )
    if match.has_marker:
        return (
            "    remedy: the exemption marker carries no justification. Add one after the\n"
            "            colon; an unexplained exemption is not sanctioned."
        )
    return (
        "    remedy: if this records the retirement, append an exemption marker with a\n"
        "            justification on the same line, for example:\n"
        f"              <!-- {MARKER_TOKEN} records the pre-migration runtime -->\n"
        "            If it asserts the framework is current, correct it instead.\n"
        "            See specs/001-validate-gate-repair/quickstart.md"
    )


def report(matches: list[Match], scanned: int, root: Path) -> int:
    violations = [m for m in matches if not m.is_exempt]
    exempt = [m for m in matches if m.is_exempt]

    # Markers, not matches: one line can hold several terms under one justification.
    markers = {(m.path, m.line_number) for m in exempt}

    print("=== Legacy-Term Scanner ===")
    print(f"Scanned: {scanned:,} files under {root}")
    print(
        f"Exemptions honoured: {len(markers)} inline "
        f"covering {len(exempt)} occurrence(s)"
    )
    print()

    if not violations:
        print("PASS: 0 unexempted occurrences.")
        return 0

    print(f"FAIL: {len(violations)} unexempted occurrences.")
    print()
    for m in violations:
        print(f"  {m.path}:{m.line_number}")
        print(f"    matched: {m.term}")
        print(f"    | {m.line_text.strip()[:120]}")
        print(_remedy(m))
        print()
    return 1


def list_exemptions(matches: list[Match]) -> int:
    """FR-026: every exemption enumerable by one command.

    Only inline markers appear. The sanctioned set has one member, so this listing is
    complete by construction. Scan-scope exclusions are deliberately absent: they decide
    what is searched, not what is forgiven.

    The unit is the MARKER, not the match. One line can contain several banned terms and
    so produce several Match objects, but it carries one marker and one justification.
    Counting matches would report a line twice for saying two words, and that count is
    the SC-012 exemption baseline, so the inflation would be recorded as growth in the
    exemption surface when nothing had been exempted.
    """
    by_marker = {
        (m.path, m.line_number): m.justification for m in matches if m.is_exempt
    }
    print("=== Legacy-Term Exemptions ===")
    print()
    print(f"inline ({len(by_marker)}):")
    for (path, line), why in sorted(by_marker.items()):
        print(f"  {path}:{line}  {why}")
    print()
    print(f"Total: {len(by_marker)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--list-exemptions",
        action="store_true",
        help="enumerate every exemption and exit 0 (FR-026)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="scan root override; exists so tests can scan a fixture tree, and so "
        "FR-027 (behaviour independent of root spelling) can be tested rather than asserted",
    )
    args = parser.parse_args(argv)

    problems = _validate_config()
    if problems:
        print("=== Legacy-Term Scanner ===")
        print()
        print("FAIL: configuration is unusable, refusing to report success.")
        for p in problems:
            print(f"  cause: {p}")
        print("  remedy: scripts/check_banned_terms.py defines the authoritative term")
        print("          list. An empty list means the scanner cannot detect anything,")
        print("          which is not the same as finding nothing.")
        return 1

    root = (args.root or repo_root()).resolve()
    if not root.is_dir():
        print(f"FAIL: scan root does not exist: {root}")
        return 1

    matches = scan(root)
    if args.list_exemptions:
        return list_exemptions(matches)

    scanned = sum(1 for _ in iter_files(root))
    return report(matches, scanned, root)


if __name__ == "__main__":
    sys.exit(main())
