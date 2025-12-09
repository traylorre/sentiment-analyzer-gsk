# Quickstart: Local SAST Validation

**Feature**: 070-validation-blindspot-audit
**Audience**: Developers setting up local security validation

## Prerequisites

- Python 3.13+
- pip/pipx for package installation
- pre-commit installed (`pip install pre-commit`)

## Setup (One-Time)

### 1. Install SAST Tools

```bash
# Install Bandit (fast Python security linter)
pip install bandit>=1.7.0

# Install Semgrep (comprehensive SAST)
pip install semgrep>=1.50.0

# Or via project dependencies
pip install -e ".[dev]"
```

### 2. Update Pre-commit Hooks

```bash
pre-commit install
pre-commit install --hook-type pre-push
```

## Usage

### Quick Security Check (Bandit)

```bash
# Fast scan (~5-15 seconds)
bandit -r src/ -ll  # Only HIGH severity
bandit -r src/      # All severities
```

### Comprehensive Security Scan (Semgrep)

```bash
# Full SAST scan (~15-45 seconds)
make sast

# Or directly
semgrep scan --config auto src/
```

### Full Validation (Recommended Before Push)

```bash
# Runs all validation including SAST
make validate
```

## What Gets Checked

### Bandit Detects

- Hardcoded passwords/secrets
- Use of unsafe functions (eval, exec, pickle)
- SQL injection patterns
- Command injection patterns
- Weak cryptography

### Semgrep Detects (Additional)

- Log injection vulnerabilities
- Clear-text logging of sensitive data
- Taint flow from user input to dangerous sinks
- OWASP Top 10 patterns

## Handling Findings

### Severity Levels

| Severity | Action Required |
|----------|----------------|
| HIGH | Must fix before commit |
| MEDIUM | Must fix before commit |
| LOW | Review and fix when possible |

### False Positives

If a finding is a false positive, document and suppress:

```python
# Bandit false positive - input is already validated
result = subprocess.run(validated_cmd)  # nosec B603

# Semgrep false positive - data is not user-controlled
logger.info(f"Config: {config}")  # nosemgrep: python.lang.security.audit.logging
```

### Required for Suppressions

1. Inline comment explaining why it's safe
2. Code review approval
3. Document in tech debt registry if systemic

## Troubleshooting

### Semgrep Too Slow

```bash
# Use faster ruleset
semgrep scan --config p/python-security src/

# Exclude generated files
semgrep scan --exclude tests/fixtures --config auto src/
```

### Pre-commit Hook Fails

```bash
# Run specific hook manually to see details
pre-commit run bandit --all-files

# Update hooks if outdated
pre-commit autoupdate
```

### Tool Not Found

```bash
# Reinstall tools
pip install --force-reinstall bandit semgrep

# Verify installation
which bandit && bandit --version
which semgrep && semgrep --version
```

## Verification

After setup, verify the tools detect known vulnerable patterns:

```bash
# Create test file with vulnerability
echo 'import logging; logging.info(f"Key: {user_input}")' > /tmp/test_vuln.py

# Should flag log injection
semgrep scan --config auto /tmp/test_vuln.py

# Cleanup
rm /tmp/test_vuln.py
```

## Related Documentation

- [research.md](research.md) - Tool selection rationale
- [spec.md](spec.md) - Feature requirements
- [plan.md](plan.md) - Implementation details
