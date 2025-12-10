"""Unit tests for SentimentScore model validation (T038).

Tests sentiment score range validation:
- Score must be between -1.0 and 1.0
- Confidence must be between 0.0 and 1.0 (or null for Tiingo)
- Label derivation based on score thresholds
- Low confidence detection for UI distinction
"""

import pytest
from pydantic import ValidationError

from src.lambdas.shared.models.news_item import SentimentScore


class TestSentimentScoreValidation:
    """Tests for SentimentScore field validation."""

    def test_valid_score_range_minimum(self) -> None:
        """Score of -1.0 (minimum) should be valid."""
        sentiment = SentimentScore(score=-1.0, confidence=0.8, label="negative")
        assert sentiment.score == -1.0

    def test_valid_score_range_maximum(self) -> None:
        """Score of 1.0 (maximum) should be valid."""
        sentiment = SentimentScore(score=1.0, confidence=0.8, label="positive")
        assert sentiment.score == 1.0

    def test_valid_score_range_neutral(self) -> None:
        """Score of 0.0 (neutral) should be valid."""
        sentiment = SentimentScore(score=0.0, confidence=0.8, label="neutral")
        assert sentiment.score == 0.0

    def test_invalid_score_below_minimum(self) -> None:
        """Score below -1.0 should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentScore(score=-1.5, confidence=0.8, label="negative")
        assert "greater than or equal to -1" in str(exc_info.value).lower()

    def test_invalid_score_above_maximum(self) -> None:
        """Score above 1.0 should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentScore(score=1.5, confidence=0.8, label="positive")
        assert "less than or equal to 1" in str(exc_info.value).lower()

    def test_valid_confidence_range_minimum(self) -> None:
        """Confidence of 0.0 (minimum) should be valid."""
        sentiment = SentimentScore(score=0.5, confidence=0.0, label="positive")
        assert sentiment.confidence == 0.0

    def test_valid_confidence_range_maximum(self) -> None:
        """Confidence of 1.0 (maximum) should be valid."""
        sentiment = SentimentScore(score=0.5, confidence=1.0, label="positive")
        assert sentiment.confidence == 1.0

    def test_invalid_confidence_below_minimum(self) -> None:
        """Confidence below 0.0 should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentScore(score=0.5, confidence=-0.1, label="positive")
        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_invalid_confidence_above_maximum(self) -> None:
        """Confidence above 1.0 should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SentimentScore(score=0.5, confidence=1.5, label="positive")
        assert "less than or equal to 1" in str(exc_info.value).lower()


class TestSentimentScoreNullConfidence:
    """Tests for null confidence handling (Tiingo unscored)."""

    def test_null_confidence_for_tiingo_unscored(self) -> None:
        """Confidence can be null for Tiingo (unscored) data."""
        sentiment = SentimentScore(score=0.5, confidence=None, label="positive")
        assert sentiment.confidence is None

    def test_null_confidence_still_has_valid_score(self) -> None:
        """Even with null confidence, score validation still applies."""
        sentiment = SentimentScore(score=-0.5, confidence=None, label="negative")
        assert sentiment.score == -0.5
        assert sentiment.confidence is None

    def test_null_confidence_with_neutral_label(self) -> None:
        """Null confidence works with neutral label."""
        sentiment = SentimentScore(score=0.0, confidence=None, label="neutral")
        assert sentiment.confidence is None
        assert sentiment.label == "neutral"


