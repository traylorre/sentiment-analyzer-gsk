# Whitelist Ledger, sentiment-analyzer-gsk cleanup map

Scope: manifest domain only. Every row is citation-backed from reconciled findings. `whitelisted = yes` means proven-live, protect from deletion. `whitelisted = no` means cleanup candidate pending resolution. UNKNOWN verdicts are open questions, never asserted as dead.

## File Manifest, Category Table

Tracked files: **2659** (`git ls-files | wc -l`, reproduced exact). Top-level breakdown reproduced exact.

| Path | Count | Category | Runtime blast radius |
|---|---|---|---|
| specs/ | 1415 | Docs (spec trees) | None (SUSPECT, no import graph) |
| tests/ | 375 | Test code | CI-only |
| frontend/ | 278 | Runtime (Next.js/Amplify) | High |
| docs/ | 204 | Docs | None |
| src/ | 171 | Runtime (Lambdas/lib) | High |
| infrastructure/ | 94 | Infra (Terraform) | High (deploy) |
| scripts/ | 39 | Tooling | Local/CI |
| .specify/ | 20 | Docs/tooling | None |
| reports/ | 13 | Docs | None |
| .github/ | 10 | CI/CD | High (deploy) |
| interview/ | 4 | Unknown (demo?) | UNKNOWN |
| chaos-plans/ | 2 | Docs | None |
| root files | (enumerated) | Mixed config + session artifacts | See ledger |

Root non-dir files enumerated identical: CONTEXT-CARRYOVER-2026-02-03-session4.md, -session5.md, DRIFT-INVENTORY.md, pyproject.toml, Makefile, requirements{,-dev,-ci}.txt, .pre-commit-config.yaml, .gitleaks.toml, .checkov.baseline, index.html, .nojekyll.

## Proposed Processing Order (UNVERIFIED PROPOSAL, not fact)

Blast-radius ordering is a proposal from the manifest finding, not a verified conclusion. Per-file KEEP/DELETE still needs reachability analysis not performed. Safest-first:

1. Docs / specs (specs/, docs/, reports/, .specify/, chaos-plans/), zero import graph, SUSPECT-class
2. Root session artifacts (CONTEXT-CARRYOVER*, DRIFT-INVENTORY.md), only doc references
3. Vestigial infra config (dev.tfvars, backend-dev.hcl), no CI consumer, README-only refs
4. Dev-gated runtime (src/dashboard/), needs runtime probe before deletion
5. Ambiguous served surfaces (root index.html/.nojekyll, interview/), classification unresolved
6. Live Terraform / CI (.github/, infrastructure/ WAF etc.), LAST, high blast radius

## Ledger

Schema: | path | verdict | evidence | whitelisted |

