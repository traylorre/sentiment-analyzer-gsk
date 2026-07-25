# Feature Specification: M1 Phase C Seal — WI-6 Google OAuth Full-Harness Attestation

**Feature Branch**: `1388-m1-phase-c-seal`
**Created**: 2026-07-24
**Status**: Draft (planning only — no implementation in this pipeline)
**Milestone**: GitHub Milestone #1 "Verifiable user-auth (non-SSE)" — this feature closes it at **6/6**.
**Target**: Customer Dashboard (Next.js/Amplify) on preprod — `https://main.d29tlmksqcx494.amplifyapp.com/`.
**Input**: Google OAuth login is LIVE and works end-to-end (sealed as a go-live attestation in PR #939,
`docs/cleanup-pristine/evidence/m1/wi6-preprod/ATTESTATION.md` + `verify-oauth-deploy.txt`). What remains
is NOT code — it is the **evidence trust-contract seal**: the full `auth-oauth-01..05` instrumented-harness
capture that #939 explicitly deferred, independently attested and sealed, after which Milestone #1 is marked 6/6.

---

## 1. Context & Framing

This is a **seal-and-close feature, not a build feature**. The four coupled OAuth parts are wired (spec
`specs/1375-wi6-google-oauth-enablement/spec.md`, §1), the deploy is verified
(`scripts/verify-oauth-deploy.sh preprod` all PASS, captured at
`docs/cleanup-pristine/evidence/m1/wi6-preprod/verify-oauth-deploy.txt`), and a real owner Google login
completed end-to-end (`ATTESTATION.md`, "Human-witnessed login (row 01–03 equivalent)").

The go-live seal was **honestly scoped**: it attests OAuth *enablement* + a human-witnessed login, but NOT the
full instrumented `auth-oauth-01..05` harness. Rows **04/05** (post-reload session restore) were deferred
because a real post-login defect — `POST /api/v2/auth/refresh` returning 401 for the OAuth session — prevented
the session from persisting across reload (`ATTESTATION.md`, "Known gaps" #2/#3/#4).

That defect is being fixed under the session-persistence feature (**battleplan Feature 1384**; in-repo planning
lives at `specs/1381-oauth-session-persistence/spec.md`, live fix commit `6a33c1c` on branch
`1381-session-persistence`). **Feature 1388 does not fix any code.** It runs the capture→verify→redact→seal
harness once 1384 is verified working, and marks the milestone complete.

### What this feature produces (the deliverable is the seal itself)
The DoD deliverable is a **GPG-signed, append-only evidence commit** under
`docs/cleanup-pristine/evidence/m1/wi6-preprod/` containing an independent verifier's `attestation.json` (rows
01–05 all `pass`), the run's `auth-oauth.manifest.json`, the step PNGs, and the existing `verify-oauth-deploy.txt`
— with **zero live credentials** and **no Playwright trace** committed. The harness spec
(`frontend/tests/e2e/auth-oauth.spec.ts`), the redaction gate (`scripts/redact-oauth-evidence.py`), and the
canonical convention amendment all arrive via **PR #934** (branch `m1-wi6-preprod-verification`), which must be
merged first.

---

## 2. User Scenarios & Testing *(mandatory)*

### User Story 1 — Owner trusts the result without opening a browser (Priority: P1)

As the repository owner, when I look at Milestone #1's scoreboard I want it to read 6/6 **because an independent
verifier sealed a signed attestation against the canonical expected-state table** — not because an agent told me
"OAuth works." I should never have to re-open a browser, re-run a test, or take the implementer's word for it. The
sealed artifacts (screenshots + manifest + verdict) must be self-contained enough that any third party can
re-judge rows 01, 03, 05 from the commit alone, and the ephemeral trace-only checks (rows 02, 04) must be quoted
as ground-truth evidence inside the attestation reason.

**Why this priority**: This is the entire point of the trust contract
(`docs/cleanup-pristine/milestone-1-verifiable-auth.md`, "Trust contract"). Without it the milestone is a claim.

