# Feature 1304: Tasks

### T1: Verify Terraform sets ENVIRONMENT on all Lambdas
Check main.tf for ENVIRONMENT in each Lambda module's environment block.

### T2: Replace fallbacks with crash (Category A — 11 locations)
Change `os.environ.get("ENVIRONMENT", "...")` to `os.environ["ENVIRONMENT"]` in 9 files.

### T3: Remove dead code (Category B — 3 locations)
Delete unused ENVIRONMENT declarations in 3 files.

### T4: Add justified exception comment (Category C)
Add inline comment to env_validation.py explaining why it keeps the fallback.

### T5: Verify and run tests
- `grep -rn 'os.environ.get("ENVIRONMENT"' src/` returns only env_validation.py
- `pytest tests/unit/ -q` — 3944 pass

## Adversarial Review #3

**Highest-risk task:** T2 — `alert_evaluator.py:299` is an inline expression `return os.environ.get("ENVIRONMENT", "dev") in ("dev", "test")`. Changing to `os.environ["ENVIRONMENT"]` requires restructuring the expression.

**READY FOR IMPLEMENTATION.**
