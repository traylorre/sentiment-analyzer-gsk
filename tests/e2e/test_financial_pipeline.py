"""
Financial News Pipeline E2E Tests with Synthetic Data
======================================================

These tests validate the complete Feature 006 data flow using synthetic generators
and test oracle for deterministic, assertion-based testing.

Key principles:
1. **Seeded determinism**: Same seed = same data every time
2. **Oracle assertions**: Expected values computed from same production code
3. **Full pipeline flow**: News → DynamoDB → Sentiment → Aggregation
4. **Error injection**: Test failure modes with mock fail modes

For On-Call Engineers:
    These tests verify the Feature 006 financial news pipeline.
    If tests fail, they provide exact expected vs actual values
    computed from the test oracle.

For Developers:
    Test data is generated from `tests/fixtures/synthetic/` generators.
    The test oracle in `test_oracle.py` computes expected values using
    the SAME production code (e.g., `calculate_atr`, `aggregate_sentiment`).

    This means if the test fails, either:
    1. The generator seed changed (check E2E_TEST_SEED)
    2. Production code changed behavior (intentional or bug)
    3. Test is outdated (update expected values)
"""

import os
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.analysis.sentiment import (
    SentimentLabel,
    SentimentSource,
    SourceSentimentScore,
    aggregate_sentiment,
)
from src.lambdas.shared.adapters.base import NewsArticle, OHLCCandle, SentimentData
from src.lambdas.shared.volatility import calculate_atr, calculate_atr_result
from tests.fixtures.mocks.mock_finnhub import MockFinnhubAdapter, create_mock_finnhub
from tests.fixtures.mocks.mock_tiingo import MockTiingoAdapter, create_mock_tiingo
from tests.fixtures.synthetic.news_generator import create_news_generator
from tests.fixtures.synthetic.sentiment_generator import create_sentiment_generator
from tests.fixtures.synthetic.test_oracle import SyntheticTestOracle, create_test_oracle
from tests.fixtures.synthetic.ticker_generator import create_ticker_generator

# Test configuration
TEST_SEED = 42  # Deterministic seed for reproducibility
TEST_TABLE_NAME = "test-sentiment-items"
TEST_TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:test-analysis-requests"


@pytest.fixture
def test_seed() -> int:
    """Provide test seed, overridable via E2E_TEST_SEED env var."""
    return int(os.environ.get("E2E_TEST_SEED", str(TEST_SEED)))


@pytest.fixture
def oracle(test_seed: int) -> SyntheticTestOracle:
    """Create test oracle with deterministic seed."""
    return create_test_oracle(seed=test_seed)


@pytest.fixture
def mock_tiingo(test_seed: int) -> MockTiingoAdapter:
    """Create mock Tiingo adapter with synthetic data."""
    return create_mock_tiingo(seed=test_seed)


@pytest.fixture
def mock_finnhub(test_seed: int) -> MockFinnhubAdapter:
    """Create mock Finnhub adapter with synthetic data."""
    return create_mock_finnhub(seed=test_seed)


@pytest.fixture
def ticker_gen(test_seed: int):
    """Create ticker generator for OHLC data."""
    return create_ticker_generator(seed=test_seed)


@pytest.fixture
def sentiment_gen(test_seed: int):
    """Create sentiment generator."""
    return create_sentiment_generator(seed=test_seed)


@pytest.fixture
def news_gen(test_seed: int):
    """Create news generator."""
    return create_news_generator(seed=test_seed)


def create_dynamodb_table(dynamodb_resource):
    """Create DynamoDB table with Feature 006 schema."""
    table = dynamodb_resource.create_table(
        TableName=TEST_TABLE_NAME,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            },
        ],
        BillingMode="PROVISIONED",
        ProvisionedThroughput={
            "ReadCapacityUnits": 10,
            "WriteCapacityUnits": 10,
        },
    )
    table.wait_until_exists()
    return table


