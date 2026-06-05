# Quickstart: Preprod OAuth Rollout

This is the operator runbook for Feature 1371. Execute in order. Each
section calls out the spec/AR finding it implements.

**Prerequisite**: Feature 1370 must be merged AND applied to preprod state
(Secrets Manager resources exist, even if values are placeholders).

**Estimated time**: 30-60 minutes.

---

## 1. Verify Prerequisites

```bash
export AWS_PROFILE=<your-preprod-profile>
export AWS_REGION=us-east-1

# Confirm correct AWS account before doing ANYTHING.
bash scripts/verify-oauth-deploy.sh preprod --pre-apply
# Expect: PASS: AWS account 218795110243 matches expected preprod account.

# Confirm 1370 secrets exist (placeholder JSON is fine).
aws secretsmanager describe-secret --secret-id preprod/sentiment-analyzer/google-oauth --query Name
aws secretsmanager describe-secret --secret-id preprod/sentiment-analyzer/github-oauth --query Name
```

If any of these fail, **stop**. Don't proceed.

---

## 2. Bootstrap Google Cloud OAuth Client (spec R1, AR#1 HIGH #1)

1. Sign in to [Google Cloud Console](https://console.cloud.google.com) with
   the team's preprod Google account.
2. Create a project named `sentiment-preprod`. Capture the project number.
3. Navigate to **APIs & Services → OAuth consent screen**.
   - User Type: **External**.
   - Publishing status: **Testing** (NOT Production for preprod).
   - Add **Test users** — list every email that needs to test sign-in. Without
     this, users see "Access blocked: This app's request is invalid."
   - Recommended scopes: `openid`, `email`, `profile` (no sensitive scopes).
4. Navigate to **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
   - Application type: **Web application**.
   - Name: `sentiment-analyzer-preprod`.
   - **Authorized JavaScript origins**:
     `https://<PREPROD-COGNITO-DOMAIN>.auth.us-east-1.amazoncognito.com`
   - **Authorized redirect URIs**:
     `https://<PREPROD-COGNITO-DOMAIN>.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`
   - To find `<PREPROD-COGNITO-DOMAIN>`:
     ```bash
     aws cognito-idp list-user-pools --max-results 60 \
       --query "UserPools[?starts_with(Name, 'preprod')].Id" --output text \
       | xargs -I{} aws cognito-idp describe-user-pool --user-pool-id {} \
       --query 'UserPool.Domain' --output text
     ```
5. **Download JSON** from the OAuth client ID page. Save as `~/oauth-google-preprod.json`
   (NOT in the repo — `~/` is fine, but anywhere outside the repo works).

---

## 3. Bootstrap GitHub OAuth App (spec R2)

> **HEADS UP** (spec AR#1 HIGH #2): the existing `cognito/github.tf:22-26`
> uses GitHub Actions OIDC endpoints, which won't work for user OAuth.
> GitHub sign-in is **expected to fail** in section 8. If you have a tight
> deadline, you can skip this section and ship Google-only. Section 9 covers
> the deferral procedure.

1. Sign in to GitHub as the team's preprod account owner.
2. Navigate to **Settings → Developer settings → OAuth Apps → New OAuth App**.
3. Application name: `sentiment-analyzer-preprod`.
4. Homepage URL: `https://main.d29tlmksqcx494.amplifyapp.com`
5. Authorization callback URL:
   `https://<PREPROD-COGNITO-DOMAIN>.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`
6. **Register**. Capture the Client ID immediately.
7. Click **Generate a new client secret**. Capture the secret immediately
   (GitHub shows it once).
8. Save as `~/oauth-github-preprod.txt` outside the repo.

---

## 4. Populate Secrets Manager (spec AR#1 HIGH #4)

Avoid pasting client secrets into the shell history. Use file-based input.

```bash
# Build the JSON locally. shred prevents recovery from disk after we're done.
cat > /tmp/google-creds.json <<EOF
{"client_id":"<paste-google-client-id>","client_secret":"<paste-google-client-secret>"}
EOF
aws secretsmanager put-secret-value \
  --secret-id preprod/sentiment-analyzer/google-oauth \
  --secret-string fileb:///tmp/google-creds.json
shred -u /tmp/google-creds.json

cat > /tmp/github-creds.json <<EOF
{"client_id":"<paste-github-client-id>","client_secret":"<paste-github-client-secret>"}
EOF
aws secretsmanager put-secret-value \
  --secret-id preprod/sentiment-analyzer/github-oauth \
  --secret-string fileb:///tmp/github-creds.json
shred -u /tmp/github-creds.json
```

If you skipped section 3 (GitHub deferral), leave the github secret as
placeholder.

---

## 5. Apply Terraform (spec R3)

```bash
cd infrastructure/terraform
terraform init
terraform plan -var-file=preprod.tfvars -out=preprod.plan

# Review the plan output:
#   - aws_cognito_identity_provider.google[0] CREATED
#   - aws_cognito_identity_provider.github[0] CREATED (or unchanged if deferred)
#   - dashboard Lambda env: ENABLED_OAUTH_PROVIDERS = "google,github" (or "google")
#   - Zero unrelated changes.

terraform apply preprod.plan
```

If the plan shows ANY change you didn't expect, abort. Investigate before
applying.

---

## 6. Post-Deploy Verification (spec R4)

```bash
bash scripts/verify-oauth-deploy.sh preprod
```

Expected output (paraphrased):

```
PASS: AWS account 218795110243 matches expected preprod account.
PASS: Lambda env ENABLED_OAUTH_PROVIDERS=google,github
PASS: Cognito IdPs configured: Google GitHub
PASS: Lambda env <-> Cognito IdP consistency verified.
PASS: <api-gw>/api/v2/auth/oauth/urls returned 200 with 2 provider(s).
================================================================
  All OAuth deploy checks PASSED for env: preprod
================================================================
```

If any line says FAIL, fix before proceeding to browser test.

---

## 7. Browser End-to-End Test (spec R5)

Use Chrome incognito (canonical browser).

1. Open `https://main.d29tlmksqcx494.amplifyapp.com/auth/signin`.
2. Verify: "Continue with Google" and "Continue with GitHub" buttons render
   above the email form.
3. Click **Continue with Google**.
4. Use a **test user email** (one you allow-listed in section 2).
5. Complete the consent flow.
6. Verify redirect: Cognito → `/auth/callback?code=...` → `/dashboard`.
7. Open DevTools → Application → Session Storage. Confirm the auth state
   is populated.
8. Decode the access token (spec AR#1 HIGH #5):
   ```
   echo "<paste-jwt>" | cut -d. -f2 | base64 -d | jq .
   ```
   Verify `email` claim is present and matches the Google account email.
9. **Duplicate-email test** (spec AR#1 MEDIUM #4): if the email matches an
   existing magic-link account, sign-in should succeed (Feature 1182
   auto-link). Verify the resulting user has both federation fields and
   the existing magic-link history.
10. Sign out. Repeat with **Continue with GitHub**.

---

## 8. GitHub Failure Mode (Expected, per AR#1 HIGH #2)

If GitHub sign-in fails (most likely due to OIDC config issue):

- Cognito error page shows ID token validation failure, OR
- Browser hangs at the GitHub callback, OR
- DevTools console shows a JWKS / OIDC parse error.

Capture:
- Network tab as HAR.
- Cognito CloudWatch logs from the user pool's authentication events.
- Browser console output.

---

## 9. GitHub Deferral Procedure (spec R6)

If section 8 confirms GitHub is broken:

```bash
# Reset GitHub secret to placeholder
cat > /tmp/github-placeholder.json <<'EOF'
{"client_id":"","client_secret":""}
EOF
aws secretsmanager put-secret-value \
  --secret-id preprod/sentiment-analyzer/github-oauth \
  --secret-string fileb:///tmp/github-placeholder.json
shred -u /tmp/github-placeholder.json

# Re-apply: aws_cognito_identity_provider.github[0] gets removed (count=0),
# Lambda env updates to ENABLED_OAUTH_PROVIDERS="google".
cd infrastructure/terraform
terraform apply -var-file=preprod.tfvars

# Re-verify
cd ../..
bash scripts/verify-oauth-deploy.sh preprod
```

Then:
- Open a follow-up issue/feature (suggested ID: 1375) titled
  "GitHub OAuth federation via custom OIDC proxy".
- Link to the captured failure trace from section 8.
- Tag this runbook execution as "Google-only — GitHub deferred".

---

## 10. Rollback (Full)

If something goes wrong AFTER section 5 and you need to disable OAuth
entirely:

```bash
cat > /tmp/empty.json <<'EOF'
{"client_id":"","client_secret":""}
EOF
aws secretsmanager put-secret-value \
  --secret-id preprod/sentiment-analyzer/google-oauth \
  --secret-string fileb:///tmp/empty.json
aws secretsmanager put-secret-value \
  --secret-id preprod/sentiment-analyzer/github-oauth \
  --secret-string fileb:///tmp/empty.json
shred -u /tmp/empty.json

cd infrastructure/terraform
terraform apply -var-file=preprod.tfvars
```

Both IdPs removed (count=0). Lambda env empty. Buttons hide. **Magic-link
sign-in continues to work** — no user lockout.

---

## Outcome Tracking

After this runbook completes, document:

- Date executed.
- Operator name.
- Google: PASS / FAIL.
- GitHub: PASS / FAIL / DEFERRED.
- Any deviations from this runbook.

Append to a session log or open a tracking issue. Once 1371 outcome is
recorded, Feature 1372 (prod) is unblocked for Google. GitHub is
unblocked for prod only after the GitHub follow-up feature lands.
