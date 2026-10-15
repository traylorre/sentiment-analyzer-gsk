# Card #8 remainder: the stash-B doc audit and the tier-1 deferred items

The second half of card #8, recorded in spec 1401's directory beside the deploy-gate half
(`spec.md`). Every census below is as of the base this branch was cut from, the `main` commit
whose subject is `board: card 13 received; root-checkout .claude/ runtime removed`.

## Stash-B was already applied

The card carried stash-B as "measured NOT applying, needs a rebase". The forward
`git apply --check` failure was real, but it failed because the content was already in the tree:

| Target | Measurement | Reading |
|---|---|---|
| `docs/ci-gotchas.md` | `git apply --reverse --check --include=docs/ci-gotchas.md <patch>` exits 0 | hunk applied verbatim |
| `docs/runbooks/terraform-state.md` | reverse check fails only at the last hunk (`:113`) | that hunk's trailing context gained a "Secret population" section after it landed; the text is present |
| `CLEANUP-BOARD.html` | the patch's old `CARDS` array (160) vs new (161) vs current (188), compared by title | stash-B's only content change is one added card, present on the current board byte-identical; the rest of the hunk reformats the array onto 1,455 lines |

stash-A was measured applied by the first run (`spec.md`, "Drift since the stow"). Both patch
files are deleted with `specs/stash-triage/`; git history keeps them.

The rebase was therefore moot, and the refuter pass the card required ran against the text
stash-B left in the tree.

## Refuter pass over stash-B's text

Claim-by-claim refuters against primary sources, with the parent re-verifying every correction
it applied (house standard from `specs/001-constitution-prune/BATTLEPLAN-tier1-refute.md`).

| Doc | Claims | Wrong | What was wrong, and the fix |
|---|---|---|---|
| `docs/ci-gotchas.md`, CORS section | 34 | 7 | Three statements about browser behaviour were false, measured in headless Chromium 143: the fetch rejects with `TypeError: Failed to fetch` and the console names the cause. The gateway-response status set was given as 401/403/404 and is 401, 401, 403. Three cited lines had moved. |
| `docs/ci-gotchas.md`, hook ordering | 9 citations | 9 | The doc said 23 hooks and there are 22. Every `.pre-commit-config.yaml` line citation was off by 2 to 5. |
| `docs/runbooks/terraform-state.md` | 51 | 2 false, 7 drifted | On Terraform 1.9.8, re-init with the other `.hcl` and no `-reconfigure` exits `Backend configuration changed`. It does not offer a copy; only `-migrate-state` does. The bare-init caller list missed `infrastructure/scripts/deploy.sh:136`, which goes on to plan and apply. The Makefile and deploy.yml lines had moved. |
| CLEANUP-BOARD, "Raw publisher article text is SERVED" | 21 | 4 false, 1 drifted | `:1044` is the SNS message body, not the stored item. `/api/v2/articles` reads `by_tag`, which nothing populates (board card Q6), so only `/api/v2/metrics` leaks today. The "already carded" claim about a projection narrowing was false. |

## The deferred items

| Item | Result |
|---|---|
| `SECURITY.md`, claims vs controls | 53 claims: 12 backed, 23 partial, 14 false, 4 unverifiable. The public policy (the repo is public) marked four controls FIXED that do not run: per-IP rate limiting, CloudWatch alarms, Cognito JWT validation in the Lambda, and hCaptcha. Rewritten to the controls that exist, plus a Known Gaps list. Every gap it names is already readable in the public tfvars and code. The placeholder contact became the GitHub private vulnerability reporting link (enabled). The 48-hour acknowledgement promise was kept as written: only the operator can withdraw it. |
| `docs/diagrams/TEMPLATE.md` | Both examples render under mmdc 11.15.0, which the repo does not provide (it came from the npx cache). Its "standard" claims hold for 1 of 9 diagrams in use, and were reworded. The URL snippet had drifted from `scripts/regenerate-mermaid-url.py` and was replaced with a pointer to the script. The constitution's "shared theme is `mermaid-config.json`" was false (that file says `default`, everything else `dark`, no tool reads it) and was removed. |
| `infrastructure/terraform/bootstrap/README.md` | Missing preconditions added: the exact 1.9.8 pin, local state only in the applying checkout, region and `-reconfigure` on the main init. Corrected: CI runs do serialize through the `deploy-pipeline` concurrency group, so only local runs are unprotected. |
| `injected-docs-check.sh` policy | See below. |

