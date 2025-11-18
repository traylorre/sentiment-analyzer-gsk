# Troubleshooting Guide

Common issues and solutions for the Sentiment Analyzer project.

## Table of Contents

- [Development Environment Issues](#development-environment-issues)
  - [OpenSSL/pyOpenSSL Compatibility](#opensslpyopenssl-compatibility)
  - [Python Version Issues](#python-version-issues)
- [Test Issues](#test-issues)
  - [Moto Tests Failing](#moto-tests-failing)
- [AWS Issues](#aws-issues)
  - [DynamoDB GSI Not Found](#dynamodb-gsi-not-found)

---

## Development Environment Issues

### OpenSSL/pyOpenSSL Compatibility

**Error:**
```
AttributeError: module 'lib' has no attribute 'X509_V_FLAG_NOTIFY_POLICY'
```

**Cause:**
Version mismatch between system `pyOpenSSL` (old) and user-installed `cryptography` (new). This commonly occurs on Ubuntu/Debian systems where:
- System pyOpenSSL: 21.0.0 (from `/usr/lib/python3/dist-packages`)
- User cryptography: 46.x (from `~/.local/lib/python3.11/site-packages`)

The `X509_V_FLAG_NOTIFY_POLICY` attribute was removed in newer cryptography versions, causing pyOpenSSL 21.x to fail.

**Solution:**
Install a compatible pyOpenSSL version in user space that overrides the system package:

```bash
# Upgrade pyOpenSSL to match cryptography version
pip3 install --user --upgrade pyopenssl

# Verify the upgrade
pip3 show pyopenssl | grep -E "Version|Location"
# Should show:
# Version: 25.3.0 (or newer)
# Location: /home/USER/.local/lib/python3.11/site-packages
```

**Verification:**
```bash
# Run tests to confirm fix
python3 -m pytest tests/unit/test_dashboard_metrics.py -v
```

**Root Cause Analysis:**
- Ubuntu/Debian ship with system Python packages in `/usr/lib/python3/dist-packages`
- User packages installed via `pip install --user` go to `~/.local/lib/python3.X/site-packages`
- Python prioritizes user packages over system packages
- When `cryptography` is upgraded but `pyOpenSSL` isn't, incompatibility occurs
- The fix ensures both packages are from the same generation

**Prevention:**
- Always use virtual environments for project development
- Pin package versions in requirements.txt
- Include this check in CI/CD to catch mismatches early

---

### Python Version Issues

**Error:**
```
/bin/bash: python: command not found
```

**Cause:**
On some systems (especially Ubuntu 20.04+), `python` command is not available, only `python3`.

**Solution:**
Always use `python3` explicitly:

```bash
# Instead of
python -m pytest tests/

# Use
python3 -m pytest tests/
```

**Alternative:**
Create an alias or use `python-is-python3` package:

```bash
# Ubuntu/Debian
sudo apt install python-is-python3
```

---

## Test Issues

### Moto Tests Failing

**Error:**
```
ImportError: cannot import name 'mock_aws' from 'moto'
```

**Cause:**
Moto 5.x changed the import structure. Old imports like `mock_dynamodb` are deprecated.

**Solution:**
Use the new `mock_aws` decorator:

```python
# Old (moto < 5.0)
from moto import mock_dynamodb

@mock_dynamodb
def test_something():
    ...

# New (moto >= 5.0)
from moto import mock_aws

@mock_aws
def test_something():
    ...
```

**Verification:**
```bash
pip3 show moto | grep Version
# Should be 5.x or newer
```

---

## AWS Issues

### DynamoDB GSI Not Found

**Error:**
```
ValidationException: The table does not have the specified index: by_sentiment
```

**Cause:**
Dashboard queries require GSIs that may not exist on the DynamoDB table.

**Required GSIs:**
- `by_sentiment` (PK: sentiment, SK: timestamp)
- `by_tag` (PK: tag, SK: timestamp)
- `by_status` (PK: status, SK: timestamp)

**Solution:**
Verify GSIs exist on the table:

```bash
aws dynamodb describe-table \
  --table-name sentiment-items \
  --query 'Table.GlobalSecondaryIndexes[*].IndexName'
```

If missing, update Terraform and redeploy infrastructure.

---

## Getting Help

If you encounter an issue not covered here:

1. Check the error message carefully for clues
2. Search existing GitHub issues
3. Check CloudWatch logs for Lambda-specific errors
4. Create a new GitHub issue with:
   - Full error message
   - Steps to reproduce
   - Environment details (OS, Python version, package versions)

---

*Last updated: 2025-11-17*
