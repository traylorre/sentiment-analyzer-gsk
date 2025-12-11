"""SRI (Subresource Integrity) Validator.

Detects CDN scripts and stylesheets missing integrity attributes.

Feature: 090-security-first-burndown
Canonical Sources:
- https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity
- https://owasp.org/www-community/controls/SubresourceIntegrity
- https://w3c.github.io/webappsec-subresource-integrity/
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SRISeverity(Enum):
    """Severity levels for SRI findings."""

    CRITICAL = "critical"  # CDN script without SRI (executable code)
    HIGH = "high"  # CDN stylesheet without SRI
    MEDIUM = "medium"  # CDN resource without crossorigin
    INFO = "info"  # Local resource (no SRI needed)


@dataclass
class SRIFinding:
    """A finding from SRI validation."""

    file_path: str
    line_number: int
    resource_type: str  # 'script' or 'link'
    url: str
    severity: SRISeverity
    message: str
    has_integrity: bool = False
    has_crossorigin: bool = False


@dataclass
class SRIValidationResult:
    """Result of SRI validation across all files."""

    findings: list[SRIFinding] = field(default_factory=list)
    files_scanned: int = 0
    cdn_resources_found: int = 0
    cdn_resources_with_sri: int = 0

    @property
    def pass_rate(self) -> float:
        """Percentage of CDN resources with SRI."""
        if self.cdn_resources_found == 0:
            return 1.0
        return self.cdn_resources_with_sri / self.cdn_resources_found

    @property
    def is_passing(self) -> bool:
        """Check if validation passed (no critical/high findings)."""
        return not any(
            f.severity in (SRISeverity.CRITICAL, SRISeverity.HIGH)
            for f in self.findings
        )


# CDN domains that should have SRI
CDN_DOMAINS = [
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "unpkg.com",
    "ajax.googleapis.com",
    "stackpath.bootstrapcdn.com",
    "cdn.tailwindcss.com",  # Note: JIT compiler, SRI not applicable
    "fonts.googleapis.com",
]

# JIT compilers that generate dynamic content (SRI not applicable)
JIT_CDNS = [
    "cdn.tailwindcss.com",
]

# Default exclusion patterns
DEFAULT_EXCLUDES = [
    "node_modules/",
    "tests/fixtures/",
    ".git/",
    "vendor/",
]

# Regex patterns for detecting script and link tags
SCRIPT_TAG_PATTERN = re.compile(
    r'<script[^>]+src=["\']([^"\']+)["\']([^>]*)>', re.IGNORECASE
)
LINK_TAG_PATTERN = re.compile(
    r'<link[^>]+href=["\']([^"\']+)["\']([^>]*)>', re.IGNORECASE
)
INTEGRITY_ATTR_PATTERN = re.compile(r'integrity=["\']([^"\']+)["\']', re.IGNORECASE)
CROSSORIGIN_ATTR_PATTERN = re.compile(
    r'crossorigin=["\']?([^"\'\s>]*)["\']?', re.IGNORECASE
)


def is_cdn_url(url: str) -> bool:
    """Check if URL is from a known CDN domain."""
    return any(domain in url for domain in CDN_DOMAINS)


def is_jit_cdn(url: str) -> bool:
    """Check if URL is from a JIT compiler CDN (SRI not applicable)."""
    return any(domain in url for domain in JIT_CDNS)


def should_exclude(file_path: Path, excludes: list[str]) -> bool:
    """Check if file should be excluded from scanning."""
    path_str = str(file_path)
    return any(exclude in path_str for exclude in excludes)


def validate_html_file(file_path: Path) -> list[SRIFinding]:
    """Validate a single HTML file for SRI compliance."""
    findings = []
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    for line_num, line in enumerate(lines, start=1):
        # Check script tags
        for match in SCRIPT_TAG_PATTERN.finditer(line):
            url = match.group(1)
            attrs = match.group(2)

            if not is_cdn_url(url):
                continue

            has_integrity = bool(INTEGRITY_ATTR_PATTERN.search(attrs))
            has_crossorigin = bool(CROSSORIGIN_ATTR_PATTERN.search(attrs))

            if is_jit_cdn(url):
                # JIT CDN - SRI not applicable, but note it
                findings.append(
                    SRIFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        resource_type="script",
                        url=url,
                        severity=SRISeverity.INFO,
                        message=f"JIT compiler CDN (SRI not applicable): {url}",
                        has_integrity=has_integrity,
                        has_crossorigin=has_crossorigin,
                    )
                )
            elif not has_integrity:
                findings.append(
                    SRIFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        resource_type="script",
                        url=url,
                        severity=SRISeverity.CRITICAL,
                        message=f"CDN script missing integrity attribute: {url}",
                        has_integrity=has_integrity,
                        has_crossorigin=has_crossorigin,
                    )
                )
            elif not has_crossorigin:
                findings.append(
                    SRIFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        resource_type="script",
                        url=url,
                        severity=SRISeverity.MEDIUM,
                        message=f"CDN script missing crossorigin attribute: {url}",
                        has_integrity=has_integrity,
                        has_crossorigin=has_crossorigin,
                    )
                )

        # Check link tags (stylesheets)
        for match in LINK_TAG_PATTERN.finditer(line):
            url = match.group(1)
            attrs = match.group(2)

            if not is_cdn_url(url):
                continue

            # Only check stylesheets
            if 'rel="stylesheet"' not in line and "rel='stylesheet'" not in line:
                continue

            has_integrity = bool(INTEGRITY_ATTR_PATTERN.search(attrs))
            has_crossorigin = bool(CROSSORIGIN_ATTR_PATTERN.search(attrs))

            if not has_integrity:
                findings.append(
                    SRIFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        resource_type="link",
                        url=url,
                        severity=SRISeverity.HIGH,
                        message=f"CDN stylesheet missing integrity attribute: {url}",
                        has_integrity=has_integrity,
                        has_crossorigin=has_crossorigin,
                    )
                )
            elif not has_crossorigin:
                findings.append(
                    SRIFinding(
                        file_path=str(file_path),
                        line_number=line_num,
                        resource_type="link",
                        url=url,
                        severity=SRISeverity.MEDIUM,
                        message=f"CDN stylesheet missing crossorigin attribute: {url}",
                        has_integrity=has_integrity,
                        has_crossorigin=has_crossorigin,
                    )
                )

    return findings


def validate_sri(
    root_path: Path | str,
    excludes: list[str] | None = None,
) -> SRIValidationResult:
    """Validate SRI compliance for all HTML files in a directory.

    Args:
        root_path: Root directory to scan
        excludes: List of path patterns to exclude

    Returns:
        SRIValidationResult with findings and statistics
    """
    root = Path(root_path)
    excludes = excludes or DEFAULT_EXCLUDES

    result = SRIValidationResult()

    for html_file in root.rglob("*.html"):
        if should_exclude(html_file, excludes):
            continue

        result.files_scanned += 1
        findings = validate_html_file(html_file)
        result.findings.extend(findings)

        # Update statistics
        for finding in findings:
            if finding.severity != SRISeverity.INFO:  # Don't count JIT CDNs
                result.cdn_resources_found += 1
                if finding.has_integrity:
                    result.cdn_resources_with_sri += 1

    return result


def format_findings(result: SRIValidationResult) -> str:
    """Format findings as human-readable output."""
    lines = [
        "SRI Validation Report",
        "=" * 50,
        f"Files scanned: {result.files_scanned}",
        f"CDN resources found: {result.cdn_resources_found}",
        f"CDN resources with SRI: {result.cdn_resources_with_sri}",
        f"Pass rate: {result.pass_rate:.1%}",
        "",
    ]

    if result.is_passing:
        lines.append("PASSED: No critical or high severity findings")
    else:
        lines.append("FAILED: Critical or high severity findings detected")

    if result.findings:
        lines.append("")
        lines.append("Findings:")
        lines.append("-" * 50)

        for finding in sorted(result.findings, key=lambda f: f.severity.value):
            lines.append(
                f"[{finding.severity.value.upper()}] {finding.file_path}:{finding.line_number}"
            )
            lines.append(f"  {finding.message}")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    result = validate_sri(path)
    print(format_findings(result))
    sys.exit(0 if result.is_passing else 1)
