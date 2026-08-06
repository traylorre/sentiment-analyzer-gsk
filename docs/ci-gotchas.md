# CI/CD Gotchas

> **CANON**: verified against code.

Common pitfalls and their fixes discovered during development. Each entry follows the pattern: Problem, Symptom, Fix, Prevention.

---

## CORS Wildcard + Credentials (Feature 1267)

**Problem**: `Access-Control-Allow-Origin: *` silently fails when `credentials: 'include'` is used on `fetch()`.

**Why**: Per CORS spec, the wildcard `*` is treated as the literal string `"*"` (not a wildcard) when credentials mode is enabled. The browser rejects the preflight response and the fetch silently fails.

**Symptom**: API calls return no data. Frontend shows empty state. No error in the browser console (CORS failures are opaque by design).

**Root Cause**: six locations in `infrastructure/terraform/modules/api_gateway/main.tf` set
`Access-Control-Allow-Origin`, and they do **not** all take the same value. Feature 1267 replaced
`"'*'"` everywhere with origin echoing; commit `12abfbf` then had to revert half of that, because
**API Gateway MOCK integrations reject `method.request.header.X` in `response_parameters`** and
every `terraform apply` failed with `PutIntegrationResponse` 400.

The split that survived, and the one to preserve:

| Kind | Lines | Value | Why |
|---|---|---|---|
| Gateway responses (401/403/404) | `:77`, `:102`, `:126` | `method.request.header.origin` | echoing IS supported here |
| MOCK integration responses (`cors_headers`, `proxy_options`, `root_options`) | `:229`, `:640`, `:704` | `"'${local.cors_origin}'"` | echoing is NOT supported here |

**Do not "fix" the MOCK sites to `method.request.header.Origin`.** That reverts `12abfbf` and
breaks every apply. The reasoning is in the code comment at `main.tf:210-213`; read it before
touching any of the six.

**Live hazard, unfixed**: `main.tf:214` is

```hcl
cors_origin = length(var.cors_allowed_origins) > 0 ? var.cors_allowed_origins[0] : "*"
```

so an environment with `cors_allowed_origins` unset emits `Access-Control-Allow-Origin: *` next to
`Access-Control-Allow-Credentials: 'true'`, which is the exact defect this section is about. The
wildcard-rejection validators (`variables.tf:73`, `modules/api_gateway/variables.tf:143`)
short-circuit on an empty list, and the non-empty guard at `infrastructure/terraform/main.tf:44`
only fires for `environment == "prod"`. Both checked-in tfvars are currently non-empty, so this is
latent rather than firing.

Second known gap: `local.cors_origin` is `var.cors_allowed_origins[0]`, so OPTIONS preflight
returns only the **first** allowed origin. preprod lists four.

Additionally:
- Proxy and root OPTIONS responses carry `Access-Control-Allow-Credentials: 'true'`
- `Vary: Origin` is set on the MOCK paths (`:231`, `:642`, `:706`) and is **absent** from the three
  gateway responses, which are the ones that actually echo

**Prevention** (weaker than it looks, do not rely on it):
- `tests/unit/test_api_gateway_cognito.py:256` asserts no literal `'*'` appears in an
  `Access-Control-Allow-Origin` value. It reads **unresolved HCL**, so it sees the string
  `'${local.cors_origin}'` and cannot evaluate the `"*"` fallback above. It also skips
  `aws_api_gateway_gateway_response` blocks entirely, and its acceptable-value set at `:288`
  whitelists `method.request.header.Origin`, so the apply-breaking edit passes this test green.
- Never use `Access-Control-Allow-Origin: *` when `Access-Control-Allow-Credentials: true` is set
- `Vary: Origin` belongs on any response that echoes the origin. The three gateway responses
  currently violate this and nothing enforces it.

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

---

## GitHub environments gate the deploy pipeline

Three environments, configured only in GitHub settings, so this section is the sole written
record: `preprod` (no reviewers, deploys automatically), `production` (required reviewer
`@traylorre`), and `production-auto` (no reviewers; the Dependabot bypass, selected by a live
conditional in `deploy.yml`).

- `production-auto` must carry the same secrets as `production` or Dependabot deploys fail.
- Secrets the pipeline consumes: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `DASHBOARD_API_KEY`, `PREPROD_JWT_SECRET`, `PROD_JWT_SECRET`, plus `vars.AWS_REGION`.
- Deployment branches are restricted to `main`.

## Related CI surfaces

- Terraform state, locks, and backend setup: `docs/runbooks/terraform-state.md`
- Terraform module conventions: `docs/terraform-patterns.md`
- One-time account bootstrap: `infrastructure/terraform/bootstrap/README.md`
