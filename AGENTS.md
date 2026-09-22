# sentiment-analyzer-gsk

Repo-specific knowledge that is hard to derive from the code. Rules that bind changes are in
`.specify/memory/constitution.md`. Architecture is in `docs/SERVICE-SHAPE.md`.

This file does not restate what a source file already states. Restated facts drift and give no
signal that they have drifted; a pointer cannot. It extends the host-global House Rules
(`~/.pi/agent/AGENTS.md`), which pi loads on every turn, rather than replacing them, so what holds
on this host regardless of repo stays there. `CLAUDE.md` is a pointer at this file so both harnesses
read one copy.

## CRITICAL: Two Dashboards

Two separate dashboards, different stacks, different routes. Confusing them has caused four
incidents. Verify which one you mean before writing code, tests, or fixes.

| | Customer Dashboard | Admin Dashboard |
|---|---|---|
| **Tech** | Next.js 14 + React 18 + TypeScript | Vanilla JS + Chart.js |
| **Source** | `frontend/` | `src/dashboard/` |
| **URL** | `https://main.d29tlmksqcx494.amplifyapp.com/` | Served by the dashboard Lambda |
| **API routes** | `/api/v2/configurations/{id}/sentiment` | `/api/v2/timeseries`, `/api/v2/metrics`, `/api/v2/articles`, `/api/v2/tickers` |
| **Data access** | `useSentiment(configId)` in React | `fetch()` in vanilla JS |
| **Env var** | `PREPROD_FRONTEND_URL` | `DASHBOARD_URL` |
| **Test suite** | `frontend/tests/e2e/*.spec.ts` | `tests/e2e/test_*.py` |
| **Test runner** | `cd frontend && npx playwright test` | `pytest tests/e2e/` |
| **Header comment** | `// Target: Customer Dashboard (Next.js/Amplify)` | `# Target: Admin Dashboard (Lambda HTMX)` |

Rules:

- "Dashboard" means the customer dashboard unless qualified as "admin".
- Customer-facing E2E targets the Amplify URL, never the Lambda. Verify user-visible fixes there.

Three traps in that table. There is **no HTMX** in the admin dashboard despite the header string
saying so; the string is historical and dozens of test files carry it. The
`check-test-target-headers` gate (`Makefile:124`) greps only
`Target:.*(Dashboard|Infrastructure)`, so the wording after that is convention, not enforcement. Second, the dashboard Lambda has no Function
URL; it is reached through API Gateway. Third, **routes do not discriminate**: both dashboards are
served by `src/lambdas/dashboard/handler.py` and their route sets overlap, so the API row above is
a usage example, not a partition. Check the caller, not the route.

## Where code goes

- Per-Lambda code in `src/lambdas/<name>/`. The Lambdas and their roles are listed in
  `docs/SERVICE-SHAPE.md`.
- Shared by several Lambdas: `src/lambdas/shared/` (`models/`, `middleware/`, `adapters/`,
  `auth/`, `errors/`, `cache/`, `utils/`).
- Cross-cutting library code: `src/lib/`. Adding an `src/lib/` import to **SSE** code breaks the
  image build, because the SSE Dockerfile copies that directory file by file while the dashboard
  and analysis ones copy it wholesale. See `docs/ci-gotchas.md`.
- `src/dashboard/` is the admin dashboard's static assets, not a Lambda.

## Commands

Task commands live in the Makefile; `make help` lists them. Prefer the make targets over raw
pytest, so you run the same gates CI does.

```bash
make validate      # format, lint, security, sast, banned terms, header + race guards
make test-local    # unit + integration
make test-unit     # unit only
make sast          # semgrep
make audit-pragma  # audits # noqa and dead suppressions (NOT part of make validate)
```

Frontend tasks are `cd frontend && npm run <script>`; the scripts are in `frontend/package.json`.

Python work needs the venv, which is 3.13 while system Python is not:
`source .venv/bin/activate`. Terraform commits need it active too, or the checkov hook crashes.

## Gotchas that cost real time

- **`make validate` does not rewrite your working tree.** Its first stage is `fmt-check`
  (`Makefile:85`), not `fmt`. The mutating `fmt` target still exists (`Makefile:138`) and nothing
  in `validate` calls it. `make -n validate` is refused outright, because `-n` propagates to the
  sub-makes and every stage would report success without running.
