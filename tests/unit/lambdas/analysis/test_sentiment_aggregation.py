"""
Unit Tests: Dual-Source Sentiment Aggregation (T065)
====================================================

Tests for aggregating sentiment from Tiingo, Finnhub, and our ML model.

Constitution v1.1:
- All code requires unit tests
- External dependencies mocked (transformers)
- LOCAL environment only
"""

from datetime import UTC
from datetime import datetime as dt
from unittest.mock import patch

import pytest

from src.lambdas.analysis.sentiment import (
    SOURCE_WEIGHTS,
    AggregatedSentiment,
    SentimentLabel,
    SentimentSource,
    SourceSentimentScore,
    _label_to_score,
    _score_to_label_enum,
    aggregate_sentiment,
    analyze_text_sentiment,
    create_finnhub_score,
    create_tiingo_score,
)


class TestSourceSentimentScore:
    """Tests for SourceSentimentScore dataclass."""

    def test_create_source_score(self):
        """Should create a valid source sentiment score."""
        timestamp = dt.now(UTC)
        score = SourceSentimentScore(
            source=SentimentSource.FINNHUB,
            score=0.75,
            label=SentimentLabel.POSITIVE,
            confidence=0.9,
            timestamp=timestamp,
            metadata={"test": True},
        )

        assert score.source == SentimentSource.FINNHUB
        assert score.score == 0.75
        assert score.label == SentimentLabel.POSITIVE
        assert score.confidence == 0.9
        assert score.timestamp == timestamp
        assert score.metadata == {"test": True}

    def test_source_score_without_metadata(self):
        """Should allow None metadata."""
        score = SourceSentimentScore(
            source=SentimentSource.TIINGO,
            score=-0.5,
            label=SentimentLabel.NEGATIVE,
            confidence=0.7,
            timestamp=dt.now(UTC),
        )

        assert score.metadata is None


class TestScoreToLabelEnum:
    """Tests for _score_to_label_enum helper."""

    def test_positive_score(self):
        """Scores >= 0.33 should be positive."""
        assert _score_to_label_enum(0.33) == SentimentLabel.POSITIVE
        assert _score_to_label_enum(0.5) == SentimentLabel.POSITIVE
        assert _score_to_label_enum(1.0) == SentimentLabel.POSITIVE

    def test_negative_score(self):
        """Scores <= -0.33 should be negative."""
        assert _score_to_label_enum(-0.33) == SentimentLabel.NEGATIVE
        assert _score_to_label_enum(-0.5) == SentimentLabel.NEGATIVE
        assert _score_to_label_enum(-1.0) == SentimentLabel.NEGATIVE

    def test_neutral_score(self):
        """Scores between -0.33 and 0.33 should be neutral."""
        assert _score_to_label_enum(0.0) == SentimentLabel.NEUTRAL
        assert _score_to_label_enum(0.32) == SentimentLabel.NEUTRAL
        assert _score_to_label_enum(-0.32) == SentimentLabel.NEUTRAL
        assert _score_to_label_enum(0.1) == SentimentLabel.NEUTRAL


class TestLabelToScore:
    """Tests for _label_to_score helper."""

    def test_positive_label(self):
        """Positive sentiment should return positive score."""
        assert _label_to_score("positive", 0.8) == 0.8
        assert _label_to_score("positive", 0.95) == 0.95

    def test_negative_label(self):
        """Negative sentiment should return negative score."""
        assert _label_to_score("negative", 0.8) == -0.8
        assert _label_to_score("negative", 0.95) == -0.95

    def test_neutral_label(self):
        """Neutral sentiment should return 0."""
        assert _label_to_score("neutral", 0.5) == 0.0
        assert _label_to_score("neutral", 0.9) == 0.0


