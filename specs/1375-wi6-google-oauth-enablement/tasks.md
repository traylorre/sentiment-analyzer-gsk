# Tasks: M1 WI-6 — Verifiable Google OAuth Enablement (preprod)

**Feature:** 1375-wi6-google-oauth-enablement · **Spec:** ./spec.md · **Plan:** ./plan.md

Legend: `[P]` = parallelizable with the owner-gated credential steps. Gate markers: 🔒 owner-gated.

## Phase A — Pre-work (no owner gate; do before the merge)

- **T001 [P] (FR-5, WI-6.6)** Author `frontend/tests/e2e/auth-oauth.spec.ts`. **Author-only before the
  gate — do NOT execute against preprod before T008's apply**: `/oauth/urls` is empty and the Google
  button absent until then, so a pre-gate run is red *by design*, not a spec defect (the mid-sequence
  trap). Green execution happens only in T010.
  - Header `// Target: Customer Dashboard (Next.js/Amplify)`; `import { test, expect } from
    './helpers/verification'`; response listener (no `page.route`).
  - `verify.forbid({method:'POST', path:'/api/v2/auth/anonymous', status:201, max_count:1})`.
  - Row 01 (`signin-buttons`): `goto('/auth/signin')`; assert listener saw `GET /oauth/urls 200`
    non-empty; `verify.shot('signin-buttons',{probe:{selector:'text=Continue with Google'}})`.
  - Rows 02–05 in one interactive block: clean context → click Google → **owner completes Google login**
    → `verify.shot('callback-return')` after listener sees `POST /oauth/callback 200`
    → `shot('identity')` (probe `[data-testid="user-menu-trigger"]` text ≠ "Guest")
    → F5 → `shot('post-reload')` (`/refresh 200`, identity == row-03)
    → `goto('/alerts')` → `shot('alerts-page')`.
