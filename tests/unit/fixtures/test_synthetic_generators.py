"""Unit tests for synthetic data generators."""


import pytest

from tests.fixtures.mocks.mock_finnhub import create_mock_finnhub
from tests.fixtures.mocks.mock_sendgrid import create_mock_sendgrid
from tests.fixtures.mocks.mock_tiingo import create_mock_tiingo
from tests.fixtures.synthetic.config_generator import (
    SyntheticConfiguration,
    create_config_generator,
)
from tests.fixtures.synthetic.news_generator import (
    create_news_generator,
)
from tests.fixtures.synthetic.sentiment_generator import (
    create_sentiment_generator,
)
from tests.fixtures.synthetic.test_oracle import (
    OracleExpectation,
    ValidationResult,
    create_test_oracle,
)
from tests.fixtures.synthetic.ticker_generator import (
    create_ticker_generator,
)


class TestTickerGenerator:
    """Tests for ticker/OHLC data generator."""

    def test_create_generator(self):
        """Test generator factory function."""
        gen = create_ticker_generator(seed=123, base_price=50.0)
        assert gen.config.seed == 123
        assert gen.config.base_price == 50.0

    def test_generate_candles_returns_list(self):
        """Test that generate_candles returns a list."""
        gen = create_ticker_generator()
        candles = gen.generate_candles("AAPL", days=10)
        assert isinstance(candles, list)
        assert len(candles) > 0

    def test_generate_candles_deterministic(self):
        """Test that same seed produces same data."""
        gen1 = create_ticker_generator(seed=42)
        gen2 = create_ticker_generator(seed=42)

        candles1 = gen1.generate_candles("AAPL", days=10)
        candles2 = gen2.generate_candles("AAPL", days=10)

        assert len(candles1) == len(candles2)
        for c1, c2 in zip(candles1, candles2, strict=True):
            assert c1.open == c2.open
            assert c1.high == c2.high
            assert c1.low == c2.low
            assert c1.close == c2.close

    def test_generate_candles_different_seeds(self):
        """Test that different seeds produce different data."""
        gen1 = create_ticker_generator(seed=42)
        gen2 = create_ticker_generator(seed=99)

        candles1 = gen1.generate_candles("AAPL", days=10)
        candles2 = gen2.generate_candles("AAPL", days=10)

        # At least some values should differ
        different = any(
            c1.close != c2.close for c1, c2 in zip(candles1, candles2, strict=True)
        )
        assert different

    def test_candle_ohlc_relationship(self):
        """Test that OHLC values are valid."""
        gen = create_ticker_generator()
        candles = gen.generate_candles("AAPL", days=10)

        for candle in candles:
            assert candle.high >= candle.open
            assert candle.high >= candle.close
            assert candle.low <= candle.open
            assert candle.low <= candle.close
            assert candle.volume > 0

    def test_generate_candles_date_assignment(self):
        """Test that dates are correctly assigned."""
        gen = create_ticker_generator()
        candles = gen.generate_candles("MSFT", days=10)

        # OHLCCandle doesn't have ticker field, but dates should be present
        assert all(candle.date is not None for candle in candles)

    def test_generate_volatile_period(self):
        """Test high volatility data generation."""
        gen = create_ticker_generator()
        normal = gen.generate_candles("AAPL", days=20)
        gen.reset()
        volatile = gen.generate_volatile_period(
            "AAPL", days=20, volatility_multiplier=5.0
        )

        # Volatile period should have larger price swings
        normal_ranges = [c.high - c.low for c in normal]
        volatile_ranges = [c.high - c.low for c in volatile]

        avg_normal = sum(normal_ranges) / len(normal_ranges)
        avg_volatile = sum(volatile_ranges) / len(volatile_ranges)

        assert avg_volatile > avg_normal

    def test_generate_trending_period(self):
        """Test trending data generation."""
        gen = create_ticker_generator()
        up = gen.generate_trending_period("AAPL", days=20, trend_direction="up")

        # Uptrend should have higher close at end
        assert up[-1].close > up[0].open

    def test_reset_generator(self):
        """Test generator reset."""
        gen = create_ticker_generator(seed=42)
        candles1 = gen.generate_candles("AAPL", days=5)

        gen.reset()
        candles2 = gen.generate_candles("AAPL", days=5)

        for c1, c2 in zip(candles1, candles2, strict=True):
            assert c1.close == c2.close