**Independent Test**: Hand a third party only the sealed commit + `m1-verifier-convention.md`. They can confirm
each row's verdict from the screenshots/manifest and read the verifier's quoted trace evidence for rows 02/04,
and reach the same overall `pass` — without any session state from the implementer.

**Acceptance Scenarios**:
1. **Given** the sealed evidence commit, **When** the owner reads `attestation.json`, **Then** every row
   `auth-oauth-01..05` has verdict `pass`, `overall: pass`, a `verifier` identity string that is NOT the
   implementer, and a `convention_version` git sha.
2. **Given** the sealed commit, **When** the owner runs `git verify-commit <sha>`, **Then** the GPG signature
   verifies.
3. **Given** the sealed commit diff, **When** anyone greps it for token-shaped strings or a `code=` param,
   **Then** none are present and no `trace.zip` is committed.

### User Story 2 — Independent verifier attests against ground truth, not the manifest (Priority: P1)

As a verifier agent who did **not** implement or run the capture, I judge rows 01–05 against the canonical table
and spot-check the raw Playwright trace **locally** for the two checks that cannot be forged from the
implementer-built manifest: row-04 restore (`/refresh 200`, same `user_id`) and row-02 authenticity
(`POST /oauth/callback 200` **and** `id_token.iss = accounts.google.com`). Only after both are recorded in my
attestation is the trace destroyed and the safe artifacts sealed.

**Why this priority**: The `capture_mode: interactive` run is CI-irreproducible; the trace is the only ground
truth proving a *real Google* leg vs a reused Cognito session. This is convention amendment (e) and the AR#3
compensating control (`m1-verifier-convention.md`; `specs/1375-.../tasks.md` T004/T011).

**Independent Test**: Give the verifier only the run directory + the convention. They produce
`attestation.json` with per-row `{verdict, reason}` naming which criterion carried each verdict, and the row-02
`id_token.iss` value quoted from the trace.

**Acceptance Scenarios**:
1. **Given** the run directory, **When** the verifier opens `trace.zip`, **Then** they locate `POST /oauth/callback
   200` and confirm `id_token.iss = accounts.google.com` before the trace is destroyed.
2. **Given** the reload boundary in the trace, **When** the verifier lists `/api/v2/auth/*` after it, **Then**
   `POST /refresh 200` is present, the restored `user_id` equals row-03's, and no unexpected `anonymous 201` appears.
3. **Given** any manifest with `interception_at_capture: true` or `target: localhost-mock`, **Then** the verifier
   returns overall `fail`/`suspicious` and nothing is sealed.

### User Story 3 — Milestone closes honestly at 6/6 (Priority: P2)

As the campaign lead, once the seal exists I want `milestone-1-verifiable-auth.md` (WI-6) and the memory
scoreboard flipped to DONE / M1 6/6, and the GitHub Milestone #1 closed — with out-of-charter debt (prod
rollout, WAF, alerts snake_case, magic-link) explicitly noted, not silently absorbed.

**Why this priority**: Depends on Stories 1–2 landing; it is the bookkeeping that makes "done" visible.

**Acceptance Scenarios**:
1. **Given** the sealed attestation, **When** WI-6 is updated, **Then** its status reads DONE with the evidence
   commit sha referenced, and the milestone reads 6/6.
2. **Given** M1 6/6, **When** GitHub Milestone #1 is closed, **Then** the closure notes list the deferred
   out-of-charter items.

### Edge Cases

- **Row-04/05 depend on Feature 1384.** If the session-persistence fix (battleplan 1384 / in-repo 1381, `/auth/refresh`
  401) is not verified working at capture time, rows 04/05 cannot pass and the milestone cannot honestly hit 6/6.
  The capture (T010) is **blocked** on 1384 being verified, not merely merged. See Clarification Q3.
- **Google bot-detection.** Rows 02–05 cannot be headless — Google bot-detects automated browsers on its consent
  screen; every headless path to `POST /oauth/callback 200` is blocked or a false-green via Cognito session reuse
  (`specs/1375-.../spec.md` FR-6, R-3). Capture is headed, interactive, single-window, clean context; the owner
  performs one real Google login.