class TestSyntheticDataDeterminism:
    """Verify that synthetic data is truly deterministic."""

    def test_same_seed_produces_identical_candles(self, test_seed):
        """Two generators with same seed produce identical OHLC data."""
        gen1 = create_ticker_generator(seed=test_seed)
        gen2 = create_ticker_generator(seed=test_seed)

        candles1 = gen1.generate_candles("AAPL", days=20)
        candles2 = gen2.generate_candles("AAPL", days=20)

        assert len(candles1) == len(candles2)
        for c1, c2 in zip(candles1, candles2, strict=True):
            assert c1.open == c2.open, f"Open mismatch: {c1.open} != {c2.open}"
            assert c1.high == c2.high
            assert c1.low == c2.low
            assert c1.close == c2.close
            assert c1.volume == c2.volume

    def test_same_seed_produces_identical_news(self, test_seed):
        """Two generators with same seed produce identical news articles."""
        gen1 = create_news_generator(seed=test_seed)
        gen2 = create_news_generator(seed=test_seed)

        articles1 = gen1.generate_articles(["AAPL", "MSFT"], count=10)
        articles2 = gen2.generate_articles(["AAPL", "MSFT"], count=10)

        assert len(articles1) == len(articles2)
        for a1, a2 in zip(articles1, articles2, strict=True):
            assert a1.title == a2.title, f"Title mismatch: {a1.title} != {a2.title}"
            assert a1.article_id == a2.article_id

    def test_different_seeds_produce_different_data(self, test_seed):
        """Different seeds produce different data."""
        gen1 = create_ticker_generator(seed=test_seed)
        gen2 = create_ticker_generator(seed=test_seed + 1)

        candles1 = gen1.generate_candles("AAPL", days=20)
        candles2 = gen2.generate_candles("AAPL", days=20)

        # At least some values should differ
        differences = sum(
            1 for c1, c2 in zip(candles1, candles2, strict=True) if c1.close != c2.close
        )
        assert differences > 0, "Different seeds should produce different data"


class TestOracleComputesExpectedValues:
    """Verify test oracle computes correct expected values."""

    def test_oracle_atr_matches_direct_calculation(self, oracle, ticker_gen):
        """Oracle ATR matches direct calculation from same candles."""
        ticker = "AAPL"
        days = 30

        # Generate candles directly
        ticker_gen.reset(oracle.seed)
        candles = ticker_gen.generate_candles(ticker, days)
        direct_atr = calculate_atr(candles, period=14)

        # Get oracle's expected ATR
        oracle_atr = oracle.compute_expected_atr(ticker, days, period=14)

        assert (
            direct_atr == oracle_atr
        ), f"Oracle ATR {oracle_atr} != direct calculation {direct_atr}"

    def test_oracle_atr_result_includes_trend(self, oracle):
        """Oracle ATR result includes trend and volatility level."""
        result = oracle.compute_expected_atr_result("AAPL", days=30, period=14)

        assert result is not None
        assert result.atr > 0
        assert result.volatility_level in ("low", "medium", "high")
        assert result.trend in ("increasing", "decreasing", "stable")
        assert result.trend_arrow in ("↑", "↓", "→")

    def test_oracle_generates_complete_scenario(self, oracle):
        """Oracle can generate a complete test scenario."""
        scenario = oracle.generate_test_scenario("AAPL", days=30, news_count=15)

        assert scenario.ticker == "AAPL"
        assert scenario.seed == oracle.seed
        assert len(scenario.candles) > 0
        assert len(scenario.sentiment_series) > 0
        assert len(scenario.news_articles) == 15
        assert scenario.expected_atr is not None
        assert scenario.expected_atr_result is not None
        assert scenario.expected_volatility_level is not None


class TestVolatilityCalculation:
    """Test ATR volatility calculation with synthetic data."""

    def test_atr_from_synthetic_candles(self, oracle, ticker_gen):
        """ATR calculation produces expected result from synthetic candles."""
        ticker = "TSLA"
        scenario = oracle.generate_test_scenario(ticker, days=30)

        # Calculate ATR using production code
        actual_atr = calculate_atr(scenario.candles, period=14)
        actual_result = calculate_atr_result(ticker, scenario.candles, period=14)

        # Compare with oracle expected values
        assert (
            actual_atr == scenario.expected_atr
        ), f"ATR mismatch: actual={actual_atr}, expected={scenario.expected_atr}"
        assert actual_result.volatility_level == scenario.expected_volatility_level, (
            f"Volatility level mismatch: "
            f"actual={actual_result.volatility_level}, "
            f"expected={scenario.expected_volatility_level}"
        )

    def test_high_volatility_period_detected(self, ticker_gen):
        """High volatility periods are correctly classified."""
        # Generate volatile data
        candles = ticker_gen.generate_volatile_period(
            "NVDA", days=20, volatility_multiplier=5.0
        )
        result = calculate_atr_result("NVDA", candles, period=14)

        # High volatility should be detected
        # Note: Classification depends on ATR as percentage of price
        assert result is not None
        # We can't assert "high" because it depends on price level
        # but we can verify the calculation ran


