# Repo Cleanup: Sign-Post Maps (MAPPING run)

Branch `Q-pin-hcl2`. These maps exist so a later execution run cannot wander into
rabbit holes. This run mapped terrain and planted sign-posts. It did not fix, delete,
edit, or refactor anything. Not one line of `src/`, `frontend/src/`, `*.tf`, or a test
was touched. The only files written were these documents under `docs/cleanup/`.

Every claim in every map cites a real `file:line` that was opened this run, or a
grep-proven absence. Comments, READMEs, SPEC.md, ADRs, and CHANGELOGs are treated as
suspects to reconcile against real source, never as evidence. Anything that could not be
pinned to a live locus is left as an OPEN QUESTION with the exact evidence needed to
resolve it. Optimism count: zero.

## The maps

| Map | What it answers |
|---|---|
| [url-inventory.md](url-inventory.md) | Every URL/endpoint surface, LIVE / DISABLED / ORPHANED, with emitter→consumer wiring. The anti-rabbit-hole map. |
| [dependency-map.md](dependency-map.md) | Workstream DAG (WS0-WS5), what blocks what, parallel-safe set, and CI-cost ordering so CI waits are rare and batched. |
| [open-questions.md](open-questions.md) | Decision nodes that cannot yet be answered. Q-HTMX first, fully scoped but deliberately unanswered. |
| [whitelist-ledger.md](whitelist-ledger.md) | The one-file-at-a-time processing loop: file manifest, proposed order, ledger schema, seeded rows. Nothing whitelisted without a citation. |
| [validator-inventory.md](validator-inventory.md) | Every validator's true run-state (declared / wired / actually runs) and activation cost. |
| [diagram-drift.md](diagram-drift.md) | WS0 chart verification, full repo sweep. 56 confirmed drifts across 16 diagram files (chaos docs describe deleted code, ops runbook gives wrong remediation, security doc off by 60x). Plus the honest import-graph outcome. |

## How this was built

An adversarial two-pass workflow. For each domain (urls, comments, dead-code, validators,
manifest+Q-HTMX) one agent re-verified every seeded citation against live source, then an
independent skeptic re-opened each locus and re-ran each grep, defaulting any thin or
line-drifted claim to UNKNOWN. Only claims that survived a personal re-check kept a
CONFIRMED / LIVE / DISABLED / ORPHANED verdict. The five maps were then synthesized from
the reconciled findings only. 15 agents, zero errors.

## Where the seeded priors were wrong (refutation deltas)

The value of the refute pass is this list. Each item was a prior belief carried into the
run that did not survive re-verification:

- **`/api/v2/runtime` "would 403" was stated as unconditional.** Refuted. The raw
  IAM-locked SSE Function URL is handed to the browser only in dev; the non-dev branch
  returns `sse_url: None` (gate at `src/lambdas/dashboard/handler.py:619`, leak at `:621`).
  Still worth logging, but dev-scoped, not an always-on prod bug.
- **`hypothesis` property tests "never run."** Refuted. They are collected and do run in
  the CI pytest job via `pyproject.toml` `testpaths`. What is true: they never run in the
  pre-commit push hook (scoped to `tests/unit`). "Dead validator" was the wrong frame.
- **"README, CHANGELOG, specs/1159, and diagrams ALL still describe the pre-Amplify world."**
  Refuted. Only `specs/1159-*` is genuinely stale. README:249/252, CHANGELOG:39, and the
  main diagram were re-checked and are already current.
- **Dashboard Function URL disabled at `main.tf:615`.** That line is the *notification*
  Lambda. The dashboard disable is `main.tf:508`.
- **Cognito circular-dependency patch is a `null_resource`.** It is `terraform_data
  "cognito_callback_patch"` (`main.tf:1316`).
- **`module.amplify_frontend` at `main.tf:1320`.** Off by ~36; the module is at `main.tf:1284`.
- **CONTEXT-CARRYOVER pile as a flat DELETE-CANDIDATE, and "two index.html files."** Both
  refuted as too coarse. The pile needs per-file handling, and there are three
  GitHub-Pages / index.html surfaces (root stub redirecting to `interview/`, `interview/`,
  and `src/dashboard/`), not two.

## What is confirmed and ready for the execution run

- **Dead code (confirmed):** `src/lambdas/ingestion/storage.py` `store_news_items()` /
  `store_news_items_with_notification()` have no caller in `src/` (grep-proven). The live
  persistence path is `handler.py` → `dedup.py:upsert_article_with_source`.
- **Misleading comments (confirmed):** the `dynamodb/main.tf` `source_id` example and the
  `by_status` "minimal storage" comment (projection is `ALL`), and the `sentiment.py` /
  `analysis/handler.py` "/opt/model layer" docstrings (live path downloads from S3 to
  `/tmp/model`). Details and loci in `url-inventory.md` and the reconciled findings.
- **URL surface (confirmed):** dashboard Function URL DISABLED; frontend routes through API
  Gateway; SSE infra is LIVE but the frontend never reads `NEXT_PUBLIC_SSE_URL` (it builds
  the stream URL from `NEXT_PUBLIC_API_URL`), so the emitted var is orphaned at the consumer.
- **WAF (confirmed live):** two live modules, `module.waf` (REGIONAL, Feature 1254) and
  `module.waf_cloudfront` (CLOUDFRONT, Feature 1255). No orphaned refs found.

## Deliberately not decided here

- **Q-HTMX**: whether `src/dashboard/` is vestigial. Scoped in `open-questions.md`, not
  answered. Three of four sub-questions remain UNKNOWN pending the evidence listed there.
- **Whitelist processing order**: left UNKNOWN pending an actual import graph
  (`src`/`tests` unreferenced modules) and the Terraform module dependency graph.
- **WS5 git-history hygiene**: settled, not a gate: append-only, keep history, no rewrite.
- Two latent bugs (cross-source dedup tz mismatch; the dev-only SSE URL exposure) are
  logged in `open-questions.md` as fix-out-of-scope.

## Constraints for the execution run

- Canonical `.tf`/source citation for every claim, at every review stage. Comments are
  suspects, never evidence.
- Verify-before-verdict: grep references and run local tests, then decide.
- Append-only history. No rewrite without a fresh explicit decision.
- Commit footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

All six documents are scrubbed of em-dashes and AI-tell phrasing. `file:line` citations,
verdicts, and table structure are byte-for-byte unchanged from the verification run.
