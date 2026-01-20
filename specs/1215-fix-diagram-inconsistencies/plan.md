# Implementation Plan: Fix Architecture Diagram Inconsistencies

**Branch**: `1215-fix-diagram-inconsistencies` | **Date**: 2026-01-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1215-fix-diagram-inconsistencies/spec.md`

## Summary

Fix documentation drift where architecture diagrams show removed components (CloudFront CF node, NewsAPI data source) instead of current architecture (Amplify direct, Tiingo/Finnhub sources). Create a reproducible mermaid.live URL generation script to eliminate regeneration churn.

## Technical Context

**Language/Version**: Markdown (diagrams), Python 3.13 (URL generation script)
**Primary Dependencies**: zlib, base64, json (all stdlib)
**Storage**: N/A (documentation-only)
**Testing**: Mermaid syntax validation via GitHub markdown preview
**Target Platform**: GitHub repository documentation
**Project Type**: Documentation maintenance + utility script
**Performance Goals**: N/A
**Constraints**: Mermaid diagrams must render in GitHub markdown
**Scale/Scope**: 5 files to update, 1 new script

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| TLS for external traffic | N/A | Documentation-only, no network |
| Secrets management | N/A | No secrets involved |
| Authentication | N/A | No endpoints |
| Testing accompaniment | PASS | Script will have validation tests |
| GPG-signed commits | PASS | Will sign all commits |
| Pre-push validation | PASS | Will run make validate |

**Result**: All applicable gates pass. This is documentation maintenance with no security implications.

## Project Structure

### Documentation (this feature)

```text
specs/1215-fix-diagram-inconsistencies/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── checklists/          # Quality checklists
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# Files to UPDATE (documentation fixes)
README.md                              # CF node removal, mermaid.live badge
docs/diagrams/architecture.mmd         # NewsAPI → Tiingo/Finnhub
src/README.md                          # NewsAPI → Tiingo/Finnhub
src/lambdas/ingestion/README.md        # NewsAPI → Tiingo/Finnhub

# Files to CREATE (automation)
scripts/regenerate-mermaid-url.py      # URL generation script

# Makefile target addition
Makefile                               # Add regenerate-mermaid-url target
```

**Structure Decision**: This feature modifies existing documentation files and adds one utility script. No new directory structure needed.

## Complexity Tracking

No complexity violations. This is straightforward documentation maintenance with a utility script.

## Phase 0: Research

### Research Tasks

1. **Mermaid pako encoding**: Verify the encoding format used by mermaid.live
2. **Theme embedding**: Confirm theme config can be embedded in pako payload
3. **Existing template**: Review docs/diagrams/TEMPLATE.md for reusable patterns

### Research Findings

**Finding 1: Pako Encoding Format**
- mermaid.live uses pako (zlib) compression with base64url encoding
- The payload is a JSON object: `{"code": "...", "mermaid": {"theme": "dark"}, ...}`
- Existing Python snippet in TEMPLATE.md is correct but doesn't embed full theme

**Finding 2: Theme Embedding**
- The `%%{init: ...}%%` directive in mermaid code embeds theme in the diagram itself
- The mermaid.live JSON payload's `"mermaid": {"theme": "dark"}` is secondary
- Best approach: Keep theme in diagram code (already there), payload just sets base theme

**Finding 3: TEMPLATE.md Assets**
- Full dark theme configuration exists at lines 10-11
- Python URL generation snippet exists at lines 99-117
- classDef styles for all node types exist at lines 18-33

**Decision**: Use TEMPLATE.md's Python snippet as base, enhance to:
1. Read .mmd file from command line
2. Validate mermaid syntax before encoding
3. Output URL to stdout for easy copy/paste or piping

## Phase 1: Design

### Script Design: regenerate-mermaid-url.py

```python
#!/usr/bin/env python3
"""Generate mermaid.live URLs from .mmd diagram files."""

import argparse
import base64
import json
import sys
import zlib
from pathlib import Path


def validate_mermaid_syntax(code: str) -> list[str]:
    """Basic validation - check for common syntax issues."""
    errors = []
    if not code.strip():
        errors.append("Empty diagram code")
    if "flowchart" not in code and "graph" not in code and "sequenceDiagram" not in code:
        errors.append("Missing diagram type declaration")
    # Check for balanced brackets
    if code.count("[") != code.count("]"):
        errors.append("Unbalanced square brackets")
    if code.count("{") != code.count("}"):
        errors.append("Unbalanced curly brackets")
    return errors


def generate_mermaid_url(diagram_code: str) -> str:
    """Generate mermaid.live view URL from diagram code."""
    payload = {
        "code": diagram_code,
        "mermaid": {"theme": "dark"},
        "autoSync": True,
        "updateDiagram": True,
    }
    json_str = json.dumps(payload)
    compressed = zlib.compress(json_str.encode("utf-8"), 9)
    encoded = base64.urlsafe_b64encode(compressed).decode("utf-8").rstrip("=")
    return f"https://mermaid.live/view#pako:{encoded}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate mermaid.live URL from .mmd file")
    parser.add_argument("file", type=Path, help="Path to .mmd diagram file")
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't generate URL")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        return 1

    code = args.file.read_text()
    errors = validate_mermaid_syntax(code)

    if errors:
        print("Validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if args.validate_only:
        print("Validation passed")
        return 0

    url = generate_mermaid_url(code)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Makefile Target

```makefile
.PHONY: regenerate-mermaid-url
regenerate-mermaid-url: ## Generate mermaid.live URL from architecture diagram
	@python scripts/regenerate-mermaid-url.py docs/diagrams/architecture.mmd
```

### Diagram Changes Summary

| File | Change | Details |
|------|--------|---------|
| README.md | Remove CF node | Lines 248-252, 314: Remove `CF` references, update Browser connections |
| README.md | Update mermaid.live badge | Line 185: Replace pako URL with regenerated one |
| docs/diagrams/architecture.mmd | Replace NewsAPI | Lines 4-5: NewsAPI → Tiingo + Finnhub |
| src/README.md | Update ingestion desc | Line 8: "NewsAPI" → "Tiingo + Finnhub" |
| src/lambdas/ingestion/README.md | Replace NewsAPI refs | Lines 5, 14, 34, 60-63: All NewsAPI → Tiingo/Finnhub |

### Verification Steps

1. After README.md edits, push to branch and verify diagram renders in GitHub
2. After architecture.mmd edits, run `make regenerate-mermaid-url` and update badge
3. Run grep to verify zero NewsAPI/CF matches in target files