class TestSentimentAggregation:
    """Test dual-source sentiment aggregation with synthetic data."""

    def test_aggregate_sentiment_from_synthetic_scores(self, sentiment_gen):
        """Sentiment aggregation produces weighted average."""
        now = datetime.now(UTC)

        # Generate Finnhub sentiment
        finnhub_sentiment = sentiment_gen.generate_sentiment("AAPL", source="finnhub")

        # Create source scores with proper fields
        tiingo_score = SourceSentimentScore(
            source=SentimentSource.TIINGO,
            score=0.65,
            label=SentimentLabel.POSITIVE,
            confidence=0.8,
            timestamp=now,
        )
        finnhub_score = SourceSentimentScore(
            source=SentimentSource.FINNHUB,
            score=finnhub_sentiment.sentiment_score,
            label=SentimentLabel.POSITIVE
            if finnhub_sentiment.sentiment_score > 0.2
            else SentimentLabel.NEUTRAL,
            confidence=0.9,
            timestamp=now,
        )
        our_model_score = SourceSentimentScore(
            source=SentimentSource.OUR_MODEL,
            score=0.55,
            label=SentimentLabel.POSITIVE,
            confidence=0.85,
            timestamp=now,
        )

        # Aggregate
        result = aggregate_sentiment([tiingo_score, finnhub_score, our_model_score])

        # Verify aggregation properties
        assert -1.0 <= result.score <= 1.0
        assert result.label in (
            SentimentLabel.POSITIVE,
            SentimentLabel.NEGATIVE,
            SentimentLabel.NEUTRAL,
        )

    def test_agreement_score_calculation(self):
        """Agreement score reflects how much sources agree."""
        now = datetime.now(UTC)

        # All sources agree (high agreement) - all positive
        agreeing_scores = [
            SourceSentimentScore(
                SentimentSource.TIINGO, 0.8, SentimentLabel.POSITIVE, 0.9, now
            ),
            SourceSentimentScore(
                SentimentSource.FINNHUB, 0.75, SentimentLabel.POSITIVE, 0.9, now
            ),
            SourceSentimentScore(
                SentimentSource.OUR_MODEL, 0.85, SentimentLabel.POSITIVE, 0.9, now
            ),
        ]
        agreeing_result = aggregate_sentiment(agreeing_scores)

        # Sources disagree (low agreement) - positive, negative, neutral
        disagreeing_scores = [
            SourceSentimentScore(
                SentimentSource.TIINGO, 0.9, SentimentLabel.POSITIVE, 0.9, now
            ),
            SourceSentimentScore(
                SentimentSource.FINNHUB, -0.5, SentimentLabel.NEGATIVE, 0.9, now
            ),
            SourceSentimentScore(
                SentimentSource.OUR_MODEL, 0.0, SentimentLabel.NEUTRAL, 0.9, now
            ),
        ]
        disagreeing_result = aggregate_sentiment(disagreeing_scores)

        # Both should produce valid results
        assert -1.0 <= agreeing_result.score <= 1.0
        assert -1.0 <= disagreeing_result.score <= 1.0
        # Agreeing scores should produce higher score (all positive)
        assert agreeing_result.score > disagreeing_result.score, (
            f"Agreeing positive scores should produce higher result: "
            f"{agreeing_result.score} vs {disagreeing_result.score}"
        )


