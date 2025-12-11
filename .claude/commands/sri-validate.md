# SRI Validation

Run Subresource Integrity (SRI) validator to detect CDN scripts and stylesheets missing integrity attributes.

## What This Command Does

1. Scans all HTML files in the repository
2. Detects CDN resources (scripts and stylesheets) from known CDN domains
3. Reports resources missing `integrity` or `crossorigin` attributes
4. Outputs structured findings with severity levels

## Severity Levels

- **CRITICAL**: CDN script without integrity (executable code risk)
- **HIGH**: CDN stylesheet without integrity
- **MEDIUM**: CDN resource missing crossorigin attribute
- **INFO**: JIT compiler CDN (SRI not applicable, e.g., cdn.tailwindcss.com)

## Execution

```bash
python3 src/validators/sri.py .
```

Or via pytest for validation:
```bash
pytest tests/unit/test_sri_validator.py -v
```

## Canonical Sources

- [MDN: Subresource Integrity](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity)
- [OWASP: Subresource Integrity](https://owasp.org/www-community/controls/SubresourceIntegrity)
- [W3C SRI Specification](https://w3c.github.io/webappsec-subresource-integrity/)

## Generating SRI Hashes

To generate a SHA384 hash for a CDN resource:

```bash
curl -sL "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js" | \
  openssl dgst -sha384 -binary | openssl base64 -A
```

Add to your HTML:
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
        integrity="sha384-<hash>"
        crossorigin="anonymous"></script>
```

## Feature Reference

Created by: 090-security-first-burndown
Methodology: `.specify/methodologies/index.yaml` → `sri_validation`