- **Trace redaction incompleteness.** The trace carries live refresh tokens and the callback `code`; the manifest
  can carry the `code=` `page_url`; a row-02 PNG could in-page-render a token. The trace is **never** sealed; the
  manifest is scrubbed by `scripts/redact-oauth-evidence.py` (SENSITIVE_QUERY_KEYS + JWT regex) and gated with
  `--check` (exit non-zero if anything token-shaped survives) before signing.
- **False green via session reuse.** A lingering Cognito hosted-UI cookie can yield `POST /oauth/callback 200` with
  no real Google leg. Mitigated by clean context per capture + the row-02 `id_token.iss` trace check.
- **Partial-seal temptation.** If only rows 01–03 + 05 pass (1384 not done), a partial seal MUST NOT be labeled
  6/6. Either wait for 1384, or (owner decision) seal 01–03/05 and keep row-04 as the single tracked open item —
  the milestone stays 5.x/6, not 6/6. See Clarification Q2.

---

## 3. Requirements *(mandatory)*

### Functional Requirements

- **FR-1 (merge the harness prep).** PR #934 (branch `m1-wi6-preprod-verification`) MUST be merged to `main`
  first: it delivers `frontend/tests/e2e/auth-oauth.spec.ts` (rows `auth-oauth-01..05`),
  `scripts/redact-oauth-evidence.py`, the `specs/1375-*` suite, and the `m1-verifier-convention.md` amendments
  (a)–(e). No capture may run against preprod before this lands.
- **FR-2 (deploy re-verification).** `./scripts/verify-oauth-deploy.sh preprod` MUST pass (Lambda env non-empty,
  Cognito IdP present, Lambda↔Cognito consistency, `/oauth/urls` 200 with ≥1 provider); its stdout is the sealed
  `verify-oauth-deploy.txt`. Maps 1375 **T009**. (The go-live capture of this file already exists; re-confirm it
  is current at seal time.)
- **FR-3 (headed interactive capture — rows 01–05, single window).** An owner-assisted **headed, interactive,
  single-window** Playwright run captures all five canonical rows: `PREPROD_FRONTEND_URL` and `baseURL` set to the
  exact Amplify URL, `VERIFICATION=1` (trace on), **clean browser context** (cookies cleared so the Google leg
  genuinely runs). Row 01 is headless-automatable; rows 02→03→04→05 run in one interactive block from **one real
  owner Google login**, lineage-tied to that login. `capture_mode: interactive` (not headless-repeatable). No
  route interception; no mocked auth on preprod (convention hard-fail). Maps 1375 **T010**.
- **FR-4 (independent verifier attestation).** The run directory + `m1-verifier-convention.md` are handed to an
  **independent verifier agent that did not implement or run the capture**. The verifier judges rows 01–05 against
  the canonical expected-state table and, from the raw `trace.zip` **locally**, spot-checks BOTH: row-04 restore
  (`POST /refresh 200`, restored `user_id` == row-03) AND row-02 authenticity (`POST /oauth/callback 200` present
  AND `id_token.iss = accounts.google.com`). The attestation records verifier identity, `convention_version` git
  sha, per-row `{verdict, reason}`, and the quoted row-02 `iss`. The implementer NEVER self-attests. Maps 1375
  **T011**; convention "Who verifies" + amendment (e).
- **FR-5 (redact before seal — FR-9 gate).** Before any commit, `scripts/redact-oauth-evidence.py <manifest>
  --check` MUST exit 0 (no `code`/`state`/`access_token`/`id_token`/`refresh_token` query params, no JWT-shaped
  strings) on the manifest, and the row-02 PNG MUST be inspected for in-page token render. A manual `git diff`
  scan for token-shaped strings runs before signing. Maps 1375 **T012**/FR-9.
- **FR-6 (destroy the trace; never seal it).** The Playwright `trace.zip` MUST be destroyed **after** the verifier
  records the row-02 + row-04 checks and **before** the seal, and MUST never enter a sealed path. `storageState`/
  auth artifacts are `.gitignore`d. A sealed, GPG-signed, append-only commit is the worst possible place for a
  refresh token. Maps 1375 **T012**/FR-7.
