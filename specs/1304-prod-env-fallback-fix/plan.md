# Feature 1304: Implementation Plan

## Change Categories

### A: Replace with crash (11 locations)
`os.environ.get("ENVIRONMENT", "...")` → `os.environ["ENVIRONMENT"]`

| File | Line | Old Default | Risk |
|------|------|-------------|------|
| dashboard/chaos.py | 53 | "dev" | Security gating (dead code via handler crash) |
| notification/alert_evaluator.py | 299 | "dev" | Auth bypass |
| shared/cache/ohlc_cache.py | 114 | "preprod" | Wrong DynamoDB table |
| shared/middleware/security_headers.py | 32 | "dev" | Info disclosure |
| shared/middleware/hcaptcha.py | 31 | "dev" | Captcha bypass |
| chaos_restore/handler.py | 34 | "dev" | Wrong SSM paths |
| sse_streaming/metrics.py | 40 | "dev" | Wrong metric dimension |
| canary/handler.py | 90,191,203 | "unknown" | Wrong metric dimension |
| metrics/handler.py | 163 | "dev" | Wrong metric dimension |

### B: Remove dead code (3 locations)
Delete the entire `ENVIRONMENT = os.environ.get(...)` line:

| File | Line | Reason |
|------|------|--------|
| notification/handler.py | 41 | Declared, never used |
| shared/middleware/rate_limit.py | 43 | Declared, never used |
| sse_streaming/handler.py | 51 | Declared, never used |

### C: Justified exception (1 location)
KEEP `os.environ.get("ENVIRONMENT", "unknown")` in `env_validation.py:25` — its job is to detect missing env vars.

### D: Already correct (2 locations)
No changes:
- `dashboard/handler.py:104` — `os.environ["ENVIRONMENT"]`
- `lib/metrics.py:216,262` — `os.environ["ENVIRONMENT"]`

## Verification

1. Verify Terraform sets ENVIRONMENT on canary Lambda: `grep -A30 'module "canary_lambda"' main.tf | grep ENVIRONMENT`
2. Run `pytest tests/unit/ -q` — all 3944 must pass
3. `grep -rn 'os.environ.get("ENVIRONMENT"' src/` should return only env_validation.py

## Adversarial Review #2

No drift. Plan matches spec including env_validation.py exception. Gate: PASS.