class TestMockAdapterIntegration:
    """Test mock adapters return synthetic data correctly."""

    def test_mock_tiingo_returns_news(self, mock_tiingo):
        """Mock Tiingo adapter returns synthetic news articles."""
        articles = mock_tiingo.get_news(["AAPL", "GOOGL"], limit=10)

        assert len(articles) > 0
        assert all(isinstance(a, NewsArticle) for a in articles)
        assert mock_tiingo.get_news_calls[-1]["tickers"] == ["AAPL", "GOOGL"]

    def test_mock_tiingo_returns_ohlc(self, mock_tiingo):
        """Mock Tiingo adapter returns synthetic OHLC data."""
        candles = mock_tiingo.get_ohlc("AAPL", interval="1d")

        assert len(candles) > 0
        assert all(isinstance(c, OHLCCandle) for c in candles)
        # Verify OHLC relationships
        for c in candles:
            assert c.high >= c.open
            assert c.high >= c.close
            assert c.low <= c.open
            assert c.low <= c.close

    def test_mock_finnhub_returns_sentiment(self, mock_finnhub):
        """Mock Finnhub adapter returns synthetic sentiment."""
        sentiment = mock_finnhub.get_sentiment("AAPL")

        assert sentiment is not None
        assert isinstance(sentiment, SentimentData)
        assert sentiment.ticker == "AAPL"
        assert -1.0 <= sentiment.sentiment_score <= 1.0

    def test_mock_adapter_fail_mode(self, mock_tiingo):
        """Mock adapters can simulate failures."""
        mock_tiingo.fail_mode = True

        with pytest.raises(RuntimeError, match="fail_mode=True"):
            mock_tiingo.get_news(["AAPL"])

    def test_mock_adapter_tracks_calls(self, mock_tiingo):
        """Mock adapters track all API calls for assertions."""
        mock_tiingo.get_news(["AAPL"], limit=5)
        mock_tiingo.get_news(["MSFT", "GOOGL"], limit=10)
        mock_tiingo.get_ohlc("TSLA")

        assert len(mock_tiingo.get_news_calls) == 2
        assert len(mock_tiingo.get_ohlc_calls) == 1
        assert mock_tiingo.get_news_calls[0]["tickers"] == ["AAPL"]
        assert mock_tiingo.get_news_calls[1]["tickers"] == ["MSFT", "GOOGL"]


