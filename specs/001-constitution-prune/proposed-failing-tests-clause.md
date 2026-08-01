# Proposed constitution clause: broken tests

Not yet applied. The constitution stays untouched until F1 runs behind the F5 evaluation gate.

## Clause

> ### Broken tests
>
> A test is working or broken. There is no third state.
>
> A test that does not pass every time is broken. Re-running it does not change that. A re-run
> measures determinism. It does not find a cause and it does not repair anything.
>
> None of these closes a break:
>
> - "It is unrelated to my change." Diff scope is a reason to look, not a reason to dismiss.
> - "It passed on re-run."
> - Any label that recasts a break as a kind of test rather than a defect.
>
> Capture the evidence before re-running. A re-run overwrites the logs and destroys the failure
> it was meant to explain.
>
> A broken test is diagnosed to a named mechanism, then fixed or deleted. Nothing is tracked,
> indexed, registered or quarantined, because every such list is a place to keep broken tests.
>
> A test that has failed is not re-run. Re-running reports a broken test as working. Retrying
> an action inside a test is unaffected.

137 words.

## Conformance check (criterion 8)

1. Playwright's test-level `retries` is 0 everywhere. Assert `playwright.config.ts` sets
   `retries: 0` unconditionally and that no workflow passes a nonzero `--retries`. This is the
   re-run-after-failure setting only; it does not touch retry logic inside a test.
2. Zero `test.skip(`, `test.fixme(`, `test.slow(` in the suites.

Demonstrate the check failing: set `--retries=1` in any workflow, or add one `test.skip`, and
confirm the build goes red.

## Cost of adopting, measured

Retry posture is inverted. The most consequential gate is the most forgiving:

| Workflow | Retries | Effect |
|---|---|---|
| `pr-checks.yml` | `--retries=0` explicit | honest |
| `nightly-e2e.yml` | `--retries=1` | one failure reported green |
| `deploy.yml` | none passed, inherits config | two failures reported green |

`frontend/playwright.config.ts:14` reads `retries: process.env.CI ? 2 : 0`. `deploy.yml:1674`
invokes Playwright without `--retries`, so the preprod deploy gate runs with two retries.

21 `skip`/`fixme` occurrences across `frontend/tests/e2e/`. Each is fixed or deleted under this
clause. The two that matter most:

- `sentiment-visibility.spec.ts:31-50` hand-rolls a 3-attempt retry loop and then skips itself
  when the search endpoint returns 429.
- `helpers/data-api-guard.ts` probes a hardcoded `http://127.0.0.1:8000` and skips on failure.
  It gates `sanity.spec.ts`, which is the preprod deploy gate. See the separate finding.

Removal reasoning goes in the commit message, not in the document.
