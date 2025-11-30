"""Synthetic configuration generator for E2E tests.

Generates deterministic, reproducible configurations for API tests.
"""

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar


@dataclass
class SyntheticTicker:
    """Generated ticker with weight."""

    symbol: str
    weight: float

    def to_dict(self) -> dict:
        """Convert to dict for API payload."""
        return {"symbol": self.symbol, "weight": self.weight}


@dataclass
class SyntheticConfiguration:
    """Generated test configuration."""

    config_id: str
    name: str
    tickers: list[SyntheticTicker]
    created_at: datetime
    user_id: str

    def to_api_payload(self) -> dict:
        """Convert to API request payload.

        Note: API v2 expects tickers as simple string list, not objects.
        The weight field is only used for internal test calculations.
        """
        return {
            "name": self.name,
            "tickers": [t.symbol for t in self.tickers],
        }


class ConfigGenerator:
    """Generates synthetic configurations for API tests.

    Produces deterministic configurations based on seed for reproducible
    testing. Each configuration has a unique name, set of tickers with
    weights, and user ID.
    """

    TICKER_POOL: ClassVar[list[str]] = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "META",
        "NVDA",
        "TSLA",
        "JPM",
        "V",
        "JNJ",
        "WMT",
        "PG",
        "UNH",
        "HD",
        "DIS",
    ]

    def __init__(self, seed: int = 42) -> None:
        """Initialize with random seed.

        Args:
            seed: Random seed for reproducibility
        """
        if not isinstance(seed, int):
            raise TypeError(f"seed must be int, got {type(seed).__name__}")
        self._seed = seed
        self._rng = random.Random(seed)

    def reset(self, seed: int) -> None:
        """Reset generator with new seed.

        Args:
            seed: New random seed
        """
        if not isinstance(seed, int):
            raise TypeError(f"seed must be int, got {type(seed).__name__}")
        self._seed = seed
        self._rng = random.Random(seed)

    def generate_config(
        self,
        test_run_id: str,
        ticker_count: int = 3,
    ) -> SyntheticConfiguration:
        """Generate a synthetic configuration.

        Args:
            test_run_id: Unique test run identifier for isolation
            ticker_count: Number of tickers (1-5)

        Returns:
            SyntheticConfiguration with unique name and tickers

        Raises:
            ValueError: If ticker_count is out of valid range
        """
        if ticker_count < 1:
            raise ValueError("min 1 ticker")
        if ticker_count > 5:
            raise ValueError("max 5 tickers")

        return SyntheticConfiguration(
            config_id=self._generate_id(),
            name=self.generate_name("Test-Config"),
            tickers=self.generate_tickers(ticker_count),
            created_at=datetime.now(UTC),
            user_id=self.generate_user_id(test_run_id),
        )

    def generate_name(self, prefix: str = "Test-Config") -> str:
        """Generate unique configuration name.

        Format: {prefix}-{random_hex}
        Example: "Test-Config-a1b2c3d4"

        Args:
            prefix: Name prefix

        Returns:
            Unique configuration name
        """
        hex_suffix = self._generate_hex(8)
        return f"{prefix}-{hex_suffix}"

    def generate_tickers(self, count: int) -> list[SyntheticTicker]:
        """Generate list of tickers with weights.

        Weights are normalized to sum to 1.0.
        Tickers are sampled without replacement from TICKER_POOL.

        Args:
            count: Number of tickers to generate

        Returns:
            List of SyntheticTicker with normalized weights

        Raises:
            ValueError: If count exceeds available tickers
        """
        if count > len(self.TICKER_POOL):
            raise ValueError("ticker pool exhausted")

        # Sample tickers without replacement
        symbols = self._rng.sample(self.TICKER_POOL, count)

        # Generate raw weights (0.1 to 1.0)
        raw_weights = [self._rng.uniform(0.1, 1.0) for _ in range(count)]

        # Normalize weights to sum to 1.0
        total = sum(raw_weights)
        normalized_weights = [w / total for w in raw_weights]

        return [
            SyntheticTicker(symbol=symbol, weight=weight)
            for symbol, weight in zip(symbols, normalized_weights, strict=True)
        ]

    def generate_user_id(self, test_run_id: str) -> str:
        """Generate test user ID.

        Format: {test_run_id}-user-{random_hex}

        Args:
            test_run_id: Test run identifier

        Returns:
            Unique user ID
        """
        hex_suffix = self._generate_hex(8)
        return f"{test_run_id}-user-{hex_suffix}"

    def _generate_id(self) -> str:
        """Generate unique ID using RNG state.

        Returns:
            UUID-like string
        """
        # Generate 16 random bytes worth of hex
        hex_chars = self._generate_hex(32)
        # Format as UUID
        return f"{hex_chars[:8]}-{hex_chars[8:12]}-{hex_chars[12:16]}-{hex_chars[16:20]}-{hex_chars[20:32]}"

    def _generate_hex(self, length: int) -> str:
        """Generate random hex string of given length.

        Args:
            length: Number of hex characters

        Returns:
            Random hex string
        """
        return "".join(self._rng.choice("0123456789abcdef") for _ in range(length))


def create_config_generator(seed: int = 42) -> ConfigGenerator:
    """Factory function to create config generator.

    Args:
        seed: Random seed for reproducibility

    Returns:
        ConfigGenerator instance
    """
    return ConfigGenerator(seed=seed)