## injected-docs-check.sh: measured, fixed, recommended BLOCKING

Run against the base with nothing having run it since it was written. Regenerate with
`bash specs/001-constitution-prune/checks/injected-docs-check.sh` in a checkout of that base:

| Finding | Count | Verdict |
|---|---|---|
| R6 anchored citation moved (AGENTS.md on `Makefile`, ci-gotchas on `.pre-commit-config.yaml`, ACTIVE-TECHNOLOGIES on `main.tf`) | 12 | real drift |
| R1 `specs/001-alarm-restore/card.md` cited but absent | 1 | real drift |
| R4 `SentimentAnalyzer/Alerts`, `/Notifications` "exist nowhere" | 2 | false positive: R4 did not read namespaces only `modules/monitoring/dashboard.tf` references |
| `CLAUDE.md [missing-core-doc]` | 1 | checker defect: CORE named the renamed file, so AGENTS.md went unchecked |

Adding AGENTS.md to CORE surfaced one more real drift (`specs/001-quarrysome-promotion/`, now card
#11). The checker also had a latent bug: an anchor pattern beginning with `-` was parsed as a grep
option. All of it is fixed. The checker, its proof harness, `anchors.tsv` and
`no-such-path.txt` moved to `scripts/injected-docs/`, out of a specs directory that card #9's
sweep will dispose of. `make check-injected-docs` runs it on demand and is not part of
`validate`. Current state: clean, and the proof harness proves 7 of 7 perturbations firing. A mutant
removing `SentimentAnalyzer/Alerts` from `dashboard.tf` makes R4 fire in both directions.

Recommendation: wire `check-injected-docs` into the validate driver as a BLOCKING stage. The
false-positive rate on the current tree is 0, and 14 real drifts accumulated in the injected docs
while nothing ran it. The cost is that a commit moving an anchored line must update the citing doc
and `anchors.tsv` in the same commit, and the land gate runs `validate`. Not landed here, by Helios's
ruling: a BLOCKING stage changes every future commit, so the decision is the operator's. It is
carried by the NEW card this branch raises.

## Not settled from this host

- Whether the S3 backend ever writes a `.tflock` without `use_lockfile`, and whether 1.9.8 accepts
  `use_lockfile`: needs AWS. The runbook keeps "can never be written" on the strength of no
  `use_lockfile` anywhere.
- Four claims kept in CANON docs that the refuters could neither confirm nor refute:
  - `docs/ci-gotchas.md`: that MOCK integrations reject `method.request.header.*` and that the
    echo edit made every apply fail with a 400. Both rest on the `12abfbf` commit message and
    the comment at `modules/api_gateway/main.tf:210`.
  - `docs/runbooks/terraform-state.md`: that a working copy's cached backend is "normally
    preprod".
  - The same runbook: that a fresh environment serves 500s until its empty secrets are
    populated.
- CodeQL's sensitive-data heuristics (claimed on the "Raw publisher" card): needs the pinned
  codeql-action's query source.
- Whether an anonymous session satisfies `_get_user_id_from_event` (the same card's open
  question): out of scope here, left open on the card.

## Adjacent defects, carded on CLEANUP-BOARD

Not fixed here:
- Three committed callers run a bare `terraform init` and then write state.
- CI stale-lock steps and three comments describe a Terraform lock that does not exist.
- API Gateway CORS MOCK preflights fall back to `*` with credentials, return only the first
  origin, and the guarding test cannot see either.
- `rate_limit.py` and `hcaptcha.py` are complete middleware with no caller.
- `mermaid-config.json` has no reader.
