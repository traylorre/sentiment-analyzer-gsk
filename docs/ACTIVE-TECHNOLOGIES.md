# Active Technologies

Lazy-loaded inventory. Load this when you need to look up what is in the service; it is not worth
per-spawn context. Architecture is in `docs/SERVICE-SHAPE.md`.

**The manifests are authoritative for versions, not this file.** `requirements.txt`,
`requirements-dev.txt`, `pyproject.toml` and `frontend/package.json` are the sources.

## Current stack

| Layer | What |
|---|---|
| Runtime | Python 3.13 (`requires-python = ">=3.13"`). Node is **split**: CI tests on 18, deploy builds on 20 |
| Backend | aws-lambda-powertools, boto3, pydantic, httpx, orjson, PyJWT, aws-xray-sdk |
| Frontend | Next.js 14, React 18, TypeScript 5, Zustand, TanStack Query, Tailwind |
| Charting | TradingView lightweight-charts and Chart.js (customer), Chart.js (admin) |
| AWS | Lambda, DynamoDB, S3, SNS, EventBridge, Cognito, Amplify, API Gateway, CloudFront (SSE edge), WAF, KMS, Secrets Manager, X-Ray |
| External | Tiingo and Finnhub (news), SendGrid (email), hCaptcha (bot protection) |
| Tooling | Ruff, Semgrep, pre-commit, Terraform (pinned by `.terraform-version`, enforced by the blocking `check-terraform-version` stage), infracost (`cost*` targets and the PR cost gate), pytest, Playwright, Vitest |

## test-e2e

`make test-e2e` runs `AWS_ENV=preprod pytest tests/e2e/ -v -m preprod`: the ADMIN dashboard
suite (per the two-dashboards table in CLAUDE.md), against a live preprod deployment, which it
requires. The customer dashboard's e2e suite is separate: `cd frontend && npx playwright test`.

Two negatives worth stating, because an agent will otherwise go looking.

There is no NewsAPI. Zero references in `src/`, `tests/` or `frontend/src/`.

CloudFront is **live**, in front of the SSE Lambda:
`infrastructure/terraform/modules/cloudfront_sse/`, wired at
`infrastructure/terraform/main.tf:966`, with the SSE Function URL locked to `AWS_IAM` for
CloudFront OAC only (`main.tf:825`).

## Where the per-feature record lives

There is no per-feature log here. Three sources, in order of authority:

- What is installed now: the manifests named above.
- When and why something changed: `git log`.
- What a feature introduced: `specs/<feature>/plan.md`, under **Language/Version** and **Primary
  Dependencies**; archived features are under `specs/archive/`. These record intent at authoring
  time, not what shipped, and they disagree with each other. Verify against code before relying on
  one.

`.specify/scripts/bash/update-agent-context.sh` appends new entries to `CLAUDE.md` (`:62`), matching
the exact headings `## Active Technologies` and `## Recent Changes`, and recreates those headings if
they are absent. Fold anything that accumulates there into the **Current stack** table above,
rewritten as a statement of what is current. Do not start a per-feature log.
