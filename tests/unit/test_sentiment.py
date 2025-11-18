"""
Unit Tests for Sentiment Analysis Module
========================================

Tests model loading and inference with mocked HuggingFace pipeline.

For On-Call Engineers:
    These tests verify:
    - Model caching behavior
    - Sentiment classification (positive, negative, neutral)
    - Neutral threshold (score < 0.6)
    - Text truncation (512 chars)
    - Error handling

For Developers:
    - Uses mocks to avoid loading actual model in tests
    - Test both happy path and error scenarios
    - Verify neutral detection for low-confidence results
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.analysis.sentiment import (
    InferenceError,
    ModelLoadError,
    analyze_sentiment,
    clear_model_cache,
    get_model_load_time_ms,
    is_model_loaded,
    load_model,
)


@pytest.fixture(autouse=True)
def reset_model_cache():
    """Reset model cache before each test."""
    clear_model_cache()
    yield
    clear_model_cache()


class TestLoadModel:
    """Tests for load_model function."""

    def test_load_model_success(self):
        """Test successful model loading."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            result = load_model("/test/model/path")

            assert result == mock_instance
            mock_pipeline.assert_called_once_with(
                "sentiment-analysis",
                model="/test/model/path",
                tokenizer="/test/model/path",
                framework="pt",
                device=-1,
            )

    def test_load_model_caching(self):
        """Test that model is cached after first load."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_pipeline.return_value = mock_instance

            # First load
            result1 = load_model("/test/model/path")
            # Second load
            result2 = load_model("/test/model/path")

            # Should only call pipeline once (cached)
            assert mock_pipeline.call_count == 1
            assert result1 == result2

    def test_load_model_uses_env_var(self):
        """Test model path from environment variable."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock()

            os.environ["MODEL_PATH"] = "/env/model/path"
            try:
                load_model()
                mock_pipeline.assert_called_once()
                call_args = mock_pipeline.call_args
                assert call_args[1]["model"] == "/env/model/path"
            finally:
                del os.environ["MODEL_PATH"]

    def test_load_model_default_path(self):
        """Test default model path when no env var."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock()

            # Ensure no MODEL_PATH env var
            os.environ.pop("MODEL_PATH", None)

            load_model()

            call_args = mock_pipeline.call_args
            assert call_args[1]["model"] == "/opt/model"

    def test_load_model_failure(self):
        """Test error handling when model load fails."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            mock_pipeline.side_effect = Exception("Model not found")

            with pytest.raises(ModelLoadError, match="Failed to load model"):
                load_model("/bad/path")

    def test_load_model_records_time(self):
        """Test that model load time is recorded."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock()

            load_model("/test/path")

            load_time = get_model_load_time_ms()
            assert load_time >= 0


class TestAnalyzeSentiment:
    """Tests for analyze_sentiment function."""

    def test_positive_sentiment(self):
        """Test detection of positive sentiment."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_pipeline.return_value = [{"label": "POSITIVE", "score": 0.95}]
            mock_load.return_value = mock_pipeline

            sentiment, score = analyze_sentiment("This is amazing!")

            assert sentiment == "positive"
            assert score == 0.95

    def test_negative_sentiment(self):
        """Test detection of negative sentiment."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_pipeline.return_value = [{"label": "NEGATIVE", "score": 0.88}]
            mock_load.return_value = mock_pipeline

            sentiment, score = analyze_sentiment("This is terrible!")

            assert sentiment == "negative"
            assert score == 0.88

    def test_neutral_from_low_positive_confidence(self):
        """Test neutral classification from low positive confidence."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_pipeline.return_value = [{"label": "POSITIVE", "score": 0.55}]
            mock_load.return_value = mock_pipeline

            sentiment, score = analyze_sentiment("This is okay.")

            assert sentiment == "neutral"
            assert score == 0.55

    def test_neutral_from_low_negative_confidence(self):
        """Test neutral classification from low negative confidence."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_pipeline.return_value = [{"label": "NEGATIVE", "score": 0.52}]
            mock_load.return_value = mock_pipeline

            sentiment, score = analyze_sentiment("It's not great.")

            assert sentiment == "neutral"
            assert score == 0.52

    def test_boundary_threshold_positive(self):
        """Test exactly at threshold (0.6) is classified correctly."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_pipeline.return_value = [{"label": "POSITIVE", "score": 0.60}]
            mock_load.return_value = mock_pipeline

            sentiment, score = analyze_sentiment("This is fine.")

            # At exactly 0.6, should use the label (not neutral)
            assert sentiment == "positive"
            assert score == 0.60

    def test_boundary_threshold_neutral(self):
        """Test just below threshold (0.59) is neutral."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_pipeline.return_value = [{"label": "POSITIVE", "score": 0.59}]
            mock_load.return_value = mock_pipeline

            sentiment, score = analyze_sentiment("This is kind of okay.")

            assert sentiment == "neutral"
            assert score == 0.59

    def test_text_truncation(self):
        """Test that text is truncated to 512 characters."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_pipeline.return_value = [{"label": "POSITIVE", "score": 0.80}]
            mock_load.return_value = mock_pipeline

            long_text = "x" * 1000
            analyze_sentiment(long_text)

            # Verify pipeline received truncated text
            call_args = mock_pipeline.call_args[0][0]
            assert len(call_args) == 512

    def test_empty_text_returns_neutral(self):
        """Test empty text returns neutral with 0.5 score."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_load.return_value = mock_pipeline

            sentiment, score = analyze_sentiment("")

            assert sentiment == "neutral"
            assert score == 0.5
            # Pipeline should not be called for empty text
            mock_pipeline.assert_not_called()

    def test_none_text_returns_neutral(self):
        """Test None-like text returns neutral."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_load.return_value = mock_pipeline

            # Empty string after truncation
            sentiment, score = analyze_sentiment("")

            assert sentiment == "neutral"
            assert score == 0.5

    def test_inference_failure(self):
        """Test error handling when inference fails."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_pipeline.side_effect = RuntimeError("CUDA error")
            mock_load.return_value = mock_pipeline

            with pytest.raises(InferenceError, match="Sentiment inference failed"):
                analyze_sentiment("Test text")

    def test_label_case_insensitivity(self):
        """Test that label case is normalized."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            # Model returns uppercase
            mock_pipeline.return_value = [{"label": "POSITIVE", "score": 0.90}]
            mock_load.return_value = mock_pipeline

            sentiment, score = analyze_sentiment("Great!")

            # Should be lowercase
            assert sentiment == "positive"