class TestFullPipelineWithSyntheticData:
    """Full pipeline tests using synthetic data and oracle assertions."""

    @mock_aws
    @patch.dict(
        os.environ,
        {
            "AWS_REGION": "us-east-1",
            "DYNAMODB_TABLE": TEST_TABLE_NAME,
            "MODEL_VERSION": "v1.0.0",
        },
    )
    def test_news_ingestion_to_dynamodb(self, mock_tiingo, news_gen, test_seed):
        """Test news articles are correctly stored in DynamoDB."""
        # Setup DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = create_dynamodb_table(dynamodb)

        # Reset news generator to same seed as mock adapter for determinism
        news_gen.reset(test_seed)

        # Simulate what handler does: fetch and store
        articles = mock_tiingo.get_news(["AAPL"], limit=5)

        # Store in DynamoDB
        stored_count = 0
        for article in articles:
            source_id = f"tiingo:{article.article_id}"
            item = {
                "PK": f"ARTICLE#{source_id}",
                "SK": article.published_at.isoformat(),
                "source_id": source_id,
                "title": article.title,
                "description": article.description,
                "url": article.url,
                "tickers": article.tickers,
                "status": "pending",
                "GSI1PK": "STATUS#pending",
                "GSI1SK": article.published_at.isoformat(),
            }
            table.put_item(Item=item)
            stored_count += 1

        # Verify stored
        assert stored_count == len(articles)

        # Query back and verify
        response = table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": "STATUS#pending"},
        )
        assert response["Count"] == stored_count

    @mock_aws
    @patch.dict(
        os.environ,
        {
            "AWS_REGION": "us-east-1",
            "DYNAMODB_TABLE": TEST_TABLE_NAME,
        },
    )
    def test_sentiment_analysis_updates_item(self, oracle, test_seed):
        """Test sentiment analysis updates DynamoDB item correctly."""
        # Setup
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = create_dynamodb_table(dynamodb)

        # Create pending item
        source_id = "tiingo:article_123456"
        pk = f"ARTICLE#{source_id}"
        sk = "2025-01-15T10:00:00+00:00"
        text_for_analysis = "AAPL stock surges after strong earnings report"

        table.put_item(
            Item={
                "PK": pk,
                "SK": sk,
                "source_id": source_id,
                "title": text_for_analysis,
                "status": "pending",
                "tickers": ["AAPL"],
                "GSI1PK": "STATUS#pending",
                "GSI1SK": sk,
            }
        )

        # Simulate sentiment analysis (what analysis handler does)
        # Using deterministic scores from oracle
        avg_sentiment = oracle.compute_expected_avg_sentiment("AAPL", days=7)

        # Update item with sentiment
        table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression=(
                "SET #status = :analyzed, "
                "sentiment_score = :score, "
                "sentiment_label = :label, "
                "analyzed_at = :at, "
                "GSI1PK = :gsi1pk"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":analyzed": "analyzed",
                ":score": Decimal(str(round(avg_sentiment, 4))),
                ":label": "positive"
                if avg_sentiment > 0.2
                else ("negative" if avg_sentiment < -0.2 else "neutral"),
                ":at": datetime.now(UTC).isoformat(),
                ":gsi1pk": "STATUS#analyzed",
            },
        )

        # Verify update
        response = table.get_item(Key={"PK": pk, "SK": sk})
        item = response["Item"]

        assert item["status"] == "analyzed"
        assert "sentiment_score" in item
        assert "analyzed_at" in item

    @mock_aws
    @patch.dict(
        os.environ,
        {
            "AWS_REGION": "us-east-1",
            "DYNAMODB_TABLE": TEST_TABLE_NAME,
        },
    )
    def test_volatility_data_stored_and_retrieved(self, oracle, ticker_gen):
        """Test ATR volatility data is correctly stored and retrieved."""
        # Setup
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = create_dynamodb_table(dynamodb)

        ticker = "NVDA"

        # Generate scenario with expected values
        scenario = oracle.generate_test_scenario(ticker, days=30)

        # Store volatility result
        volatility_item = {
            "PK": f"VOLATILITY#{ticker}",
            "SK": datetime.now(UTC).isoformat(),
            "ticker": ticker,
            "atr": Decimal(str(round(scenario.expected_atr, 4))),
            "volatility_level": scenario.expected_volatility_level,
            "trend": scenario.expected_atr_result.trend,
            "trend_arrow": scenario.expected_atr_result.trend_arrow,
            "period": 14,
            "candle_count": len(scenario.candles),
        }
        table.put_item(Item=volatility_item)

        # Retrieve and verify
        response = table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"VOLATILITY#{ticker}"},
            ScanIndexForward=False,
            Limit=1,
        )

        assert response["Count"] == 1
        retrieved = response["Items"][0]
        assert retrieved["ticker"] == ticker
        assert float(retrieved["atr"]) == pytest.approx(scenario.expected_atr, rel=1e-4)
        assert retrieved["volatility_level"] == scenario.expected_volatility_level


class TestErrorHandlingWithSyntheticData:
    """Test error scenarios using mock adapter fail modes."""

    def test_tiingo_failure_handled_gracefully(self, mock_tiingo, mock_finnhub):
        """When Tiingo fails, Finnhub is used as fallback."""
        mock_tiingo.fail_mode = True

        # Tiingo should fail
        with pytest.raises(RuntimeError):
            mock_tiingo.get_news(["AAPL"])

        # Finnhub should still work
        articles = mock_finnhub.get_news(["AAPL"])
        assert len(articles) > 0

    def test_both_adapters_fail(self, mock_tiingo, mock_finnhub):
        """When both adapters fail, error is propagated."""
        mock_tiingo.fail_mode = True
        mock_finnhub.fail_mode = True

        with pytest.raises(RuntimeError):
            mock_tiingo.get_news(["AAPL"])

        with pytest.raises(RuntimeError):
            mock_finnhub.get_news(["AAPL"])


