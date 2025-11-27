import type { SentimentLabel } from '@/types/sentiment';

export const SENTIMENT_COLORS = {
  positive: '#22C55E',  // Green
  neutral: '#EAB308',   // Yellow
  negative: '#EF4444',  // Red
  accent: '#00FFFF',    // Cyan
} as const;

/**
 * Get the color for a sentiment score
 * @param score - Sentiment score from -1.0 to 1.0
 */
export function getSentimentColor(score: number): string {
  if (score >= 0.33) return SENTIMENT_COLORS.positive;
  if (score <= -0.33) return SENTIMENT_COLORS.negative;
  return SENTIMENT_COLORS.neutral;
}

/**
 * Get a CSS gradient for chart fills based on sentiment
 * @param score - Sentiment score from -1.0 to 1.0
 */
export function getSentimentGradient(score: number): string {
  const color = getSentimentColor(score);
  return `linear-gradient(180deg, ${color}40 0%, ${color}00 100%)`;
}

/**
 * Get the sentiment label for a score
 * @param score - Sentiment score from -1.0 to 1.0
 */
export function getScoreLabel(score: number): SentimentLabel {
  if (score >= 0.33) return 'positive';
  if (score <= -0.33) return 'negative';
  return 'neutral';
}

/**
 * Get the color for a sentiment label
 */
export function getLabelColor(label: SentimentLabel): string {
  return SENTIMENT_COLORS[label];
}

/**
 * Interpolate color based on score for heat map
 * Returns a color between red (-1) through yellow (0) to green (1)
 */
export function interpolateSentimentColor(score: number): string {
  // Clamp score to [-1, 1]
  const clampedScore = Math.max(-1, Math.min(1, score));

  if (clampedScore < 0) {
    // Red to yellow: interpolate from negative to neutral
    const t = (clampedScore + 1); // 0 to 1 range
    const r = 239;
    const g = Math.round(68 + (179 - 68) * t);
    const b = Math.round(68 + (8 - 68) * t);
    return `rgb(${r}, ${g}, ${b})`;
  } else {
    // Yellow to green: interpolate from neutral to positive
    const t = clampedScore; // 0 to 1 range
    const r = Math.round(234 + (34 - 234) * t);
    const g = Math.round(179 + (197 - 179) * t);
    const b = Math.round(8 + (94 - 8) * t);
    return `rgb(${r}, ${g}, ${b})`;
  }
}
