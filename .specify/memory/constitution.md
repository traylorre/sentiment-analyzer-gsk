# Sentiment Analyzer Constitution

Rules for changing this repo. For what the service is and how it is built, see
`docs/SERVICE-SHAPE.md`.

## 1. Scope

The service ingests financial news from external publishers (Tiingo, Finnhub), scores sentiment,
and serves the result through a REST API and a customer dashboard.

Persistence is DynamoDB. Items are deduplicated by content hash, and consumers are idempotent.

Every deployed model has a version string, and inference is re-runnable against a given
`model_version`.

## 2. Security

- Secrets live in a managed secrets service, never in source control.
- All traffic uses TLS. Admin and management endpoints require authentication.
- Never write raw user-provided text into logs or dashboard fields without redaction. Use
  `sanitize_for_log()` from `src/lambdas/shared/logging_utils.py`.
- Request logs are structured. Do not log raw input text by default.
- When building DynamoDB expressions, always use `ExpressionAttributeNames` and
  `ExpressionAttributeValues` for user-controlled values.
- Do not suppress a SAST finding without documented justification, and do not rename variables to
  avoid detection.
- Confidential security material lives in the private repo `../sentiment-analyzer-gsk-security/`.
  Public policy stays in `SECURITY.md`.

## 3. Testing

The tier decides what may be real and what must be mocked.

- Unit (`tests/unit/`): everything mocked. `moto` for AWS, `responses` for HTTP.
- Integration (`tests/integration/`): AWS is simulated. Most modules use `moto`;
  `tests/integration/timeseries/` uses LocalStack, started by `make test-integration`. The
  `*_preprod.py` files in that directory are the exception and hit real preprod under the
  `preprod` marker.
- E2E (`tests/e2e/`, marker `preprod`): real preprod AWS.
- Browser E2E (`frontend/tests/e2e/`): a local dev server against a mock backend, unless
  `PREPROD_FRONTEND_URL` is set, which points the suite at deployed Amplify.

External publishers (Tiingo, Finnhub, SendGrid, hCaptcha) are mocked everywhere except specs
tagged `@external-api`, which run against the real APIs on a nightly schedule and are excluded
from PR checks.

An integration test that fails has a bug in the code or in its own setup. Do not repoint a mocked
test at real AWS to make it pass.

Preprod E2E uses deterministic synthetic data: see `docs/E2E-SYNTHETIC-DATA.md`.

### New code

- Every new function or module carries unit tests.
- Tests cover the happy path and at least one error path.
- Coverage floor is 80%.

### Broken tests

A test is working or broken. There is no third state.

A test that does not pass every time is broken. A re-run measures determinism; it does not find a
cause and it does not repair anything. A test that has failed is not re-run. Retrying an action
inside a test is unaffected.

Never green a failing test by editing the fixture to match broken code. Root-cause it: the bug is
either in the source or in the expectation. A broken test is diagnosed to a named mechanism, then
fixed or deleted. Nothing is quarantined, tracked, or indexed, because every such list is a place
to keep broken tests.

### Dates

Tests use fixed dates (`date(2024, 1, 2)`) or `freezegun`. Never `date.today()`,
`datetime.now()`, `time.time()`, or `datetime.utcnow()`.

## 4. Push rules

These bind the main thread. Sub-agents do not push, open PRs, or merge.

- `make validate` passes before push (format, lint, security, SAST).
- `make test-local` passes before push.
- Commits are GPG-signed (`git commit -S`).
- Pushes target a feature branch, never main.

Feature branch, then PR. The pipeline squash-merges on green and deletes the remote branch. Clean
up the local branch afterward.

Never bypass the pipeline: no `--no-verify`, no `--admin`, no force-push to a protected branch, no
disabling branch protection, no marking a failing check as expected.

## 5. Pointers

- Service shape, deployment topology, and what does not exist: `docs/SERVICE-SHAPE.md`
- Output schema, retention, model versioning: `docs/MODELING.md`
- Metrics, alarms, dashboard privacy rules: `docs/OBSERVABILITY.md`
- Diagrams: build from `docs/diagrams/TEMPLATE.md`; shared theme is `mermaid-config.json`
- Tech debt: `CLEANUP-BOARD.html`. Append to an existing card rather than creating a duplicate.
