# SRI (Subresource Integrity) Methodology

**Feature**: 090-security-first-burndown
**Created**: 2025-12-11

## Overview

Subresource Integrity (SRI) is a security feature that enables browsers to verify that resources they fetch are delivered without unexpected manipulation. It works by comparing a cryptographic hash of the fetched resource against the expected hash.

## Why SRI Matters

**Supply Chain Attack Mitigation**: If a CDN is compromised, attackers could inject malicious code into popular libraries. SRI ensures the browser rejects modified resources.

**Examples of CDN compromises**:
- 2019: Magecart attacks via compromised CDN-hosted scripts
- 2021: ua-parser-js npm supply chain attack
- 2022: ctx and phpass Python package compromises

## Detection Patterns

The SRI validator detects:

| Pattern | Severity | Description |
|---------|----------|-------------|
| CDN script without integrity | CRITICAL | Executable JavaScript from external CDN |
| CDN stylesheet without integrity | HIGH | CSS from external CDN (less severe) |
| Missing crossorigin attribute | MEDIUM | Required for SRI to work cross-origin |
| JIT compiler CDN | INFO | Dynamic CDNs like Tailwind (SRI N/A) |

## Implementation Guide

### Step 1: Generate SRI Hash

Use SHA-384 (recommended by W3C):

```bash
# For remote resources
curl -sL "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js" | \
  openssl dgst -sha384 -binary | openssl base64 -A

# For local files
openssl dgst -sha384 -binary myfile.js | openssl base64 -A
```

### Step 2: Add Integrity Attribute

```html
<!-- Script -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
        integrity="sha384-e6nUZLBkQ86NJ6TVVKAeSaK8jWa3NhkYWZFomE39AvDbQWeie9PlQqM3pmYW5d1g"
        crossorigin="anonymous"></script>

<!-- Stylesheet -->
<link href="https://cdn.jsdelivr.net/npm/daisyui@4.12.14/dist/full.min.css"
      rel="stylesheet"
      integrity="sha384-hlhTcK8D1Pj0594UWVQ6V40KGnB4Y8+Pf6mov3DVLV2lr0PqHuq/x1lVg/hZn7jt"
      crossorigin="anonymous">
```

### Step 3: Verify Locally

Test in a browser that the resource loads successfully with SRI:
1. Open developer tools → Network tab
2. Refresh the page
3. Check that resources load without errors

## Exceptions

### JIT Compilers (e.g., Tailwind CDN)

`cdn.tailwindcss.com` is a JIT (Just-In-Time) compiler that generates CSS dynamically based on classes in your HTML. Because the output changes based on input, SRI hashes would break functionality.

**Recommended**: Migrate to build-time Tailwind compilation for production:
```bash
npx tailwindcss -i ./src/input.css -o ./dist/output.css
```

### Version-Pinned vs Latest

**Good**: Pin to specific versions with SRI
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
        integrity="sha384-..."></script>
```

**Avoid**: Using `@latest` or unpinned versions (hash changes on updates)
```html
<!-- BAD: No SRI possible -->
<script src="https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js"></script>
```

## Validator Usage

### Command Line

```bash
python3 src/validators/sri.py .
```

### As Library

```python
from src.validators.sri import validate_sri, format_findings

result = validate_sri("./src")
print(format_findings(result))

if not result.is_passing:
    exit(1)
```

### In CI Pipeline

Add to `.github/workflows/pr-checks.yml`:

```yaml
sri-check:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.13'
    - run: python3 src/validators/sri.py .
```

## Troubleshooting

### "Resource blocked" Error

If a resource fails to load with SRI:

1. **Hash Mismatch**: CDN updated the file. Regenerate the hash.
2. **Wrong Algorithm**: Ensure you're using SHA-384, not SHA-256 or SHA-512.
3. **Missing crossorigin**: Add `crossorigin="anonymous"` attribute.

### CI Detecting Changes

The CDN may have updated the resource content. To fix:

1. Check the CDN changelog for version updates
2. Consider pinning to specific versions
3. Regenerate hashes and update HTML

## Canonical Sources

- [MDN: Subresource Integrity](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity)
- [OWASP: Subresource Integrity](https://owasp.org/www-community/controls/SubresourceIntegrity)
- [W3C SRI Specification](https://w3c.github.io/webappsec-subresource-integrity/)
- [MDN: SRI Implementation Guide](https://developer.mozilla.org/en-US/docs/Web/Security/Practical_implementation_guides/SRI)

## Related

- `.specify/methodologies/index.yaml` - Methodology registry
- `src/validators/sri.py` - SRI validator implementation
- `tests/unit/test_sri_validator.py` - Unit tests
- `.claude/commands/sri-validate.md` - Slash command
