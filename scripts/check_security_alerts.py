#!/usr/bin/env python3
"""Report every open security alert on the repository, or refuse to give a verdict.

    python3 scripts/check_security_alerts.py                 # query both alert families
    python3 scripts/check_security_alerts.py --print-corpus  # live corpus sizes, to revise floors
    python3 scripts/check_security_alerts.py --scan-copies   # report restated alert queries

This file is the one place the alert-list queries live. Prose names
``make check-security-alerts``; ``--scan-copies`` reports any document that restates a query.

EXIT CODES
----------
0  CLEAN                every family read, anchored, and holds no open alert
1  FINDINGS             every family read and anchored, and at least one alert is open
2  COULD-NOT-DETERMINE  some family could not be read or failed an anchor

COULD-NOT-DETERMINE outranks FINDINGS: a run that cannot see one family says so even when the
other family has open alerts.

WHY THE ANCHORS
---------------
An empty result is what a correct query over a clean repository prints, and also what a query
prints when it read one page, read the wrong field, or reached the wrong endpoint. Every pass
condition here is therefore paired with a positive assertion that the channel carrying it is live:

- corpus floor: the all-states record count is at least the recorded floor;
- vocabulary anchor: every record's state is one the family is known to use;
- field anchors: every path the report reads resolves on every record, read through the same
  ``dig`` call the report uses, so a mistyped path fails here instead of printing blanks.

REVISING A FLOOR
----------------
Floors are the all-states corpus sizes at the last revision. Corpora grow as alerts are created;
alerts change state and are not deleted. A floor failure therefore means a fetch that stopped early,
unless the corpus was genuinely reset (an analysis deleted, the repository transferred). Confirm
which with ``--print-corpus`` and a hand-run ``gh api --paginate --slurp`` reference count, then
set the floor to the measured size.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SANCTIONED = "scripts/check_security_alerts.py"
DEFAULT_REPO = "traylorre/sentiment-analyzer-gsk"
GH_TIMEOUT_SECONDS = 180

CLEAN, FINDINGS, UNDETERMINED = 0, 1, 2
VERDICT_NAMES = {
    CLEAN: "CLEAN",
    FINDINGS: "FINDINGS",
    UNDETERMINED: "COULD-NOT-DETERMINE",
}

# Copies under these prefixes are dated records (specs/, docs/archive/) or board files (cards/).
COPY_SCAN_EXCLUDED = ("specs/", "cards/", "docs/archive/")


@dataclass(frozen=True)
class Family:
    name: str
    endpoint: str
    states: frozenset[str]
    floor: int
    # (label, path) pairs. "state" is required; every other label is printed per open alert.
    fields: tuple[tuple[str, tuple[str, ...]], ...]

    def path(self, label: str) -> tuple[str, ...]:
        return dict(self.fields)[label]


FAMILIES: tuple[Family, ...] = (
    Family(
        name="code scanning",
        endpoint="code-scanning/alerts",
        states=frozenset({"open", "dismissed", "fixed"}),
        floor=156,
        fields=(
            ("number", ("number",)),
            ("state", ("state",)),
            ("rule", ("rule", "id")),
            ("path", ("most_recent_instance", "location", "path")),
        ),
    ),
    Family(
        name="dependabot",
        endpoint="dependabot/alerts",
        states=frozenset({"open", "dismissed", "fixed", "auto_dismissed"}),
        floor=208,
        fields=(
            ("number", ("number",)),
            ("state", ("state",)),
            ("severity", ("security_advisory", "severity")),
            ("ecosystem", ("dependency", "package", "ecosystem")),
            ("package", ("dependency", "package", "name")),
            ("manifest", ("dependency", "manifest_path")),
            ("advisory", ("security_advisory", "ghsa_id")),
        ),
    ),
)


class Undetermined(Exception):
    """A family whose alerts could not be read; the message says why."""


def dig(record: object, path: tuple[str, ...]) -> object:
    value = record
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def usable(value: object) -> bool:
    return value is not None and value != ""


def gh_command(repo: str, family: Family) -> list[str]:
    # gh resolves through the caller's PATH: its install location differs per machine.
    return [
        "gh",
        "api",
        "--paginate",
        "--slurp",
        f"repos/{repo}/{family.endpoint}?per_page=100",
    ]


def fetch(repo: str, family: Family) -> list[dict]:
    """Every record of the family across all pages, or Undetermined."""
    command = gh_command(repo, family)
    try:
        proc = subprocess.run(  # noqa: S603 - argv built from FAMILIES and a validated repo
            command,
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        raise Undetermined("gh is not installed or not on PATH") from None
    except subprocess.TimeoutExpired:
        raise Undetermined(f"gh did not finish within {GH_TIMEOUT_SECONDS}s") from None
    if proc.returncode != 0:
        detail = (proc.stderr.strip().splitlines() or ["no stderr"])[0]
        raise Undetermined(f"gh exited {proc.returncode}: {detail}")
    try:
        pages = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise Undetermined(f"gh output is not JSON: {exc}") from None
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        raise Undetermined("gh output is not a list of pages (was --slurp dropped?)")
    records = [record for page in pages for record in page]
    if not all(isinstance(record, dict) for record in records):
        raise Undetermined("a page holds something other than alert objects")
    return records


@dataclass
class FamilyResult:
    family: Family
    examined: int = 0
    problems: list[str] = field(default_factory=list)
    states: Counter = field(default_factory=Counter)
    open_alerts: list[dict] = field(default_factory=list)

    @property
    def verdict(self) -> int:
        if self.problems:
            return UNDETERMINED
        return FINDINGS if self.open_alerts else CLEAN


def evaluate(family: Family, records: list[dict]) -> FamilyResult:
    """Apply the floor and every anchor, then collect the open alerts."""
    result = FamilyResult(family, examined=len(records))
    total = len(records)
    if total < family.floor:
        result.problems.append(
            f"corpus floor: fetched {total} records, floor is {family.floor} "
            "(a fetch that stopped early, or a reset corpus; see REVISING A FLOOR)"
        )

    state_path = family.path("state")
    states = [dig(record, state_path) for record in records]
    result.states = Counter(str(state) for state in states)
    unknown = Counter(repr(state) for state in states if state not in family.states)
    if unknown:
        seen = ", ".join(f"{value} x{count}" for value, count in unknown.most_common(5))
        result.problems.append(
            f"vocabulary anchor: {sum(unknown.values())} of {total} records carry a state "
            f"outside {sorted(family.states)} at {'.'.join(state_path)}: {seen}"
        )

    for label, path in family.fields:
        resolved = sum(1 for record in records if usable(dig(record, path)))
        if resolved != total:
            result.problems.append(
                f"field anchor '{label}': {'.'.join(path)} resolves on {resolved} of {total} records"
            )

    result.open_alerts = [r for r in records if dig(r, state_path) == "open"]
    return result


def alert_line(family: Family, record: dict) -> str:
    cells = [
        str(dig(record, path)) for label, path in family.fields if label != "state"
    ]
    cells[0] = f"#{cells[0]}"
    return "  " + "  ".join(cells)


def report(result: FamilyResult) -> list[str]:
    family = result.family
    name = VERDICT_NAMES[result.verdict]
    if result.verdict == UNDETERMINED:
        lines = [f"{family.name}: {name}"]
        lines += [f"  - {problem}" for problem in result.problems]
        return lines
    states = ", ".join(
        f"{state} {count}" for state, count in sorted(result.states.items())
    )
    labels = ", ".join(label for label, _ in family.fields)
    lines = [
        f"{family.name}: {name}  {len(result.open_alerts)} open of {result.examined} records "
        f"examined (floor {family.floor}); states [{states}]; "
        f"fields {labels} resolve on {result.examined}/{result.examined}"
    ]
    lines += [alert_line(family, record) for record in result.open_alerts]
    return lines


def check(repo: str, families: tuple[Family, ...] = FAMILIES) -> tuple[int, list[str]]:
    results = []
    for family in families:
        try:
            records = fetch(repo, family)
        except Undetermined as exc:
            results.append(FamilyResult(family, problems=[str(exc)]))
            continue
        results.append(evaluate(family, records))

    lines = [f"repository: {repo}"]
    for result in results:
        lines += report(result)
    verdict = max(result.verdict for result in results)
    examined = sum(result.examined for result in results)
    opened = sum(len(result.open_alerts) for result in results)
    if verdict == UNDETERMINED:
        tail = (
            "a family could not be read or failed an anchor; this is not a clean result"
        )
    elif verdict == FINDINGS:
        tail = f"{opened} open alerts across {len(results)} families"
    else:
        tail = f"no open alerts; {examined} records examined across {len(results)} families"
    lines.append(f"VERDICT: {VERDICT_NAMES[verdict]} (exit {verdict}): {tail}")
    return verdict, lines


def print_corpus(repo: str) -> tuple[int, list[str]]:
    lines, verdict = [f"repository: {repo}"], CLEAN
    for family in FAMILIES:
        try:
            size = len(fetch(repo, family))
        except Undetermined as exc:
            lines.append(f"{family.name}: COULD-NOT-DETERMINE: {exc}")
            verdict = UNDETERMINED
            continue
        lines.append(
            f"{family.name}: {size} records, all states (floor {family.floor})"
        )
    return verdict, lines


def copy_pattern(families: tuple[Family, ...] = FAMILIES) -> re.Pattern[str]:
    """Alert-list endpoints, excluding single-alert paths such as ``.../alerts/144``."""
    endpoints = "|".join(re.escape(family.endpoint) for family in families)
    return re.compile(rf"(?:{endpoints})(?![\w/-])")


def tracked_files(root: Path) -> list[str]:
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv
            ["git", "-C", str(root), "ls-files", "-z"],  # noqa: S607 - git from the caller's PATH
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise Undetermined("git is not installed or not on PATH") from None
    if proc.returncode != 0:
        detail = (proc.stderr.strip().splitlines() or ["no stderr"])[0]
        raise Undetermined(f"git ls-files exited {proc.returncode}: {detail}")
    return [name for name in proc.stdout.split("\0") if name]


def scan_copies(root: Path, paths: list[str]) -> tuple[int, list[str]]:
    """Report every restated alert-list query outside the sanctioned location."""
    pattern = copy_pattern()
    findings, problems = [], []
    scanned = skipped = 0
    anchored: set[str] = set()
    sanctioned_seen = False
    for rel in sorted(paths):
        if rel.startswith(COPY_SCAN_EXCLUDED):
            continue
        path = root / rel
        if path.is_symlink():
            skipped += 1
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            problems.append(f"cannot read {rel}: {exc.strerror or exc}")
            continue
        if b"\0" in data:
            skipped += 1
            continue
        scanned += 1
        text = data.decode("utf-8", errors="replace")
        if rel == SANCTIONED:
            sanctioned_seen = True
            anchored = {match.group(0) for match in pattern.finditer(text)}
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                findings.append(f"{rel}:{number}: {line.strip()[:160]}")

    expected = {family.endpoint for family in FAMILIES}
    if not sanctioned_seen:
        problems.append(
            f"sanctioned location {SANCTIONED} was not among the scanned files"
        )
    elif anchored != expected:
        missing = ", ".join(sorted(expected - anchored))
        problems.append(f"the pattern does not find {missing} in {SANCTIONED}")

    lines = [
        f"copy scan: {scanned} files scanned, {skipped} skipped (binary or symlink)"
    ]
    lines += [f"  {finding}" for finding in findings]
    if problems:
        lines += [f"  - {problem}" for problem in problems]
        lines.append(
            f"VERDICT: {VERDICT_NAMES[UNDETERMINED]} (exit {UNDETERMINED}): "
            "the scan could not see what it must see; this is not a clean result"
        )
        return UNDETERMINED, lines
    lines.append(f"anchored on {SANCTIONED}: {', '.join(sorted(anchored))}")
    if findings:
        lines.append(
            f"VERDICT: {VERDICT_NAMES[FINDINGS]} (exit {FINDINGS}): {len(findings)} restated "
            "alert-list queries; name `make check-security-alerts` instead"
        )
        return FINDINGS, lines
    lines.append(
        f"VERDICT: {VERDICT_NAMES[CLEAN]} (exit {CLEAN}): no restated alert-list query"
    )
    return CLEAN, lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--print-corpus", action="store_true", help="print live corpus sizes"
    )
    mode.add_argument(
        "--scan-copies", action="store_true", help="report restated alert queries"
    )
    parser.add_argument(
        "--repo", default=DEFAULT_REPO, help="owner/name (default %(default)s)"
    )
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="tree for --scan-copies"
    )
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
        parser.error(f"--repo must be owner/name, got {args.repo!r}")

    if args.scan_copies:
        try:
            verdict, lines = scan_copies(args.root, tracked_files(args.root))
        except Undetermined as exc:
            verdict = UNDETERMINED
            lines = [
                f"copy scan: {exc}",
                f"VERDICT: {VERDICT_NAMES[UNDETERMINED]} (exit 2)",
            ]
    elif args.print_corpus:
        verdict, lines = print_corpus(args.repo)
    else:
        verdict, lines = check(args.repo)
    print("\n".join(lines))
    return verdict


if __name__ == "__main__":
    sys.exit(main())