class TestAggregateSentiment:
    """Tests for aggregate_sentiment function."""

    def test_empty_sources(self):
        """Empty source list should return neutral."""
        result = aggregate_sentiment([])

        assert result.score == 0.0
        assert result.label == SentimentLabel.NEUTRAL
        assert result.confidence == 0.0
        assert result.sources == {}
        assert result.agreement_score == 0.0

    def test_single_source_positive(self):
        """Single positive source should return positive."""
        scores = [
            SourceSentimentScore(
                source=SentimentSource.FINNHUB,
                score=0.8,
                label=SentimentLabel.POSITIVE,
                confidence=0.9,
                timestamp=dt.now(UTC),
            )
        ]

        result = aggregate_sentiment(scores)

        assert result.score > 0.5
        assert result.label == SentimentLabel.POSITIVE
        assert result.confidence > 0.5
        assert result.agreement_score == 1.0  # Single source agrees with itself

    def test_single_source_negative(self):
        """Single negative source should return negative."""
        scores = [
            SourceSentimentScore(
                source=SentimentSource.OUR_MODEL,
                score=-0.7,
                label=SentimentLabel.NEGATIVE,
                confidence=0.85,
                timestamp=dt.now(UTC),
            )
        ]

        result = aggregate_sentiment(scores)

        assert result.score < -0.5
        assert result.label == SentimentLabel.NEGATIVE

    def test_multiple_sources_agreement(self):
        """Multiple sources with same sentiment should have high agreement."""
        scores = [
            SourceSentimentScore(
                source=SentimentSource.FINNHUB,
                score=0.7,
                label=SentimentLabel.POSITIVE,
                confidence=0.9,
                timestamp=dt.now(UTC),
            ),
            SourceSentimentScore(
                source=SentimentSource.OUR_MODEL,
                score=0.8,
                label=SentimentLabel.POSITIVE,
                confidence=0.85,
                timestamp=dt.now(UTC),
            ),
            SourceSentimentScore(
                source=SentimentSource.TIINGO,
                score=0.6,
                label=SentimentLabel.POSITIVE,
                confidence=0.8,
                timestamp=dt.now(UTC),
            ),
        ]

        result = aggregate_sentiment(scores)

        assert result.score > 0.5
        assert result.label == SentimentLabel.POSITIVE
        assert result.agreement_score > 0.8  # High agreement

    def test_multiple_sources_disagreement(self):
        """Sources with conflicting sentiment should have low agreement."""
        scores = [
            SourceSentimentScore(
                source=SentimentSource.FINNHUB,
                score=0.8,
                label=SentimentLabel.POSITIVE,
                confidence=0.9,
                timestamp=dt.now(UTC),
            ),
            SourceSentimentScore(
                source=SentimentSource.OUR_MODEL,
                score=-0.7,
                label=SentimentLabel.NEGATIVE,
                confidence=0.85,
                timestamp=dt.now(UTC),
            ),
        ]

        result = aggregate_sentiment(scores)

        # Agreement should be moderate-low due to conflicting scores
        assert result.agreement_score < 0.75

    def test_weighted_average(self):
        """Should use weights correctly."""
        # Finnhub (40% weight) positive, Others negative
        scores = [
            SourceSentimentScore(
                source=SentimentSource.FINNHUB,
                score=1.0,
                label=SentimentLabel.POSITIVE,
                confidence=1.0,
                timestamp=dt.now(UTC),
            ),
            SourceSentimentScore(
                source=SentimentSource.OUR_MODEL,
                score=-1.0,
                label=SentimentLabel.NEGATIVE,
                confidence=1.0,
                timestamp=dt.now(UTC),
            ),
            SourceSentimentScore(
                source=SentimentSource.TIINGO,
                score=-1.0,
                label=SentimentLabel.NEGATIVE,
                confidence=1.0,
                timestamp=dt.now(UTC),
            ),
        ]

        result = aggregate_sentiment(scores)

        # With default weights (40% + 35% + 25%), score should be:
        # (1.0 * 0.4 + -1.0 * 0.35 + -1.0 * 0.25) / 1.0 = 0.4 - 0.35 - 0.25 = -0.2
        assert -0.3 < result.score < 0.0

    def test_custom_weights(self):
        """Should allow custom weights."""
        scores = [
            SourceSentimentScore(
                source=SentimentSource.FINNHUB,
                score=1.0,
                label=SentimentLabel.POSITIVE,
                confidence=1.0,
                timestamp=dt.now(UTC),
            ),
            SourceSentimentScore(
                source=SentimentSource.OUR_MODEL,
                score=-1.0,
                label=SentimentLabel.NEGATIVE,
                confidence=1.0,
                timestamp=dt.now(UTC),
            ),
        ]

        # Equal weights
        custom_weights = {
            SentimentSource.FINNHUB: 0.5,
            SentimentSource.OUR_MODEL: 0.5,
        }

        result = aggregate_sentiment(scores, weights=custom_weights)

        # Should average to ~0
        assert -0.1 < result.score < 0.1

    def test_confidence_affects_weight(self):
        """Lower confidence should reduce source impact."""
        scores = [
            SourceSentimentScore(
                source=SentimentSource.FINNHUB,
                score=1.0,
                label=SentimentLabel.POSITIVE,
                confidence=0.1,  # Very low confidence
                timestamp=dt.now(UTC),
            ),
            SourceSentimentScore(
                source=SentimentSource.OUR_MODEL,
                score=-0.5,
                label=SentimentLabel.NEGATIVE,
                confidence=1.0,  # High confidence
                timestamp=dt.now(UTC),
            ),
        ]

        result = aggregate_sentiment(scores)

        # Despite Finnhub having higher weight, low confidence reduces its impact
        assert result.score < 0  # Should lean negative

    def test_score_clamped_to_range(self):
        """Score should be clamped to [-1, 1]."""
        scores = [
            SourceSentimentScore(
                source=SentimentSource.FINNHUB,
                score=1.5,  # Out of range
                label=SentimentLabel.POSITIVE,
                confidence=1.0,
                timestamp=dt.now(UTC),
            ),
        ]

        result = aggregate_sentiment(scores)

        assert result.score <= 1.0
        assert result.score >= -1.0

    def test_returns_all_sources(self):
        """Result should contain all source scores."""
        scores = [
            SourceSentimentScore(
                source=SentimentSource.FINNHUB,
                score=0.5,
                label=SentimentLabel.POSITIVE,
                confidence=0.8,
                timestamp=dt.now(UTC),
            ),
            SourceSentimentScore(
                source=SentimentSource.OUR_MODEL,
                score=0.3,
                label=SentimentLabel.NEUTRAL,
                confidence=0.7,
                timestamp=dt.now(UTC),
            ),
        ]

        result = aggregate_sentiment(scores)

        assert SentimentSource.FINNHUB in result.sources
        assert SentimentSource.OUR_MODEL in result.sources
        assert result.sources[SentimentSource.FINNHUB].score == 0.5


