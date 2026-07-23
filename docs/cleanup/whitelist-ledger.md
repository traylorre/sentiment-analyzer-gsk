# Whitelist Ledger: one-file-at-a-time cleanup loop

Purpose: seed the sequential processing loop for repo cleanup. This document maps terrain only. **Nothing is whitelisted without a citation. Zero files are modified by this run. No fix is recommended or performed here.**

Branch: `Q-pin-hcl2`. All loci below are drawn from the reconciled findings JSON of this MAPPING run.

---

## (a) File Manifest: category counts

Source: `git ls-files | awk -F/ '{print $1}' | sort | uniq -c` (re-verified this run). Total tracked = **2659**.

| Top-level tree | Tracked files |
|---|---|
| specs | 1415 |
| tests | 375 |
| frontend | 278 |
| docs | 204 |
| src | 171 |
| infrastructure | 94 |
| scripts | 39 |
| .specify | 20 |
| reports | 13 |
| .github | 10 |
| interview | 4 |
| chaos-plans | 2 |
| loose root files | 32 |

Evidence: manifest domain, `git ls-files` this session, EXACT match on every named count; `git ls-files | grep -v '/' | wc -l` = 32.

---

## (b) Proposed Processing Order

Safest / most-isolated first; infra + CI-gated last. **The sequencing itself is an analyst recommendation (verdict UNKNOWN in the manifest domain), not a proven repo fact**, the underlying anchors are real, but the ordering is unproven until a later run builds the Python import graph and the Terraform module dependency graph.

| Tier | Scope | Rationale | Gate |
|---|---|---|---|
| 1 | Tracked CONTEXT-CARRYOVER pile + build/errata cruft | Most isolated; no runtime import surface | none |
| 2 | Docs drift / misleading comments | `docs/` = 204 files with no runtime import; comment fixes touch no execution path | none |
| 3 | Dead code (unreferenced src/tests modules) | Requires import-graph proof before firming | import graph pending |
| 4 | Infrastructure / HCL | Referenced by `main.tf`, gated by `.github/workflows/deploy.yml` | CI-gated; TF module dep graph pending |

OPEN QUESTION (manifest, UNKNOWN): a later run must build the actual Python import graph (unreferenced src/tests modules) and the Terraform module dependency graph before firming the dead-code and infra tiers.

---

## (c) Ledger Schema

| path | verdict (KEEP / DELETE-CANDIDATE / RECONCILE / UNKNOWN) | evidence (file:line or grep-absence) | whitelisted (yes/no) |
|---|---|---|---|

---

## (d) Seed Rows: citation-backed only

Each row below carries its citation from this run. `whitelisted = no` for every row: whitelisting is a decision for the processing loop, not this map. UNKNOWN rows are OPEN QUESTIONS pending the evidence noted, never settled facts.

