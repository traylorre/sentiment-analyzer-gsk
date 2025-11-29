# Synthetic test data generators

from tests.fixtures.synthetic.config_generator import (
    ConfigGenerator,
    SyntheticConfiguration,
    SyntheticTicker,
    create_config_generator,
)
from tests.fixtures.synthetic.news_generator import (
    NewsGenerator,
    create_news_generator,
)
from tests.fixtures.synthetic.sentiment_generator import (
    SentimentGenerator,
    create_sentiment_generator,
)
from tests.fixtures.synthetic.test_oracle import (
    OracleExpectation,
    SyntheticTestOracle,
    TestOracle,
    TestScenario,
    ValidationResult,
    create_test_oracle,
)
from tests.fixtures.synthetic.ticker_generator import (
    TickerGenerator,
    create_ticker_generator,
)

__all__ = [
    # Config generator
    "ConfigGenerator",
    "SyntheticConfiguration",
    "SyntheticTicker",
    "create_config_generator",
    # News generator
    "NewsGenerator",
    "create_news_generator",
    # Sentiment generator
    "SentimentGenerator",
    "create_sentiment_generator",
    # Test oracle
    "OracleExpectation",
    "SyntheticTestOracle",
    "TestOracle",
    "TestScenario",
    "ValidationResult",
    "create_test_oracle",
    # Ticker generator
    "TickerGenerator",
    "create_ticker_generator",
]
