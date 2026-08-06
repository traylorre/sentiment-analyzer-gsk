# SERVICE.md

> **CANON**: verified against code.

The root of the service's documentation tree. Start here; every answer is one click away.

## The watermark

Every file reachable from this tree carries exactly one marker line under its title:

- `> **CANON**: verified against code.` The attaching pass or a category audit verified the
  file's claims. Trust it; when you find drift, that is a defect to card, not a reason to
  re-audit the tree.
- `> **QUARRYSOME**: unaudited; verify against code before trusting.` The file is not yet
  reflected in code: attached without a full audit, or adjudicated as current pending work.
  Audit passes promote QUARRYSOME to CANON or delete it; v1 of this doc set is done when every
  remaining QUARRYSOME is adjudicated pending work.

A file with neither marker is outside the tree and carries no trust claim either way.

## One question per file

| Question | Answer |
|---|---|
| What is this product supposed to do, for whom? | [PRODUCT.md](PRODUCT.md) |
| What is the architecture, and what does not exist? | [docs/SERVICE-SHAPE.md](docs/SERVICE-SHAPE.md) |
| What is in the stack? | [docs/ACTIVE-TECHNOLOGIES.md](docs/ACTIVE-TECHNOLOGIES.md) |
| How is data modeled, retained, and versioned? | [docs/MODELING.md](docs/MODELING.md) |
| How does candlestick/OHLC data behave? | [docs/candlestick-behaviour.md](docs/candlestick-behaviour.md) |
| How is it monitored? | [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) |
| How is it traced? | [docs/x-ray.md](docs/x-ray.md) |
| How are requests authorized? | [docs/authorization.md](docs/authorization.md) |
| What is cached, and how stale can it get? | [docs/cache.md](docs/cache.md) |
| How would it scale? | [docs/runbooks/scaling.md](docs/runbooks/scaling.md) |
| How is it operated when it breaks? | [docs/operations.md](docs/operations.md) |
| How is Terraform state handled? | [docs/runbooks/terraform-state.md](docs/runbooks/terraform-state.md) |
| How is it chaos-tested? | [docs/chaos.md](docs/chaos.md) |
| What has been audited, and what is open? | [docs/audit.md](docs/audit.md) |
| What bites in CI? | [docs/ci-gotchas.md](docs/ci-gotchas.md) |
| How is the workspace set up? | [docs/setup/WORKSPACE_SETUP.md](docs/setup/WORKSPACE_SETUP.md) |
| What is the interview kit? | [docs/interview.md](docs/interview.md) |

`docs/cache.md` states what each cache may serve stale; [PRODUCT.md](PRODUCT.md) states what
freshness the product promises. Read them together when touching either.

## Testing

- Gates and suites run through the Makefile; `make help` lists them. `make validate` is the CI
  gate set, `make test-local` the unit + integration run.
- Admin dashboard e2e: `pytest tests/e2e/` (preprod required). Customer dashboard e2e:
  `cd frontend && npx playwright test`. The two dashboards are distinct stacks; the table in
  `CLAUDE.md` is the authority.
- Performance methodology: [docs/operations/PERFORMANCE_VALIDATION.md](docs/operations/PERFORMANCE_VALIDATION.md)
- Customer e2e suite guide: [frontend/tests/e2e/README.md](frontend/tests/e2e/README.md)
- Chaos preflight: [docs/chaos-testing/preflight-checklist.md](docs/chaos-testing/preflight-checklist.md)

## Not part of this tree

Rules that bind changes live in `.specify/memory/constitution.md`. Repo-specific agent knowledge
lives in `CLAUDE.md`. Tech debt lives on `CLEANUP-BOARD.html`. `README.md` is the landing page
and will later point here.
