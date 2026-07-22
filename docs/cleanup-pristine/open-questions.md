# Open Questions

Everything below is UNKNOWN read-only. These are scoped, not answered. Each is a question the repo alone cannot close; every "evidence to resolve" is the concrete artifact that would settle it. All UNKNOWN verdicts in this run live in the file-manifest domain; the one contradiction-sweep result folds into the flagship.

## Summary

| # | Open question | State | Blocks deletion? | Resolve with |
|---|---|---|---|---|
| Q1 (flagship) | Is `src/dashboard/` (11-file HTMX admin dashboard) dead in deployed preprod/prod, i.e. safe to delete? | DELETE-CANDIDATE / UNKNOWN | Yes | HTTP probe of deployed `/`, `/favicon.ico`, `/static/*` in preprod+prod; proof `frontend/` imports zero `src/dashboard` assets |
| Q2 | Does `ENVIRONMENT` ever reach a dev-class value in any *live* Lambda? | RECONCILE / UNKNOWN | Informs Q1 | Runtime read of deployed Lambda `ENVIRONMENT`; confirm no out-of-band `terraform apply -var-file=dev.tfvars` |
| Q3 | Are `dev.tfvars` + `backend-dev.hcl` truly orphaned (deletable)? | DELETE-CANDIDATE / UNKNOWN | Yes | Confirm no human runbook still runs the documented manual dev apply |
| Q4 | Are root `index.html` (+`.nojekyll`) and `interview/` live surfaces or artifacts? | UNKNOWN | Yes | Check repo Settings > Pages (not tracked in-repo); open `interview/` files for intent |
| Q5 | Are `CONTEXT-CARRYOVER-*.md` + `DRIFT-INVENTORY.md` deletable? | DELETE-CANDIDATE / UNKNOWN | Low-risk | Judgment call; removal leaves 2 dangling links in `docs/cleanup/*` |

---

## Q1 (flagship): Is the `src/dashboard/` HTMX admin dashboard dead in prod?

**Scope.** The code-level serving gate is settled. The deployed-runtime deadness is not. Deletion depends on the latter.

**Confirmed at source:**
- Dev-gated serving: `serve_index` (handler.py:387), `serve_favicon` (:408), `serve_static` (:429) each open with `if not _is_dev_environment(): return _make_not_found_response(...)`.
- `_is_dev_environment()` (handler.py:139-146) fail-closes: True only for `ENVIRONMENT` in {local, dev, test}; preprod/prod/unset return False -> 404.
- Still bundled: `Dockerfile:54` `COPY dashboard /var/task/src/dashboard` ships all 11 files into the image.
- Only reachable via API Gateway anyway: dashboard Function URL disabled (`main.tf:508` `create_function_url=false`, Feature 1300).

**Contradiction reconciled (sweep result).** The `urls` domain calls this surface DISABLED / CONFIRMED; the `manifest` domain calls it DELETE-CANDIDATE / UNKNOWN. Not a factual conflict, a scope difference. `urls` asserts the readable source gate (CONFIRMED disabled outside dev). `manifest` refuses to assert a *deployed* Lambda returns 404 without an HTTP probe. Net: code gate = CONFIRMED disabled; runtime deadness = UNKNOWN read-only.

**Evidence to resolve:**
1. Probe deployed preprod + prod Lambda for `/`, `/favicon.ico`, `/static/*` returning 404.
2. Prove `frontend/` imports zero `src/dashboard` assets.

Neither is doable from the repo.

---

## Q2: Does `ENVIRONMENT` ever reach dev-class in a live Lambda?

**Scope.** Underwrites Q1 (if no live Lambda is dev-class, the admin dashboard 404s everywhere deployed).

**Confirmed at source:**
- `deploy.yml:7-8` comment: "Simplified 2-environment flow (preprod + prod). Dev environment removed."
- `main.tf:472` `ENVIRONMENT=var.environment`; `preprod.tfvars:7`='preprod', `prod.tfvars:7`='prod'.
- `deploy.yml:442` `ENVIRONMENT: dev` is scoped to the moto unit-test job only.
- Grep across all 5 workflows: no `dev.tfvars` / `backend-dev` usage; terraform apply/plan blocks (deploy.yml:826-961, 1301, 1875-1961) use only preprod/prod backends and tfvars.

**Why still UNKNOWN.** The claim is about "any live Lambda", a deployed-runtime fact. Cannot rule out a manual/out-of-band `terraform apply -var-file=dev.tfvars`. `deploy.yml:7-8` is a comment (SUSPECT), corroborated but not proven by the terraform-block greps.

**Evidence to resolve:** runtime read of deployed Lambda `ENVIRONMENT` env var; confirmation no out-of-band dev apply exists.

---

## Q3: Are `dev.tfvars` and `backend-dev.hcl` orphaned config?

**Confirmed at source:**
- `dev.tfvars:3` environment='dev'.
- Repo-wide grep: references only in SUSPECT docs/specs (specs/1189-*, specs/1269-*, `infrastructure/terraform/README.md` lines 41/64/67/98/99/151/245, `.github/WORKFLOW_DOCUMENTATION.md:281`). Zero references in `deploy.yml`, any workflow, `scripts/`, or `Makefile`.
- `backend-dev.hcl` exists and is tracked but is likewise referenced by no workflow.

**Why still UNKNOWN.** "Orphaned/deletable" needs confirmation no local runbook or human process still runs these. The README documents a manual `terraform apply -var-file=dev.tfvars`, so a human dev workflow may intentionally retain them. Deletion is a judgment call, not a proven fact.

**Evidence to resolve:** confirm no human/runbook process consumes `dev.tfvars` or `backend-dev.hcl`.

---

## Q4: Are root `index.html` (+`.nojekyll`) and `interview/` live surfaces?

**Confirmed at source (git ls-files):**
- Root has `index.html` and `.nojekyll`.
- `interview/` = `index.html`, `traffic_generator.py`, `README.md`, `FUTURE_IMPROVEMENTS.md`. Neither under `frontend/` nor `src/`.
- No tracked GitHub Pages deploy job: grep across `.github/` for `actions/deploy-pages`, `peaceiris`, `gh-pages`, `github-pages` returned nothing; no workflow references root `index.html`.

**Why still UNKNOWN.** Absence of a Pages workflow weakens the "live Pages surface" hypothesis but does not kill it, Pages can be enabled via repo settings, which are not tracked in-repo and are unverifiable read-only. `interview/` purpose (demo/hiring artifact vs live surface) is undetermined; files not opened line-by-line.

**Evidence to resolve:** check repo Settings > Pages for an enabled source; open `interview/` files to classify intent.

---

## Q5: Are stale session artifacts deletable?

**Confirmed at source (git ls-files):**
- `CONTEXT-CARRYOVER-2026-02-03-session4.md`, `-session5.md`, `DRIFT-INVENTORY.md` all tracked at repo root.
- `CONTEXT-CARRYOVER-2026-02-03` referenced only in `docs/cleanup/dependency-map.md` and `docs/cleanup/whitelist-ledger.md` (both SUSPECT docs, no import graph). `DRIFT-INVENTORY.md` has zero references anywhere.
- No runtime/CI code references any of the three.

**Why still UNKNOWN.** "Tracked" is CONFIRMED and "zero runtime blast radius" is well-supported. But DELETE-CANDIDATE stays a proposal: removing the two carryover files leaves two dangling doc links in `docs/cleanup/*` to fix. Low-risk, not a verified deletion.

**Evidence to resolve:** decide whether to fix or accept the dangling `docs/cleanup/*` links; then delete.
