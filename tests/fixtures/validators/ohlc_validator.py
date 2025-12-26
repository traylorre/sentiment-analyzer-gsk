"""OHLC response validator for test assertions.

Validates OHLC candle data against business rules:
- Required fields present: date, open, high, low, close
- Price relationships: high >= max(open, close), low <= min(open, close)
- Price bounds: all prices > 0, no NaN/Infinity
- Volume bounds: volume >= 0 if present
- Date ordering: candles sorted by date ascending
- Count consistency: count field matches array length
"""

import math
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class ValidationError:
    """Single validation error with context."""

    field: str
    message: str
    value: Any = None


class OHLCValidator:
    """Validates OHLC candle data against business rules."""

    REQUIRED_CANDLE_FIELDS = ["date", "open", "high", "low", "close"]

    def validate_candle(self, candle: dict, index: int = 0) -> list[ValidationError]:
        """Validate a single OHLC candle.

        Args:
            candle: Candle data dict with date, open, high, low, close, volume
            index: Candle index in array (for error messages)

        Returns:
            List of ValidationError objects (empty if valid)
        """
        errors: list[ValidationError] = []
        prefix = f"candles[{index}]."

        # Check required fields
        for field in self.REQUIRED_CANDLE_FIELDS:
            if field not in candle:
                errors.append(
                    ValidationError(
                        field=f"{prefix}{field}",
                        message=f"Missing required field: {field}",
                    )
                )

        # Can't validate further without required fields
        if errors:
            return errors

        o = candle["open"]
        h = candle["high"]
        low = candle["low"]
        c = candle["close"]

        # OHLC-004: All prices must be positive
        for name, value in [("open", o), ("high", h), ("low", low), ("close", c)]:
            if not isinstance(value, int | float):
                errors.append(
                    ValidationError(
                        field=f"{prefix}{name}",
                        message=f"Price must be numeric, got {type(value).__name__}",
                        value=value,
                    )
                )
            elif value <= 0:
                errors.append(
                    ValidationError(
                        field=f"{prefix}{name}",
                        message=f"Price must be positive, got {value}",
                        value=value,
                    )
                )

        # Can't validate relationships without valid numeric prices
        price_errors = [e for e in errors if "must be" in e.message]
        if price_errors:
            return errors

        # OHLC-005: No NaN or Infinity
        for name, value in [("open", o), ("high", h), ("low", low), ("close", c)]:
            if math.isnan(value):
                errors.append(
                    ValidationError(
                        field=f"{prefix}{name}",
                        message="Price cannot be NaN",
                        value=value,
                    )
                )
            elif math.isinf(value):
                errors.append(
                    ValidationError(
                        field=f"{prefix}{name}",
                        message="Price cannot be Infinity",
                        value=value,
                    )
                )

        # OHLC-001: high >= low
        if h < low:
            errors.append(
                ValidationError(
                    field=f"{prefix}high",
                    message=f"high ({h}) must be >= low ({low})",
                    value={"high": h, "low": low},
                )
            )

        # OHLC-002: low <= open <= high
        if o < low or o > h:
            errors.append(
                ValidationError(
                    field=f"{prefix}open",
                    message=f"open ({o}) must be between low ({low}) and high ({h})",
                    value={"open": o, "low": low, "high": h},
                )
            )

        # OHLC-003: low <= close <= high
        if c < low or c > h:
            errors.append(
                ValidationError(
                    field=f"{prefix}close",
                    message=f"close ({c}) must be between low ({low}) and high ({h})",
                    value={"close": c, "low": low, "high": h},
                )
            )

        # OHLC-006: Volume >= 0 if present
        if "volume" in candle and candle["volume"] is not None:
            volume = candle["volume"]
            if not isinstance(volume, int | float):
                errors.append(
                    ValidationError(
                        field=f"{prefix}volume",
                        message=f"Volume must be numeric, got {type(volume).__name__}",
                        value=volume,
                    )
                )
            elif volume < 0:
                errors.append(
                    ValidationError(
                        field=f"{prefix}volume",
                        message=f"Volume cannot be negative, got {volume}",
                        value=volume,
                    )
                )

        # OHLC-007: Valid date format
        candle_date = candle["date"]
        if not isinstance(candle_date, str | date):
            errors.append(
                ValidationError(
                    field=f"{prefix}date",
                    message=f"Date must be string or date, got {type(candle_date).__name__}",
                    value=candle_date,
                )
            )

        return errors

    def validate_response(self, response: dict) -> list[ValidationError]:
        """Validate a full OHLC API response.

        Args:
            response: OHLCResponse dict with ticker, candles, time_range, etc.

        Returns:
            List of ValidationError objects (empty if valid)
        """
        errors: list[ValidationError] = []

        # Check required response fields
        required_fields = [
            "ticker",
            "candles",
            "time_range",
            "start_date",
            "end_date",
            "count",
            "source",
        ]
        for field in required_fields:
            if field not in response:
                errors.append(
                    ValidationError(
                        field=field,
                        message=f"Missing required field: {field}",
                    )
                )

        if errors:
            return errors

        candles = response["candles"]

        # Validate each candle
        for i, candle in enumerate(candles):
            candle_errors = self.validate_candle(candle, index=i)
            errors.extend(candle_errors)

        # OHLC-009: count == len(candles)
        if response["count"] != len(candles):
            errors.append(
                ValidationError(
                    field="count",
                    message=f"count ({response['count']}) must equal len(candles) ({len(candles)})",
                    value={"count": response["count"], "len": len(candles)},
                )
            )

        # OHLC-008: Candles sorted by date ascending
        if len(candles) >= 2:
            dates = [c["date"] for c in candles]
            for i in range(1, len(dates)):
                if dates[i] < dates[i - 1]:
                    errors.append(
                        ValidationError(
                            field=f"candles[{i}].date",
                            message=f"Candles not sorted: {dates[i - 1]} > {dates[i]}",
                            value={"prev": dates[i - 1], "curr": dates[i]},
                        )
                    )
                    break  # Only report first out-of-order

        # OHLC-010: start_date == candles[0].date (compare date parts only)
        # Feature 1056: Intraday candles have datetime format, response has date format
        if candles:
            first_candle_date = str(candles[0]["date"]).split("T")[0]
            if str(response["start_date"]) != first_candle_date:
                errors.append(
                    ValidationError(
                        field="start_date",
                        message=f"start_date ({response['start_date']}) must equal first candle date ({first_candle_date})",
                        value={
                            "start_date": response["start_date"],
                            "first_candle": candles[0]["date"],
                        },
                    )
                )

        # OHLC-011: end_date == candles[-1].date (compare date parts only)
        # Feature 1056: Intraday candles have datetime format, response has date format
        if candles:
            last_candle_date = str(candles[-1]["date"]).split("T")[0]
            if str(response["end_date"]) != last_candle_date:
                errors.append(
                    ValidationError(
                        field="end_date",
                        message=f"end_date ({response['end_date']}) must equal last candle date ({last_candle_date})",
                        value={
                            "end_date": response["end_date"],
                            "last_candle": candles[-1]["date"],
                        },
                    )
                )

        # Validate source
        if response["source"] not in ("tiingo", "finnhub"):
            errors.append(
                ValidationError(
                    field="source",
                    message=f"source must be 'tiingo' or 'finnhub', got '{response['source']}'",
                    value=response["source"],
                )
            )

        return errors

    def assert_valid(self, response: dict) -> None:
        """Assert response is valid, raise AssertionError if not.

        Args:
            response: OHLCResponse dict to validate

        Raises:
            AssertionError: If validation fails, with detailed error messages
        """
        errors = self.validate_response(response)
        if errors:
            error_details = "\n".join(
                f"  - {e.field}: {e.message} (value={e.value})" for e in errors
            )
            raise AssertionError(f"OHLC response validation failed:\n{error_details}")

    def assert_candle_valid(self, candle: dict) -> None:
        """Assert a single candle is valid.

        Args:
            candle: Candle dict to validate

        Raises:
            AssertionError: If validation fails
        """
        errors = self.validate_candle(candle)
        if errors:
            error_details = "\n".join(
                f"  - {e.field}: {e.message} (value={e.value})" for e in errors
            )
            raise AssertionError(f"Candle validation failed:\n{error_details}")