- **FR-7 (GPG-signed seal under the evidence path).** On overall `pass` and after FR-5/FR-6, seal `attestation.json`
  + `auth-oauth.manifest.json` + step PNGs + `verify-oauth-deploy.txt` in a **GPG-signed** commit under
  `docs/cleanup-pristine/evidence/m1/wi6-preprod/`. Verify zero live credentials in the diff before signing. The
  existing go-live `ATTESTATION.md` is preserved (append-only) alongside the new Phase C attestation.
- **FR-8 (mark milestone 6/6 + close).** Update `docs/cleanup-pristine/milestone-1-verifiable-auth.md` WI-6 → DONE
  (referencing the evidence commit sha), and the memory scoreboard `m1-milestone-progress.md` → M1 6/6. Close
  GitHub Milestone #1, noting out-of-charter debt (prod rollout, WAF, alerts snake_case, magic-link). Maps 1375
  **T013**.
- **FR-9 (row-04/05 gate on 1384).** The capture (FR-3) MUST NOT proceed to a 6/6 seal until the session-persistence
  fix (Feature 1384 / in-repo 1381) is **verified working** — `POST /api/v2/auth/refresh 200` for the OAuth session
  and identity preserved across reload. Row-04 = post-reload restore is the direct dependency.

### Key Entities

- **Phase C attestation (`attestation.json`)**: independent verifier's signed judgment of rows 01–05; schema
  `frontend/tests/e2e/schemas/attestation.schema.json`. Sealed, hash-referenced from the signed commit.
- **Run manifest (`auth-oauth.manifest.json`)**: implementer-built per-step sidecars (`page_url`, `main_status`,
  `auth_requests`, `forbidden_requests`, `dom_probe`, `interception_at_capture`); informational for prose, judged
  against the canonical table. Redacted before seal.
- **Playwright trace (`trace.zip`)**: ephemeral ground truth for rows 02/04; spot-checked locally, then destroyed;
  **never** sealed.

## 4. Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-1**: Independent verifier's `attestation.json` shows rows `auth-oauth-01..05` all `pass` and `overall: pass`,
  with `verifier` ≠ implementer identity.
- **SC-2**: The evidence commit under `docs/cleanup-pristine/evidence/m1/wi6-preprod/` is GPG-signed
  (`git verify-commit` passes) and append-only (go-live `ATTESTATION.md` retained).
- **SC-3**: Zero live credentials in the sealed diff (`redact-oauth-evidence.py --check` exit 0; no `code=`; no
  JWT-shaped string; no `trace.zip`).
- **SC-4**: Row-02 authenticity is proven from the trace (`id_token.iss = accounts.google.com`) and quoted in the
  attestation reason; row-04 restore (`/refresh 200`, same `user_id`) confirmed from the trace.
- **SC-5**: `milestone-1-verifiable-auth.md` WI-6 = DONE, milestone = 6/6, GitHub Milestone #1 closed with
  out-of-charter debt noted.

## Adversarial Review #1

Independent reviewer (security-first) attacked the **trust contract** of this seal.

