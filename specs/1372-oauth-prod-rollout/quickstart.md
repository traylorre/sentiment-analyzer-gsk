# Quickstart: Prod OAuth Rollout

This is the operator runbook for Feature 1372. It mirrors 1371's preprod
runbook with prod-specific differences. **Execute this only after 1371
has been browser-tested green** (at minimum for Google; GitHub may be
deferred).

**Prerequisite**: Feature 1370 merged + applied to prod state.

**Estimated time**: 60-90 minutes (longer than preprod due to "In
Production" consent-screen requirements).

---

## 1. Pre-Apply Account Guard (spec AR#1 HIGH #4)

**Critical — run this FIRST, before anything else:**

```bash
export AWS_PROFILE=<your-prod-profile>
export AWS_REGION=us-east-1
export EXPECTED_PROD_ACCOUNT=<prod-account-id>  # set this to the prod account ID

bash scripts/verify-oauth-deploy.sh prod --pre-apply
```

If this fails, you're on the wrong AWS profile. Fix before proceeding.

---

## 2. Verify Public-Facing Pages (spec AR#1 HIGH #2)

Google's "In Production" consent screen requires live `/terms` and
`/privacy` URLs:

```bash
PROD_URL="<your-prod-amplify-url>"
curl -sS -o /dev/null -w '%{http_code}\n' "$PROD_URL/terms"   # expect 200
curl -sS -o /dev/null -w '%{http_code}\n' "$PROD_URL/privacy" # expect 200
```

Confirm both pages have substantive content (not "Lorem ipsum"). If
either is missing or placeholder, **stop**. Get content live before
proceeding — Google will reject the OAuth verification submission.

---

## 3. Bootstrap Google Cloud (Distinct Project — spec AR#1 HIGH #3)

**Do NOT reuse the preprod Google Cloud project.** Compromise of one
must not implicate the other.

1. Create a new project named `sentiment-prod`. Capture the project
   number (different from preprod's).
2. **OAuth consent screen → Publishing status: In Production** (NOT
   Testing). This requires the verified privacy + terms URLs from step 2.
   Verification can take days for sensitive scopes; for `openid email
   profile` (basic), self-attestation is usually approved in hours.
3. Create OAuth 2.0 Client ID:
   - Application type: Web application.
   - Name: `sentiment-analyzer-prod`.
   - Authorized JavaScript origins: `https://<PROD-COGNITO-DOMAIN>.auth.us-east-1.amazoncognito.com`.
   - Authorized redirect URIs: `https://<PROD-COGNITO-DOMAIN>.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`.
4. Download JSON. Save as `~/oauth-google-prod.json` (NOT in the repo).

5. **Verify project distinctness** — compare the numeric prefix of the
   prod `client_id` to the preprod one:
   ```bash
   PREPROD_PROJECT="$(jq -r .client_id ~/oauth-google-preprod.json | cut -d- -f1)"
   PROD_PROJECT="$(jq -r .client_id ~/oauth-google-prod.json | cut -d- -f1)"
   [[ "$PREPROD_PROJECT" != "$PROD_PROJECT" ]] && echo "OK: distinct projects" || \
     { echo "FAIL: same project number — recreate prod in a separate project"; exit 1; }
   ```

---

## 4. Bootstrap GitHub OAuth App — CONDITIONAL on 1371 Outcome

**If 1371's section 8 fired (GitHub deferred in preprod)**: skip this
section. The github_oauth secret stays as placeholder for prod.

**If GitHub worked in preprod**: create a separate prod OAuth App named
`sentiment-analyzer-prod` with the prod Cognito domain in the callback
URL. Same procedure as 1371 section 3.

---

## 5. Populate Prod Secrets Manager

Same file-based pattern as 1371 section 4, but with `prod/` paths:

```bash
cat > /tmp/google-creds.json <<EOF
{"client_id":"<prod-google-client-id>","client_secret":"<prod-google-client-secret>"}
EOF
aws secretsmanager put-secret-value \
  --secret-id prod/sentiment-analyzer/google-oauth \
  --secret-string fileb:///tmp/google-creds.json
shred -u /tmp/google-creds.json

# Repeat for github (or leave as placeholder if deferred)
```

---

## 6. Plan Review with Second Pair of Eyes (spec AR#1 HIGH #1)

```bash
cd infrastructure/terraform
terraform init
terraform plan -var-file=prod.tfvars -out=prod.plan
```

**REQUIRED**: have another engineer review the plan output. Look for:

- Expected: `aws_cognito_identity_provider.google[0]` CREATED.
- Expected: `aws_cognito_identity_provider.github[0]` CREATED (or unchanged if deferred).
- Expected: `module.dashboard_lambda` env update to set `ENABLED_OAUTH_PROVIDERS`.
- **Reject any unrelated changes** (e.g., user pool client config drift,
  Lambda runtime changes, IAM policy edits). If you see them, halt and
  investigate.

Apply only after the second engineer signs off.

---

## 7. Apply (Low-Traffic Window — spec AR#1 HIGH #1)

Pick a low-traffic window if possible. Production OAuth deploy can
disrupt active sessions if there's hidden drift in user pool client
config.

```bash
terraform apply prod.plan
```

Watch the apply output. Any errors mid-apply → consider rollback per
section 11.

---

## 8. Post-Deploy Verification

```bash
bash scripts/verify-oauth-deploy.sh prod
```

Same expected output as 1371 section 6 (substituting `prod` for `preprod`).

---

## 9. Browser End-to-End Test (Real User)

1. Open `https://<prod-amplify-url>/auth/signin` in Chrome incognito.
2. Verify OAuth buttons render.
3. Click **Continue with Google**. Use a **real Google account** (not a
   test allow-listed account — production consent screen serves all
   users).
4. Complete consent. Verify redirect to `/dashboard`.
5. Decode the JWT, verify `email` claim. Same as 1371 step 8.
6. **Existing-user account-linking**: if the test account's email matches
   an existing prod user, verify Feature 1182 auto-link merges them
   correctly.
7. (If GitHub enabled) Repeat with GitHub.

---

## 10. Watch Items (First 24 Hours)

Monitor these after the deploy:

| Metric | Watch For |
|---|---|
| Cognito sign-in success rate | Should not drop. If it drops, something broke. |
| Cognito sign-in throttling (default 30/sec) | If exceeded, request a quota increase. |
| `/api/v2/auth/oauth/urls` 5xx rate | Should be ~0. |
| `/auth/callback` exceptions in CloudWatch | New OIDC errors are red flags. |
| User-reported "can't sign in" Slack/support tickets | Triage immediately. |

---

## 11. Full Rollback (spec R6)

If anything broke and you need OAuth off prod immediately:

```bash
cat > /tmp/empty.json <<'EOF'
{"client_id":"","client_secret":""}
EOF
aws secretsmanager put-secret-value --secret-id prod/sentiment-analyzer/google-oauth --secret-string fileb:///tmp/empty.json
aws secretsmanager put-secret-value --secret-id prod/sentiment-analyzer/github-oauth --secret-string fileb:///tmp/empty.json
shred -u /tmp/empty.json

cd infrastructure/terraform
terraform apply -var-file=prod.tfvars
```

Buttons hide. Magic-link continues working — no user lockout.

---

## Outcome Tracking

Same as 1371: document date, operator, Google PASS/FAIL, GitHub
PASS/FAIL/DEFERRED, deviations, and any incidents in the watch window.