- **Semgrep is the only security scanner that gates.** `pip-audit` (`Makefile:161`) ends in
  `|| true`, so a green run is no evidence it found nothing. The `security` stage that carries
  `pip-audit` is declared ADVISORY in the driver, so it cannot fail the run even in principle.
  Every other stage is BLOCKING; the `run_stage` lines in the validate driver
  (`Makefile`, `validate:` target) are the authoritative stage list. The driver runs all of
  them and reports each before failing, so one broken stage cannot hide the ones behind it.
- **SSE handler tests** need `make_function_url_event()` and `parse_streaming_response()` from
  `tests/conftest.py`. A hand-built API Gateway event returns 404 and reads as a routing bug.
- **Checking security alerts before a push:** filtering `state` client-side returns 0, because the
  default page is truncated. Query server-side instead:

  ```bash
  gh api 'repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?state=open&per_page=100' --jq length
  ```

  CI green is not the same as no open alerts.
- **Push and open the PR in one step** or the branch orphans:
  `git push -u origin HEAD && gh pr create --fill`. The `check-branch-collision` pre-push hook
  catches orphans that slip through.
- **`terraform init` needs `-backend-config=backend-preprod.hcl`.** Bare init fails; `main.tf`
  carries no bucket name. State locking is **not** configured, so running terraform locally during
  a CI deploy is an unprotected concurrent write rather than a lock conflict.
  See `docs/runbooks/terraform-state.md`.
- **Two `generate_dedup_key` functions exist and they behave differently.** The live ingestion
  handler uses the two-argument one at `src/lambdas/ingestion/dedup.py:59` (headline and publish
  date only, so the same story from two publishers collides on purpose). The three-argument
  version at `src/lambdas/shared/utils/dedup.py:11` also hashes source and is **not** on the live
  path, despite living under `shared/` with the fuller docstring. Reading either file alone gives
  you the wrong answer.

## Active Technologies

Audited inventory: `docs/ACTIVE-TECHNOLOGIES.md`. The manifests (`requirements.txt`,
`pyproject.toml`, `frontend/package.json`) are authoritative for versions.

`.specify/scripts/bash/update-agent-context.sh` appends new feature entries under this heading.
Move them into the inventory file rather than letting them accumulate here.

## Recent Changes

The stack inventory lives in `docs/ACTIVE-TECHNOLOGIES.md`. `update-agent-context.sh` appends to
both headings above; fold what lands there into that file rather than letting it accumulate.

## Cards

`cards/` is this repo's backlog, one JSON file per card, named for its id. The lifecycle is
**Hydrostat** and `~/dotfiles/docs/hydrostat.md` is canon for it: the actors (Helios, Dynamo,
Flares), the stages, and what each transition requires. Use its names. Nothing here restates it.

- `cards/goal.json` holds the priority order for the whole board and answers "what is next" on its
  own. On `main`, update it in the same commit that adds, trims or deletes a card. On a card branch
  it is not yours to write: report the board change you need in your final message.
- Board files commit on `main` alone. A Dynamo does not allocate a card id, because a worktree
  cannot see what a sibling worktree has already allocated and two Dynamos each correctly compute
  the same next number. Raise a card as `cards/NEW-<branch>-<slug>.json` with its `id` field set to
  the string `NEW`; Helios assigns the number when it merges. Editing an existing card's file is
  fine; creating a numbered one is not.
- Each card carries `blocks` and `blockedBy` as arrays of card ids, so a Dynamo dispatched on one
  card sees the orderings that reach it, plus `specNumber` naming its dir under `specs/` when one
  exists.
- Each card carries `runConfiguration` with the battleplan's seven fields. `work_items` names the
  card, `audience`, `allow_git_log` and `md_is_canonical` carry the battleplan's defaults, and
  `backwards_compatibility`, `security_tier` and `operational_rigour` hold null until the operator
  answers them at the run's opening pause.
- A card records a decision in its own text as it is made, and a half-shipped card is trimmed to
  what remains, so the card describes the work that is left. Cite a card by id and by what it owns:
  a closed card's id survives in prose where no sweep can strike it.
