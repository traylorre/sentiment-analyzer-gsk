# Implementation Plan: M1 Phase C Seal — WI-6 Google OAuth Full-Harness Attestation

**Feature Branch**: `1388-m1-phase-c-seal`
**Spec**: `specs/1388-m1-phase-c-seal/spec.md`
**Status**: Draft (planning only — implementation is an evidence-capture + seal process, not code)

## Technical Context

**Language/Runtime**: TypeScript 5 / Playwright 1.57+ (headed capture), Python 3.13 (redaction gate), Git + GPG (seal), `gh` CLI (milestone close). No AWS resources created (constraint).
**Primary artifacts (all pre-existing, arriving via PR #934)**:
- `frontend/tests/e2e/auth-oauth.spec.ts` — rows `auth-oauth-01..05`, headed interactive block (FR-3 substrate).
- `frontend/tests/e2e/helpers/verification.ts` — `verify.shot`/`verify.forbid`, response listener, manifest writer.
- `frontend/tests/e2e/schemas/{verification-manifest,attestation}.schema.json` — validation.
- `scripts/redact-oauth-evidence.py` — FR-5 redaction + `--check` gate.
- `scripts/verify-oauth-deploy.sh` — FR-2 deploy re-verification.
- `docs/cleanup-pristine/m1-verifier-convention.md` — pass/fail authority + canonical table + amendments (a)–(e).
**Evidence path**: `docs/cleanup-pristine/evidence/m1/wi6-preprod/` (already holds go-live `ATTESTATION.md` + `verify-oauth-deploy.txt`).
**Constraints**: append-only git history; GPG-signed seal commit; the trace is NEVER committed; redaction verified before any seal; independent verifier ≠ implementer.
**Out of scope**: any code fix (esp. the `/auth/refresh` 401 — that is Feature 1384 / in-repo 1381); prod rollout; WAF; alerts snake_case; magic-link.

## Hard Dependencies (must all be satisfied before capture)

1. **PR #934 merged to `main`** — supplies the harness spec, redaction script, and convention amendments (FR-1). Without it there is nothing to run and the convention lacks amendment (e).
2. **Feature 1384 (session persistence) VERIFIED working** — `POST /api/v2/auth/refresh 200` for the OAuth session and identity preserved across reload, so rows 04/05 can pass (FR-9). In-repo planning `specs/1381-oauth-session-persistence/`; live fix commit `6a33c1c` (branch `1381-session-persistence`). "Verified" = attested/observed on preprod, not merely merged.
3. **Owner available for one live interactive Google login** — rows 02–05 are CI-irreproducible; Google bot-detects headless (FR-3).

## Capture → Verify → Redact → Seal Sequence (mapped from 1375 T009–T013)

The core of this feature is a strict 5-stage pipeline. Each stage gates the next.

### Stage A — Deploy re-verification (1375 **T009** → FR-2)
Run `./scripts/verify-oauth-deploy.sh preprod`. Confirm: Lambda `ENABLED_OAUTH_PROVIDERS=google`, Cognito IdP `["Google"]`, app-client supported IdPs include `Google`, `/oauth/urls` 200 with the Google provider. Capture stdout → `docs/cleanup-pristine/evidence/m1/wi6-preprod/verify-oauth-deploy.txt` (overwrite/confirm current). The unrelated WAF integration gate may be RED (EC-4, `specs/1375-.../tasks.md` T009) — not a blocker.

### Stage B — Owner-assisted headed interactive capture (1375 **T010** → FR-3)
Run config (the exact-URL note prevents a `localhost-mock` hard-fail downgrade):
- `PREPROD_FRONTEND_URL` = `https://main.d29tlmksqcx494.amplifyapp.com` (exact Amplify URL); Playwright `baseURL` identical.
- `VERIFICATION=1` (→ `trace: 'on'`), headed, **clean browser context** (cookies cleared).
- Row 01 (`signin-buttons`): `goto('/auth/signin')`, assert `GET /oauth/urls 200` non-empty, `verify.shot` with Google-button probe.
- Rows 02–05 in one interactive block: click "Continue with Google" → **owner completes the real Google login** → capture callback (`POST /oauth/callback 200`), identity (UserMenu ≠ "Guest"), F5 restore (`POST /refresh 200`, same identity), `/alerts` page.
- `forbid` rule for row-04: `anonymous 201 max_count:1` (convention amendment (d)).
Produces the run directory: `auth-oauth.manifest.json` + step PNGs + `trace.zip`.

### Stage C — Independent verifier attestation (1375 **T011** → FR-4)
Hand the run directory + `m1-verifier-convention.md` to an **independent verifier agent** invoked in a **fresh context with no implementer carryover**. The verifier:
1. Validates the manifest against `verification-manifest.schema.json`; hard-fails on `interception_at_capture: true` or `target: localhost-mock`.
2. Judges rows 01–05 against the canonical expected-state table (screenshot + `page_url` + `main_status` + required `auth_requests` + `dom_probe` + `forbidden_requests`).
3. Opens `trace.zip` locally and records BOTH ground-truth checks in the attestation reason:
   - **Row-02 authenticity (amendment (e))**: `POST /oauth/callback 200` present AND `id_token.iss = accounts.google.com` (quoted).
   - **Row-04 restore**: at the reload boundary, `POST /refresh 200` and restored `user_id` == row-03.
4. Writes `attestation.json` (schema `attestation.schema.json`) with per-row `{verdict, reason}`, `verifier` identity (≠ implementer), `convention_version` git sha, `hard_fail_checks`, `overall`.

### Stage D — Redact + destroy trace (1375 **T012** → FR-5, FR-6)
Only on `overall: pass` AND after Stage C's trace checks are recorded in `attestation.json`:
1. `python scripts/redact-oauth-evidence.py auth-oauth.manifest.json` (scrub row-02 `code=`/token params), then `--check` MUST exit 0.
2. Inspect the row-02 PNG for any in-page-rendered token.
3. **Destroy `trace.zip`** (and any `storageState`/auth artifact). Confirm `.gitignore` covers them; confirm `git status` shows no trace/storageState staged.

### Stage E — GPG-signed seal + milestone close (1375 **T012/T013** → FR-7, FR-8)
1. Stage ONLY: `attestation.json`, `auth-oauth.manifest.json`, step PNGs, `verify-oauth-deploy.txt` under `docs/cleanup-pristine/evidence/m1/wi6-preprod/` (go-live `ATTESTATION.md` retained — append-only).
2. Pre-sign gate: `git diff --cached` scanned for token-shaped strings / `code=` / `trace.zip` — must be clean.
3. `git commit -S` (GPG-signed). `git verify-commit` passes.
4. Update `milestone-1-verifiable-auth.md` WI-6 → DONE (reference the commit sha); memory `m1-milestone-progress.md` → M1 6/6.
5. Owner closes GitHub Milestone #1 via `gh`, noting out-of-charter debt (prod rollout, WAF, alerts snake_case, magic-link).

## PR #934 Merge Plan (FR-1)

PR #934 (branch `m1-wi6-preprod-verification`) is large (273 files) and mixes the WI-6 harness prep with cleanup-campaign docs and dead-code removal. Plan:
1. Confirm PR #934 CI is green and no open CodeQL/Dependabot alerts (pre-push checklist).
2. Rebase on `main` if stale; resolve conflicts favoring `main` for unrelated files.
3. Merge to `main` (squash), which lands `auth-oauth.spec.ts`, `redact-oauth-evidence.py`, the `specs/1375-*` suite, and the `m1-verifier-convention.md` amendments (a)–(e) — the substrate the capture and verifier require.
4. Only after merge is on `main` does Stage A begin. The convention amendment (esp. (e) — row-02 `id_token.iss` check) MUST be present before any capture, per `specs/1375-.../tasks.md` T004 (⛔ BLOCKS T010).

## Row-04/05 Dependency on Feature 1384 (FR-9)

Row-04 (`auth-oauth-04-post-reload`) requires `POST /refresh 200` with identity preserved. Until Feature 1384's session-persistence fix is **verified working on preprod**, that leg 401s (go-live `ATTESTATION.md`, Known gap #4) and row-04 fails by design. Stage B MUST NOT be run for a 6/6 seal until 1384 is verified. If the owner elects a partial seal (rows 01–03 + 05), the milestone stays below 6/6 and row-04 remains the single tracked open item (spec Clarification Q2).

## Adversarial Review #2 (drift + cross-artifact + gate)

| Check | Finding | Resolution |
|---|---|---|
| **Drift vs spec** | Plan Stages A–E map 1:1 to spec FR-2→FR-8; FR-1 (merge) and FR-9 (1384 gate) are called out as preconditions, not stages. | Consistent. Stage ordering enforces "trace destroyed only after both spot-checks" (FR-6 after FR-4). |
| **Cross-artifact: convention amendment (e)** | Row-02 authenticity check exists in `m1-verifier-convention.md` only if PR #934's amendment landed. | FR-1 / merge-plan step 4 make amendment (e) a hard precondition of Stage B (mirrors `specs/1375-.../tasks.md` T004 ⛔). |
| **Cross-artifact: schemas** | Attestation/manifest schemas live in `frontend/tests/e2e/schemas/`, delivered by PR #934. | Verifier validates against them in Stage C; hard-fail on schema mismatch (convention "Hard-fail rules"). |
| **Naming drift: 1384 vs 1381** | Spec cites "Feature 1384 (session persistence)"; in-repo the planning dir is `specs/1381-oauth-session-persistence/` and the fix is commit `6a33c1c`. | Documented explicitly in both artifacts as the same dependency to avoid a dangling reference; "verified working" defined as preprod-observed `/refresh 200`. |
| **Constraint: no new AWS** | Every stage is capture/verify/redact/seal + a `gh` milestone close; `verify-oauth-deploy.sh` is read-only queries. | No resource creation. Compliant. |
| **Gate** | 0 CRITICAL, 0 HIGH. Top residual risks (fresh-context verifier separation; 1384-verified precondition) are carried into tasks.md as explicit gates. | **READY for tasks.** |