| path | verdict | evidence (file:line or grep-absence) | whitelisted |
|---|---|---|---|
| src/lambdas/ingestion/storage.py `store_news_items()` / `store_news_items_with_notification()` | DELETE-CANDIDATE | defs at storage.py:50 and :281; `grep -rn store_news_items src/ tests/` → only internal storage.py refs + tests; live path uses upsert_article_with_source (handler.py:87-91 import, :1006 call); dedup.py:152 | no |
| CONTEXT-CARRYOVER-2026-02-03-session4.md (root) | DELETE-CANDIDATE | tracked; `git ls-files \| grep -i CONTEXT-CARRYOVER` | no |
| CONTEXT-CARRYOVER-2026-02-03-session5.md (root) | DELETE-CANDIDATE | tracked; `git ls-files \| grep -i CONTEXT-CARRYOVER` | no |
| specs/1219-xray-exclusive-tracing/context-carryover-r21.md | DELETE-CANDIDATE | tracked; `git ls-files \| grep -i CONTEXT-CARRYOVER` | no |
| specs/1219-xray-exclusive-tracing/context-carryover-r22.md | DELETE-CANDIDATE | tracked; `git ls-files \| grep -i CONTEXT-CARRYOVER` | no |
| infrastructure/terraform/modules/dynamodb/main.tf | RECONCILE | :20 comment `# String (e.g., "newsapi#abc123def456")` misleads, live source_id is `dedup:<sha256>` (dedup.py:183, :98); :69 `projection_type = "ALL" # Minimal storage for monitoring` self-contradictory | no |
| src/lambdas/analysis/sentiment.py | RECONCILE | :10 and :36 docstrings claim model at `/opt/model` (Lambda layer); live loader uses `/tmp/model` (:60) + S3 download (:70); no `aws_lambda_layer_version` in terraform (grep exit 1) | no |
| src/lambdas/analysis/handler.py | RECONCILE | :43 docstring `/opt/model` (Lambda layer) contradicts S3→/tmp live path | no |
| specs/1159-samesite-cors-update/spec.md | RECONCILE | :5, :9, :10, :48 describe pre-Amplify "CloudFront frontend / Lambda Function URL backend" world (stale) | no |
| specs/1159-samesite-cors-update/plan.md | RECONCILE | :5 same stale pre-Amplify architecture | no |
| src/lambdas/shared/models/news_item.py `to_dynamodb_item()` | RECONCILE | :108 emits PK/SK (`NEWS#{dedup_key}` :101, `{source}#{ingested_at}` :106) that shares no primary-key attr with live `source_id`/`timestamp` schema (dedup.py:183, :197, :244-251) | no |
| src/dashboard/index.html (HTMX admin dashboard) | UNKNOWN | serve_index dev-gated (handler.py:384-389, :139-146 fail-closed); no API Gateway route to `/` (main.tf:877-892); STATIC_DIR confined to handler.py (:168,:170,:389,:410,:444) | no |
| src/dashboard/* (favicon/static assets under `/` route) | UNKNOWN | handler.py:408 (favicon), :429 (static) share dev-only gate; no deploy smoke HTTP GET (deploy.yml:708-715, :1766-1795 import-only) | no |
| index.html (repo root) | UNKNOWN (state ORPHANED by in-repo evidence) | 338-byte meta-refresh + JS redirect to `interview/`; `grep pages .github/workflows/` → rc=1; `grep github.io/gh-pages/nojekyll .github/` → rc=1 | no |
| .nojekyll (repo root) | UNKNOWN (state ORPHANED by in-repo evidence) | 0 bytes (`wc -c`); no in-repo Pages pipeline references it | no |
| Makefile `test-mutation` target (mutmut) | DELETE-CANDIDATE | Makefile:135-141 guarded stub; `grep mutmut` requirements*/pyproject/pre-commit/workflows → only Makefile:135/137/138/140; no config, no pin, no CI | no |

---

## OPEN QUESTIONS (verdict UNKNOWN: not settled)

| Question | Evidence still needed |
|---|---|
| Processing-order sequencing | Python import graph + Terraform module dependency graph (manifest) |
| Is src/dashboard HTMX `/` route reachable via API Gateway / Function URL post-Feature-1256? | Confirm whether the dashboard Lambda Function URL is publicly invokable at all after the 1256 restriction (route list + dev-gate already verified) |
| Do any E2E tests HTTP-GET the `/` route (vs in-process unit tests)? | grep tests/e2e for an HTTP GET to `/` on a deployed Function URL; re-open the 4 cited unit files for line-level assertions |
| Is src/dashboard `/` truly vestigial? | Whether any README/docs published-URL link or external consumer references the deployed dashboard root (in-repo absence is suggestive, not proof) |
| Which of the 3 index.html surfaces actually publishes via GitHub Pages? | Server-side Settings→Pages (not observable from checkout); confirm `interview/` is intended public target |

---

## Corrections carried from this run (map-relevant)

- Root `index.html` is a redirect to `interview/`, **not** a dashboard stub, the earlier "TWO index.html dashboard stubs" claim is REFUTED (3 tracked index.html: root, interview/, src/dashboard/).
- CONTEXT-CARRYOVER "~33 files" is REFUTED for **tracked** files, only **4** are tracked; the ~33 are untracked and gitignored (`.gitignore` patterns `CONTEXT-CARRYOVER*.md`, `CONTEXT-CARRYOVER*.md.loaded`), so a tracked-file ledger cannot touch them.
- `/api/v2/runtime` SSE-URL leak is dev-environment-only (handler.py:619 gate), REFUTED as an unconditional prod issue.
- The bundled "ALL docs still pre-Amplify" claim is REFUTED, README.md:252, CHANGELOG.md:39, and the main diagram are current; only specs/1159 remains genuinely stale.

**Reminder: no file above is whitelisted, and this run modified nothing.**
