# Plan: M1 WI-6 — Verifiable Google OAuth Enablement (preprod)

**Feature:** 1375-wi6-google-oauth-enablement · **Spec:** ./spec.md · **Branch:** `wi6-enable-google-idp`

## Technical Context

- **Language/stack:** Terraform (HCL, AWS provider ~>5.0); TypeScript/Playwright (Next.js frontend E2E).
- **Change surface is tiny by design.** OAuth code + secret-wiring already merged (Features 1169–1193,
  1370). Confirmed in-tree: `main.tf:119` secret data source → `local.google_oauth.client_id` →
  `local.enabled_oauth_providers` (`main.tf:138`) → Lambda `ENABLED_OAUTH_PROVIDERS` (`main.tf:468`),
  and → Cognito module `google_client_id/secret` (`main.tf:159`). IdP resource `google.tf:13`, `count`
  gated on `contains([...lower(p)...],"google")` from `var.cognito_identity_providers` only.
- **The only infra delta:** `cognito_identity_providers = ["Google"]` in `preprod.tfvars` (staged, HOLD
  commit `9629502`, draft PR #932).
- **Live baseline (this session):** `/oauth/urls` `{"providers":{},"state":""}`; IdPs `[]`; secret empty;
  exact hosted-UI error `Login option is not available. Please try another one`.
- **Deploy mechanism:** `deploy.yml` runs `terraform apply -auto-approve` on push to main → **merging
  #932 IS the apply.** Secret must be populated first (FR-1) so all four parts land together.
- **Test harness:** `frontend/tests/e2e/helpers/verification.ts` (`verify.shot`/`verify.forbid`/response
  listener; `VERIFICATION=1`→`trace:'on'`). Template: `auth-guest.spec.ts`. **No route interception**
  (banned + detected on preprod targets).
- **Verifier authority:** `docs/cleanup-pristine/m1-verifier-convention.md` (rows `auth-oauth-01..05`).

## The Four-Parts Sequence (the anti-whack-a-mole model)

```
OWNER (gated)                         AUTOMATED (single terraform apply on #932 merge)
─────────────                         ─────────────────────────────────────────────
1. Google client  ─┐
   (client_id/secret)                  ┌─ part 3: Cognito Google IdP created
2. put-secret-value ┼─ secret populated ┤    (google.tf count←tfvars list; creds←secret)
   into google-oauth │  BEFORE apply     └─ part 4: Lambda ENABLED_OAUTH_PROVIDERS="google"
                     │                        (local←secret.client_id != "")
3. mark #932 ready ──┘  ── merge ⇒ deploy.yml terraform apply ⇒ parts 3+4 consistent together
```
Testing between steps is the trap: any probe before the single apply sees an inconsistent subset and
errors. **Do not test mid-sequence.** Verify only after the apply, via `verify-oauth-deploy.sh`.

## Owner Runbook (FR-2 — single authoritative copy)

> Secrets stay on the owner's machine; never pasted into chat or committed.

**Step A — Google Cloud console (create the OAuth client):** *(personal Gmail is fine for preprod — no
separate account needed. DQ-2/DQ-3 resolved.)*
1. Google Cloud console (signed in with the personal Gmail) → create a project e.g. `sentiment-preprod`
   (or reuse one). APIs & Services.
2. **OAuth consent screen** → User type **External** → fill app name/support email → **add the personal
   Gmail as a Test user**. Leave in **Testing** (do NOT need "Publish"). *Gotcha: External+Testing only
   admits listed test users; a missing test user yields `access_denied` at capture (R-1/T010).*
3. Credentials → *Create Credentials* → *OAuth client ID* → Application type **Web application**.
4. **Authorized redirect URI** (exact, Cognito domain — NOT the Amplify URL):
   `https://preprod-sentiment-218795110243.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`
5. (Scopes `email`, `profile`, `openid`.) Create → copy **Client ID** + **Client secret**.
   *Note: the login Gmail becomes a federated user in the preprod pool with its real email — fine for
   preprod verification.*

**Step B — populate the secret (owner's terminal, preprod creds):**
```bash
aws secretsmanager put-secret-value \
  --secret-id preprod/sentiment-analyzer/google-oauth \
  --region us-east-1 \
  --secret-string '{"client_id":"<CLIENT_ID>","client_secret":"<CLIENT_SECRET>"}'
```
Verify shape (no secret echoed): `aws secretsmanager get-secret-value --secret-id
preprod/sentiment-analyzer/google-oauth --region us-east-1 --query 'SecretString' --output text | jq 'keys'`
→ must show `["client_id","client_secret"]`.

**Step C — release the hold:** mark draft PR #932 *Ready for review* → merge. deploy.yml auto-applies.
FR-8 guard blocks the apply if the secret is still empty (belt-and-suspenders).

**Step D — verify the deploy (after apply completes):**
```bash
./scripts/verify-oauth-deploy.sh preprod   # expects: Lambda env, Cognito IdP, /oauth/urls 200 ≥1 provider
```
Capture stdout → `docs/cleanup-pristine/evidence/m1/wi6-preprod/verify-oauth-deploy.txt`.

## Implementation Approach

### A. Infra (WI-6.3–6.5)
- No terraform edits beyond the staged tfvars line. **Watch the apply plan for unexpected
  `preprod-dashboard` Lambda changes (Issue #491 drift) — stop and `terraform import` if seen** (EC-3).
- **FR-8 guard:** add a pre-apply check in the deploy workflow (before `terraform apply`) that reads the
  `google-oauth` secret's `client_id` and fails if empty while `preprod.tfvars` contains `"Google"` in
  `cognito_identity_providers`. Pure shell + `aws`/`jq`; no AWS resource. Delivered in its own small PR
  (not #932) so #932 stays a clean single-line diff.
- WAF integration gate will be RED for unrelated SQLi/XSS (EC-4) — expected; the deploy still succeeds.

### B. Tests (WI-6.6 — `frontend/tests/e2e/auth-oauth.spec.ts`)
- Copy the `auth-guest.spec.ts` structure: `import { test, expect } from './helpers/verification'`,
  response listener (no interception). **`verify.forbid({method:'POST',
  path:'/api/v2/auth/anonymous', status:201, max_count:1})`** — NOT 0. `SessionProvider` is in the ROOT
  layout (`app/layout.tsx:54`), so a clean-context load of `/auth/signin` fires `useSessionInit` and
  mints exactly one inherent pre-login guest (no cookie → `/refresh` fails → one `anonymous 201`). A
  **second** mint would mean a signed-in reload silently re-guested — that's the real regression the rule
  catches. The "session survived without re-guesting" guarantee is carried by the **row-04 identity
  probe** (still the Google identity, `/refresh 200`, not "Guest"), since `forbid` counts across the
  whole spec at teardown and cannot be scoped post-login.
- **Row 01** (headless-capable): `goto('/auth/signin')`, assert `GET /oauth/urls 200` non-empty via
  listener, `verify.shot('signin-buttons', {probe:{selector:'text=Continue with Google'}})`. The Google
  button has **no `data-testid`** (C1) — probe by accessible name `Continue with Google`
  (`oauth-buttons.tsx:65`).
- **Run config (target=preprod):** the manifest self-labels `preprod` only if `PREPROD_FRONTEND_URL`
  equals `https://main.d29tlmksqcx494.amplifyapp.com` exactly (`verification.ts:174-178`); the Playwright
  `baseURL` (for `goto('/')`) must be the same. Any other value → `localhost-mock` → convention hard-fail.
- **Rows 02–05** (headed interactive, one run): clean context → click Google → owner completes Google
  login → callback. `verify.shot('callback-return')` gated on listener `POST /oauth/callback 200` (accept
  page_url `{/auth/callback*, /}`). Then `identity`/`post-reload`(F5)/`alerts-page`, identity probes
  lineage-checked against row 03.
- Selectors: confirm the real Google-button `data-testid` in `oauth-buttons.tsx` and a signed-in
  UserMenu identity probe during Stage-7 task authoring (don't guess).

### C. Convention amendment (WI-6.6, pre-capture, signed)
Edit `m1-verifier-convention.md` rows for `auth-oauth-02` (page_url tolerance + callback-POST gate),
add `capture_mode: interactive` note and the rows 03–05 lineage requirement. Signed commit **before**
capture (convention forbids attestation-time edits).

### D. Attestation + seal (WI-6.7)
Run with `VERIFICATION=1` → hand run dir + convention to an **independent verifier agent**. Verifier
spot-checks `trace.zip` locally (row 04 restore), then trace destroyed. Redact (FR-9) → seal
`attestation.json` + manifest + PNGs + `verify-oauth-deploy.txt` in a GPG-signed commit under
`docs/cleanup-pristine/evidence/m1/wi6-preprod/`. `.gitignore` any storageState/auth artifacts.

## Constitution / Standards Check

| Gate | Status |
|---|---|
| No new AWS resources without asking | PASS — IdP is created by *existing* module code the tfvars line activates; no hand-authored net-new resource. FR-8 guard is shell, not infra. Watch plan for surprises. |
| Google-only (Q-M1-1); never "GitHub" | PASS — tfvars is `["Google"]` only. |
| GPG-signed commits; secrets never in git/chat | PASS — runbook keeps secrets on owner's machine; FR-9 redaction; `.gitignore` auth artifacts. |
| Independent verifier; no self-attestation | PASS — FR-7 separate agent + local trace spot-check. |
| No mocked auth on preprod target | PASS — no route interception; interactive real login. |
| Branch/PR hygiene | PASS — #932 stays intact on this branch; FR-8 guard + specs land as separate PRs off fresh main. |

## Adversarial Review #2

Read the full suite (spec + plan) focusing on drift introduced by the Stage-4 clarifications and on
cross-artifact consistency with the actual harness (`verification.ts`) and app (`SessionProvider`).

| Severity | Drift / inconsistency | Resolution |
|---|---|---|
| **HIGH** | **Canonical convention vs. app reality.** Row `auth-oauth-04` mandates "zero `anonymous 201`," but root-layout `SessionProvider` (`app/layout.tsx:54`) mints one inherent guest on the clean-context signin load; `forbid` counts spec-wide at teardown (`verification.ts:322-330`) and cannot be scoped post-login. The rule as written would hard-fail on correct behavior. | Amend row-04 to `max_count:1` (amendment (d)); "no silent re-guest" carried by the row-04 identity-equality probe. Spec DoD + plan §B updated. |
| **MEDIUM (drift from C1)** | plan §B referenced a `[data-testid=...google...]` selector; C1 established the button has **no** data-testid. | plan §B fixed to `text=Continue with Google` (accessible name, `oauth-buttons.tsx:65`). |
| **MEDIUM** | Manifest `target` self-labels `preprod` only if `PREPROD_FRONTEND_URL` === the exact Amplify URL (`verification.ts:174-178`); a wrong/missing value silently yields `localhost-mock` → convention hard-fail, wasting a capture. | plan §B "Run config" note added; becomes an explicit Stage-7 task + a pre-capture assertion. |
| **LOW** | Row-02 `auth_requests` are per-step (reset each `shot`); the callback POST must be captured in the step where it lands. | plan §B: fire the row-02 `shot` **after** the listener sees `POST /oauth/callback 200`. |
| **LOW (consistency confirmed)** | redirect_uri `origin+pathname` = `.../auth/callback` (C3) matches the Cognito callback allowlist (EC-6); scopes `email profile openid` match `google.tf:23` and the runbook. | No action; verified consistent. |

**Gate: 0 CRITICAL, 0 HIGH remaining.** The one HIGH (convention-vs-reality) is resolved by amendment
(d) which lands in the same signed pre-capture convention edit already required. Drift from clarifications
reconciled. Proceed to Stage 6.
