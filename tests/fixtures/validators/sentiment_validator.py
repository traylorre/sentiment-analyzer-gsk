"""Sentiment history response validator for test assertions.

Validates sentiment history data against business rules:
- Required fields present: date, score, source
- Score bounds: -1.0 <= score <= 1.0
- Confidence bounds: 0.0 <= confidence <= 1.0 (if present)
- Label consistency: label matches score thresholds
- Date ordering: history sorted by date ascending
- Count consistency: count field matches array length
"""

import math
from datetime import date

from tests.fixtures.validators.ohlc_validator import ValidationError


class SentimentValidator:
    """Validates sentiment history data against business rules."""

    REQUIRED_POINT_FIELDS = ["date", "score", "source", "label"]
    VALID_SOURCES = ["tiingo", "finnhub", "our_model", "aggregated"]
    VALID_LABELS = ["positive", "neutral", "negative"]

    # Label thresholds (as per contract)
    POSITIVE_THRESHOLD = 0.33
    NEGATIVE_THRESHOLD = -0.33

    def validate_point(self, point: dict, index: int = 0) -> list[ValidationError]:
        """Validate a single sentiment point.

        Args:
            point: Sentiment point dict with date, score, source, confidence, label
            index: Point index in array (for error messages)

        Returns:
            List of ValidationError objects (empty if valid)
        """
        errors: list[ValidationError] = []
        prefix = f"history[{index}]."

        # Check required fields
        for field in self.REQUIRED_POINT_FIELDS:
            if field not in point:
                errors.append(
                    ValidationError(
                        field=f"{prefix}{field}",
                        message=f"Missing required field: {field}",
                    )
                )

        # Can't validate further without required fields
        if errors:
            return errors

        score = point["score"]
        label = point["label"]
        source = point["source"]

        # SENT-001: -1.0 <= score <= 1.0
        if not isinstance(score, int | float):
            errors.append(
                ValidationError(
                    field=f"{prefix}score",
                    message=f"Score must be numeric, got {type(score).__name__}",
                    value=score,
                )
            )
        elif math.isnan(score):
            errors.append(
                ValidationError(
                    field=f"{prefix}score",
                    message="Score cannot be NaN",
                    value=score,
                )
            )
        elif math.isinf(score):
            errors.append(
                ValidationError(
                    field=f"{prefix}score",
                    message="Score cannot be Infinity",
                    value=score,
                )
            )
        elif score < -1.0 or score > 1.0:
            errors.append(
                ValidationError(
                    field=f"{prefix}score",
                    message=f"Score must be in [-1.0, 1.0], got {score}",
                    value=score,
                )
            )

        # SENT-002: 0.0 <= confidence <= 1.0 (if present)
        if "confidence" in point and point["confidence"] is not None:
            confidence = point["confidence"]
            if not isinstance(confidence, int | float):
                errors.append(
                    ValidationError(
                        field=f"{prefix}confidence",
                        message=f"Confidence must be numeric, got {type(confidence).__name__}",
                        value=confidence,
                    )
                )
            elif confidence < 0.0 or confidence > 1.0:
                errors.append(
                    ValidationError(
                        field=f"{prefix}confidence",
                        message=f"Confidence must be in [0.0, 1.0], got {confidence}",
                        value=confidence,
                    )
                )

        # SENT-003 to SENT-005: Label consistency with score
        if isinstance(score, int | float) and not (
            math.isnan(score) or math.isinf(score)
        ):
            expected_label = self._compute_expected_label(score)
            if label != expected_label:
                errors.append(
                    ValidationError(
                        field=f"{prefix}label",
                        message=f"Label '{label}' inconsistent with score {score} (expected '{expected_label}')",
                        value={
                            "label": label,
                            "score": score,
                            "expected": expected_label,
                        },
                    )
                )

        # Validate label is valid
        if label not in self.VALID_LABELS:
            errors.append(
                ValidationError(
                    field=f"{prefix}label",
                    message=f"Label must be one of {self.VALID_LABELS}, got '{label}'",
                    value=label,
                )
            )

        # SENT-008: source matches valid sources
        if source not in self.VALID_SOURCES:
            errors.append(
                ValidationError(
                    field=f"{prefix}source",
                    message=f"Source must be one of {self.VALID_SOURCES}, got '{source}'",
                    value=source,
                )
            )

        # Validate date format
        point_date = point["date"]
        if not isinstance(point_date, str | date):
            errors.append(
                ValidationError(
                    field=f"{prefix}date",
                    message=f"Date must be string or date, got {type(point_date).__name__}",
                    value=point_date,
                )
            )

        return errors

    def _compute_expected_label(self, score: float) -> str:
        """Compute expected label based on score.

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

    def validate_response(self, response: dict) -> list[ValidationError]:
        """Validate a full sentiment history API response.

        Args:
            response: SentimentHistoryResponse dict with ticker, history, etc.

        Returns:
            List of ValidationError objects (empty if valid)
        """
        errors: list[ValidationError] = []

        # Check required response fields
        required_fields = [
            "ticker",
            "source",
            "history",
            "start_date",
            "end_date",
            "count",
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

        history = response["history"]

        # Validate each point
        for i, point in enumerate(history):
            point_errors = self.validate_point(point, index=i)
            errors.extend(point_errors)

        # SENT-007: count == len(history)
        if response["count"] != len(history):
            errors.append(
                ValidationError(
                    field="count",
                    message=f"count ({response['count']}) must equal len(history) ({len(history)})",
                    value={"count": response["count"], "len": len(history)},
                )
            )

        # SENT-006: History sorted by date ascending
        if len(history) >= 2:
            dates = [p["date"] for p in history]
            for i in range(1, len(dates)):
                if dates[i] < dates[i - 1]:
                    errors.append(
                        ValidationError(
                            field=f"history[{i}].date",
                            message=f"History not sorted: {dates[i-1]} > {dates[i]}",
                            value={"prev": dates[i - 1], "curr": dates[i]},
                        )
                    )
                    break  # Only report first out-of-order

        # Validate start_date equals first point date
        if history and str(response["start_date"]) != str(history[0]["date"]):
            errors.append(
                ValidationError(
                    field="start_date",
                    message=f"start_date ({response['start_date']}) must equal first history date ({history[0]['date']})",
                    value={
                        "start_date": response["start_date"],
                        "first_history": history[0]["date"],
                    },
                )
            )

        # Validate end_date equals last point date
        if history and str(response["end_date"]) != str(history[-1]["date"]):
            errors.append(
                ValidationError(
                    field="end_date",
                    message=f"end_date ({response['end_date']}) must equal last history date ({history[-1]['date']})",
                    value={
                        "end_date": response["end_date"],
                        "last_history": history[-1]["date"],
                    },
                )
            )

        # Validate response source
        if response["source"] not in self.VALID_SOURCES:
            errors.append(
                ValidationError(
                    field="source",
                    message=f"Response source must be one of {self.VALID_SOURCES}, got '{response['source']}'",
                    value=response["source"],
                )
            )

        return errors

    def assert_valid(self, response: dict) -> None:
        """Assert response is valid, raise AssertionError if not.

        Args:
            response: SentimentHistoryResponse dict to validate

        Raises:
            AssertionError: If validation fails, with detailed error messages
        """
        errors = self.validate_response(response)
        if errors:
            error_details = "\n".join(
                f"  - {e.field}: {e.message} (value={e.value})" for e in errors
            )
            raise AssertionError(
                f"Sentiment history response validation failed:\n{error_details}"
            )

    def assert_point_valid(self, point: dict) -> None:
        """Assert a single sentiment point is valid.

        Args:
            point: Sentiment point dict to validate

        Raises:
            AssertionError: If validation fails
        """
        errors = self.validate_point(point)
        if errors:
            error_details = "\n".join(
                f"  - {e.field}: {e.message} (value={e.value})" for e in errors
            )
            raise AssertionError(f"Sentiment point validation failed:\n{error_details}")
