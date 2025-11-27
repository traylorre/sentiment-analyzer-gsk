import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  SentimentPill,
  ScoreBadge,
  HeroScore,
  CompactScore,
} from '@/components/charts/sentiment-pill';

// framer-motion is mocked globally in tests/setup.ts

describe('SentimentPill', () => {
  it('should render score', () => {
    render(<SentimentPill score={0.5} />);

    // Should display formatted score (+0.50)
    expect(screen.getByText('+0.50')).toBeInTheDocument();
  });

  it('should show bullish label for positive score', () => {
    render(<SentimentPill score={0.5} showLabel />);

    expect(screen.getByText('Bullish')).toBeInTheDocument();
  });

  it('should show bearish label for negative score', () => {
    render(<SentimentPill score={-0.5} showLabel />);

    expect(screen.getByText('Bearish')).toBeInTheDocument();
  });

  it('should show neutral label for scores near zero', () => {
    render(<SentimentPill score={0.1} showLabel />);

    expect(screen.getByText('Neutral')).toBeInTheDocument();
  });

  it('should apply size classes', () => {
    const { container, rerender } = render(<SentimentPill score={0.5} size="sm" />);
    expect(container.firstChild).toHaveClass('text-xs');

    rerender(<SentimentPill score={0.5} size="lg" />);
    expect(container.firstChild).toHaveClass('text-base');
  });
});

describe('ScoreBadge', () => {
  it('should render score', () => {
    render(<ScoreBadge score={0.75} />);

    expect(screen.getByText('+0.75')).toBeInTheDocument();
  });

  it('should have colored background', () => {
    const { container } = render(<ScoreBadge score={0.75} />);
    const badge = container.firstChild as HTMLElement;

    // Should have a background color set
    expect(badge.style.backgroundColor).toBeTruthy();
  });
});

describe('HeroScore', () => {
  it('should render ticker and score', () => {
    render(<HeroScore score={0.65} ticker="AAPL" />);

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('+0.65')).toBeInTheDocument();
  });

  it('should show sentiment label', () => {
    render(<HeroScore score={0.65} ticker="AAPL" />);

    expect(screen.getByText('Bullish')).toBeInTheDocument();
  });

  it('should show source when provided', () => {
    render(<HeroScore score={0.65} ticker="AAPL" source="Tiingo" />);

    expect(screen.getByText('via Tiingo')).toBeInTheDocument();
  });
});

describe('CompactScore', () => {
  it('should render score', () => {
    render(<CompactScore score={0.45} />);

    expect(screen.getByText('+0.45')).toBeInTheDocument();
  });

  it('should show positive change', () => {
    render(<CompactScore score={0.45} change={0.05} />);

    expect(screen.getByText('+5.0%')).toBeInTheDocument();
  });

  it('should show negative change', () => {
    render(<CompactScore score={0.45} change={-0.03} />);

    expect(screen.getByText('-3.0%')).toBeInTheDocument();
  });
});