class TestSentimentGenerator:
    """Tests for sentiment score generator."""

    def test_create_generator(self):
        """Test generator factory function."""
        gen = create_sentiment_generator(seed=123, base_sentiment=0.2)
        assert gen.config.seed == 123
        assert gen.config.base_sentiment == 0.2

    def test_generate_sentiment(self):
        """Test single sentiment generation."""
        gen = create_sentiment_generator()
        sentiment = gen.generate_sentiment("AAPL")

        assert sentiment.ticker == "AAPL"
        assert -1.0 <= sentiment.sentiment_score <= 1.0
        assert sentiment.buzz_score >= 0

    def test_generate_sentiment_deterministic(self):
        """Test that same seed produces same data."""
        gen1 = create_sentiment_generator(seed=42)
        gen2 = create_sentiment_generator(seed=42)

        s1 = gen1.generate_sentiment("AAPL")
        s2 = gen2.generate_sentiment("AAPL")

        assert s1.sentiment_score == s2.sentiment_score
        assert s1.buzz_score == s2.buzz_score

    def test_generate_sentiment_series(self):
        """Test sentiment series generation."""
        gen = create_sentiment_generator()
        series = gen.generate_sentiment_series("AAPL", days=10)

        assert len(series) == 10
        assert all(s.ticker == "AAPL" for s in series)

    def test_generate_bullish_period(self):
        """Test bullish sentiment generation."""
        gen = create_sentiment_generator()
        bullish = gen.generate_bullish_period("AAPL", days=10)

        avg = sum(s.sentiment_score for s in bullish) / len(bullish)
        assert avg > 0  # Average should be positive

    def test_generate_bearish_period(self):
        """Test bearish sentiment generation."""
        gen = create_sentiment_generator()
        bearish = gen.generate_bearish_period("AAPL", days=10)

        avg = sum(s.sentiment_score for s in bearish) / len(bearish)
        assert avg < 0  # Average should be negative

    def test_classify_sentiment(self):
        """Test sentiment classification."""
        gen = create_sentiment_generator()

        assert gen.classify_sentiment(0.5) == "positive"
        assert gen.classify_sentiment(-0.5) == "negative"
        assert gen.classify_sentiment(0.0) == "neutral"
        assert gen.classify_sentiment(0.1) == "neutral"


class TestNewsGenerator:
    """Tests for news article generator."""

    def test_create_generator(self):
        """Test generator factory function."""
        gen = create_news_generator(seed=123)
        assert gen.config.seed == 123

    def test_generate_article(self):
        """Test single article generation."""
        gen = create_news_generator()
        article = gen.generate_article(["AAPL"])

        assert "AAPL" in article.tickers
        assert article.title
        assert article.url
        assert article.source

    def test_generate_article_deterministic(self):
        """Test that same seed produces same articles."""
        gen1 = create_news_generator(seed=42)
        gen2 = create_news_generator(seed=42)

        a1 = gen1.generate_article(["AAPL"])
        a2 = gen2.generate_article(["AAPL"])

        assert a1.title == a2.title
        assert a1.article_id == a2.article_id

    def test_generate_articles(self):
        """Test multiple article generation."""
        gen = create_news_generator()
        articles = gen.generate_articles(["AAPL", "MSFT"], count=10)

        assert len(articles) == 10
        # Should be sorted by date descending
        for i in range(len(articles) - 1):
            assert articles[i].published_at >= articles[i + 1].published_at

    def test_generate_positive_news_event(self):
        """Test positive news cluster generation."""
        gen = create_news_generator()
        articles = gen.generate_positive_news_event("AAPL", article_count=5)

        assert len(articles) == 5
        # All should be AAPL-related
        for a in articles:
            assert "AAPL" in a.tickers

    def test_generate_negative_news_event(self):
        """Test negative news cluster generation."""
        gen = create_news_generator()
        articles = gen.generate_negative_news_event("TSLA", article_count=3)

        assert len(articles) == 3


