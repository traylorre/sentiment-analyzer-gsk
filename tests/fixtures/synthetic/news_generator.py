"""Synthetic news article generator for deterministic E2E tests.

Generates realistic news articles based on seed values.
Used by test oracle to compute expected outcomes from same inputs.
"""

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from src.lambdas.shared.adapters.base import NewsArticle

# Realistic headline templates by sentiment
HEADLINE_TEMPLATES = {
    "positive": [
        "{ticker} Surges After Strong Earnings Report",
        "{ticker} Hits New All-Time High on Strong Demand",
        "{ticker} Announces Major Partnership Deal",
        "{ticker} Beats Analyst Expectations by Wide Margin",
        "{ticker} Stock Rallies on Positive Guidance",
        "Analysts Upgrade {ticker} After Impressive Quarter",
        "{ticker} Expands into New Markets, Stock Rises",
        "{ticker} Revenue Growth Exceeds Forecasts",
    ],
    "negative": [
        "{ticker} Drops After Missing Revenue Targets",
        "{ticker} Shares Plunge on Weak Guidance",
        "{ticker} Faces Regulatory Investigation",
        "{ticker} Reports Unexpected Quarterly Loss",
        "{ticker} Stock Tumbles Amid Market Concerns",
        "Analysts Downgrade {ticker} on Margin Pressure",
        "{ticker} Announces Layoffs, Stock Falls",
        "{ticker} Cuts Full-Year Outlook",
    ],
    "neutral": [
        "{ticker} Reports Mixed Quarterly Results",
        "{ticker} Maintains Steady Performance",
        "{ticker} Trading Sideways on Light Volume",
        "{ticker} Earnings In Line with Expectations",
        "{ticker} Holds Annual Shareholder Meeting",
        "What to Watch for {ticker} This Quarter",
        "{ticker} Market Update: Key Levels to Monitor",
        "{ticker} Remains Stable Amid Market Volatility",
    ],
}

# Source names (stored in source_name field)
SOURCE_NAMES = [
    "finance",
    "marketwatch",
    "reuters",
    "bloomberg",
    "wsj",
    "cnbc",
    "seekingalpha",
    "fool",
]


@dataclass
class NewsGeneratorConfig:
    """Configuration for news article generation."""

    seed: int = 42
    positive_probability: float = 0.35  # Probability of positive article
    negative_probability: float = 0.25  # Probability of negative article
    # Neutral = 1 - positive - negative