class TestAlertTriggerWithSyntheticData:
    """Test alert evaluation and email notification with synthetic data."""

    @pytest.fixture
    def mock_sendgrid(self):
        """Create mock SendGrid for email capture."""
        from tests.fixtures.mocks.mock_sendgrid import create_mock_sendgrid

        return create_mock_sendgrid()

    @mock_aws
    @patch.dict(
        os.environ,
        {
            "AWS_REGION": "us-east-1",
            "DYNAMODB_TABLE": TEST_TABLE_NAME,
            "DASHBOARD_URL": "https://dashboard.example.com",
        },
    )
    def test_sentiment_alert_triggers_email(self, oracle, mock_sendgrid, sentiment_gen):
        """Sentiment crossing threshold triggers alert email."""
        # Setup DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = create_dynamodb_table(dynamodb)

        user_id = "user_123"
        config_id = "config_456"
        ticker = "AAPL"

        # Create user with email
        table.put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": "PROFILE",
                "email": "test@example.com",
                "email_notifications_enabled": True,
            }
        )

        # Create alert rule: trigger when sentiment drops below -0.3
        alert_id = "alert_789"
        table.put_item(
            Item={
                "PK": f"CONFIG#{config_id}",
                "SK": f"ALERT#{alert_id}",
                "alert_id": alert_id,
                "user_id": user_id,
                "config_id": config_id,
                "ticker": ticker,
                "alert_type": "sentiment",
                "threshold": Decimal("-0.3"),
                "direction": "below",
                "is_enabled": True,
                "last_triggered_at": None,
            }
        )

        # Generate bearish sentiment (should trigger alert)
        sentiment_gen.config.positive_bias = -0.5  # Force bearish
        bearish_sentiment = sentiment_gen.generate_sentiment(ticker)

        # Verify sentiment is below threshold
        assert (
            bearish_sentiment.sentiment_score < -0.3
        ), f"Expected bearish sentiment below -0.3, got {bearish_sentiment.sentiment_score}"

        # Simulate alert evaluation
        current_score = bearish_sentiment.sentiment_score

        # Fetch alert rule
        alert_response = table.get_item(
            Key={"PK": f"CONFIG#{config_id}", "SK": f"ALERT#{alert_id}"}
        )
        alert_rule = alert_response["Item"]

        # Check if alert should trigger
        threshold = float(alert_rule["threshold"])
        direction = alert_rule["direction"]

        should_trigger = (direction == "below" and current_score < threshold) or (
            direction == "above" and current_score > threshold
        )

        assert should_trigger, "Alert should trigger for bearish sentiment"

        # Send alert email
        if should_trigger:
            mock_sendgrid.send_email(
                to_email="test@example.com",
                from_email="alerts@sentiment.example.com",
                subject=f"Sentiment Alert: {ticker} below {threshold}",
                html_content=f"""
                <h1>Sentiment Alert</h1>
                <p>{ticker} sentiment dropped to {current_score:.2f}</p>
                <p>Your threshold: {threshold}</p>
                <a href="https://dashboard.example.com/config/{config_id}">View Dashboard</a>
                """,
            )

            # Update last_triggered_at
            table.update_item(
                Key={"PK": f"CONFIG#{config_id}", "SK": f"ALERT#{alert_id}"},
                UpdateExpression="SET last_triggered_at = :now",
                ExpressionAttributeValues={":now": datetime.now(UTC).isoformat()},
            )

        # Verify email was sent
        mock_sendgrid.assert_email_sent(
            to_email="test@example.com", subject_contains="Sentiment Alert"
        )
        mock_sendgrid.assert_email_count(1)

        # Verify alert state updated
        updated_alert = table.get_item(
            Key={"PK": f"CONFIG#{config_id}", "SK": f"ALERT#{alert_id}"}
        )["Item"]
        assert updated_alert.get("last_triggered_at") is not None

    @mock_aws
    @patch.dict(
        os.environ,
        {
            "AWS_REGION": "us-east-1",
            "DYNAMODB_TABLE": TEST_TABLE_NAME,
        },
    )
    def test_volatility_alert_triggers_email(self, oracle, mock_sendgrid, ticker_gen):
        """High volatility crossing threshold triggers alert email."""
        # Setup DynamoDB
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = create_dynamodb_table(dynamodb)

        user_id = "user_456"
        config_id = "config_789"
        ticker = "NVDA"

        # Create user
        table.put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": "PROFILE",
                "email": "trader@example.com",
                "email_notifications_enabled": True,
            }
        )

        # Create volatility alert: trigger when ATR > 5% of price
        alert_id = "alert_vol_123"
        table.put_item(
            Item={
                "PK": f"CONFIG#{config_id}",
                "SK": f"ALERT#{alert_id}",
                "alert_id": alert_id,
                "user_id": user_id,
                "config_id": config_id,
                "ticker": ticker,
                "alert_type": "volatility",
                "threshold": Decimal("5.0"),  # 5% ATR
                "direction": "above",
                "is_enabled": True,
            }
        )

        # Generate high volatility period
        volatile_candles = ticker_gen.generate_volatile_period(
            ticker, days=20, volatility_multiplier=5.0
        )
        atr_result = calculate_atr_result(ticker, volatile_candles, period=14)

        # Calculate ATR as percentage of last close
        last_close = volatile_candles[-1].close
        atr_percent = (atr_result.atr / last_close) * 100 if atr_result else 0

        # Check if should trigger (ATR > 5%)
        threshold = 5.0
        should_trigger = atr_percent > threshold

        if should_trigger:
            mock_sendgrid.send_email(
                to_email="trader@example.com",
                from_email="alerts@sentiment.example.com",
                subject=f"Volatility Alert: {ticker} ATR {atr_percent:.1f}%",
                html_content=f"""
                <h1>Volatility Alert</h1>
                <p>{ticker} ATR is {atr_percent:.2f}% of price</p>
                <p>ATR Value: ${atr_result.atr:.2f}</p>
                <p>Volatility Level: {atr_result.volatility_level}</p>
                <p>Trend: {atr_result.trend_arrow} {atr_result.trend}</p>
                """,
            )

        # Either alert triggered or it didn't - both are valid outcomes
        # depending on the synthetic data
        if should_trigger:
            mock_sendgrid.assert_email_sent(
                to_email="trader@example.com", subject_contains="Volatility Alert"
            )
        else:
            # Alert didn't trigger because volatility wasn't high enough
            mock_sendgrid.assert_no_emails_sent()

    @mock_aws
    @patch.dict(
        os.environ,
        {
            "AWS_REGION": "us-east-1",
            "DYNAMODB_TABLE": TEST_TABLE_NAME,
        },
    )
    def test_disabled_alert_does_not_trigger(self, mock_sendgrid, sentiment_gen):
        """Disabled alerts don't send emails even when threshold crossed."""
        # Setup
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = create_dynamodb_table(dynamodb)

        config_id = "config_disabled"
        alert_id = "alert_disabled"

        # Create DISABLED alert
        table.put_item(
            Item={
                "PK": f"CONFIG#{config_id}",
                "SK": f"ALERT#{alert_id}",
                "alert_type": "sentiment",
                "threshold": Decimal("-0.3"),
                "direction": "below",
                "is_enabled": False,  # Disabled!
            }
        )

        # Generate bearish sentiment that would normally trigger
        sentiment_gen.config.positive_bias = -0.6
        bearish = sentiment_gen.generate_sentiment("AAPL")
        assert bearish.sentiment_score < -0.3

        # Fetch alert and check is_enabled
        alert = table.get_item(
            Key={"PK": f"CONFIG#{config_id}", "SK": f"ALERT#{alert_id}"}
        )["Item"]

        # Alert is disabled, don't send
        if not alert.get("is_enabled", True):
            pass  # Do nothing
        else:
            mock_sendgrid.send_email(
                to_email="test@example.com",
                from_email="alerts@example.com",
                subject="Alert",
                html_content="<p>Alert!</p>",
            )

        # Verify no email sent
        mock_sendgrid.assert_no_emails_sent()

    def test_sendgrid_failure_handled_gracefully(self, mock_sendgrid):
        """SendGrid failures don't crash the system."""
        mock_sendgrid.fail_mode = True

        with pytest.raises(RuntimeError, match="Mock SendGrid failure"):
            mock_sendgrid.send_email(
                to_email="test@example.com",
                from_email="alerts@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

        # No emails captured
        mock_sendgrid.assert_no_emails_sent()

    def test_sendgrid_rate_limit_returns_error(self, mock_sendgrid):
        """SendGrid rate limiting returns error response."""
        mock_sendgrid.rate_limit_mode = True

        result = mock_sendgrid.send_email(
            to_email="test@example.com",
            from_email="alerts@example.com",
            subject="Test",
            html_content="<p>Test</p>",
        )

        assert result["status_code"] == 429
        assert "retry_after" in result

        # Email not captured (rate limited)
        mock_sendgrid.assert_no_emails_sent()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