- **T002 [P] (FR-5, C4)** During T001 authoring, confirm real selectors in-app (don't guess): signed-in
  UserMenu identity probe (`user-menu.tsx:75/82`) and the alerts-page landmark selector. Record in T001.
- **T003 [P] (FR-8, EC-1/EC-2, R-4)** Author the pre-apply poison guard: a shell check (`aws`+`jq`) that
  fails if `preprod.tfvars` `cognito_identity_providers` contains "Google" while the `google-oauth`
  secret's `client_id` is empty. **Placement (exact):** in the deploy-preprod job **after** "Configure
  AWS Credentials", **before** "Terraform Plan" (so creds exist to read the secret and it *prevents*, not
  just detects). **Match must be HCL-aware** (comment-stripped — a naive `grep "Google"` false-matches
  the tfvars comment block), e.g. `terraform console`/`jq`-parse rather than `grep`. Only fails on the
  exact poison combo (Google-in-tfvars + empty secret); prod unaffected (no Google in prod.tfvars). Ship
  as its own small PR off fresh `origin/main` (keep #932 a clean one-line diff).
- **T004 [P] (convention; ⛔ BLOCKS T010 — must be a signed commit BEFORE any capture)** Amend
  `docs/cleanup-pristine/m1-verifier-convention.md` rows per plan: (a) row-02 `page_url {/auth/callback*,
  /}` + callback-POST gate; (b) `capture_mode: interactive`; (c) rows 03–05 lineage-tied; (d) row-04
  forbidden `anonymous 201 max_count:1`; **(e) row-02 trace spot-check (AR#3): the verifier confirms in
  the raw trace, before destruction, both `POST /oauth/callback 200` AND that the returned `id_token`'s
  `iss` = `accounts.google.com` — proving a real Google leg, not a reused Cognito session. This is the
  compensating control that makes `capture_mode: interactive` sound.** Convention forbids attestation-time
  edits, so this lands first.
- **T005 [P] (FR-9, R-2)** Add `.gitignore` entries for Playwright `storageState`/auth artifacts and the
  run's `trace.zip`. Author the seal-time redaction step and **enumerate exactly the sealed fields it
  scrubs**: manifest step `page_url` (`code=` param), any `auth_requests`/body `access_token`/`id_token`/
  `refresh_token`. **Also confirm the row-02 PNG does not render `code`/token text in-page** (screenshots
  are viewport-only with no URL bar, so a raster leak is unlikely, but an in-page render would evade text
  redaction). Sealed set must carry zero live creds.

## Phase B — Owner-gated (🔒 blocking; owner performs; secrets never in chat/git)

- **T006 🔒 (FR-2, runbook Step A, DQ-2/DQ-3)** Owner creates the Google OAuth **Web application** client;
  redirect URI exactly `https://preprod-sentiment-218795110243.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`;
  scopes `email profile openid`; captures client_id/secret.
- **T007 🔒 (FR-1, Step B)** Owner `put-secret-value` into `preprod/sentiment-analyzer/google-oauth`
  (valid JSON `{"client_id","client_secret"}`); verifies `keys` == `["client_id","client_secret"]`.
- **T008 🔒 (FR-3, Step C, EC-3)** Owner marks **PR #932 ready → merge**. deploy.yml auto-applies. FR-8
  guard (T003) must be merged first so it can block a mis-sequenced apply. **Watch the plan for
  unexpected `preprod-dashboard` Lambda changes (Issue #491) — stop and `terraform import` if seen.**

## Phase C — Post-apply (automated after the single apply)

- **T009 (FR-4, WI-6.5)** Run `./scripts/verify-oauth-deploy.sh preprod`; capture stdout →
  `docs/cleanup-pristine/evidence/m1/wi6-preprod/verify-oauth-deploy.txt`. (Expect the unrelated WAF
  integration gate RED, EC-4 — not a blocker.)
- **T010 🔒 (FR-6, WI-6.7)** Owner-assisted **headed interactive** capture: `PREPROD_FRONTEND_URL` set to
  the exact Amplify URL, Playwright `baseURL` same, `VERIFICATION=1`, clean context. Owner completes the
  one real Google login. Produces the run dir (manifest + PNGs + trace).
- **T011 (FR-7)** Hand the run dir + `m1-verifier-convention.md` to an **independent verifier agent**
  (never the implementer). Verifier judges rows 01–05 vs the canonical table and, from the raw
  `trace.zip` locally, spot-checks **both**: row-04 restore (`/refresh 200`, same user_id) **and row-02
  authenticity (amendment (e)) — `POST /oauth/callback 200` present AND `id_token.iss =
  accounts.google.com`.** Row-02's Google provenance is confirmed from ground truth, not the
  implementer's manifest.
- **T012 (FR-7, FR-9)** On PASS **and after** the T011 trace spot-checks are recorded in the
  attestation: run the T005 redaction; **then destroy the trace** (never before the row-02 + row-04
  checks); seal `attestation.json` + `{spec}.manifest.json` + step PNGs + `verify-oauth-deploy.txt` in a
  **GPG-signed commit** under `docs/cleanup-pristine/evidence/m1/wi6-preprod/`. Verify zero live creds in
  the diff before signing.
- **T013** Update memory `m1-milestone-progress.md`: WI-6 done → **M1 6/6**. Note prod rollout + M1 debt
  (WAF, alerts snake_case, magic-link) remain out of charter.

## Analyze — Requirement → Task Coverage

| Requirement | Task(s) | Covered |
|---|---|---|
| FR-1 single-apply consistency | T007, T008 | ✅ |
| FR-2 owner runbook | plan §Runbook, T006 | ✅ |
| FR-3 tfvars enablement (Google-only) | T008 (PR #932) | ✅ |
| FR-4 deploy verification | T009 | ✅ |
| FR-5 instrumented specs | T001, T002 | ✅ |
| FR-6 real-identity headed capture | T010 | ✅ |
| FR-7 independent attestation + seal | T011, T012 | ✅ |
| FR-8 pre-apply poison guard | T003 | ✅ |
| FR-9 evidence redaction | T005, T012 | ✅ |
| EC-1/EC-2 poison IdP | T003 (guard) + T008 sequencing | ✅ |
| EC-3 #491 drift | T008 (watch/import) | ✅ |
| EC-4 WAF red herring | T009 (noted, not a blocker) | ✅ |
| EC-5 redirect URI | T006 (exact URI) | ✅ |
| EC-6 callback allowlist | C3 (already present) + T009 | ✅ |
| DoD rows auth-oauth-01..05 | T001, T004, T010, T011 | ✅ |
| Convention amendment (a-d) | T004 | ✅ |

**Coverage: every FR and edge case maps to ≥1 task.** No orphan requirements; no task without a
requirement. `verify-oauth-deploy.sh` (FR-4) and the OAuth code (all FRs' substrate) pre-exist.

## Adversarial Review #3

Independent reviewer read spec + plan + tasks together against ground truth (deploy.yml apply sequence,
google.tf gate, main.tf wiring, live convention). Findings and resolutions:

| Severity | Finding | Resolution |
|---|---|---|
| HIGH | Row-02 Google-authenticity was verifier-unconfirmable: trace destroyed after the row-04 check only, so the Google leg was judged from the implementer-built manifest — a self-assertion loophole in `capture_mode: interactive`. | **Amendment (e) added** (T004): verifier spot-checks row-02 in the trace — `POST /oauth/callback 200` + `id_token.iss = accounts.google.com` — before destruction. T011/T012 reordered so trace dies only after both checks. |
| MEDIUM | FR-8 guard placement/match under-specified (needs creds; naive `grep "Google"` false-matches the tfvars comment). | T003: pinned to post-"Configure AWS Credentials"/pre-"Terraform Plan"; HCL-aware (comment-stripped) match. |
| MEDIUM | T001 `[P]` for authoring but green execution is gated on T008's apply; risk of misreading a pre-gate red as a spec bug. | T001: "author-only; do not execute pre-gate; empty-providers red is expected." |
| LOW | T004 is a hard precondition of T010, not a peer `[P]`. | T004 marked "⛔ BLOCKS T010". |
| LOW | T005 didn't enumerate scrubbed fields or the in-page-render risk. | T005: field list enumerated + row-02 PNG in-page-render check added. |
| (cleared) | FR-8 feasibility, T003/T008 merge-timeline safety, no surviving contradictions. | Reviewer confirmed guard is essential (not scope creep) and the merge timeline has no poison window. |

**Highest-risk task: T010** (owner-assisted headed interactive capture) — single-shot, CI-irreproducible,
three distinct waste/false-green modes (target-mislabel → `localhost-mock` hard-fail; Cognito session
reuse → false green; trace token leak). Amendment (e) + the exact-URL config note are its guardrails.

**Most likely rework:** a wasted/re-run interactive capture (T010) — target-mislabel silently
downgrading the manifest to `localhost-mock`, or the row-02 authenticity check surfacing late. Both are
now pre-empted by the plan §B run-config note and amendment (e).

**Gate: 0 CRITICAL, 0 HIGH remaining. READY FOR IMPLEMENTATION.**