class TestSentimentScoreLabelDerivation:
    """Tests for automatic label derivation from score."""

    def test_from_score_positive_threshold(self) -> None:
        """Score >= 0.33 should derive 'positive' label."""
        sentiment = SentimentScore.from_score(score=0.33, confidence=0.8)
        assert sentiment.label == "positive"

    def test_from_score_positive_high(self) -> None:
        """High positive score derives 'positive' label."""
        sentiment = SentimentScore.from_score(score=0.9, confidence=0.8)
        assert sentiment.label == "positive"

    def test_from_score_negative_threshold(self) -> None:
        """Score <= -0.33 should derive 'negative' label."""
        sentiment = SentimentScore.from_score(score=-0.33, confidence=0.8)
        assert sentiment.label == "negative"

    def test_from_score_negative_high(self) -> None:
        """High negative score derives 'negative' label."""
        sentiment = SentimentScore.from_score(score=-0.9, confidence=0.8)
        assert sentiment.label == "negative"

    def test_from_score_neutral_positive_boundary(self) -> None:
        """Score just below 0.33 derives 'neutral' label."""
        sentiment = SentimentScore.from_score(score=0.32, confidence=0.8)
        assert sentiment.label == "neutral"

    def test_from_score_neutral_negative_boundary(self) -> None:
        """Score just above -0.33 derives 'neutral' label."""
        sentiment = SentimentScore.from_score(score=-0.32, confidence=0.8)
        assert sentiment.label == "neutral"

    def test_from_score_neutral_zero(self) -> None:
        """Score of 0.0 derives 'neutral' label."""
        sentiment = SentimentScore.from_score(score=0.0, confidence=0.8)
        assert sentiment.label == "neutral"

    def test_from_score_with_null_confidence(self) -> None:
        """from_score works with null confidence."""
        sentiment = SentimentScore.from_score(score=0.5, confidence=None)
        assert sentiment.label == "positive"
        assert sentiment.confidence is None


class TestSentimentScoreLowConfidenceDetection:
    """Tests for low confidence flag detection (US3 requirement).

    Per spec clarification: confidence < 0.6 OR confidence is null
    should be flagged as "low confidence" for UI distinction.
    """

    def test_is_low_confidence_below_threshold(self) -> None:
        """Confidence < 0.6 is low confidence."""
        sentiment = SentimentScore(score=0.5, confidence=0.5, label="positive")
        assert sentiment.is_low_confidence is True

    def test_is_low_confidence_at_threshold(self) -> None:
        """Confidence == 0.6 is NOT low confidence."""
        sentiment = SentimentScore(score=0.5, confidence=0.6, label="positive")
        assert sentiment.is_low_confidence is False

    def test_is_low_confidence_above_threshold(self) -> None:
        """Confidence > 0.6 is NOT low confidence."""
        sentiment = SentimentScore(score=0.5, confidence=0.8, label="positive")
        assert sentiment.is_low_confidence is False

    def test_is_low_confidence_null_confidence(self) -> None:
        """Null confidence is low confidence (Tiingo unscored)."""
        sentiment = SentimentScore(score=0.5, confidence=None, label="positive")
        assert sentiment.is_low_confidence is True

    def test_is_low_confidence_edge_case_zero(self) -> None:
        """Confidence of 0.0 is low confidence."""
        sentiment = SentimentScore(score=0.5, confidence=0.0, label="positive")
        assert sentiment.is_low_confidence is True

    def test_is_low_confidence_edge_case_high(self) -> None:
        """Confidence of 1.0 is NOT low confidence."""
        sentiment = SentimentScore(score=0.5, confidence=1.0, label="positive")
        assert sentiment.is_low_confidence is False


class TestSentimentScoreInvalidLabel:
    """Tests for label validation."""

    def test_invalid_label_value(self) -> None:
        """Invalid label value should raise ValidationError."""
        with pytest.raises(ValidationError):
            SentimentScore(score=0.5, confidence=0.8, label="invalid")

    def test_valid_label_positive(self) -> None:
        """'positive' is a valid label."""
        sentiment = SentimentScore(score=0.5, confidence=0.8, label="positive")
        assert sentiment.label == "positive"

    def test_valid_label_negative(self) -> None:
        """'negative' is a valid label."""
        sentiment = SentimentScore(score=-0.5, confidence=0.8, label="negative")
        assert sentiment.label == "negative"

    def test_valid_label_neutral(self) -> None:
        """'neutral' is a valid label."""
        sentiment = SentimentScore(score=0.0, confidence=0.8, label="neutral")
        assert sentiment.label == "neutral"
