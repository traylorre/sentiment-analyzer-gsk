# Synthetic test data and the test oracle

Where the synthetic-data machinery is, what it actually covers, and what it does not. Read this
before writing a test that claims to validate sentiment or price values.

## What exists

Generators in `tests/fixtures/synthetic/`: `ticker_generator.py`, `news_generator.py`,
`sentiment_generator.py`, `config_generator.py`, `edge_case_generator.py`. Each takes a seed.

Two oracle classes, both real and both able to compute expected values from generated input:
`SyntheticTestOracle` (`tests/fixtures/synthetic/test_oracle.py:140`) and `TestOracle`
(`tests/fixtures/oracles/test_oracle.py:14`).

Mock publisher adapters `MockTiingoAdapter` and `MockFinnhubAdapter`, seeded at construction via
`create_mock_tiingo(seed=...)`. They expose `reset(seed)`. There is no method that accepts a
prepared dataset.

## Where it actually runs

In-process tests that mock AWS with `moto`. `tests/e2e/test_financial_pipeline.py` and
`tests/e2e/test_full_pipeline.py` are the two files that use the full generator-plus-oracle stack,
and both import `moto.mock_aws`, create local tables, and call the scorer in-process. Neither
carries the `preprod` marker, so neither is part of the preprod suite despite living under
`tests/e2e/`.

The seeded fixture path is `e2e_seed`, defaulting to `DEFAULT_TEST_SEED = 42` and overridable with
`E2E_TEST_SEED` (`tests/e2e/conftest.py:185`, `:246`). It feeds `mock_tiingo`, `mock_finnhub` and
`test_oracle`.

## Where it does not run: preprod

**Preprod E2E does not use synthetic market data, and cannot.** The deployed Lambdas construct
`TiingoAdapter` and `FinnhubAdapter` unconditionally from Secrets Manager
(`src/lambdas/shared/dependencies.py`). There is no synthetic-mode switch anywhere in `src/` or
`infrastructure/`, so an in-process mock adapter in the pytest runner cannot reach a deployed
Lambda over HTTP or Invoke. Wiring one is a code change to the service, not a test change.

Preprod tests therefore assert against whatever real data is already in preprod, or against live
publisher responses. Two consequences worth knowing before you trust a green run:

- The two tests named for the oracle do not compare against a computed expectation.
  `tests/e2e/test_sentiment.py:379` sets `expected_value=actual`, asserting the response equals
  itself; the sibling at `:301` uses `expected_value=0.0` with `tolerance=1.0`, which accepts the
  entire legal range.
- `synthetic_seed` is **not deterministic** despite its docstring. It derives from `test_run_id`,
  which is `f"e2e-{uuid.uuid4().hex[:8]}"` (`tests/e2e/conftest.py:437`), so it is a fresh random
  value per run. It feeds the `synthetic_config` request-payload fixtures.

What preprod tests do generate synthetically is **request payloads** (`synthetic_config`), not
market data. That is a real and useful pattern; it just is not what the word "oracle" implies.

## What binds

Nothing mechanically. No Makefile target, pre-commit hook, or workflow fails when a test asserts
against real data. `pr-checks.yml` passes `--ignore=tests/e2e`, so the preprod suite is not even
collected before merge, and the deploy pipeline's Playwright leg ends in `exit 0`
(`.github/workflows/deploy.yml:1694`), marked non-blocking.

Write the assertion that computes its expectation from input you control, because it is the only
kind that can fail for the right reason, not because a gate will catch you.
