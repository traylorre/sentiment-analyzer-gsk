# Local CodeQL/Security Checking with Pre-Push Hook

## Problem

CodeQL security scans run in GitHub CI can fail PRs, causing pipeline blockages. These failures are often not caught during local development, leading to:
- Failed PR checks
- Blocked merge pipelines
- Wasted CI/CD time
- Developer frustration

## Solution

A git pre-push hook that runs local security scanning using **Bandit** (similar to CodeQL) BEFORE code reaches CI.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements-dev.txt
```

This installs `bandit==1.7.10` for security scanning.

### 2. Install the Pre-Push Hook

The hook is already created at `.git/hooks/pre-push` and should be executable. If not:

```bash
chmod +x .git/hooks/pre-push
```

## How It Works

When you run `git push`, the hook automatically:

1. **Identifies changed Python files** - Only scans files you modified
2. **Runs Bandit** - Catches common security issues (SQL injection, log injection, etc.)
3. **Checks for log injection patterns** - Specifically looks for unsanitized logging
4. **Blocks push if issues found** - Prevents bad code from reaching CI
5. **Provides fix suggestions** - Shows exactly how to fix the issues

## What It Catches

- **Log Injection** (CWE-117) - Unsanitized user input in logs
- **SQL Injection** (CWE-89) - Unsafe database queries
- **Path Traversal** (CWE-22) - Unsafe file operations
- **Command Injection** (CWE-78) - Unsafe shell command execution
- **Hardcoded Secrets** - API keys, passwords in code

## Example Output

### ✅ Clean Code
```bash
$ git push origin feat/my-feature
🔒 Running security checks before push...
📁 Checking 3 Python file(s)...
🔍 Running Bandit security scan...
✅ Bandit: No high/medium security issues found
🔍 Checking for log injection vulnerabilities...
✅ All security checks passed!
```

### ❌ Security Issues Detected
```bash
$ git push origin feat/my-feature
🔒 Running security checks before push...
📁 Checking 2 Python file(s)...
🔍 Running Bandit security scan...
>> Issue: [B608:hardcoded_sql_expressions] Possible SQL injection
   Location: src/lambdas/api/handler.py:45

❌ SECURITY ISSUES DETECTED
   Bandit found potential security vulnerabilities in your code.

   Common fixes:
   - Log injection: Use sanitize_for_log() from logging_utils
   - Path injection: Use sanitize_path_component() from logging_utils
   - SQL injection: Use parameterized queries

   To bypass this check (NOT RECOMMENDED):
   git push --no-verify
```

## Fixing Log Injection

The most common issue caught by the hook is log injection. Here's how to fix it:

### ❌ Bad (Unsafe)
```python
logger.info(f"User {user_id} performed action {action}")
logger.error("Failed for user: %s", user_input)
```

### ✅ Good (Safe)
```python
from src.lambdas.shared.logging_utils import sanitize_for_log

logger.info(
    "User performed action",
    extra={
        "user_id": sanitize_for_log(user_id),
        "action": sanitize_for_log(action)
    }
)
```

## Bypassing the Hook (Emergency Only)

If you absolutely must push without passing security checks:

```bash
git push --no-verify origin feat/my-feature
```

**⚠️ WARNING**: This will likely cause CodeQL failures in CI, blocking your PR.

## Running Manual Security Scans

### Scan Specific Files
```bash
bandit -ll src/lambdas/dashboard/chaos.py
```

### Scan Entire Codebase
```bash
bandit -r src/ -ll
```

### Output to File
```bash
bandit -r src/ -ll -f json -o security-report.json
```

## Integration with CI/CD

The pre-push hook catches issues locally, but CI still runs full CodeQL scans. This provides:
- **Fast feedback** - Hook runs in seconds locally
- **Comprehensive analysis** - CodeQL in CI catches everything
- **Defense in depth** - Multiple layers of security checking

## Troubleshooting

### Hook Not Running
```bash
# Check if executable
ls -l .git/hooks/pre-push

# Make executable if needed
chmod +x .git/hooks/pre-push
```

### Bandit Not Found
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Verify installation
bandit --version
```

### False Positives

If Bandit reports a false positive:
1. Review the code carefully - is it really safe?
2. If truly safe, add a `# nosec` comment with justification
3. Document WHY it's safe in the comment

```python
# This is safe because file_id is validated against UUID format
file_path = f"/secure/uploads/{file_id}.pdf"  # nosec B608
```

## References

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [CodeQL Python Queries](https://codeql.github.com/codeql-query-help/python/)
- Project Logging Utils: `src/lambdas/shared/logging_utils.py`