@dataclass
class NewsGenerator:
    """Generates deterministic news articles for testing.

    Uses seeded random number generator for reproducibility.
    Same seed + config always produces identical articles.
    """

    config: NewsGeneratorConfig = field(default_factory=NewsGeneratorConfig)
    _rng: random.Random = field(init=False)

    def __post_init__(self):
        """Initialize random generator with seed."""
        self._rng = random.Random(self.config.seed)

    def reset(self, seed: int | None = None) -> None:
        """Reset generator with optional new seed."""
        if seed is not None:
            self.config.seed = seed
        self._rng = random.Random(self.config.seed)

    def _select_sentiment(self) -> Literal["positive", "negative", "neutral"]:
        """Select article sentiment based on probabilities."""
        roll = self._rng.random()
        if roll < self.config.positive_probability:
            return "positive"
        elif roll < self.config.positive_probability + self.config.negative_probability:
            return "negative"
        else:
            return "neutral"

    def generate_article(
        self,
        tickers: list[str],
        published_at: datetime | None = None,
        sentiment: Literal["positive", "negative", "neutral"] | None = None,
        source: Literal["tiingo", "finnhub"] = "tiingo",
    ) -> NewsArticle:
        """Generate a single news article.

        Args:
            tickers: List of stock symbols mentioned
            published_at: Publication timestamp (defaults to now UTC)
            sentiment: Force specific sentiment (random if None)
            source: Data source (default: tiingo for news)

        Returns:
            NewsArticle with realistic content
        """
        if published_at is None:
            published_at = datetime.now(UTC)

        if sentiment is None:
            sentiment = self._select_sentiment()

        # Select headline template
        templates = HEADLINE_TEMPLATES[sentiment]
        template = self._rng.choice(templates)
        ticker = tickers[0] if tickers else "UNKNOWN"
        headline = template.format(ticker=ticker)

        # Generate article ID
        article_id = f"article_{self._rng.randint(100000, 999999)}"

        # Select source name (the actual publisher)
        source_name = self._rng.choice(SOURCE_NAMES)

        # Generate URL
        slug = headline.lower().replace(" ", "-").replace(",", "")[:50]
        url = f"https://{source_name}.example.com/news/{article_id}/{slug}"

        # Generate description
        description = self._generate_description(ticker, sentiment)

        return NewsArticle(
            article_id=article_id,
            source=source,
            title=headline,
            description=description,
            url=url,
            published_at=published_at,
            tickers=tickers,
            source_name=source_name,
        )

    def _generate_description(
        self, ticker: str, sentiment: Literal["positive", "negative", "neutral"]
    ) -> str:
        """Generate article description based on sentiment."""
        descriptions = {
            "positive": [
                f"Shares of {ticker} rose sharply in today's trading session "
                f"following positive news that exceeded market expectations.",
                f"{ticker} stock gained momentum after management provided "
                f"upbeat commentary on future growth prospects.",
            ],
            "negative": [
                f"{ticker} shares faced selling pressure as investors digested "
                f"concerning developments that raised questions about near-term outlook.",
                f"Market participants turned cautious on {ticker} following "
                f"reports that highlighted emerging challenges.",
            ],
            "neutral": [
                f"{ticker} traded in a narrow range as investors weighed "
                f"mixed signals from recent company announcements.",
                f"Trading activity in {ticker} remained subdued with no "
                f"significant catalysts driving price action.",
            ],
        }
        return self._rng.choice(descriptions[sentiment])

    def generate_articles(
        self,
        tickers: list[str],
        count: int = 10,
        days_back: int = 7,
        end_date: datetime | None = None,
    ) -> list[NewsArticle]:
        """Generate multiple news articles over a time period.

        Args:
            tickers: List of stock symbols
            count: Number of articles to generate
            days_back: Days to spread articles over
            end_date: End date (defaults to now UTC)

        Returns:
            List of NewsArticle sorted by published_at descending
        """
        if end_date is None:
            end_date = datetime.now(UTC)

        articles = []
        for _ in range(count):
            # Distribute articles over the time period
            hours_back = self._rng.randint(0, days_back * 24)
            published_at = end_date - timedelta(hours=hours_back)

            # Sometimes use single ticker, sometimes multiple
            article_tickers = (
                tickers[: self._rng.randint(1, min(3, len(tickers)))]
                if len(tickers) > 1
                else tickers
            )

            article = self.generate_article(article_tickers, published_at)
            articles.append(article)

        # Sort by published_at descending (newest first)
        articles.sort(key=lambda a: a.published_at, reverse=True)
        return articles

    def generate_positive_news_event(
        self,
        ticker: str,
        article_count: int = 5,
    ) -> list[NewsArticle]:
        """Generate a cluster of positive news articles.

        Simulates a positive news event like earnings beat.

        Args:
            ticker: Stock symbol
            article_count: Number of articles

        Returns:
            List of positive NewsArticles
        """
        now = datetime.now(UTC)
        articles = []
        for _ in range(article_count):
            # Cluster articles within a few hours
            published_at = now - timedelta(hours=self._rng.randint(0, 4))
            article = self.generate_article(
                [ticker], published_at, sentiment="positive"
            )
            articles.append(article)

        return articles

    def generate_negative_news_event(
        self,
        ticker: str,
        article_count: int = 5,
    ) -> list[NewsArticle]:
        """Generate a cluster of negative news articles.

        Simulates a negative news event like earnings miss.

        Args:
            ticker: Stock symbol
            article_count: Number of articles

        Returns:
            List of negative NewsArticles
        """
        now = datetime.now(UTC)
        articles = []
        for _ in range(article_count):
            # Cluster articles within a few hours
            published_at = now - timedelta(hours=self._rng.randint(0, 4))
            article = self.generate_article(
                [ticker], published_at, sentiment="negative"
            )
            articles.append(article)

        return articles


def create_news_generator(
    seed: int = 42,
    positive_probability: float = 0.35,
    negative_probability: float = 0.25,
) -> NewsGenerator:
    """Factory function to create a news generator.

    Args:
        seed: Random seed for reproducibility
        positive_probability: Probability of positive article
        negative_probability: Probability of negative article

    Returns:
        Configured NewsGenerator
    """
    config = NewsGeneratorConfig(
        seed=seed,
        positive_probability=positive_probability,
        negative_probability=negative_probability,
    )
    return NewsGenerator(config=config)
