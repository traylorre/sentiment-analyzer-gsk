import { describe, it, expect } from 'vitest';
import {
  getSentimentColor,
  getSentimentGradient,
  getScoreLabel,
  getLabelColor,
  interpolateSentimentColor,
  SENTIMENT_COLORS,
} from '@/lib/utils/colors';

describe('Color Utilities', () => {
  describe('getSentimentColor', () => {
    it('should return green for positive scores (>= 0.33)', () => {
      expect(getSentimentColor(0.33)).toBe(SENTIMENT_COLORS.positive);
      expect(getSentimentColor(0.5)).toBe(SENTIMENT_COLORS.positive);
      expect(getSentimentColor(1.0)).toBe(SENTIMENT_COLORS.positive);
    });

    it('should return red for negative scores (<= -0.33)', () => {
      expect(getSentimentColor(-0.33)).toBe(SENTIMENT_COLORS.negative);
      expect(getSentimentColor(-0.5)).toBe(SENTIMENT_COLORS.negative);
      expect(getSentimentColor(-1.0)).toBe(SENTIMENT_COLORS.negative);
    });

    it('should return yellow for neutral scores (-0.33 to 0.33)', () => {
      expect(getSentimentColor(0)).toBe(SENTIMENT_COLORS.neutral);
      expect(getSentimentColor(0.1)).toBe(SENTIMENT_COLORS.neutral);
      expect(getSentimentColor(-0.1)).toBe(SENTIMENT_COLORS.neutral);
      expect(getSentimentColor(0.32)).toBe(SENTIMENT_COLORS.neutral);
      expect(getSentimentColor(-0.32)).toBe(SENTIMENT_COLORS.neutral);
    });
  });

  describe('getSentimentGradient', () => {
    it('should return a gradient string', () => {
      const gradient = getSentimentGradient(0.5);
      expect(gradient).toContain('linear-gradient');
      expect(gradient).toContain(SENTIMENT_COLORS.positive);
    });

    it('should include transparency values', () => {
      const gradient = getSentimentGradient(0);
      expect(gradient).toMatch(/40.*00/);
    });
  });

  describe('getScoreLabel', () => {
    it('should return "positive" for scores >= 0.33', () => {
      expect(getScoreLabel(0.33)).toBe('positive');
      expect(getScoreLabel(1)).toBe('positive');
    });

    it('should return "negative" for scores <= -0.33', () => {
      expect(getScoreLabel(-0.33)).toBe('negative');
      expect(getScoreLabel(-1)).toBe('negative');
    });

    it('should return "neutral" for scores between -0.33 and 0.33', () => {
      expect(getScoreLabel(0)).toBe('neutral');
      expect(getScoreLabel(0.32)).toBe('neutral');
      expect(getScoreLabel(-0.32)).toBe('neutral');
    });
  });

  describe('getLabelColor', () => {
    it('should return correct color for each label', () => {
      expect(getLabelColor('positive')).toBe(SENTIMENT_COLORS.positive);
      expect(getLabelColor('negative')).toBe(SENTIMENT_COLORS.negative);
      expect(getLabelColor('neutral')).toBe(SENTIMENT_COLORS.neutral);
    });
  });

  describe('interpolateSentimentColor', () => {
    it('should return red-ish color for -1', () => {
      const color = interpolateSentimentColor(-1);
      expect(color).toMatch(/^rgb\(239,/);
    });

    it('should return yellow-ish color for 0', () => {
      const color = interpolateSentimentColor(0);
      expect(color).toMatch(/rgb\(234, 179, 8\)/);
    });

    it('should return green-ish color for 1', () => {
      const color = interpolateSentimentColor(1);
      expect(color).toMatch(/rgb\(34, 197, 94\)/);
    });

    it('should clamp values outside -1 to 1 range', () => {
      const colorAtMinus2 = interpolateSentimentColor(-2);
      const colorAtMinus1 = interpolateSentimentColor(-1);
      expect(colorAtMinus2).toBe(colorAtMinus1);

      const colorAt2 = interpolateSentimentColor(2);
      const colorAt1 = interpolateSentimentColor(1);
      expect(colorAt2).toBe(colorAt1);
    });
  });
});
