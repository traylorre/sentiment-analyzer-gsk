# Pragma Comment Audit

**Feature**: 057-pragma-comment-stability
**Date**: 2025-12-09
**Total Pragmas**: 35 (not 31 as initially estimated)

## Summary

| Category | Count | Status |
|----------|-------|--------|
| `# noqa: E402` (module-level import) | 17 | **12 UNUSED** - E402 not enabled in Ruff |
| `# noqa: S311` (random for non-security) | 6 | Valid - suppresses bandit warning |
| `# noqa: S110` (try-except-pass) | 3 | Valid - suppresses bandit warning |
| `# noqa: S108` (hardcoded /tmp) | 1 | Valid - suppresses bandit warning |
| `# noqa: S202` (tarfile extractall) | 1 | Valid - suppresses bandit warning |
| `# noqa: S105` (hardcoded password string) | 1 | Valid - enum value not a password |
| `# noqa: ARG001` (unused argument) | 1 | **UNUSED** - ARG001 not enabled in Ruff |
| `# nosec B324` (MD5 hash) | 3 | Valid - MD5 for caching, not security |
| `# nosec B108` (hardcoded /tmp) | 3 | Valid - Lambda /tmp storage |
| `# nosec B202` (tarfile extractall) | 1 | Valid - trusted source model file |
| `# type: ignore` | 1 | Valid - pydantic model override |

## Findings

### UNUSED Pragmas (13 total) - Action Required

These `# noqa` comments suppress rules not enabled in current Ruff configuration:

| File | Line | Pragma | Issue |
|------|------|--------|-------|
| `src/lambdas/analysis/handler.py` | 60 | `# noqa: E402` | E402 not enabled |
| `src/lambdas/analysis/handler.py` | 67 | `# noqa: E402` | E402 not enabled |
| `src/lambdas/analysis/handler.py` | 68 | `# noqa: E402` | E402 not enabled |
| `src/lambdas/analysis/handler.py` | 69 | `# noqa: E402` | E402 not enabled |
| `src/lambdas/ingestion/handler.py` | 63-78 | `# noqa: E402` (10x) | E402 not enabled |
| `src/lambdas/dashboard/handler.py` | 33 | `# noqa: E402` | E402 not enabled |
| `src/lambdas/dashboard/auth.py` | 1710 | `# noqa: ARG001` | ARG001 not enabled |
| `tests/unit/test_sentiment.py` | 42 | `# noqa: E402` | E402 not enabled |
| `tests/unit/interview/test_traffic_generator.py` | 24 | `# noqa: E402` | E402 not enabled |

**Recommendation**: Either:
1. Enable E402/ARG001 in Ruff config, OR
2. Remove these unused pragmas (cleaner option)

### Valid Pragmas - Security Suppressions

#### `# nosec B324` - MD5 for Non-Security (3 instances)

| File | Line | Context |
|------|------|---------|
| `src/lambdas/dashboard/sentiment.py` | 63 | MD5 for ticker cache key |
| `src/lambdas/shared/adapters/finnhub.py` | 44 | MD5 for request deduplication |
| `src/lambdas/shared/adapters/tiingo.py` | 41 | MD5 for request deduplication |

**Justification**: MD5 used for cache fingerprinting, not cryptographic security. All three use `hashlib.md5(...).hexdigest()` for deterministic key generation.

#### `# nosec B108` - Lambda /tmp Usage (3 instances)

| File | Line | Context |
|------|------|---------|
| `src/lambdas/analysis/sentiment.py` | 60 | `LOCAL_MODEL_PATH = "/tmp/model"` |
| `src/lambdas/analysis/sentiment.py` | 102 | `tar_path = "/tmp/model.tar.gz"` |
| `src/lambdas/analysis/sentiment.py` | 118 | `tar.extractall(path="/tmp")` |

**Justification**: AWS Lambda's `/tmp` is the only writable filesystem. This is expected behavior, not a security vulnerability.

#### `# nosec B202` - Tarfile Extractall (1 instance)

| File | Line | Context |
|------|------|---------|
| `src/lambdas/analysis/sentiment.py` | 118 | `tar.extractall(path="/tmp")` |

**Justification**: Tarfile comes from S3 model artifact controlled by us. Path traversal risk is mitigated by trusted source.

### Valid Pragmas - Linter Suppressions

#### `# noqa: S311` - Random for Non-Security (6 instances)

| File | Line | Context |
|------|------|---------|
| `tests/fixtures/oracles/test_oracle.py` | 77 | Random variation for test data |
| `tests/fixtures/oracles/test_oracle.py` | 82 | Random confidence for test data |
| `interview/traffic_generator.py` | 301 | Random ticker selection |
| `interview/traffic_generator.py` | 304 | Random config name |
| `interview/traffic_generator.py` | 409-426 | Random ops/delays in load testing |

**Justification**: `random` module used for test data generation and load testing, not security-sensitive operations.

#### `# noqa: S110` - Try-Except-Pass (3 instances)

| File | Line | Context |
|------|------|---------|
| `tests/e2e/test_auth_oauth.py` | 345 | Cleanup in test teardown |
| `tests/e2e/test_rate_limiting.py` | 207 | Non-critical error in rate limit test |
| `tests/e2e/test_failure_injection.py` | 400 | Expected failures in chaos test |

**Justification**: Silent exception handling acceptable in test cleanup and chaos testing scenarios.

#### `# noqa: S108` - Hardcoded /tmp in Tests (1 instance)

| File | Line | Context |
|------|------|---------|
| `tests/unit/test_sentiment.py` | 130 | Assert model path in mock |

**Justification**: Test assertion checking expected model path.

#### `# noqa: S202` - Tarfile Extractall (1 instance in tests)

Covered by `# nosec B202` on same line in production code.

#### `# noqa: S105` - Hardcoded Password String (1 instance)

| File | Line | Context |
|------|------|---------|
| `src/lambdas/shared/errors_module.py` | 65 | `SECRET_ERROR = "..."` |

**Justification**: This is an error code enum value, not an actual password. <!-- pragma: allowlist secret -->

### Type Pragmas (1 instance)

| File | Line | Context |
|------|------|---------|
| `src/lambdas/shared/models/ohlc.py` | 52 | `# type: ignore[arg-type]` |

**Justification**: Pydantic model with complex typing that mypy doesn't understand.

## Action Items

1. **Remove 13 unused `# noqa: E402` comments** - These suppress a rule that's not enabled
2. **Remove 1 unused `# noqa: ARG001` comment** - Same reason
3. **Keep all `# nosec` comments** - All are valid and justified
4. **Keep all `# noqa: S*` comments** - Suppressing valid Bandit/safety warnings
5. **Consider enabling E402 in Ruff** - Then the pragmas become valid again

## Post-Migration Verification

After formatter migration, re-run:
```bash
ruff check --extend-select RUF100 src/ tests/
bandit -r src/ --ignore-nosec
```

Expected outcome: Zero RUF100 findings once unused pragmas are removed.