class TestCreateFinnhubScore:
    """Tests for create_finnhub_score function."""

    def test_bullish_sentiment(self):
        """High bullish percentage should be positive."""
        score = create_finnhub_score(
            sentiment_score=0.8,
            bullish_percent=0.8,
            bearish_percent=0.2,
        )

        assert score.source == SentimentSource.FINNHUB
        assert score.score == 0.8
        assert score.label == SentimentLabel.POSITIVE
        assert score.confidence > 0.5

    def test_bearish_sentiment(self):
        """High bearish percentage should be negative."""
        score = create_finnhub_score(
            sentiment_score=-0.7,
            bullish_percent=0.15,
            bearish_percent=0.85,
        )

        assert score.score == -0.7
        assert score.label == SentimentLabel.NEGATIVE
        assert score.confidence > 0.5

    def test_mixed_sentiment(self):
        """50/50 split should have low confidence."""
        score = create_finnhub_score(
            sentiment_score=0.0,
            bullish_percent=0.5,
            bearish_percent=0.5,
        )

        assert score.label == SentimentLabel.NEUTRAL
        assert score.confidence == 0.5  # Minimum confidence for even split

    def test_includes_metadata(self):
        """Should include bullish/bearish percentages in metadata."""
        score = create_finnhub_score(
            sentiment_score=0.5,
            bullish_percent=0.7,
            bearish_percent=0.3,
        )

        assert score.metadata is not None
        assert score.metadata["bullish_percent"] == 0.7
        assert score.metadata["bearish_percent"] == 0.3

    def test_custom_timestamp(self):
        """Should use provided timestamp."""
        timestamp = dt(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        score = create_finnhub_score(
            sentiment_score=0.5,
            bullish_percent=0.6,
            bearish_percent=0.4,
            timestamp=timestamp,
        )

        assert score.timestamp == timestamp

    def test_default_timestamp(self):
        """Should use current time if timestamp not provided."""
        before = dt.now(UTC)
        score = create_finnhub_score(
            sentiment_score=0.5,
            bullish_percent=0.6,
            bearish_percent=0.4,
        )
        after = dt.now(UTC)

        assert before <= score.timestamp <= after


class TestCreateTiingoScore:
    """Tests for create_tiingo_score function."""

    def test_mostly_positive_articles(self):
        """More positive articles should be positive."""
        score = create_tiingo_score(
            positive_count=8,
            negative_count=2,
            total_articles=10,
        )

        assert score.source == SentimentSource.TIINGO
        assert score.score == 0.6  # (8-2)/10 = 0.6
        assert score.label == SentimentLabel.POSITIVE

    def test_mostly_negative_articles(self):
        """More negative articles should be negative."""
        score = create_tiingo_score(
            positive_count=1,
            negative_count=9,
            total_articles=10,
        )

        assert score.score == -0.8  # (1-9)/10 = -0.8
        assert score.label == SentimentLabel.NEGATIVE

    def test_balanced_articles(self):
        """Equal positive and negative should be neutral."""
        score = create_tiingo_score(
            positive_count=5,
            negative_count=5,
            total_articles=10,
        )

        assert score.score == 0.0
        assert score.label == SentimentLabel.NEUTRAL

    def test_no_articles(self):
        """Zero articles should return neutral with zero confidence."""
        score = create_tiingo_score(
            positive_count=0,
            negative_count=0,
            total_articles=0,
        )

        assert score.score == 0.0
        assert score.label == SentimentLabel.NEUTRAL
        assert score.confidence == 0.0
        assert score.metadata["article_count"] == 0

    def test_more_articles_higher_confidence(self):
        """More articles should increase confidence."""
        few_articles = create_tiingo_score(
            positive_count=2,
            negative_count=0,
            total_articles=2,
        )

        many_articles = create_tiingo_score(
            positive_count=20,
            negative_count=0,
            total_articles=20,
        )

        assert many_articles.confidence > few_articles.confidence

    def test_includes_metadata(self):
        """Should include article counts in metadata."""
        score = create_tiingo_score(
            positive_count=7,
            negative_count=3,
            total_articles=15,
        )

        assert score.metadata["article_count"] == 15
        assert score.metadata["positive_count"] == 7
        assert score.metadata["negative_count"] == 3

    def test_score_clamped(self):
        """Score should be clamped to [-1, 1] even with extreme ratios."""
        # This shouldn't happen in practice, but ensure bounds
        score = create_tiingo_score(
            positive_count=100,
            negative_count=0,
            total_articles=50,  # More positives than total (edge case)
        )

        # (100-0)/50 = 2.0, but should be clamped
        assert score.score == 1.0


class TestAnalyzeTextSentiment:
    """Tests for analyze_text_sentiment function."""

    @patch("src.lambdas.analysis.sentiment.analyze_sentiment")
    def test_positive_text(self, mock_analyze):
        """Positive text should return positive score."""
        mock_analyze.return_value = ("positive", 0.9)

        score = analyze_text_sentiment("This stock is amazing!")

        assert score.source == SentimentSource.OUR_MODEL
        assert score.score == 0.9  # Positive score
        assert score.label == SentimentLabel.POSITIVE
        mock_analyze.assert_called_once_with("This stock is amazing!")

    @patch("src.lambdas.analysis.sentiment.analyze_sentiment")
    def test_negative_text(self, mock_analyze):
        """Negative text should return negative score."""
        mock_analyze.return_value = ("negative", 0.85)

        score = analyze_text_sentiment("This company is failing badly")

        assert score.score == -0.85  # Negative score
        assert score.label == SentimentLabel.NEGATIVE

    @patch("src.lambdas.analysis.sentiment.analyze_sentiment")
    def test_neutral_text(self, mock_analyze):
        """Neutral text should return neutral score."""
        mock_analyze.return_value = ("neutral", 0.55)

        score = analyze_text_sentiment("The market is open today")

        assert score.score == 0.0  # Neutral maps to 0
        assert score.label == SentimentLabel.NEUTRAL

    @patch("src.lambdas.analysis.sentiment.analyze_sentiment")
    def test_includes_metadata(self, mock_analyze):
        """Should include model version and text length in metadata."""
        mock_analyze.return_value = ("positive", 0.8)

        score = analyze_text_sentiment("Great earnings report!")

        assert score.metadata is not None
        assert "model_version" in score.metadata
        assert score.metadata["text_length"] == len("Great earnings report!")

    @patch("src.lambdas.analysis.sentiment.analyze_sentiment")
    def test_confidence_calculation(self, mock_analyze):
        """Confidence should be based on model score."""
        # High confidence positive
        mock_analyze.return_value = ("positive", 0.95)
        score = analyze_text_sentiment("Excellent!")
        assert score.confidence == 0.95

        # Low confidence (mapped up)
        mock_analyze.return_value = ("positive", 0.4)
        score = analyze_text_sentiment("Okay")
        # confidence = 0.5 + (0.5 - 0.4) = 0.6
        assert score.confidence == 0.6


class TestSourceWeights:
    """Tests for SOURCE_WEIGHTS constant."""

    def test_weights_sum_to_one(self):
        """Source weights should sum to 1.0."""
        total = sum(SOURCE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_sources_have_weight(self):
        """All sentiment sources should have a weight."""
        assert SentimentSource.FINNHUB in SOURCE_WEIGHTS
        assert SentimentSource.OUR_MODEL in SOURCE_WEIGHTS
        assert SentimentSource.TIINGO in SOURCE_WEIGHTS

    def test_finnhub_highest_weight(self):
        """Finnhub should have highest weight (market data)."""
        assert SOURCE_WEIGHTS[SentimentSource.FINNHUB] >= max(
            SOURCE_WEIGHTS[SentimentSource.OUR_MODEL],
            SOURCE_WEIGHTS[SentimentSource.TIINGO],
        )


class TestAggregatedSentiment:
    """Tests for AggregatedSentiment named tuple."""

    def test_named_tuple_fields(self):
        """Should have all expected fields."""
        result = AggregatedSentiment(
            score=0.5,
            label=SentimentLabel.POSITIVE,
            confidence=0.8,
            sources={},
            agreement_score=0.9,
        )

        assert result.score == 0.5
        assert result.label == SentimentLabel.POSITIVE
        assert result.confidence == 0.8
        assert result.sources == {}
        assert result.agreement_score == 0.9

    def test_named_tuple_immutable(self):
        """Named tuple should be immutable."""
        result = AggregatedSentiment(
            score=0.5,
            label=SentimentLabel.POSITIVE,
            confidence=0.8,
            sources={},
            agreement_score=0.9,
        )

        with pytest.raises(AttributeError):
            result.score = 0.7


class TestIntegration:
    """Integration tests combining multiple functions."""

    @patch("src.lambdas.analysis.sentiment.analyze_sentiment")
    def test_full_aggregation_pipeline(self, mock_analyze):
        """Test complete aggregation from raw data to result."""
        mock_analyze.return_value = ("positive", 0.85)

        # Create scores from each source
        finnhub_score = create_finnhub_score(
            sentiment_score=0.7,
            bullish_percent=0.75,
            bearish_percent=0.25,
        )

        tiingo_score = create_tiingo_score(
            positive_count=15,
            negative_count=5,
            total_articles=25,
        )

        ml_score = analyze_text_sentiment("Company reports record profits")

        # Aggregate all sources
        result = aggregate_sentiment([finnhub_score, tiingo_score, ml_score])

        # Verify result
        assert result.label == SentimentLabel.POSITIVE
        assert result.score > 0.5
        assert len(result.sources) == 3
        assert result.agreement_score > 0.7  # All positive, should agree

    @patch("src.lambdas.analysis.sentiment.analyze_sentiment")
    def test_partial_sources(self, mock_analyze):
        """Aggregation should work with subset of sources."""
        mock_analyze.return_value = ("neutral", 0.55)

        # Only ML model available
        ml_score = analyze_text_sentiment("The market closed flat today")
        result = aggregate_sentiment([ml_score])

        assert result.label == SentimentLabel.NEUTRAL
        assert SentimentSource.OUR_MODEL in result.sources
        assert SentimentSource.FINNHUB not in result.sources
