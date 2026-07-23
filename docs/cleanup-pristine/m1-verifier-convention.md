# M1 Verifier Convention

WI-2 of `milestone-1-verifiable-auth.md`. This document is the pass/fail authority
for Milestone 1 evidence. The manifest's `expected_ui_state` prose is written by the
implementer and is informational only; verdicts come from the canonical table below.

## Who verifies

A separate agent that did NOT write or run the tests. The implementer (human or
agent) never attests their own evidence. The verifier receives file paths and this
document, nothing else from the implementer's session state.

## What the verifier consumes

All of these, never just the PNGs:

1. `{spec}.manifest.json` (validates against
   `frontend/tests/e2e/schemas/verification-manifest.schema.json`)
2. Every step screenshot (`{spec}-{NN}-{step}.png`), viewed, not just listed
3. The manifest sidecars per step: `page_url`, `main_status`, `auth_requests`,
   `api_errors`, `console_errors`, `page_errors`, `dom_probe`,
   `interception_at_capture`
4. For restore-critical steps (`auth-guest-03`, `auth-oauth-04`): the raw
   Playwright trace (`trace.zip` from the same run, produced because verification
   runs set `VERIFICATION=1` → `trace: 'on'`). Spot-check procedure below.

## Pass rule (per step)

A step passes only if ALL hold:

1. The screenshot matches the step's row in the canonical expected-state table.
2. `page_url` matches the row (a redirect-to-signin fails a step that expects a
   content page; a pretty error page with a 200 fails on the DOM probe).
3. `main_status` matches the row (default: 200).
4. Required `auth_requests` entries for the row are present with the required
   statuses. 2xx entries are recorded by the pipeline, so absence is evidence.
5. `console_errors` and `page_errors` are empty unless the row grants an explicit
   allowlist.
6. The DOM probe hit (`present: true`, and `text_match: true` where the row
   requires text).
7. Every `forbidden_requests` entry in the manifest has `pass: true`.

Verdicts per step: `pass` | `fail` | `suspicious` (evidence is internally
inconsistent or insufficient to judge; suspicious is never rounded up to pass).
The overall verdict is `pass` only if every step passes.

## Hard-fail rules (non-negotiable)

- Any `target: preprod` step with `interception_at_capture: true`, or a manifest
  `interception.clean: false`: **overall fail**, regardless of screenshots. A
  mocked run against the real URL is the exact failure mode this contract kills.
- Any `forbidden_requests` entry with `pass: false`: **overall fail**.
- `target: localhost-mock` evidence: never counts toward a DoD; attest it
  `suspicious` with reason "wrong target" if submitted for a DoD.
- Manifest fails schema validation: **overall fail** (evidence pipeline itself is
  broken or tampered).

## Trace spot-check (restore-critical steps)

For `auth-guest-03-post-reload` and `auth-oauth-04-post-reload`:

1. Open the run's Playwright trace (`npx playwright show-trace <trace.zip>` or
   unzip and read `trace.network` entries directly).
2. Locate the reload boundary; list every `/api/v2/auth/*` request after it.
3. Compare against the manifest's `auth_requests` for that step: same set, same
   statuses. Any divergence: the step is `suspicious` at best — the manifest is
   implementer-built and the trace is the ground truth.

## Where attestations live

`attestation.json` is written into the same run's verification directory, next to
the manifest it judges, and sealed per trust contract item 7 (append-only,
GPG-signed commit under `docs/cleanup-pristine/evidence/m1/`). An attestation not
hash-referenced from a signed evidence commit is not a completion certificate.
Schema: `frontend/tests/e2e/schemas/attestation.schema.json`.

## Canonical expected-state table

One row per DoD step in the milestone. The verifier judges against THESE rows.
"Auth log" entries are required `{method path status}` in that step's
`auth_requests`. Rows for later WIs may be refined by their WI before capture, via
an edit to this table in a signed commit — never at attestation time.

| Step | WI | Screenshot must show | page_url | Auth log (required) | Probe | Extra |
|---|---|---|---|---|---|---|
| `infra-smoke-01-landing` | 1 | Customer dashboard landing: sidebar nav, ticker search, header present; no raw error text | Amplify domain `/` | none required | `header` present | interception false; forbidden anonymous-201>1 holds |
| `auth-guest-01-landing` | 3 | Header UserMenu shows "Guest" | `/` | `POST /api/v2/auth/refresh 401` (cold-load restore attempt, no cookie yet) then `POST /api/v2/auth/anonymous 201` | UserMenu w/ text "Guest" | console allowlist (this step only): the single browser-logged `Failed to load resource ... 401` from that restore attempt. Restore-first makes it inherent |
| `auth-guest-02-menu-open` | 3 | Open menu: Guest identity + anonymous "Sign in with email" upsell item (session-remaining chip renders in the HEADER trigger area, not the menu; WI-3 reality correction) | `/` | none additional | `text=Sign in with email` present | |
| `auth-guest-03-post-reload` | 3 | Same UI as 01, still "Guest" | `/` | `POST /api/v2/auth/refresh 200`; NO new `anonymous 201` | UserMenu "Guest"; user_id equality vs step 01 verified from response bodies in the TRACE | forbidden `anonymous 201 max_count:1` holds; TRACE SPOT-CHECK |
| `auth-guest-04-alerts-redirect` | 5 | Guest bounced off `/alerts` | redirect destination (signin), NOT `/alerts` | per WI-5 fix direction (Q-M1-2) | — | row updates when Q-M1-2 resolves |
| `next-version.txt` | 4 | n/a (text artifact) | n/a | n/a | n/a | installed Next.js >= 14.2.25; guest set re-captured green against bumped build |
| `auth-oauth-01-signin-buttons` | 6 | Google button visible on signin page | `/auth/signin` | `GET /api/v2/auth/oauth/urls 200` (non-empty providers) | Google button selector | |
| `auth-oauth-02-callback-return` | 6 | Callback completing (loading/redirect state acceptable) | `/auth/callback*` | `POST /api/v2/auth/oauth/callback 200` | — | |
| `auth-oauth-03-identity` | 6 | UserMenu shows non-Guest display name or masked email; session chip in open menu | `/` | none additional | UserMenu, text NOT "Guest" | |
| `auth-oauth-04-post-reload` | 6 | Same identity as 03 after F5 | `/` | `POST /api/v2/auth/refresh 200` | identity probe equal to step-03 | forbidden: zero `anonymous 201` in oauth spec; TRACE SPOT-CHECK |
| `auth-oauth-05-alerts-page` | 6 | Alerts page rendered for the signed-in Google user | ends `/alerts` | none additional | named alerts-page selector present | |

## Attestation contents

Per step: `{step, verdict, reason}` where reason states WHICH criteria carried the
verdict (e.g. "screenshot shows Guest chip; anonymous 201 present in auth log;
probe text matched; forbidden rule holds"). Plus: `overall` verdict, `run_id`,
`spec`, `verifier` (model/agent identity string), `convention_version` (git sha of
this file at attestation time), `hard_fail_checks` (each rule above with its
boolean), and `timestamp`.
