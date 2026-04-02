# AR#2: Cross-Check — Terraform Env Blocks vs Code Changes

## Adversarial Question

Are there any gaps between what Terraform provides and what the code now demands?
Could a successful `terraform apply` still leave a Lambda unable to start?

## Systematic Cross-Check

### Method

For each Category A variable, verify:
1. The env var key exists in the Lambda's Terraform `environment_variables` block
2. The Terraform value expression always resolves to a non-empty string
3. No conditional logic could produce an empty value

### Results

| # | Variable | Lambda | TF Line | Expression | Always Non-Empty? |
|---|----------|--------|---------|------------|-------------------|
| A1 | `DASHBOARD_URL` (security_headers.py) | dashboard | N/A | N/A | **DEAD CODE -- REMOVE** |
| A2 | `COGNITO_USER_POOL_ID` | dashboard | 426 | `module.cognito.user_pool_id` | Yes -- Cognito module always creates pool |
| A3 | `COGNITO_CLIENT_ID` | dashboard | 427 | `module.cognito.client_id` | Yes -- Cognito module always creates client |
| A4 | `COGNITO_DOMAIN` | dashboard | 429 | `module.cognito.domain` | Yes -- Cognito module always creates domain |
| A5 | `COGNITO_REDIRECT_URI` | dashboard | 431 | `length(callback_urls) > 0 ? [0] : ""` | Yes (default `["http://localhost:3000/auth/callback"]`) |
| A6 | `SENDGRID_SECRET_ARN` | notification | 570 | `module.secrets.sendgrid_secret_arn` | Yes -- secrets module creates ARN |
| A7 | `DASHBOARD_URL` (notification) | notification | 575 | `var.frontend_url` | **MAYBE** -- defaults to `""` in variables.tf |
| A8 | `SSE_LAMBDA_URL` | dashboard | 466 | `module.sse_streaming_lambda.function_url` | Yes -- SSE module always creates URL |
| A9 | `FRONTEND_URL` | dashboard | 434 | `var.frontend_url` | **MAYBE** -- defaults to `""` in variables.tf |
| A10 | `SNS_TOPIC_ARN` | ingestion | 301 | `module.sns.topic_arn` | Yes -- SNS module always creates topic |
| A11 | `TIINGO_SECRET_ARN` | ingestion | 302 | `module.secrets.tiingo_secret_arn` | Yes -- secrets module creates ARN |
| A12 | `FINNHUB_SECRET_ARN` | ingestion | 303 | `module.secrets.finnhub_secret_arn` | Yes -- secrets module creates ARN |

### Findings

#### Finding 1: A7 and A9 depend on `var.frontend_url` (default: "")

Both `DASHBOARD_URL` (notification Lambda) and `FRONTEND_URL` (dashboard Lambda)
source from `var.frontend_url`, which defaults to `""` in `variables.tf:143`.

**Risk Assessment**:
- `os.environ["DASHBOARD_URL"]` and `os.environ["FRONTEND_URL"]` will NOT crash
  (key exists, value is empty string)
- The code change from `get("VAR", "")` to `os.environ["VAR"]` does NOT change
  runtime behavior when the key is present with empty value
- This is a Terraform configuration issue, not a code issue

**Mitigation**: The notification Lambda already calls `validate_critical_env_vars(["DASHBOARD_URL"])`
at line 36, which emits a CloudWatch metric when empty. No additional mitigation needed for
the code change.

**Verdict**: PROCEED. The `os.environ["VAR"]` change is safe because the key is always
present in Terraform. Empty value behavior is unchanged.

#### Finding 2: A1 (DASHBOARD_URL in security_headers.py) is dead code

The variable is defined but never used. Removing it is strictly superior to making it
fail-fast (which would crash the dashboard Lambda since the key is absent from its
Terraform env block).

**Verdict**: REMOVE the dead variable.

#### Finding 3: No hidden Terraform conditionals

All module outputs (`module.cognito.user_pool_id`, `module.sns.topic_arn`, etc.) are
unconditional. There are no `count` or `for_each` conditionals that could cause these
outputs to not exist.

**Verified**: The `cognito`, `sns`, `secrets`, and `sse_streaming_lambda` modules are
all instantiated unconditionally in main.tf.

## Gap Analysis

| Gap | Severity | Resolution |
|-----|----------|------------|
| `DASHBOARD_URL` not in dashboard Lambda TF | None | Dead code -- remove from Python |
| `var.frontend_url` defaults to `""` | Low | Existing `validate_critical_env_vars` handles this; no code change needed |
| `COGNITO_REDIRECT_URI` could be `""` if callback_urls forced empty | None | Default variable prevents this; even if empty, Cognito error is clear |

## Conclusion

**No blocking gaps found.** All Category A variables are present in their Terraform
env blocks. The two variables sourced from `var.frontend_url` may be empty string in
dev, but:
1. The code change doesn't alter empty-string behavior (only absent-key behavior)
2. Existing `validate_critical_env_vars` warns on empty values
3. The fallback behavior (localhost) is intentional for dev

**PROCEED with all planned changes.**