class TestTestOracle:
    """Tests for the test oracle."""

    def test_create_oracle(self):
        """Test oracle factory function."""
        oracle = create_test_oracle(seed=123)
        assert oracle.seed == 123

    def test_compute_expected_atr(self):
        """Test ATR computation from synthetic data."""
        oracle = create_test_oracle(seed=42)
        atr = oracle.compute_expected_atr("AAPL", days=30)

        assert atr is not None
        assert atr > 0

    def test_compute_expected_atr_deterministic(self):
        """Test that same seed produces same ATR."""
        oracle1 = create_test_oracle(seed=42)
        oracle2 = create_test_oracle(seed=42)

        atr1 = oracle1.compute_expected_atr("AAPL", days=30)
        atr2 = oracle2.compute_expected_atr("AAPL", days=30)

        assert atr1 == atr2

    def test_compute_expected_volatility_level(self):
        """Test volatility level classification."""
        oracle = create_test_oracle()
        vol_level = oracle.compute_expected_volatility_level("AAPL", days=30)

        assert vol_level in ["low", "medium", "high"]

    def test_compute_expected_avg_sentiment(self):
        """Test average sentiment computation."""
        oracle = create_test_oracle()
        avg = oracle.compute_expected_avg_sentiment("AAPL", days=30)

        assert -1.0 <= avg <= 1.0

    def test_generate_test_scenario(self):
        """Test complete scenario generation."""
        oracle = create_test_oracle(seed=42)
        scenario = oracle.generate_test_scenario("AAPL", days=30, news_count=15)

        assert scenario.ticker == "AAPL"
        assert scenario.seed == 42
        assert len(scenario.candles) > 0
        assert len(scenario.sentiment_series) == 30
        assert len(scenario.news_articles) == 15
        assert scenario.expected_atr is not None


class TestMockTiingoAdapter:
    """Tests for mock Tiingo adapter."""

    def test_create_mock(self):
        """Test mock factory function."""
        mock = create_mock_tiingo(seed=123)
        assert mock.seed == 123

    def test_get_news(self):
        """Test mock news retrieval."""
        mock = create_mock_tiingo()
        articles = mock.get_news(["AAPL"])

        assert len(articles) > 0
        assert len(mock.get_news_calls) == 1

    def test_get_ohlc(self):
        """Test mock OHLC retrieval."""
        mock = create_mock_tiingo()
        candles = mock.get_ohlc("AAPL")

        assert len(candles) > 0
        assert len(mock.get_ohlc_calls) == 1

    def test_get_sentiment_returns_none(self):
        """Test that Tiingo mock returns None for sentiment."""
        mock = create_mock_tiingo()
        sentiment = mock.get_sentiment("AAPL")

        assert sentiment is None

    def test_fail_mode(self):
        """Test fail mode raises errors."""
        mock = create_mock_tiingo(fail_mode=True)

        with pytest.raises(RuntimeError):
            mock.get_news(["AAPL"])

    def test_reset(self):
        """Test mock reset."""
        mock = create_mock_tiingo()
        mock.get_news(["AAPL"])
        assert len(mock.get_news_calls) == 1

        mock.reset()
        assert len(mock.get_news_calls) == 0


class TestMockFinnhubAdapter:
    """Tests for mock Finnhub adapter."""

    def test_create_mock(self):
        """Test mock factory function."""
        mock = create_mock_finnhub(seed=123)
        assert mock.seed == 123

    def test_get_sentiment(self):
        """Test mock sentiment retrieval."""
        mock = create_mock_finnhub()
        sentiment = mock.get_sentiment("AAPL")

        assert sentiment is not None
        assert sentiment.ticker == "AAPL"

    def test_fail_mode(self):
        """Test fail mode raises errors."""
        mock = create_mock_finnhub(fail_mode=True)

        with pytest.raises(RuntimeError):
            mock.get_sentiment("AAPL")


