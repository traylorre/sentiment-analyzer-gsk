# Tasks: M1 Phase C Seal — WI-6 Google OAuth Full-Harness Attestation

**Feature Branch**: `1388-m1-phase-c-seal`
**Spec**: `specs/1388-m1-phase-c-seal/spec.md` · **Plan**: `specs/1388-m1-phase-c-seal/plan.md`

Legend: `🔒` owner-gated · `⛔ BLOCKS` hard precondition · `[1384]` depends on Feature 1384 verified · `[#934]` depends on PR #934 merged.

## Phase 0 — Preconditions (gates for everything below)

- **T001 [#934] (FR-1) ⛔ BLOCKS T004** Merge PR #934 (branch `m1-wi6-preprod-verification`) to `main`.
  Confirm CI green + no open CodeQL/Dependabot alerts (pre-push checklist); rebase on `main` if stale,
  favor `main` for unrelated cleanup files. Verify post-merge that `frontend/tests/e2e/auth-oauth.spec.ts`,
  `scripts/redact-oauth-evidence.py`, `specs/1375-*`, and `m1-verifier-convention.md` amendments **(a)–(e)**
  are on `main`. **Requirements**: FR-1.
- **T002 🔒 [1384] ⛔ BLOCKS T004** Confirm Feature 1384 (session persistence; in-repo `specs/1381-oauth-session-persistence/`,
  fix commit `6a33c1c`) is **verified working on preprod**: `POST /api/v2/auth/refresh 200` for an OAuth session
  and identity preserved across reload. "Verified" = observed/attested on preprod, not merely merged. If NOT
  verified: STOP — either wait for 1384 or invoke the partial-seal decision (spec Clarification Q2). **Requirements**:
  FR-9. **[owner + 1384]**

## Phase A — Deploy re-verification (maps 1375 T009)

- **T003 (FR-2)** Run `./scripts/verify-oauth-deploy.sh preprod`; capture stdout →
  `docs/cleanup-pristine/evidence/m1/wi6-preprod/verify-oauth-deploy.txt`. Confirm: Lambda
  `ENABLED_OAUTH_PROVIDERS=google`, Cognito IdP `["Google"]`, app-client includes `Google`, `/oauth/urls` 200
  non-empty. The unrelated WAF gate may be RED (EC-4) — not a blocker. **Requirements**: FR-2.

## Phase B — Capture (maps 1375 T010) — highest-risk, single-shot

- **T004 🔒 [1384][#934] (FR-3)** Owner-assisted **headed interactive single-window** capture. Depends on T001
  (harness + amendment (e)) and T002 (1384 verified). Run config: `PREPROD_FRONTEND_URL` + `baseURL` =
  `https://main.d29tlmksqcx494.amplifyapp.com` (exact — a mislabel silently downgrades the manifest to
  `localhost-mock`, a convention hard-fail); `VERIFICATION=1`; **clean context** (cookies cleared). Row 01
  headless-automatable; rows 02→03→04→05 in one interactive block from **one real owner Google login**
  (lineage-tied). `forbid anonymous 201 max_count:1` for row-04. No route interception. Produces run dir:
  `auth-oauth.manifest.json` + step PNGs + `trace.zip`. **Requirements**: FR-3. **[owner + 1384 + #934]**

## Phase C — Independent attestation (maps 1375 T011) — independence gate

- **T005 (FR-4) ⛔ Verifier ≠ implementer** Invoke an **independent verifier agent in a fresh context with no
  implementer carryover**; hand it ONLY the run-dir paths + `m1-verifier-convention.md`. Verifier: (1) validates
  manifest schema, hard-fails on `interception_at_capture: true` / `target: localhost-mock`; (2) judges rows 01–05
  vs the canonical table; (3) opens `trace.zip` locally and records in the attestation reason BOTH — row-02
  authenticity (`POST /oauth/callback 200` + `id_token.iss = accounts.google.com`, quoted) AND row-04 restore
  (`POST /refresh 200`, restored `user_id` == row-03); (4) writes `attestation.json` with per-row `{verdict,
  reason}`, `verifier` identity (≠ implementer), `convention_version` git sha, `hard_fail_checks`, `overall`.
  **Requirements**: FR-4. If `overall` ≠ `pass`: STOP, do not seal, file the failing row(s) as defects.

## Phase D — Redact + destroy trace (maps 1375 T012)

- **T006 (FR-5) ⛔ BLOCKS T008** Run `python scripts/redact-oauth-evidence.py auth-oauth.manifest.json`, then
  `--check` MUST exit 0 (no `code`/`state`/`access_token`/`id_token`/`refresh_token` params, no JWT-shaped
  strings). Inspect the row-02 PNG for any in-page-rendered token. **Requirements**: FR-5.
- **T007 (FR-6) ⛔ BLOCKS T008 — only after T005 records both trace checks** Destroy `trace.zip` (and any
  `storageState`/auth artifact). Confirm `.gitignore` covers them and `git status` shows none staged. The trace
  MUST die AFTER T005's row-02 + row-04 checks and BEFORE any seal. **Requirements**: FR-6.

## Phase E — Seal + close (maps 1375 T012/T013)

- **T008 🔒 (FR-7)** Stage ONLY `attestation.json` + `auth-oauth.manifest.json` + step PNGs +
  `verify-oauth-deploy.txt` under `docs/cleanup-pristine/evidence/m1/wi6-preprod/` (retain go-live
  `ATTESTATION.md` — append-only). Pre-sign gate: `git diff --cached` clean of token-shaped strings / `code=` /
  `trace.zip`. `git commit -S` (GPG-signed); `git verify-commit` passes. **Requirements**: FR-7. **[owner GPG]**
- **T009 (FR-8)** Update `docs/cleanup-pristine/milestone-1-verifiable-auth.md` WI-6 → DONE (reference T008 commit
  sha); update memory `m1-milestone-progress.md` → **M1 6/6**. **Requirements**: FR-8.
- **T010 🔒 (FR-8)** Owner closes GitHub Milestone #1 via `gh`, noting out-of-charter debt (prod rollout, WAF,
  alerts snake_case, magic-link). **Requirements**: FR-8. **[owner]**

## Requirement → Task Coverage

| Requirement | Task(s) |
|---|---|
| FR-1 merge PR #934 | T001 |
| FR-2 deploy re-verification | T003 |
| FR-3 headed interactive capture | T004 |
| FR-4 independent verifier attestation | T005 |
| FR-5 redact + `--check` gate | T006 |
| FR-6 destroy trace, never seal | T007 |
| FR-7 GPG-signed seal | T008 |
| FR-8 mark 6/6 + close milestone | T009, T010 |
| FR-9 row-04/05 gate on 1384 | T002, T004 |

Every FR maps to ≥1 task; no orphan tasks.

## Adversarial Review #3 (highest-risk + likely rework + gate)

**Highest-risk task: T004 (capture) coupled with T005 (attestation).** The dominant failure is **sealing
incomplete or leaky evidence, or attesting without true independence**:
- *Leaky/incomplete seal*: a token survives into the signed, append-only commit, or rows 04/05 are sealed on a
  still-broken session. Mitigated by T006 `--check` gate + T007 never-seal-the-trace + T008 pre-sign diff scan
  (leak), and T002/FR-9 1384-verified precondition (false-green restore).
- *Attesting without independence*: the sharpest structural risk — if T005's verifier shares the implementer's
  context, the "independent attestation" is theater. Mitigated by invoking the verifier in a **fresh context**,
  handing it only paths + convention, and recording a `verifier` identity ≠ implementer plus quoted trace
  ground-truth (row-02 `iss`) that a forger cannot fabricate. This remains a **process gate, not a cryptographic
  one** — the top residual risk, carried from AR#1/AR#2.

**Most likely rework**: a wasted single-shot capture (T004) — exact-URL mislabel → `localhost-mock` hard-fail, or
Cognito session reuse → false green surfaced late by the row-02 `iss` check, or 1384 not actually verified so
row-04 fails. Each is a full re-run with the owner. Pre-empted by the T004 run-config note, amendment (e), and
the T002 gate.

**Status: BLOCKED.** Two hard preconditions unmet at plan time: **T001 (PR #934 not yet merged)** and **T002
(Feature 1384 not yet verified working on preprod)**; **T004/T008/T010 are owner-gated**. Ready to execute the
moment T001 + T002 clear and the owner is available for the interactive login. **Gate: 0 CRITICAL, 0 HIGH
unresolved; 2 process-gate residual risks tracked (verifier independence; 1384-verified).**
