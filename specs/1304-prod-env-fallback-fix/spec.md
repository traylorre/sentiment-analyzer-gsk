# Feature 1304: Remove ENVIRONMENT Fallbacks from Production Lambda Code

## Problem Statement

15 locations in production Lambda code use `os.environ.get("ENVIRONMENT", "dev")` or similar fallbacks. Terraform sets `ENVIRONMENT` on every Lambda. If it's missing, something is fundamentally broken — the Lambda should crash, not silently behave as dev.

### Security Impact (3 CRITICAL)

1. **chaos.py:53** — defaults to `"dev"` which enables chaos endpoints in production
2. **alert_evaluator.py:299** — defaults to `"dev"` which bypasses authentication when `INTERNAL_API_KEY` is missing
3. **ohlc_cache.py:114** — defaults to `"preprod"` which queries wrong DynamoDB table in production

### Behavior Impact (2 MEDIUM)

4. **security_headers.py:32** — defaults to `"dev"` which exposes internal error details to clients
5. **hcaptcha.py:31** — defaults to `"dev"` which allows captcha bypass when secret is missing

### Dead Code (4 locations)

6. **notification/handler.py:41** — ENVIRONMENT declared but never used
7. **rate_limit.py:43** — ENVIRONMENT declared but never used
8. **sse_streaming/handler.py:51** — ENVIRONMENT declared but never used

### Logging-Only (5 LOW risk)

9. **env_validation.py:25** — "unknown" default for log dimensions
10. **sse_streaming/metrics.py:40** — "dev" default for CloudWatch dimensions
11. **canary/handler.py:90,191,203** — "unknown" default for X-Ray/CloudWatch
12. **metrics/handler.py:163** — "dev" default for metric dimensions
13. **chaos_restore/handler.py:34** — "dev" default but also constructs SSM paths (BEHAVIOR risk)

### Already Correct (2 locations)

14. **dashboard/handler.py:104** — already uses `os.environ["ENVIRONMENT"]` (no fallback, crashes on missing)
15. **lib/metrics.py:216,262** — already uses `os.environ["ENVIRONMENT"]` (no fallback)

## Requirements

### FR-001: Replace SECURITY-GATING fallbacks with crash
Replace `os.environ.get("ENVIRONMENT", ...)` with `os.environ["ENVIRONMENT"]` in:
- `src/lambdas/dashboard/chaos.py:53`
- `src/lambdas/notification/alert_evaluator.py:299`
- `src/lambdas/shared/cache/ohlc_cache.py:114`

### FR-002: Replace BEHAVIOR fallbacks with crash
Replace with `os.environ["ENVIRONMENT"]` in:
- `src/lambdas/shared/middleware/security_headers.py:32`
- `src/lambdas/shared/middleware/hcaptcha.py:31`
- `src/lambdas/chaos_restore/handler.py:34`

### FR-003: Remove dead code declarations
Delete unused `ENVIRONMENT = os.environ.get(...)` in:
- `src/lambdas/notification/handler.py:41`
- `src/lambdas/shared/middleware/rate_limit.py:43`
- `src/lambdas/sse_streaming/handler.py:51`

### FR-004: Replace LOGGING fallbacks with crash
Replace with `os.environ["ENVIRONMENT"]` in:
- `src/lambdas/shared/env_validation.py:25`
- `src/lambdas/sse_streaming/metrics.py:40`
- `src/lambdas/canary/handler.py:90,191,203`
- `src/lambdas/metrics/handler.py:163`

### NFR-001: All unit tests pass
Existing unit tests set ENVIRONMENT in fixtures. No test changes expected.

### NFR-002: Terraform always sets ENVIRONMENT
Verify every Lambda module call in main.tf includes ENVIRONMENT in its environment variables.

## Success Criteria

1. Zero `os.environ.get("ENVIRONMENT"` with fallback defaults in `src/`
2. Only `os.environ["ENVIRONMENT"]` (crash on missing) in `src/`
3. Dead code declarations removed
4. All 3944 unit tests pass
5. Terraform confirmed to set ENVIRONMENT on every Lambda

## Adversarial Review #1

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | `env_validation.py:25` is called at module import time by `handler.py:92` (`validate_critical_env_vars()`). If we change it to `os.environ["ENVIRONMENT"]`, and ENVIRONMENT is missing, the validation function itself crashes before it can report which vars are missing. This defeats the purpose of the validation utility. | **Resolved:** Special case — `env_validation.py` keeps `os.environ.get("ENVIRONMENT", "unknown")` because its job IS to detect missing env vars. It can't require the var it's supposed to validate. Add inline comment explaining why this is the one justified exception. |
| HIGH | `chaos.py:53` is imported by `handler.py` at lines 52-75. If we change chaos.py to `os.environ["ENVIRONMENT"]`, the import crashes handler.py's cold start. But handler.py:104 already reads `ENVIRONMENT = os.environ["ENVIRONMENT"]` — so if ENVIRONMENT is missing, handler.py crashes first anyway. Chaos.py's fallback is dead code. | **Resolved:** Still replace with `os.environ["ENVIRONMENT"]` for consistency. The crash location doesn't matter — if ENVIRONMENT is missing, Lambda fails. But removing the fallback prevents a future refactor from accidentally making it reachable. |
| MEDIUM | `canary/handler.py` uses `os.environ.get("ENVIRONMENT", "unknown")` in 3 places. The canary Lambda is a separate Lambda (not Dashboard). Does Terraform set ENVIRONMENT on the canary Lambda? | **Resolved:** Need to verify during implementation. If Terraform doesn't set it, changing to crash would break the canary. |
| LOW | `sse_streaming/metrics.py:40` has `self._environment = environment or os.environ.get("ENVIRONMENT", "dev")`. The `environment` parameter could be passed by the caller. If it's always passed, the env var fallback is dead code. | **Accepted:** Replace anyway for consistency. |

### Spec Edits
1. FR-004: `env_validation.py` keeps its fallback (justified exception — it validates the var it reads)

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** env_validation.py exception justified. Proceeding to Stage 3.

## Clarifications

### Q1: Does Terraform set ENVIRONMENT on the canary Lambda?
**Answer:** Need to verify. Check `main.tf` for `module "canary_lambda"` environment block.
**Action:** Verify during implementation.

### Q2: Is `chaos.py` ENVIRONMENT always shadowed by `handler.py` ENVIRONMENT?
**Answer:** Yes. `handler.py:104` runs at module scope before chaos.py functions are called. If ENVIRONMENT is missing, handler.py crashes first. chaos.py's fallback never executes. But replacing it ensures consistency and prevents future refactoring from exposing it.

All questions self-answerable.
