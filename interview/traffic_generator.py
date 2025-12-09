#!/usr/bin/env python3
"""
Synthetic Traffic Generator for Interview Demonstrations.

Generates realistic traffic patterns to demonstrate:
- Authentication flows
- Configuration management
- Sentiment analysis
- Price-sentiment overlay (OHLC + historical sentiment)
- Circuit breaker behavior
- Rate limiting
- Quota tracking

Usage:
    python3 traffic_generator.py --env preprod --scenario all
    python3 traffic_generator.py --env preprod --scenario basic
    python3 traffic_generator.py --env preprod --scenario price-sentiment
    python3 traffic_generator.py --env preprod --scenario circuit-breaker
    python3 traffic_generator.py --env preprod --scenario rate-limit
"""

import argparse
import asyncio
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

# Environment configurations
ENVIRONMENTS = {
    "preprod": "https://ee2a3fxtkxmpwp2bhul3uylmb40hfknf.lambda-url.us-east-1.on.aws",
    "prod": "https://prod-sentiment-dashboard.lambda-url.us-east-1.on.aws",
}

# Sample data for generating realistic traffic
SAMPLE_TICKERS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "JPM",
    "V",
    "WMT",
]
SAMPLE_CONFIG_NAMES = [
    "Tech Giants Watchlist",
    "AI & ML Leaders",
    "Blue Chips Portfolio",
    "Growth Stocks",
    "Value Investing",
    "Dividend Kings",
    "Market Movers",
    "Sector ETFs",
]


@dataclass
class TrafficStats:
    """Track traffic generation statistics."""

    requests_sent: int = 0
    success_count: int = 0
    error_count: int = 0
    rate_limited: int = 0
    circuit_breaker_trips: int = 0
    total_latency_ms: float = 0

    @property
    def avg_latency_ms(self) -> float:
        if self.requests_sent == 0:
            return 0
        return self.total_latency_ms / self.requests_sent

    def print_summary(self) -> None:
        print("\n" + "=" * 50)
        print("TRAFFIC GENERATION SUMMARY")
        print("=" * 50)
        print(f"Total Requests:      {self.requests_sent}")
        print(f"Successful:          {self.success_count} ({self.success_rate:.1f}%)")
        print(f"Errors:              {self.error_count}")
        print(f"Rate Limited:        {self.rate_limited}")
        print(f"Circuit Breaker:     {self.circuit_breaker_trips}")
        print(f"Avg Latency:         {self.avg_latency_ms:.1f}ms")
        print("=" * 50)

    @property
    def success_rate(self) -> float:
        if self.requests_sent == 0:
            return 0
        return (self.success_count / self.requests_sent) * 100


