# Python Version Parity Guide

**Problem**: Local development was using Python 3.13, but CI/CD uses Python 3.13. This ensures type annotation compatibility.

**Example Error (if using older Python)**:
```python
_dynamodb_client: any | None = None  # Works in 3.13, FAILS in older versions
# TypeError: unsupported operand type(s) for |: 'builtin_function_or_method' and 'NoneType'
```

**Solution**: Use `typing.Any` instead:
```python
from typing import Any
_dynamodb_client: Any | None = None  # Works in Python 3.10+
```

## Setting Up Python 3.13 Locally

### Option 1: Using pyenv (Recommended)

```bash
# Install pyenv
curl https://pyenv.run | bash

# Add to ~/.bashrc or ~/.zshrc:
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"
eval "$(pyenv virtualenv-init -)"

# Restart shell or source rc file
source ~/.bashrc

# Install Python 3.13
pyenv install 3.13.1

# Set as project default
cd /path/to/sentiment-analyzer-gsk
pyenv local 3.13.1

# Verify
python --version  # Should show Python 3.13.1
```

### Option 2: Using apt (Ubuntu/Debian)

```bash
# Add deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update

# Install Python 3.13
sudo apt-get install python3.13 python3.13-venv python3.13-dev

# Create venv with 3.13
python3.13 -m venv .venv
source .venv/bin/activate

# Verify
python --version  # Should show Python 3.13.x
```

### Option 3: Using Docker (Works everywhere)

```bash
# Run tests in Python 3.13 container
docker run --rm -v $(pwd):/workspace -w /workspace python:3.13 bash -c "
  pip install -r requirements-dev.txt &&
  pytest tests/unit/ -v
"
```

## Verifying Parity

After setting up Python 3.13:

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run full test suite (what CI runs)
pytest tests/unit/ -v

# Run linters
ruff check .
black --check .

# Run security checks
bandit -r src/ -ll
```

## CI Configuration

Our GitHub Actions workflows use Python 3.13:

```yaml
- name: Setup Python
  uses: actions/setup-python@v6
  with:
    python-version: '3.13'
```

Files using 3.13:
- `.github/workflows/deploy.yml`
- `.github/workflows/pr-check-test.yml`
- `.github/workflows/pr-check-lint.yml`
- `.github/workflows/pr-check-security.yml`

## Best Practices

1. **Always test with Python 3.13 before pushing**
   - If you only have 3.11, use Docker option above

2. **Use `typing` module for type hints**
   - ✅ `from typing import Any; x: Any | None`
   - ❌ `x: any | None` (fails in 3.11)

3. **Check CLAUDE.md for official version**
   - Project standard: Python 3.13
   - Keep local environment in sync

4. **Add pre-commit hook** (future enhancement)
   - Could check Python version
   - Warn if not using 3.13

## Lessons Learned

### Issue 1: Type Annotation with `any`
**Problem**: Used lowercase `any` (builtin function) instead of `typing.Any`
**Impact**: Passed in 3.13, failed in 3.11 collection
**Fix**: Always import `Any` from `typing` module

### Issue 2: Test Expectations Out of Sync
**Problem**: Test expected "not yet implemented" but feature was implemented
**Impact**: Test failure in CI after implementation
**Fix**: Updated test to verify implementation instead of error

### Issue 3: No Local Python 3.13
**Problem**: Couldn't reproduce CI failures locally
**Impact**: Multiple push/fix cycles
**Solution**: This document + pyenv setup

## References

- [PEP 604 - Union Type Operator](https://peps.python.org/pep-0604/) (Python 3.10+)
- [typing module docs](https://docs.python.org/3/library/typing.html)
- [pyenv documentation](https://github.com/pyenv/pyenv)
