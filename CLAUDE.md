# sentiment-analyzer-gsk

Repo-specific knowledge that is hard to derive from the code. Rules that bind changes are in
`.specify/memory/constitution.md`. Architecture is in `docs/SERVICE-SHAPE.md`.

This file does not restate what a source file already states. Restated facts drift and give no
signal that they have drifted; a pointer cannot.

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
`check-test-target-headers` gate (`Makefile:49`) greps only `Target:.*Dashboard`, so the wording
after that is convention, not enforcement. Second, the dashboard Lambda no longer has a Function
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
make audit-pragma  # audits # noqa and # nosec (NOT part of make validate)
```

Frontend tasks are `cd frontend && npm run <script>`; the scripts are in `frontend/package.json`.

Python work needs the venv, which is 3.13 while system Python is not:
`source .venv/bin/activate`. Terraform commits need it active too, or the checkov hook crashes.

## Gotchas that cost real time

- **`make validate` rewrites your working tree.** Its `fmt` target runs `ruff format src tests`.
  `fmt-check` is the non-mutating variant and is not wired into `validate`.
- **Semgrep is the only security scanner that gates.** `pip-audit` (`Makefile:73`) and `bandit`
  (`Makefile:78`) both end in `|| true`, so a green run is no evidence either found nothing.
  Bandit is slated for removal in favour of semgrep, so do not fix, harden, or extend its
  invocations. The rest of `validate` does gate: `lint`, `check-banned-terms`,
  `check-test-target-headers` and `check-waitforresponse-race` all fail hard.
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

## Pointers

- Rules that bind changes: `.specify/memory/constitution.md`
- Architecture, topology, and what does not exist: `docs/SERVICE-SHAPE.md`
- Output schema, retention, model versioning: `docs/MODELING.md`
- Metrics, alarms, dashboard privacy rules: `docs/OBSERVABILITY.md`
- CI and build pitfalls: `docs/ci-gotchas.md`
- Terraform state, locks, and backend setup: `docs/runbooks/terraform-state.md`
- Tech debt: `CLEANUP-BOARD.html`