class TestMockSendGrid:
    """Tests for mock SendGrid service."""

    def test_create_mock(self):
        """Test mock factory function."""
        mock = create_mock_sendgrid()
        assert len(mock.sent_emails) == 0

    def test_send_email(self):
        """Test email capture."""
        mock = create_mock_sendgrid()
        result = mock.send_email(
            to_email="user@example.com",
            from_email="noreply@app.com",
            subject="Test",
            html_content="<p>Hello</p>",
        )

        assert result["status_code"] == 202
        assert len(mock.sent_emails) == 1

    def test_assert_email_sent(self):
        """Test email assertion helper."""
        mock = create_mock_sendgrid()
        mock.send_email(
            to_email="user@example.com",
            from_email="noreply@app.com",
            subject="Welcome",
            html_content="<p>Hello</p>",
        )

        email = mock.assert_email_sent(to_email="user@example.com")
        assert email.subject == "Welcome"

    def test_assert_no_emails_sent(self):
        """Test no-emails assertion."""
        mock = create_mock_sendgrid()
        mock.assert_no_emails_sent()  # Should not raise

    def test_fail_mode(self):
        """Test fail mode raises errors."""
        mock = create_mock_sendgrid()
        mock.fail_mode = True

        with pytest.raises(RuntimeError):
            mock.send_email(
                to_email="user@example.com",
                from_email="noreply@app.com",
                subject="Test",
                html_content="<p>Hello</p>",
            )

    def test_rate_limit_mode(self):
        """Test rate limit mode."""
        mock = create_mock_sendgrid()
        mock.rate_limit_mode = True

        result = mock.send_email(
            to_email="user@example.com",
            from_email="noreply@app.com",
            subject="Test",
            html_content="<p>Hello</p>",
        )

        assert result["status_code"] == 429
        assert "retry_after" in result


class TestConfigGenerator:
    """Tests for configuration generator."""

    def test_create_generator(self):
        """Test generator factory function."""
        gen = create_config_generator(seed=123)
        assert gen._seed == 123

    def test_generate_config_returns_configuration(self):
        """Test that generate_config returns SyntheticConfiguration."""
        gen = create_config_generator()
        config = gen.generate_config("test-run-1")

        assert isinstance(config, SyntheticConfiguration)
        assert config.name.startswith("Test-Config-")
        assert len(config.tickers) == 3  # Default ticker_count

    def test_generate_config_deterministic(self):
        """Test that same seed produces same config."""
        gen1 = create_config_generator(seed=12345)
        gen2 = create_config_generator(seed=12345)

        config1 = gen1.generate_config("test-run-1")
        config2 = gen2.generate_config("test-run-1")

        assert config1.name == config2.name
        assert config1.config_id == config2.config_id
        assert len(config1.tickers) == len(config2.tickers)
        for t1, t2 in zip(config1.tickers, config2.tickers, strict=True):
            assert t1.symbol == t2.symbol
            assert t1.weight == t2.weight

    def test_generate_config_different_seeds(self):
        """Test that different seeds produce different configs."""
        gen1 = create_config_generator(seed=42)
        gen2 = create_config_generator(seed=99)

        config1 = gen1.generate_config("test-run-1")
        config2 = gen2.generate_config("test-run-1")

        # Names should differ (different hex suffix)
        assert config1.name != config2.name

    def test_generate_tickers_normalized_weights(self):
        """Test that ticker weights sum to 1.0."""
        gen = create_config_generator()
        tickers = gen.generate_tickers(count=4)

        total_weight = sum(t.weight for t in tickers)
        assert abs(total_weight - 1.0) < 0.0001

    def test_generate_tickers_no_duplicates(self):
        """Test that generated tickers are unique."""
        gen = create_config_generator()
        tickers = gen.generate_tickers(count=5)

        symbols = [t.symbol for t in tickers]
        assert len(symbols) == len(set(symbols))

    def test_ticker_count_validation_min(self):
        """Test that ticker_count < 1 raises ValueError."""
        gen = create_config_generator()
        with pytest.raises(ValueError, match="min 1 ticker"):
            gen.generate_config("test-run-1", ticker_count=0)

    def test_ticker_count_validation_max(self):
        """Test that ticker_count > 5 raises ValueError."""
        gen = create_config_generator()
        with pytest.raises(ValueError, match="max 5 tickers"):
            gen.generate_config("test-run-1", ticker_count=6)

    def test_invalid_seed_type(self):
        """Test that non-int seed raises TypeError."""
        with pytest.raises(TypeError):
            create_config_generator(seed="not an int")

    def test_reset_generator(self):
        """Test generator reset restores state."""
        gen = create_config_generator(seed=42)
        config1 = gen.generate_config("test-run-1")

        gen.reset(42)
        config2 = gen.generate_config("test-run-1")

        assert config1.name == config2.name
        assert config1.config_id == config2.config_id

    def test_generate_user_id_format(self):
        """Test user ID format includes test run ID."""
        gen = create_config_generator()
        user_id = gen.generate_user_id("e2e-abc123")

        assert user_id.startswith("e2e-abc123-user-")
        assert len(user_id) > len("e2e-abc123-user-")

    def test_generate_name_custom_prefix(self):
        """Test name generation with custom prefix."""
        gen = create_config_generator()
        name = gen.generate_name("My-Custom-Prefix")

        assert name.startswith("My-Custom-Prefix-")

    def test_to_api_payload(self):
        """Test SyntheticConfiguration.to_api_payload().

        API v2 expects tickers as simple string list (not objects with weight).
        """
        gen = create_config_generator()
        config = gen.generate_config("test-run-1", ticker_count=2)
        payload = config.to_api_payload()

        assert "name" in payload
        assert "tickers" in payload
        assert len(payload["tickers"]) == 2
        # API v2 expects simple strings, not objects
        assert all(isinstance(t, str) for t in payload["tickers"])
        # Verify tickers match the symbols from the config
        assert payload["tickers"] == [t.symbol for t in config.tickers]