- A card that enumerates occurrences of a thing carries, beside the list, the command that
  regenerates it. An enumeration written into a card reads as complete to every reviewer who
  inherits it. A run that writes its own evidence into the tree it measures states every census as
  of a fixed commit.
- Cards are deleted when their work completes, except the quarrysome closeout
  (`specs/001-quarrysome-promotion/`), which stays open by standing operator decision until its work
  items land. History in the pull request is the archive.
- A Dynamo claiming the work is finished attests in `cards/<id>.status.json` committed on its
  branch: `status` done, `safe_to_teardown` true, `card_after` DONE when nothing remains or OPEN
  with what remains named, and anything the board needs in `for_the_board`.

## Filing what a session taught

Three standing inboxes collect rules that governed a session and live in no committed file. They
are dump targets, never queue positions, and filing never blocks a rotation.

- `improve-drop.sh local` files what holds **only in this repo**. It lands in
  `cards/improve-local.json` here; this repo's Helios batches it with `improve-collect.py local`
  from the root checkout (a linked worktree refuses).
- `improve-drop.sh global` files what would hold **in any repo on this host**. Batched by dotfiles'
  Helios into `~/dotfiles/cards/134.json`, nowhere else.
- `improve-drop.sh carryover` files **what a `/carryover` would have materially lost**. Batched by
  dotfiles' Helios into `~/dotfiles/cards/127.json`.

`improve-drop.sh --rules` prints the entry rules: one finding per drop, one citation line naming
what was measured and where, route by scope, one cheap grep for a near-duplicate first, and never
block on filing. `improve-collect.py --report` shows what pends. A candidate becomes a committed
line only when it passes the five gates of `~/dotfiles/cards/133.json`: recurrence, durability,
mechanism first, payment, placement. Dumping is free; factoring is the work.

## Carryover and the Context Guardian

Both are host-global and already active here. `carryover-bridge.ts` and `context-guardian.js` load
from `~/.pi/agent/extensions/` (symlinks into `~/dotfiles`) in every repo, and the scripts they
drive resolve through `PI_CARRYOVER_BIN_DIR`, then `$HOME/bin`, then `PATH` — the fixed path
outranks `PATH` deliberately, so a per-project prepend cannot shadow a stowed script with a
repo-supplied file of the same name. This repo adds nothing to either, and a repo-local copy of
either would be loaded **in addition** to the host one rather than replacing it
(`resource-loader.js` merges `agentDir/extensions` with `cwd/.pi/extensions`).

`/carryover` writes `.pi/handoff/<session-id>/carryover.md` and rotates the pane. Durable state goes
to its home and is committed BEFORE the document is authored: the card, the spec, or the notes carry
every conclusion that would change what a cold reader does, and the carryover document names only
what cannot yet be durable. A lesson about the machinery itself is durable state whose home is a new
card.

## Operator preferences that bind work here

- No em-dashes, ever. Graders fail edits on this.
- Terse and recommendation-first. One recommendation, no option menus, no cost tables standing in
  for a call.
- Report token spend plainly.
- No new AWS resources without asking. No CloudWatch alarms: metric and log only, deliberately.
- Code is the primary source and no `.md` file is evidence. Where a doc and the code disagree, the
  doc is amended and the code is not.
- Card an adjacent defect found mid-feature and never absorb it into the run in flight.
- No "flaky test" language. A test that fails carries a cause, and naming it is the work.

## Pointers

- The board and what is next: `cards/goal.json`
- Card lifecycle canon: `~/dotfiles/docs/hydrostat.md`
- Rules that bind changes: `.specify/memory/constitution.md`
- Architecture, topology, and what does not exist: `docs/SERVICE-SHAPE.md`
- Stack inventory (what is installed and what does not exist): `docs/ACTIVE-TECHNOLOGIES.md`
- Output schema, retention, model versioning: `docs/MODELING.md`
- Metrics, alarms, dashboard privacy rules: `docs/OBSERVABILITY.md`
- CI and build pitfalls: `docs/ci-gotchas.md`
- Terraform state, locks, and backend setup: `docs/runbooks/terraform-state.md`
- Tech debt: `CLEANUP-BOARD.html`