class TrafficGenerator:
    """Generate synthetic traffic for the sentiment analyzer service."""

    def __init__(self, base_url: str, verbose: bool = True):
        self.base_url = base_url
        self.verbose = verbose
        self.stats = TrafficStats()
        self.sessions: list[dict[str, Any]] = []

    def log(self, message: str, emoji: str = "  ") -> None:
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {emoji} {message}")

    async def make_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        endpoint: str,
        headers: dict | None = None,
        json_data: dict | None = None,
    ) -> tuple[int, dict | None]:
        """Make an HTTP request and track statistics."""
        url = f"{self.base_url}{endpoint}"
        start = time.monotonic()

        try:
            self.stats.requests_sent += 1
            response = await client.request(
                method=method,
                url=url,
                headers=headers or {},
                json=json_data,
                timeout=30.0,
            )
            latency = (time.monotonic() - start) * 1000
            self.stats.total_latency_ms += latency

            if response.status_code in (200, 201):
                self.stats.success_count += 1
            elif response.status_code == 429:
                self.stats.rate_limited += 1
                self.stats.error_count += 1
            elif response.status_code == 503:
                self.stats.circuit_breaker_trips += 1
                self.stats.error_count += 1
            else:
                self.stats.error_count += 1

            try:
                data = response.json()
            except Exception:
                data = None

            return response.status_code, data

        except Exception as e:
            self.stats.error_count += 1
            self.log(f"Request failed: {e}", "")
            return 0, None

    async def check_health(self, client: httpx.AsyncClient) -> bool:
        """Check if the service is healthy."""
        self.log("Checking service health...", "")
        status, data = await self.make_request(client, "GET", "/health")
        if status == 200 and data:
            self.log(f"Service healthy: {data.get('status', 'unknown')}", "")
            return True
        self.log("Service unhealthy or unreachable", "")
        return False

    async def create_session(self, client: httpx.AsyncClient) -> dict | None:
        """Create an anonymous session."""
        self.log("Creating anonymous session...", "")
        status, data = await self.make_request(
            client, "POST", "/api/v2/auth/anonymous", json_data={}
        )
        if status in (200, 201) and data:
            session = {
                "token": data.get("token"),
                "user_id": data.get("user_id"),
                "session_id": data.get("session_id"),
            }
            self.sessions.append(session)
            self.log(f"Session created: {session['user_id'][:8]}...", "")
            return session
        self.log(f"Failed to create session: {status}", "")
        return None

    async def create_configuration(
        self, client: httpx.AsyncClient, user_id: str, name: str, tickers: list[str]
    ) -> dict | None:
        """Create a configuration."""
        self.log(f"Creating config: {name}", "")
        headers = {"X-User-ID": user_id}
        payload = {
            "name": name,
            "tickers": tickers,  # API expects list of strings, not objects
        }
        status, data = await self.make_request(
            client, "POST", "/api/v2/configurations", headers=headers, json_data=payload
        )
        if status in (200, 201) and data:
            self.log(f"Config created: {data.get('config_id', 'unknown')[:8]}...", "")
            return data
        self.log(f"Failed to create config: {status}", "")
        return None

    async def get_configurations(
        self, client: httpx.AsyncClient, user_id: str
    ) -> list | None:
        """Get all configurations for a user."""
        headers = {"X-User-ID": user_id}
        status, data = await self.make_request(
            client, "GET", "/api/v2/configurations", headers=headers
        )
        if status == 200 and data:
            configs = data.get("configurations", [])
            self.log(f"Retrieved {len(configs)} configurations", "")
            return configs
        return None

    async def get_sentiment(
        self, client: httpx.AsyncClient, user_id: str, config_id: str
    ) -> dict | None:
        """Get sentiment for a configuration."""
        headers = {"X-User-ID": user_id}
        status, data = await self.make_request(
            client,
            "GET",
            f"/api/v2/configurations/{config_id}/sentiment",
            headers=headers,
        )
        if status == 200:
            self.log(f"Retrieved sentiment for {config_id[:8]}...", "")
            return data
        return None

    async def get_ohlc(
        self,
        client: httpx.AsyncClient,
        user_id: str,
        ticker: str,
        time_range: str = "1M",
    ) -> dict | None:
        """Get OHLC price data for a ticker."""
        headers = {"X-User-ID": user_id}
        status, data = await self.make_request(
            client,
            "GET",
            f"/api/v2/tickers/{ticker}/ohlc?range={time_range}",
            headers=headers,
        )
        if status == 200 and data:
            candle_count = data.get("count", 0)
            self.log(f"Retrieved {candle_count} OHLC candles for {ticker}", "")
            return data
        elif status == 404:
            self.log(f"No OHLC data for {ticker}", "")
        return None

    async def get_sentiment_history(
        self,
        client: httpx.AsyncClient,
        user_id: str,
        ticker: str,
        time_range: str = "1M",
        source: str = "aggregated",
    ) -> dict | None:
        """Get historical sentiment data for a ticker."""
        headers = {"X-User-ID": user_id}
        status, data = await self.make_request(
            client,
            "GET",
            f"/api/v2/tickers/{ticker}/sentiment/history?range={time_range}&source={source}",
            headers=headers,
        )
        if status == 200 and data:
            point_count = data.get("count", 0)
            self.log(f"Retrieved {point_count} sentiment points for {ticker}", "")
            return data
        elif status == 404:
            self.log(f"No sentiment history for {ticker}", "")
        return None

    async def run_scenario_basic_flow(self, client: httpx.AsyncClient) -> None:
        """Run a basic user flow: create session, config, get sentiment."""
        self.log("Starting BASIC FLOW scenario", "")
        print("-" * 40)

        # Check health
        if not await self.check_health(client):
            return

        # Create session
        session = await self.create_session(client)
        if not session:
            return

        # Create configuration
        # Using random for demo traffic generation (not security-sensitive)
        tickers = random.sample(SAMPLE_TICKERS, min(3, len(SAMPLE_TICKERS)))
        config_name = random.choice(SAMPLE_CONFIG_NAMES)  # noqa: S311
        config = await self.create_configuration(
            client,
            session["user_id"],
            config_name,
            tickers,
        )

        # List configurations
        await self.get_configurations(client, session["user_id"])

        # Get sentiment if config was created
        if config and config.get("config_id"):
            await self.get_sentiment(client, session["user_id"], config["config_id"])

        # Get OHLC and sentiment history for first ticker
        if tickers:
            ticker = tickers[0]
            await self.get_ohlc(client, session["user_id"], ticker)
            await self.get_sentiment_history(client, session["user_id"], ticker)

        self.log("Basic flow completed", "")

    async def run_scenario_price_sentiment_overlay(
        self, client: httpx.AsyncClient
    ) -> None:
        """Demo the Price-Sentiment Overlay feature (OHLC + sentiment history)."""
        self.log("Starting PRICE-SENTIMENT OVERLAY scenario", "")
        print("-" * 40)

        # Create session
        session = await self.create_session(client)
        if not session:
            return

        user_id = session["user_id"]

        # Test multiple tickers with different time ranges
        test_tickers = ["AAPL", "MSFT", "NVDA"]
        time_ranges = ["1W", "1M", "3M"]

        for ticker in test_tickers:
            self.log(f"Fetching price-sentiment data for {ticker}...", "")

            # Get OHLC data for different ranges
            for time_range in time_ranges:
                ohlc_data = await self.get_ohlc(client, user_id, ticker, time_range)
                if ohlc_data:
                    # Validate response shape
                    candles = ohlc_data.get("candles", [])
                    if candles:
                        first_candle = candles[0]
                        # Verify expected fields exist
                        expected_fields = ["date", "open", "high", "low", "close"]
                        missing = [f for f in expected_fields if f not in first_candle]
                        if missing:
                            self.log(f"OHLC missing fields: {missing}", "")
                        else:
                            self.log(
                                f"OHLC shape OK: {len(candles)} candles, "
                                f"range={time_range}",
                                "",
                            )

            # Get sentiment history
            for source in ["aggregated", "tiingo"]:
                history_data = await self.get_sentiment_history(
                    client, user_id, ticker, "1M", source
                )
                if history_data:
                    history = history_data.get("history", [])
                    if history:
                        first_point = history[0]
                        expected_fields = ["date", "score", "source"]
                        missing = [f for f in expected_fields if f not in first_point]
                        if missing:
                            self.log(f"Sentiment history missing fields: {missing}", "")
                        else:
                            self.log(
                                f"Sentiment history OK: {len(history)} points, "
                                f"source={source}",
                                "",
                            )

            await asyncio.sleep(0.2)  # Small delay between tickers

        self.log("Price-sentiment overlay scenario completed", "")

    async def run_scenario_load_test(
        self, client: httpx.AsyncClient, num_users: int = 5, requests_per_user: int = 10
    ) -> None:
        """Run a load test with multiple concurrent users."""
        self.log(
            f"Starting LOAD TEST: {num_users} users, {requests_per_user} req/user", ""
        )
        print("-" * 40)

        async def user_session(user_num: int) -> None:
            """Simulate a single user's session."""
            session = await self.create_session(client)
            if not session:
                return

            for i in range(requests_per_user):
                # Random operation mix (not security-sensitive)
                op = random.choice(  # noqa: S311
                    ["health", "list_configs", "create_config"]
                )
                if op == "health":
                    await self.check_health(client)
                elif op == "list_configs":
                    await self.get_configurations(client, session["user_id"])
                elif op == "create_config":
                    if i < 2:  # Limit config creation per user
                        tickers = random.sample(SAMPLE_TICKERS, 2)
                        await self.create_configuration(
                            client,
                            session["user_id"],
                            f"Test Config {user_num}-{i}",
                            tickers,
                        )
                # Small delay between requests
                await asyncio.sleep(random.uniform(0.1, 0.5))  # noqa: S311

        # Run user sessions concurrently
        tasks = [user_session(i) for i in range(num_users)]
        await asyncio.gather(*tasks)
        self.log("Load test completed", "")

    async def run_scenario_rate_limit(
        self, client: httpx.AsyncClient, burst_size: int = 50
    ) -> None:
        """Test rate limiting by sending a burst of requests."""
        self.log(f"Starting RATE LIMIT test: {burst_size} rapid requests", "")
        print("-" * 40)

        # Create a session first
        session = await self.create_session(client)
        if not session:
            return

        # Send burst of requests
        self.log("Sending burst of requests...", "")
        rate_limited_count = 0
        for i in range(burst_size):
            status, _ = await self.make_request(
                client,
                "GET",
                "/api/v2/configurations",
                headers={"X-User-ID": session["user_id"]},
            )
            if status == 429:
                rate_limited_count += 1
                if rate_limited_count == 1:
                    self.log(f"Rate limit hit at request {i + 1}!", "")

        self.log(f"Burst complete: {rate_limited_count}/{burst_size} rate limited", "")

    async def run_scenario_circuit_breaker(self, client: httpx.AsyncClient) -> None:
        """Demonstrate circuit breaker by checking external API status."""
        self.log("Starting CIRCUIT BREAKER scenario", "")
        print("-" * 40)

        # Check health to see circuit states
        for _ in range(5):
            await self.check_health(client)
            await asyncio.sleep(1)

        self.log("Check the interview dashboard to see circuit states", "")

    async def run_scenario_cache_warmup(
        self, client: httpx.AsyncClient, iterations: int = 20
    ) -> None:
        """Warm up caches with repeated requests to show hit rate improvement."""
        self.log(f"Starting CACHE WARMUP: {iterations} iterations", "")
        print("-" * 40)

        # Create session and config
        session = await self.create_session(client)
        if not session:
            return

        tickers = ["AAPL", "MSFT", "GOOGL"]
        config = await self.create_configuration(
            client, session["user_id"], "Cache Test Config", tickers
        )

        if not config:
            return

        config_id = config.get("config_id")
        headers = {"X-User-ID": session["user_id"]}

        # First request (cache miss)
        self.log("First request (cold cache)...", "")
        start = time.monotonic()
        await self.make_request(
            client,
            "GET",
            f"/api/v2/configurations/{config_id}/sentiment",
            headers=headers,
        )
        cold_latency = (time.monotonic() - start) * 1000
        self.log(f"Cold cache latency: {cold_latency:.1f}ms", "")

        # Subsequent requests (should be faster)
        warm_latencies = []
        for _ in range(iterations - 1):
            await asyncio.sleep(0.5)
            start = time.monotonic()
            await self.make_request(
                client,
                "GET",
                f"/api/v2/configurations/{config_id}/sentiment",
                headers=headers,
            )
            latency = (time.monotonic() - start) * 1000
            warm_latencies.append(latency)

        avg_warm = sum(warm_latencies) / len(warm_latencies) if warm_latencies else 0
        self.log(f"Warm cache avg latency: {avg_warm:.1f}ms", "")
        if cold_latency > 0:
            improvement = ((cold_latency - avg_warm) / cold_latency) * 100
            self.log(f"Cache improvement: {improvement:.1f}%", "")

    async def run_all_scenarios(self, client: httpx.AsyncClient) -> None:
        """Run all demonstration scenarios."""
        self.log("Running ALL SCENARIOS", "")
        print("=" * 50)

        await self.run_scenario_basic_flow(client)
        print()

        await self.run_scenario_price_sentiment_overlay(client)
        print()

        await self.run_scenario_cache_warmup(client, iterations=10)
        print()

        await self.run_scenario_load_test(client, num_users=3, requests_per_user=5)
        print()

        await self.run_scenario_rate_limit(client, burst_size=30)
        print()

        await self.run_scenario_circuit_breaker(client)


