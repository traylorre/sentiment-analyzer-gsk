#!/usr/bin/env python3
"""Generate mermaid.live URLs from .mmd diagram files.

This script provides a reproducible way to generate mermaid.live URLs
with consistent dark theme settings. The theme is embedded in the pako
payload to ensure diagrams render correctly regardless of mermaid.live
default settings.

Usage:
    python scripts/regenerate-mermaid-url.py docs/diagrams/architecture.mmd
    python scripts/regenerate-mermaid-url.py --validate-only docs/diagrams/architecture.mmd

The generated URL can be used directly in README badges:
    [![View Diagram](https://img.shields.io/badge/...)](GENERATED_URL)
"""

import argparse
import base64
import json
import re
import sys
import zlib
from pathlib import Path


def validate_mermaid_syntax(code: str) -> list[str]:
    """Validate mermaid diagram syntax for common issues.

    Args:
        code: The mermaid diagram code to validate.

    Returns:
        List of error messages. Empty list means validation passed.
    """
    errors = []

    if not code.strip():
        errors.append("Empty diagram code")
        return errors

    # Check for diagram type declaration
    diagram_types = [
        "flowchart",
        "graph",
        "sequenceDiagram",
        "classDiagram",
        "stateDiagram",
        "erDiagram",
        "gantt",
        "pie",
        "journey",
        "gitGraph",
        "mindmap",
        "timeline",
        "quadrantChart",
        "sankey",
    ]
    has_diagram_type = any(dt in code for dt in diagram_types)
    if not has_diagram_type:
        errors.append(
            f"Missing diagram type declaration. Expected one of: {', '.join(diagram_types[:5])}..."
        )

    # Check for balanced brackets
    if code.count("[") != code.count("]"):
        errors.append(
            f"Unbalanced square brackets: {code.count('[')} opening, {code.count(']')} closing"
        )

    if code.count("{") != code.count("}"):
        errors.append(
            f"Unbalanced curly brackets: {code.count('{')} opening, {code.count('}')} closing"
        )

    if code.count("(") != code.count(")"):
        errors.append(
            f"Unbalanced parentheses: {code.count('(')} opening, {code.count(')')} closing"
        )

    # Check for common Mermaid syntax errors (not HTML filtering)
    # CodeQL py/bad-tag-filter: False positive - validates Mermaid arrow syntax, not HTML
    if re.search(r"-->\s*$", code, re.MULTILINE):  # lgtm[py/bad-tag-filter]
        errors.append("Arrow without target node (line ends with -->)")

    if re.search(r"==>\s*$", code, re.MULTILINE):
        errors.append("Thick arrow without target node (line ends with ==>)")

    return errors


def generate_mermaid_url(diagram_code: str) -> str:
    """Generate a mermaid.live view URL from diagram code.

    The URL embeds the diagram with dark theme settings in a pako-compressed
    JSON payload. This ensures the diagram renders with the correct theme
    regardless of mermaid.live's default settings.

    Args:
        diagram_code: The mermaid diagram code.

    Returns:
        A mermaid.live URL that can be used directly in browser.
    """
    # Build the payload with dark theme settings and viewport reset
    # pan/zoom/rough params ensure diagram starts centered instead of
    # inheriting previous viewport state from localStorage
    payload = {
        "code": diagram_code,
        "mermaid": {
            "theme": "dark",
            "themeVariables": {
                "primaryColor": "#4A90A4",
                "secondaryColor": "#F5A623",
                "tertiaryColor": "#2d2d2d",
                "lineColor": "#88CCFF",
                "primaryTextColor": "#FFFFFF",
                "nodeTextColor": "#FFFFFF",
            },
        },
        "autoSync": True,
        "updateDiagram": True,
        "pan": {"x": 0, "y": 0},
        "zoom": 1,
        "rough": False,
    }

    # Serialize to JSON
    json_str = json.dumps(payload, separators=(",", ":"))

    # Compress with zlib (pako-compatible)
    compressed = zlib.compress(json_str.encode("utf-8"), 9)

    # Encode as base64url (no padding)
    encoded = base64.urlsafe_b64encode(compressed).decode("utf-8").rstrip("=")

    return f"https://mermaid.live/view#pako:{encoded}"


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate mermaid.live URL from .mmd diagram file",
        epilog="Example: python scripts/regenerate-mermaid-url.py docs/diagrams/architecture.mmd",
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to .mmd diagram file",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate syntax, don't generate URL",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only output the URL (or errors), no status messages",
    )
    args = parser.parse_args()

    # Check file exists
    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        return 1

    # Read the diagram code
    code = args.file.read_text(encoding="utf-8")

    # Validate syntax
    errors = validate_mermaid_syntax(code)
    if errors:
        print("Validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if args.validate_only:
        if not args.quiet:
            print(f"Validation passed: {args.file}")
        return 0

    # Generate URL
    url = generate_mermaid_url(code)

    if not args.quiet:
        print(f"Generated URL for: {args.file}")
        print()

    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
