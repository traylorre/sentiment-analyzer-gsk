# Open Questions: Cleanup Mapping Run

Purpose: decision nodes that CANNOT yet be answered from in-repo evidence. Each node states the question, candidate answers, and the exact evidence needed to resolve it. Nothing here is settled fact. No fixes recommended, terrain only.

---

## Q-HTMX (PRIMARY): Is the `src/dashboard` HTMX dashboard vestigial?

The umbrella question: is the HTMX admin dashboard (`serve_index` / the `/` route serving `src/dashboard/index.html`) still a reachable, consumed feature, or dead-in-prod cruft? Four sub-questions feed it. Three are UNKNOWN; one factual sub-claim (deploy smoke) is CONFIRMED but its "vestigial" conclusion is deferred. DO NOT ANSWER, collect the evidence first.

### Candidate answers
- **A. Vestigial / dead-in-prod**, dev-only route gate, no API Gateway forwarding, no inbound links, import-only smoke → safe delete candidate.
- **B. Still reachable**, via direct Function URL post-1256, or an external consumer not visible in-repo.

### Sub-nodes and evidence-to-resolve

| Sub-question | Verdict | What's already anchored | Evidence still needed |
|---|---|---|---|
| Reachable through API Gateway? | UNKNOWN | Route list is 12 entries `main.tf:877-892`, all `/api/v2/*` + `health` (`:887`) + `api/v2/runtime`; NO `path_parts=[]`, no root `/` or `{proxy+}` at api-root. `serve_index` gates on `_is_dev_environment()` (`handler.py:384-389`), fail-closed (`handler.py:139-146`) → 404 in preprod/prod. | Confirm whether the dashboard Lambda **Function URL** is publicly invokable at all post-Feature-1256 restriction (route-list + dev-gate already verified). |
| Any tests target the HTMX `/` route? | UNKNOWN | Four cited test files exist as tracked: `tests/unit/lambdas/dashboard/test_serve_index.py`, `tests/unit/test_dashboard_handler.py`, `tests/unit/dashboard/window_export_registry.py`, `tests/e2e/test_metrics_auth.py`. | Grep `tests/e2e` for an actual HTTP GET to `/` on a deployed Function URL (distinguish "tested code" from "reachable feature"); re-open the unit files to confirm their line-level assertions. |
| Anything link to / consume the route or `STATIC_DIR`? | UNKNOWN | `grep -rn STATIC_DIR src/` → only `handler.py:168,170,389,410,444` (confined). No tracked `frontend/`/`interview/` file hyperlinks to the Lambda `/` HTMX page. | Whether any README/docs published-URL link or an **external** consumer references the deployed dashboard root, in-repo absence is suggestive, not proof of vestigial. |
| In any deploy smoke test? | CONFIRMED (factual sub-claim) | `deploy.yml:708-715` and `:1766-1795` "Smoke Test Dashboard Lambda Imports" run `docker run ... python -c "from handler import lambda_handler..."`, pure IMPORT checks, no HTTP GET. `grep -rniE 'src/dashboard\|serve_index\|htmx' .github/ scripts/` → exit 1. | Factual claim closed; the downstream **"vestigial"** conclusion is deferred to a later run (import-only smoke + dev-only gate + no inbound links together support it). |

---

## Other Open Questions (UNKNOWN verdict)

### OQ-1: Processing order for the one-file whitelist ledger
**Domain:** manifest · **Verdict:** UNKNOWN

The proposed sequencing (CONTEXT-CARRYOVER pile / build errata → docs drift → dead code → infra last) is an analyst recommendation, not a repo fact. The underlying anchors are real (infra modules referenced by `main.tf`, gated by `.github/workflows/deploy.yml`; `docs/` = 204 files with no runtime import), but the ordering itself is unproven.

**Evidence still needed:** Build the actual Python import graph (unreferenced `src/`/`tests` modules) and the Terraform module dependency graph before firming the dead-code and infra tiers.

---

## Latent Bugs: LOG-ONLY, FIX OUT OF SCOPE

Both are CONFIRMED defects. Recorded here for the ledger; this run does not touch them.

### LB-1: Cross-source dedup merge never fires (tz-offset mismatch)
**Domain:** deadcode · **Verdict:** CONFIRMED

Tiingo emits tz-aware UTC datetimes (`tiingo.py:237-239` → `isoformat` yields `...+00:00`); Finnhub emits naive (`finnhub.py:227` `datetime.fromtimestamp(...)` → no offset suffix). The DynamoDB range-key `timestamp = published_at.isoformat()` (`handler.py:1005`) therefore never matches across sources, so `update_item` (`dedup.py:197`) targets a non-existent Key → `ConditionalCheckFailed` → `get_item` fallback (`dedup.py:229-230`) finds nothing → a SECOND row is created instead of merging; the "updated" branch (`dedup.py:220`) cannot fire cross-source. The `source_id=dedup:{sha256}` key itself DOES match (date-only, `dedup.py:65,88-98,183`), only the timestamp offset suffix diverges. (Correction on record: the decisive factor is the `+00:00` suffix presence/absence, which holds unconditionally; the prior "wall-clock shift" claim is TZ-dependent and does not occur under Lambda default `TZ=UTC`.)

### LB-2: `/api/v2/runtime` hands the browser the raw IAM-locked SSE Function URL (dev-only)
**Domain:** deadcode · **Verdict:** CONFIRMED

`get_runtime_config` (`handler.py:612-633`) gates on `_is_dev_environment()` (`handler.py:619`, def `:139-146`, fail-closed); in dev it returns `sse_url: SSE_LAMBDA_URL or None` (`:621`), else `sse_url: None` (`:625-628`). `SSE_LAMBDA_URL` (`handler.py:109`) is wired from `module.sse_streaming_lambda.function_url` (`main.tf:501`), which is `AWS_IAM`-auth (`main.tf:825`, Feature 1256; wired via `modules/lambda/main.tf:143-148`). An unsigned browser `EventSource` against an `AWS_IAM` Function URL gets 403. So dev-environment frontends are handed a URL the browser cannot use directly; preprod/prod hand out `None`.

**Evidence still needed (impact only, not fix):** Whether any dev-environment frontend actually consumes `runtime.sse_url` to open a direct `EventSource` (vs. routing through the CloudFront OAC origin at `main.tf:960` / `modules/cloudfront_sse`). Consumer-side confirmation not performed.

---

*All loci above are quoted from the reconciled findings JSON for this run. No citation or line number was invented.*