class TestOracleApiSentiment:
    """Tests for oracle API sentiment computation and validation."""

    def test_compute_expected_api_sentiment_empty_articles(self):
        """Test sentiment computation with no articles."""
        oracle = create_test_oracle(seed=42)
        config = create_config_generator(seed=42).generate_config("test-run")

        result = oracle.compute_expected_api_sentiment(config, [])

        assert result.expected_value == 0.0
        assert result.metadata["article_count"] == 0
        assert result.metadata["reason"] == "no_articles"

    def test_compute_expected_api_sentiment_with_articles(self):
        """Test sentiment computation with articles."""
        oracle = create_test_oracle(seed=42)
        config = create_config_generator(seed=42).generate_config("test-run")

        # Generate synthetic news
        from tests.fixtures.synthetic.news_generator import create_news_generator

        news_gen = create_news_generator(seed=42)
        tickers = [t.symbol for t in config.tickers]
        articles = news_gen.generate_articles(tickers, count=10, days_back=7)

        result = oracle.compute_expected_api_sentiment(config, articles)

        assert isinstance(result, OracleExpectation)
        assert result.metric_name == "sentiment_score"
        assert -1.0 <= result.expected_value <= 1.0
        assert result.tolerance == 0.01
        assert result.metadata["article_count"] == 10

    def test_compute_expected_api_sentiment_deterministic(self):
        """Test that same inputs produce same output."""
        oracle1 = create_test_oracle(seed=42)
        oracle2 = create_test_oracle(seed=42)

        config1 = create_config_generator(seed=42).generate_config("test-run")
        config2 = create_config_generator(seed=42).generate_config("test-run")

        from tests.fixtures.synthetic.news_generator import create_news_generator

        news1 = create_news_generator(seed=42).generate_articles(
            [t.symbol for t in config1.tickers], 10
        )
        news2 = create_news_generator(seed=42).generate_articles(
            [t.symbol for t in config2.tickers], 10
        )

        result1 = oracle1.compute_expected_api_sentiment(config1, news1)
        result2 = oracle2.compute_expected_api_sentiment(config2, news2)

        assert result1.expected_value == result2.expected_value

    def test_validate_api_response_passing(self):
        """Test validation when response matches expectation."""
        oracle = create_test_oracle()

        expectation = OracleExpectation(
            metric_name="sentiment_score",
            expected_value=0.5,
            tolerance=0.01,
        )

        response = {"sentiment_score": 0.505}
        result = oracle.validate_api_response(response, expectation)

        assert result.passed is True
        assert "matches" in result.message

    def test_validate_api_response_failing(self):
        """Test validation when response differs from expectation."""
        oracle = create_test_oracle()

        expectation = OracleExpectation(
            metric_name="sentiment_score",
            expected_value=0.5,
            tolerance=0.01,
        )

        response = {"sentiment_score": 0.7}
        result = oracle.validate_api_response(response, expectation)

        assert result.passed is False
        assert "differs" in result.message

    def test_validate_api_response_missing_field(self):
        """Test validation when response missing sentiment."""
        oracle = create_test_oracle()

        expectation = OracleExpectation(
            metric_name="sentiment_score",
            expected_value=0.5,
        )

        response = {"other_field": "value"}
        result = oracle.validate_api_response(response, expectation)

        assert result.passed is False
        assert "Could not extract" in result.message

    def test_validate_api_response_tolerance_override(self):
        """Test that tolerance can be overridden."""
        oracle = create_test_oracle()

        expectation = OracleExpectation(
            metric_name="sentiment_score",
            expected_value=0.5,
            tolerance=0.01,  # Default tight tolerance
        )

        # This would fail with 0.01 tolerance but pass with 0.1
        response = {"sentiment_score": 0.55}

        # Fail with default tolerance
        result1 = oracle.validate_api_response(response, expectation)
        assert result1.passed is False

        # Pass with relaxed tolerance
        result2 = oracle.validate_api_response(response, expectation, tolerance=0.1)
        assert result2.passed is True

    def test_extract_sentiment_nested_data(self):
        """Test extraction from nested response format."""
        oracle = create_test_oracle()

        response = {"data": {"sentiment_score": 0.75}}

        expectation = OracleExpectation(
            metric_name="sentiment_score",
            expected_value=0.75,
        )

        result = oracle.validate_api_response(response, expectation)
        assert result.passed is True

    def test_extract_sentiment_sentiments_list(self):
        """Test extraction from list of sentiments."""
        oracle = create_test_oracle()

        response = {
            "sentiments": [
                {"score": 0.4},
                {"score": 0.6},
            ]
        }

        # Average is 0.5
        expectation = OracleExpectation(
            metric_name="sentiment_score",
            expected_value=0.5,
        )

        result = oracle.validate_api_response(response, expectation)
        assert result.passed is True


