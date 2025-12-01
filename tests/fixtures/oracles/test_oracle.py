"""Test oracle for computing expected API responses.

The oracle uses the same deterministic algorithms as the synthetic
data generators to predict what responses should look like.
This enables assertions that compare actual vs expected without
hardcoding expected values in tests.
"""

import random
from datetime import date, timedelta
from typing import Any


class TestOracle:
    """Computes expected API responses for test assertions.

    Uses deterministic seeded random to generate the same data
    as the mock adapters, enabling comparison of actual vs expected.
    """

    # Same thresholds as sentiment history endpoint
    POSITIVE_THRESHOLD = 0.33
    NEGATIVE_THRESHOLD = -0.33

    def __init__(self, seed: int = 42):
        """Initialize test oracle.

        Args:
            seed: Base random seed for deterministic generation
        """
        self.seed = seed

    def expected_sentiment_label(self, score: float) -> str:
        """Compute expected sentiment label for a score.

        Args:
            score: Sentiment score in [-1.0, 1.0]

        Returns:
            Expected label: "positive", "neutral", or "negative"
        """
        if score >= self.POSITIVE_THRESHOLD:
            return "positive"
        if score <= self.NEGATIVE_THRESHOLD:
            return "negative"
        return "neutral"

    def expected_sentiment_history(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        source: str = "aggregated",
    ) -> dict[str, Any]:
        """Compute expected sentiment history response.

        Mirrors the deterministic generation in the sentiment history endpoint.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date for history
            end_date: End date for history
            source: Sentiment source filter

        Returns:
            Expected SentimentHistoryResponse dict
        """
        # Mirror the endpoint's deterministic generation
        random.seed(hash(ticker))

        history = []
        current_date = start_date
        base_score = 0.3  # Same as endpoint

        while current_date <= end_date:
            # Same variability as endpoint
            daily_variation = random.uniform(-0.3, 0.3)  # noqa: S311
            score = max(-1.0, min(1.0, base_score + daily_variation))
            score = round(score, 4)

            label = self.expected_sentiment_label(score)
            confidence = round(random.uniform(0.6, 0.95), 4)  # noqa: S311

            history.append(
                {
                    "date": current_date.isoformat(),
                    "score": score,
                    "source": source,
                    "confidence": confidence,
                    "label": label,
                }
            )

            # Same trend continuation as endpoint
            base_score = score * 0.8 + base_score * 0.2
            current_date += timedelta(days=1)

        return {
            "ticker": ticker.upper(),
            "source": source,
            "history": history,
            "start_date": history[0]["date"] if history else start_date.isoformat(),
            "end_date": history[-1]["date"] if history else end_date.isoformat(),
            "count": len(history),
        }

    def expected_trading_days(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        """Estimate expected number of trading days in a date range.

        Trading days exclude weekends (Saturdays and Sundays).
        This is an approximation - doesn't account for holidays.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Approximate number of trading days
        """
        total_days = (end_date - start_date).days + 1
        full_weeks = total_days // 7
        remaining_days = total_days % 7

        # Each full week has 5 trading days
        trading_days = full_weeks * 5

        # Count trading days in remaining days
        current = start_date + timedelta(days=full_weeks * 7)
        for _ in range(remaining_days):
            if current.weekday() < 5:  # Monday=0 through Friday=4
                trading_days += 1
            current += timedelta(days=1)

        return trading_days

    def expected_trading_day_range(
        self,
        start_date: date,
        end_date: date,
    ) -> tuple[int, int]:
        """Get expected range of trading days (min, max).

        Returns a range to account for market holidays.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Tuple of (min_days, max_days)
        """
        estimated = self.expected_trading_days(start_date, end_date)
        # Allow for ~10% variation due to holidays
        min_days = int(estimated * 0.85)
        max_days = estimated
        return (min_days, max_days)

    def expected_calendar_days(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        """Count calendar days in a date range (inclusive).

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Number of calendar days (including weekends)
        """
        return (end_date - start_date).days + 1

    def date_from_time_range(
        self, time_range: str, end_date: date | None = None
    ) -> date:
        """Calculate start date from time range string.

        Args:
            time_range: Time range code (1W, 1M, 3M, 6M, 1Y)
            end_date: End date (defaults to today)

        Returns:
            Calculated start date
        """
        if end_date is None:
            end_date = date.today()

        range_days = {
            "1W": 7,
            "1M": 30,
            "3M": 90,
            "6M": 180,
            "1Y": 365,
        }

        days = range_days.get(time_range, 30)
        return end_date - timedelta(days=days)

    def expected_candle_count_range(self, time_range: str) -> tuple[int, int]:
        """Get expected range of candle counts for a time range.

        Args:
            time_range: Time range code (1W, 1M, 3M, 6M, 1Y)

        Returns:
            Tuple of (min_candles, max_candles)
        """
        # Approximate trading days per time range
        ranges = {
            "1W": (5, 7),
            "1M": (20, 23),
            "3M": (60, 66),
            "6M": (120, 132),
            "1Y": (250, 260),
        }
        return ranges.get(time_range, (20, 23))

    def expected_history_count(self, time_range: str) -> int:
        """Get expected sentiment history point count for a time range.

        Sentiment includes all calendar days (including weekends).

        Args:
            time_range: Time range code (1W, 1M, 3M, 6M, 1Y)

        Returns:
            Expected number of sentiment points
        """
        range_days = {
            "1W": 8,  # 7 days + 1 (inclusive)
            "1M": 31,
            "3M": 91,
            "6M": 181,
            "1Y": 366,
        }
        return range_days.get(time_range, 31)

    def is_valid_ticker(self, ticker: str) -> tuple[bool, str | None]:
        """Check if ticker is valid per business rules.

        Args:
            ticker: Ticker symbol to validate

        Returns:
            Tuple of (is_valid, error_message or None)
        """
        if not ticker:
            return False, "Ticker cannot be empty"

        ticker = ticker.strip()
        if not ticker:
            return False, "Ticker cannot be only whitespace"

        if len(ticker) > 5:
            return False, f"Ticker must be 1-5 characters, got {len(ticker)}"

        if not ticker.isalpha():
            return False, "Ticker must contain only letters"

        return True, None
