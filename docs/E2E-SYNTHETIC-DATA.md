# E2E synthetic test data

Detail extracted from the constitution. Needed only when writing or changing preprod E2E tests.

All E2E tests in preprod MUST use synthetic test data:

1. Before each E2E suite run, generate deterministic synthetic data (tickers, prices, sentiment).
2. Configure mock external API adapters to return that synthetic data.
3. Assertions MUST compute expected outcomes from the same synthetic data.
4. The framework includes a test oracle that calculates correct answers from the input data.

```python
# E2E test setup
synthetic_data = generate_synthetic_ticker_data(seed=12345)
mock_tiingo.configure(synthetic_data)
mock_finnhub.configure(synthetic_data)

# Execute test
response = dashboard_api.get_sentiment(config_id)

# Assert against computed expectations, not hardcoded values
expected = compute_expected_sentiment(synthetic_data)
assert response.sentiment == expected
```