| Severity | Finding | Resolution |
|---|---|---|
| CRITICAL | **Can the implementer forge the attestation?** Within one battleplan/human session, "independent verifier" is procedural, not cryptographic — the same operator could write both the manifest and the verdict. | The seal is valid ONLY if the verifier runs as a **genuinely separate context** (fresh agent/subagent invocation) receiving only file paths + the convention, no implementer session state (`m1-verifier-convention.md`, "Who verifies"). Compensating ground truth: rows 01/03/05 are **re-judgeable by any third party from the sealed screenshots+manifest alone**, so a forged verdict is falsifiable post-hoc; row-02/04 rest on the trace, so the attestation MUST quote the exact trace evidence (`id_token.iss`, restored `user_id`) — a claim a forger cannot fabricate without the real login. `attestation.json.verifier` MUST NOT equal the implementer identity. **Residual accepted**: a single owner who runs both roles dishonestly defeats any in-repo control; the mitigation is falsifiability, not prevention. Gated. |
| CRITICAL | **Does the trace leak a refresh token if redaction misses a field?** `trace:'on'` records full bodies incl. refresh tokens; a missed manifest field or an in-page-rendered PNG could bake a live credential into signed, append-only history. | Two independent barriers: (1) the trace is **never sealed at all** (FR-6) — it is `.gitignore`d and destroyed, so a redaction miss on the trace cannot reach history; (2) the manifest is scrubbed and **`--check`-gated** (FR-5) — `SENSITIVE_QUERY_KEYS` {code,state,access_token,id_token,refresh_token} + a JWT regex belt-and-suspenders (`scripts/redact-oauth-evidence.py`), plus a manual `git diff` token-shape scan and a row-02 PNG in-page-render inspection before signing. Pre-seal `git status` MUST confirm no `trace.zip`/`storageState` staged. Gated. |
| HIGH | **Is independent-verifier separation actually enforceable inside one agent session?** If the implementer subagent and verifier subagent share context, separation is theater. | Enforce by construction: the verifier is invoked as a **fresh context with no carryover** and is handed only the run-dir paths + convention doc; it emits `attestation.json` with its own `verifier` identity string and `convention_version` sha. The implementer does not edit the attestation. This is a process gate the tasks encode (independent-verifier task marked BLOCKED-until-separate); it is auditable via the `verifier` field but not cryptographically enforced — flagged as the top residual risk. |
| HIGH | **Row-04/05 sealed on a still-broken session (1384 not verified).** Sealing 04/05 while `/refresh` still 401s would seal a false green. | FR-9: capture-to-6/6 is **gated on Feature 1384 verified working**, not merged. If 1384 is not verified, rows 04/05 cannot pass and 6/6 is not claimed (partial-seal edge case → milestone stays 5.x/6). |
| MEDIUM | Reusing the go-live `ATTESTATION.md` as if it were the harness attestation. | Distinct artifacts: go-live `ATTESTATION.md` (human-witnessed, honest partial) is retained append-only; Phase C adds a **separate** `attestation.json` (instrumented rows 01–05). FR-7. |
| MEDIUM | `verify-oauth-deploy.txt` staleness — the sealed infra file could predate a later drift. | FR-2: re-run `verify-oauth-deploy.sh preprod` at seal time and confirm the captured file is current before sealing. |

**Gate: 0 CRITICAL, 0 HIGH unresolved.** Both CRITICALs resolved by falsifiability + never-seal-the-trace; the
two HIGHs are process gates (fresh-context verifier; 1384-verified precondition) tracked as the top residual
risks and encoded in tasks.md. **Proceed to Plan.**

## Clarifications

Self-answered from repo evidence; the owner-timing and 1384-dependency items are deferred open questions.

1. **Does 1388 fix the `/auth/refresh` 401 defect?** No. That is Feature 1384 (in-repo `specs/1381-oauth-session-persistence/`,
   fix commit `6a33c1c`). 1388 is seal-only and consumes 1384's verified result (FR-9).
2. **If 1384 isn't verified at capture time, can we seal rows 01–03 + 05 and still call M1 6/6?** No — rows 04/05
   are DoD-blocking (`m1-verifier-convention.md` canonical table; `milestone-1-verifiable-auth.md` WI-6 DoD). A
   partial seal keeps row-04 as the single open item and the milestone stays below 6/6. **[Deferred: owner decides
   whether to wait for 1384 or accept a partial seal.]**
3. **When does the owner perform the single interactive Google login?** Owner-scheduled; the capture is
   CI-irreproducible and needs the owner live in one window. **[Deferred: owner picks the capture window, after
   1384 is verified and PR #934 is merged.]**
4. **Does the Phase C seal overwrite the go-live `ATTESTATION.md`?** No — append-only. Phase C adds
   `attestation.json` + `auth-oauth.manifest.json` + PNGs alongside it (FR-7).
5. **How is GitHub Milestone #1 closed?** Owner-gated via `gh` (milestone close / final issue), with out-of-charter
   debt noted in the closure (FR-8).
