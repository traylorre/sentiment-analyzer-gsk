# CI/CD Gotchas

Common pitfalls and their fixes discovered during development. Each entry follows the pattern: Problem, Symptom, Fix, Prevention.

---

## CORS Wildcard + Credentials (Feature 1267)

**Problem**: `Access-Control-Allow-Origin: *` silently fails when `credentials: 'include'` is used on `fetch()`.

**Why**: Per CORS spec, the wildcard `*` is treated as the literal string `"*"` (not a wildcard) when credentials mode is enabled. The browser rejects the preflight response and the fetch silently fails.

**Symptom**: API calls return no data. Frontend shows empty state. No error in the browser console (CORS failures are opaque by design).

**Root Cause**: Three locations in `infrastructure/terraform/modules/api_gateway/main.tf` had `"'*'"` for `Access-Control-Allow-Origin`:
1. `local.cors_headers` (used by public route OPTIONS responses)
2. `proxy_options` integration response (catch-all `{proxy+}` OPTIONS)
3. `root_options` integration response (root `/` OPTIONS)

**Fix**: Replace `"'*'"` with `"method.request.header.Origin"` (origin echoing). This is the standard AWS API Gateway pattern that echoes the requesting Origin header verbatim.

```hcl
# BEFORE (broken with credentials: 'include')
"method.response.header.Access-Control-Allow-Origin" = "'*'"

# AFTER (works with credentials: 'include')
"method.response.header.Access-Control-Allow-Origin" = "method.request.header.Origin"
```

Additionally:
- Proxy and root OPTIONS responses carry `Access-Control-Allow-Credentials: 'true'`
- `Vary: Origin` is set, to prevent CDN/proxy cache poisoning

**Prevention**:
- Unit tests in `tests/unit/test_api_gateway_cognito.py` parse the HCL and assert no wildcard `'*'` appears in any `Access-Control-Allow-Origin` value
- Never use `Access-Control-Allow-Origin: *` when `Access-Control-Allow-Credentials: true` is set
- Always include `Vary: Origin` when origin echoing is used

---

## Dockerfile selective COPY and transitive imports

**Problem**: the SSE Lambda Dockerfile copies `src/lib/` selectively, not wholesale. A new import
from `src/lib/` in code the image includes breaks the build with `ModuleNotFoundError`.

**Why**: the analysis and dashboard Dockerfiles use `COPY lib /var/task/src/lib`. The SSE one
lists individual paths to keep the image small. When `fanout.py` gained an import of
`src.lib.metrics`, the smoke test failed and blocked every deploy.

**Fix**: add an explicit COPY per dependency.

```dockerfile
COPY lib/timeseries /var/task/src/lib/timeseries
COPY lib/metrics.py /var/task/src/lib/metrics.py
```

**Prevention**: when adding an import to a module that ships in a Docker image, check every
Dockerfile that includes it. CI catches this, but only after a push to main triggers the deploy.

---

## Pre-commit hook ordering and detect-secrets churn

**Problem**: hooks that modify files can loop. `detect-secrets` records line numbers in
`.secrets.baseline`, formatters change line counts, the baseline drifts, the commit fails.

**Why**: `detect-secrets` (`.pre-commit-config.yaml:83`) runs *after* `ruff-check` (`:61`) and
`ruff-format` (`:63`), both of which add and reflow lines.

**Fix**: `scripts/detect-secrets-autostage.sh` runs the hook, auto-stages the baseline if it
changed, and retries until stable. Already wired as a local hook.

**Alternatives considered**: a slim baseline (`detect-secrets scan --slim`) drops line numbers but
breaks `detect-secrets audit`; CI-only scanning removes local churn but also local protection.

**Ordering note**: there are 23 hooks, not the 17 an older table claimed, and `default_stages` is
`[commit]` (`.pre-commit-config.yaml:36`). Only three hooks actually run at push: `pytest` (`:137`),
`check-branch-collision` (`:160`) and `check-error-log-assertions` (`:170`). `mypy` is
`stages: [manual]` (`:147`) and never runs automatically at all, so do not chase it when a push is
blocked. `trivy` and `checkov` are commit-stage and `.tf`-scoped. `tfsec` and
`checkov` were removed from `pre-commit-terraform` (`.pre-commit-config.yaml:72-74`) and replaced
by local hooks; `trivy-terraform` runs `--exit-code 0` and is currently decorative. Read
`.pre-commit-config.yaml` for the live order rather than any prose copy.