class TestOracleExpectation:
    """Tests for OracleExpectation dataclass."""

    def test_is_within_tolerance_pass(self):
        """Test value within tolerance passes."""
        expectation = OracleExpectation(
            metric_name="sentiment_score",
            expected_value=0.75,
            tolerance=0.01,
        )
        assert expectation.is_within_tolerance(0.755) is True
        assert expectation.is_within_tolerance(0.745) is True
        assert expectation.is_within_tolerance(0.75) is True

    def test_is_within_tolerance_fail(self):
        """Test value outside tolerance fails."""
        expectation = OracleExpectation(
            metric_name="sentiment_score",
            expected_value=0.75,
            tolerance=0.01,
        )
        assert expectation.is_within_tolerance(0.77) is False
        assert expectation.is_within_tolerance(0.73) is False

    def test_difference_calculation(self):
        """Test difference is absolute."""
        expectation = OracleExpectation(
            metric_name="atr",
            expected_value=10.0,
        )
        assert expectation.difference(10.5) == 0.5
        assert expectation.difference(9.5) == 0.5


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_from_comparison_pass(self):
        """Test ValidationResult for passing comparison."""
        expectation = OracleExpectation(
            metric_name="sentiment",
            expected_value=0.5,
            tolerance=0.01,
        )
        result = ValidationResult.from_comparison(expectation, 0.505)

        assert result.passed is True
        assert result.actual_value == 0.505
        assert result.difference == pytest.approx(0.005)
        assert "matches" in result.message

    def test_from_comparison_fail(self):
        """Test ValidationResult for failing comparison."""
        expectation = OracleExpectation(
            metric_name="sentiment",
            expected_value=0.5,
            tolerance=0.01,
        )
        result = ValidationResult.from_comparison(expectation, 0.6)

        assert result.passed is False
        assert result.actual_value == 0.6
        assert result.difference == pytest.approx(0.1)
        assert "differs" in result.message
        assert "exceeds tolerance" in result.message