async def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic traffic for interview demonstrations"
    )
    parser.add_argument(
        "--env",
        choices=["preprod", "prod"],
        default="preprod",
        help="Target environment",
    )
    parser.add_argument(
        "--scenario",
        choices=[
            "all",
            "basic",
            "load",
            "rate-limit",
            "circuit-breaker",
            "cache",
            "price-sentiment",
        ],
        default="basic",
        help="Scenario to run",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=5,
        help="Number of concurrent users for load test",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=10,
        help="Requests per user for load test",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity",
    )

    args = parser.parse_args()

    base_url = ENVIRONMENTS.get(args.env)
    if not base_url:
        print(f"Unknown environment: {args.env}")
        sys.exit(1)

    print(
        f"""
{"=" * 50}
SENTIMENT ANALYZER - TRAFFIC GENERATOR
{"=" * 50}
Environment: {args.env.upper()}
URL:         {base_url}
Scenario:    {args.scenario}
{"=" * 50}
    """
    )

    generator = TrafficGenerator(base_url, verbose=not args.quiet)

    async with httpx.AsyncClient() as client:
        if args.scenario == "all":
            await generator.run_all_scenarios(client)
        elif args.scenario == "basic":
            await generator.run_scenario_basic_flow(client)
        elif args.scenario == "load":
            await generator.run_scenario_load_test(
                client, num_users=args.users, requests_per_user=args.requests
            )
        elif args.scenario == "rate-limit":
            await generator.run_scenario_rate_limit(client)
        elif args.scenario == "circuit-breaker":
            await generator.run_scenario_circuit_breaker(client)
        elif args.scenario == "cache":
            await generator.run_scenario_cache_warmup(client)
        elif args.scenario == "price-sentiment":
            await generator.run_scenario_price_sentiment_overlay(client)

    generator.stats.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