class TestModelCacheHelpers:
    """Tests for cache helper functions."""

    def test_is_model_loaded_false_initially(self):
        """Test is_model_loaded returns False before loading."""
        assert is_model_loaded() is False

    def test_is_model_loaded_true_after_load(self):
        """Test is_model_loaded returns True after loading."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock()

            load_model("/test/path")

            assert is_model_loaded() is True

    def test_clear_model_cache(self):
        """Test clearing model cache."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            mock_pipeline.return_value = MagicMock()

            load_model("/test/path")
            assert is_model_loaded() is True

            clear_model_cache()

            assert is_model_loaded() is False
            assert get_model_load_time_ms() == 0

    def test_get_model_load_time_zero_before_load(self):
        """Test load time is 0 before model is loaded."""
        assert get_model_load_time_ms() == 0


class TestSentimentThresholds:
    """Tests for various sentiment score scenarios."""

    @pytest.mark.parametrize(
        "label,score,expected_sentiment",
        [
            ("POSITIVE", 0.99, "positive"),
            ("POSITIVE", 0.80, "positive"),
            ("POSITIVE", 0.60, "positive"),
            ("POSITIVE", 0.59, "neutral"),
            ("POSITIVE", 0.50, "neutral"),
            ("NEGATIVE", 0.99, "negative"),
            ("NEGATIVE", 0.75, "negative"),
            ("NEGATIVE", 0.60, "negative"),
            ("NEGATIVE", 0.55, "neutral"),
            ("NEGATIVE", 0.40, "neutral"),
        ],
    )
    def test_sentiment_threshold_parametrized(self, label, score, expected_sentiment):
        """Parametrized test for various sentiment threshold scenarios."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_pipeline.return_value = [{"label": label, "score": score}]
            mock_load.return_value = mock_pipeline

            sentiment, returned_score = analyze_sentiment("Test text")

            assert sentiment == expected_sentiment
            assert returned_score == score


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_model_load_error_is_sentiment_error(self):
        """Test ModelLoadError is a SentimentError subclass."""
        from src.lambdas.analysis.sentiment import ModelLoadError, SentimentError

        assert issubclass(ModelLoadError, SentimentError)

    def test_inference_error_is_sentiment_error(self):
        """Test InferenceError is a SentimentError subclass."""
        from src.lambdas.analysis.sentiment import InferenceError, SentimentError

        assert issubclass(InferenceError, SentimentError)

    def test_model_load_error_preserves_cause(self):
        """Test ModelLoadError preserves original exception."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            original_error = FileNotFoundError("Model files missing")
            mock_pipeline.side_effect = original_error

            with pytest.raises(ModelLoadError) as exc_info:
                load_model("/bad/path")

            assert exc_info.value.__cause__ is original_error


class TestIntegrationScenarios:
    """Integration-like tests for realistic scenarios."""

    def test_full_analysis_flow(self):
        """Test complete flow from load to inference."""
        with patch("src.lambdas.analysis.sentiment.pipeline") as mock_pipeline:
            mock_instance = MagicMock()
            mock_instance.return_value = [{"label": "POSITIVE", "score": 0.92}]
            mock_pipeline.return_value = mock_instance

            # First call loads model
            sentiment1, score1 = analyze_sentiment("Great product!")

            # Second call uses cache
            mock_instance.return_value = [{"label": "NEGATIVE", "score": 0.78}]
            sentiment2, score2 = analyze_sentiment("Terrible service!")

            assert sentiment1 == "positive"
            assert score1 == 0.92
            assert sentiment2 == "negative"
            assert score2 == 0.78

            # Model loaded only once
            assert mock_pipeline.call_count == 1

    def test_multiple_neutral_detections(self):
        """Test that low-confidence items are consistently neutral."""
        with patch("src.lambdas.analysis.sentiment.load_model") as mock_load:
            mock_pipeline = MagicMock()
            mock_load.return_value = mock_pipeline

            # Various low-confidence results
            test_cases = [
                [{"label": "POSITIVE", "score": 0.51}],
                [{"label": "NEGATIVE", "score": 0.55}],
                [{"label": "POSITIVE", "score": 0.49}],
            ]

            for result in test_cases:
                mock_pipeline.return_value = result
                sentiment, _ = analyze_sentiment("Test")
                assert sentiment == "neutral"
