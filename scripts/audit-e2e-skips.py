#!/usr/bin/env python3
"""Audit E2E test skips and classify them by risk level.

Usage:
    python scripts/audit-e2e-skips.py [--json] [--critical-only]

Output:
    Categorized list of all pytest.skip() calls in E2E tests with risk levels.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SkipCategory(Enum):
    """Skip categories ordered by risk level."""

    ERROR_500_MASKING = "500_masking"  # CRITICAL - masks server failures
    NOT_IMPLEMENTED = "not_implemented"  # HIGH - missing functionality
    CONFIG_UNAVAILABLE = "config_unavailable"  # HIGH - infrastructure issues
    RATE_LIMIT = "rate_limit"  # MEDIUM - environment-specific
    SYNTHETIC = "synthetic"  # MEDIUM - test infrastructure
    ENVIRONMENT = "environment"  # LOW - legitimate constraints
    OTHER = "other"  # VARIES


RISK_LEVELS = {
    SkipCategory.ERROR_500_MASKING: "CRITICAL",
    SkipCategory.NOT_IMPLEMENTED: "HIGH",
    SkipCategory.CONFIG_UNAVAILABLE: "HIGH",
    SkipCategory.RATE_LIMIT: "MEDIUM",
    SkipCategory.SYNTHETIC: "MEDIUM",
    SkipCategory.ENVIRONMENT: "LOW",
    SkipCategory.OTHER: "VARIES",
}


@dataclass
class SkipEntry:
    """A single pytest.skip() occurrence."""

    file: str
    line: int
    category: SkipCategory
    message: str
    context: str = ""  # Code around the skip
    has_500_check: bool = False  # True if preceded by status_code == 500

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "category": self.category.value,
            "risk": RISK_LEVELS[self.category],
            "message": self.message,
            "has_500_check": self.has_500_check,
        }


@dataclass
class AuditReport:
    """Complete audit report."""

    entries: list[SkipEntry] = field(default_factory=list)

    def by_category(self) -> dict[SkipCategory, list[SkipEntry]]:
        result: dict[SkipCategory, list[SkipEntry]] = {cat: [] for cat in SkipCategory}
        for entry in self.entries:
            result[entry.category].append(entry)
        return result

    def summary(self) -> dict[str, int]:
        by_cat = self.by_category()
        return {cat.value: len(entries) for cat, entries in by_cat.items()}

    def critical_count(self) -> int:
        return len([e for e in self.entries if RISK_LEVELS[e.category] == "CRITICAL"])

    def high_count(self) -> int:
        return len([e for e in self.entries if RISK_LEVELS[e.category] == "HIGH"])


def classify_skip(message: str, context: str) -> tuple[SkipCategory, bool]:
    """Classify a skip based on its message and surrounding context."""
    message_lower = message.lower()

    # Check for 500 error masking (CRITICAL)
    has_500_check = "status_code == 500" in context or ".status_code == 500" in context
    if has_500_check or "500" in message_lower:
        return SkipCategory.ERROR_500_MASKING, has_500_check

    # Check for "not implemented" patterns (HIGH)
    not_impl_patterns = [
        "not implemented",
        "not available",
        "endpoint not",
        "not supported",
    ]
    if any(p in message_lower for p in not_impl_patterns):
        if "config" in message_lower:
            return SkipCategory.CONFIG_UNAVAILABLE, False
        return SkipCategory.NOT_IMPLEMENTED, False

    # Check for config unavailable (HIGH)
    if "config" in message_lower and (
        "unavailable" in message_lower
        or "not available" in message_lower
        or "creation" in message_lower
    ):
        return SkipCategory.CONFIG_UNAVAILABLE, False

    # Check for rate limit (MEDIUM)
    if "rate limit" in message_lower or "rate-limit" in message_lower:
        return SkipCategory.RATE_LIMIT, False

    # Check for synthetic/token (MEDIUM)
    if "synthetic" in message_lower or "token" in message_lower:
        return SkipCategory.SYNTHETIC, False

    # Check for environment constraints (LOW)
    env_patterns = [
        "preprod",
        "environment",
        "env",
        "not set",
        "manual test",
        "requires",
    ]
    if any(p in message_lower for p in env_patterns):
        return SkipCategory.ENVIRONMENT, False

    return SkipCategory.OTHER, False


def extract_skip_message(line: str) -> str:
    """Extract the message from a pytest.skip() call."""
    # Match pytest.skip("message") or pytest.skip(f"message")
    match = re.search(r'pytest\.skip\([f]?["\'](.+?)["\']', line)
    if match:
        return match.group(1)

    # Multi-line skip - just get what we can
    match = re.search(r'pytest\.skip\([f]?["\'](.+)', line)
    if match:
        return match.group(1).rstrip("\"')")

    return "<message not extracted>"


def audit_file(filepath: Path) -> list[SkipEntry]:
    """Audit a single file for pytest.skip() calls."""
    entries = []
    content = filepath.read_text()
    lines = content.split("\n")

    for i, line in enumerate(lines):
        if "pytest.skip(" in line:
            # Get context (5 lines before)
            start = max(0, i - 5)
            context = "\n".join(lines[start:i])

            message = extract_skip_message(line)
            category, has_500 = classify_skip(message, context)

            entries.append(
                SkipEntry(
                    file=str(filepath),
                    line=i + 1,
                    category=category,
                    message=message,
                    context=context,
                    has_500_check=has_500,
                )
            )

    return entries


def audit_e2e_tests(e2e_path: Path) -> AuditReport:
    """Audit all E2E test files."""
    report = AuditReport()

    for filepath in e2e_path.rglob("*.py"):
        if filepath.name.startswith("__"):
            continue
        entries = audit_file(filepath)
        report.entries.extend(entries)

    return report


def print_report(report: AuditReport, critical_only: bool = False) -> None:
    """Print human-readable report."""
    by_cat = report.by_category()

    print("=" * 70)
    print("E2E TEST SKIP AUDIT REPORT")
    print("=" * 70)
    print()

    # Summary
    print("SUMMARY")
    print("-" * 40)
    total = len(report.entries)
    print(f"Total skips: {total}")
    print(f"Critical (500 masking): {report.critical_count()}")
    print(f"High risk: {report.high_count()}")
    print()

    # By category
    categories_to_show = (
        [SkipCategory.ERROR_500_MASKING] if critical_only else list(SkipCategory)
    )

    for category in categories_to_show:
        entries = by_cat[category]
        if not entries:
            continue

        risk = RISK_LEVELS[category]
        print(f"\n{category.value.upper()} [{risk}] - {len(entries)} occurrences")
        print("-" * 60)

        for entry in entries:
            rel_path = entry.file.replace(str(Path.cwd()) + "/", "")
            flag = " [HAS 500 CHECK]" if entry.has_500_check else ""
            print(f"  {rel_path}:{entry.line}{flag}")
            print(f"    Message: {entry.message[:70]}...")
            print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit E2E test skips")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--critical-only", action="store_true", help="Show only critical issues"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("tests/e2e"),
        help="Path to E2E tests",
    )
    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: {args.path} does not exist", file=sys.stderr)
        return 1

    report = audit_e2e_tests(args.path)

    if args.json:
        output = {
            "summary": report.summary(),
            "critical_count": report.critical_count(),
            "high_count": report.high_count(),
            "total": len(report.entries),
            "entries": [e.to_dict() for e in report.entries],
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(report, args.critical_only)

    # Exit with error if critical issues found
    if report.critical_count() > 0:
        print(
            f"\nERROR: {report.critical_count()} CRITICAL issues found!",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