| path | verdict | evidence | whitelisted |
|---|---|---|---|
| infrastructure/terraform/modules/waf/ (aws_wafv2_web_acl.main) | LIVE / CONFIRMED | Single ACL definition modules/waf/main.tf:16; instantiated twice as module.waf (main.tf:924, REGIONAL) and module.waf_cloudfront (main.tf:990, CLOUDFRONT); `grep aws_wafv2_web_acl infrastructure/` = exactly one def | yes |
| module.waf REGIONAL association → API GW stage | LIVE / CONFIRMED | modules/waf/main.tf:254-255 association count=1 when REGIONAL + non-empty resource_arn; resource_arn=module.api_gateway.stage_arn (main.tf:929); module.api_gateway unconditional (main.tf:859) | yes |
| module.waf_cloudfront → CloudFront SSE distribution | LIVE / CONFIRMED | waf_web_acl_arn=module.waf_cloudfront.web_acl_arn (main.tf:967) into module.cloudfront_sse; cloudfront_sse/main.tf:77 web_acl_id set when arn != ''; zero-count association by design (scope CLOUDFRONT, resource_arn='') | yes |
| WAF WebACL orphan check | CONFIRMED (no orphan) | Both ACL instances consumed by live targets (main.tf:929, :967); `grep aws_wafv2 infrastructure/` outside modules/waf/ = only .checkov.baseline suppression artifacts | yes |
| src/dashboard/ (11 HTMX admin files) | DELETE-CANDIDATE / UNKNOWN | Dev-gated serving: serve_index/favicon/static each `if not _is_dev_environment(): return _make_not_found_response` (handler.py:387,:408,:429); _is_dev_environment fail-closed {local,dev,test} (handler.py:139-146); still bundled Dockerfile:54 `COPY dashboard`. Deadness in deployed prod Lambda not provable read-only (needs HTTP probe of preprod/prod '/', '/favicon.ico', '/static/*' → 404, plus proof frontend/ imports zero src/dashboard assets) | no |
| infrastructure/terraform/dev.tfvars | DELETE-CANDIDATE / UNKNOWN | dev.tfvars:3 environment='dev'; repo-wide grep: live-tooling refs ABSENT, only SUSPECT docs (specs/1189-*, specs/1269-*, README.md lines 41,64,67,98,99,151,245, WORKFLOW_DOCUMENTATION.md:281); zero refs in deploy.yml/any workflow/scripts/Makefile. README documents manual `terraform apply -var-file=dev.tfvars`, so a human runbook may retain it, deletion is judgment, not proven | no |
| infrastructure/terraform/backend-dev.hcl | DELETE-CANDIDATE / UNKNOWN | Tracked and exists; referenced by NO workflow (deploy.yml terraform blocks lines 826-961,1301,1875-1961 use only backend-preprod.hcl/backend-prod.hcl). Tracked-but-unused-by-CI; same human-runbook caveat as dev.tfvars | no |
| CONTEXT-CARRYOVER-2026-02-03-session4.md | DELETE-CANDIDATE / UNKNOWN | Tracked at root (git ls-files exact); referenced only in docs/cleanup/dependency-map.md and docs/cleanup/whitelist-ledger.md (SUSPECT docs, no import graph); no runtime/CI reference. Removal leaves two dangling doc links | no |
| CONTEXT-CARRYOVER-2026-02-03-session5.md | DELETE-CANDIDATE / UNKNOWN | Same as session4: tracked root, only doc references, zero runtime/CI reference | no |
| DRIFT-INVENTORY.md | DELETE-CANDIDATE / UNKNOWN | Tracked at root; ZERO references anywhere (self-only); no runtime/CI code references it | no |
| index.html (root) + .nojekyll | UNKNOWN | Both tracked at root. `grep` across .github/ for Pages deploy (actions/deploy-pages, peaceiris, gh-pages, github-pages) = NOTHING; no workflow references root index.html → no tracked Pages deploy job. Pages could be enabled via repo settings (not in-repo, unverifiable read-only) | no |
| interview/ (index.html, traffic_generator.py, README.md, FUTURE_IMPROVEMENTS.md) | UNKNOWN | Exact 4 files via git ls-files; not under frontend/ or src/; no Pages workflow consumes them. Purpose (demo/hiring artifact vs live surface) undetermined; files not opened line-by-line | no |

## Open Questions (UNKNOWN verdicts, evidence to resolve)

| Item | Evidence needed to close |
|---|---|
| src/dashboard/ deadness in deployed Lambda | HTTP probe of preprod+prod '/', '/favicon.ico', '/static/*' returning 404; proof frontend/ imports zero src/dashboard assets |
| "No live Lambda reaches dev-class ENVIRONMENT" | Cannot rule out out-of-band `terraform apply -var-file=dev.tfvars`; deploy.yml:7-8 dev-removed note is a comment (SUSPECT) though terraform-block greps corroborate |
| dev.tfvars / backend-dev.hcl deletability | Confirm no local runbook/human process runs them (README documents manual dev apply) |
| root index.html / .nojekyll classification | Whether GitHub Pages is enabled via repo settings (not tracked in-repo) |
| interview/ classification | Open files line-by-line; determine demo artifact vs live surface |

## Notes

- Counts (2659 total, per-dir breakdown) are CONFIRMED, personally reproduced exact, the only fact-grade rows in the manifest domain.
- Processing order is a PROPOSAL, not verified.
- Both WAF instances run bot_control_action='COUNT' (observe, not block), permissiveness note, not an orphan.
- Manifest↔urls contradiction on src/dashboard resolves as claim-scope, not factual conflict: code-level serving gate = CONFIRMED disabled outside dev (handler.py:387/408/429,139-146); deployed-runtime deadness stays UNKNOWN read-only.
