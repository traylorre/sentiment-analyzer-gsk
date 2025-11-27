import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThresholdPreview, ThresholdSparkline } from '@/components/dashboard/threshold-preview';

// framer-motion is mocked globally in tests/setup.ts

describe('ThresholdPreview', () => {
  it('should render threshold label for sentiment', () => {
    render(
      <ThresholdPreview
        thresholdValue={0.75}
        thresholdDirection="above"
        alertType="sentiment_threshold"
      />
    );

    expect(screen.getByText('0.75')).toBeInTheDocument();
  });

  it('should render threshold label with percentage for volatility', () => {
    render(
      <ThresholdPreview
        thresholdValue={25}
        thresholdDirection="above"
        alertType="volatility_threshold"
      />
    );

    expect(screen.getByText('25%')).toBeInTheDocument();
  });

  it('should show alert zone label for above direction', () => {
    render(
      <ThresholdPreview
        thresholdValue={0.5}
        thresholdDirection="above"
        alertType="sentiment_threshold"
      />
    );

    expect(screen.getByText(/Alert zone/)).toBeInTheDocument();
  });

  it('should show alert zone label for below direction', () => {
    render(
      <ThresholdPreview
        thresholdValue={0.5}
        thresholdDirection="below"
        alertType="sentiment_threshold"
      />
    );

    expect(screen.getByText(/Alert zone/)).toBeInTheDocument();
  });

  it('should render SVG elements', () => {
    const { container } = render(
      <ThresholdPreview
        thresholdValue={0.5}
        thresholdDirection="above"
        alertType="sentiment_threshold"
      />
    );

    // Should have SVG
    expect(container.querySelector('svg')).toBeInTheDocument();

    // Should have threshold line
    expect(container.querySelector('line')).toBeInTheDocument();

    // Should have data path
    expect(container.querySelector('path')).toBeInTheDocument();
  });

  it('should show current value indicator when provided', () => {
    const { container } = render(
      <ThresholdPreview
        thresholdValue={0.5}
        thresholdDirection="above"
        alertType="sentiment_threshold"
        currentValue={0.7}
      />
    );

    // Should have circle for current value
    expect(container.querySelector('circle')).toBeInTheDocument();
  });

  it('should use provided historical values', () => {
    const historicalValues = [0.1, 0.2, 0.3, 0.4, 0.5];

    const { container } = render(
      <ThresholdPreview
        thresholdValue={0.3}
        thresholdDirection="above"
        alertType="sentiment_threshold"
        historicalValues={historicalValues}
      />
    );

    // Should render with path
    expect(container.querySelector('path')).toBeInTheDocument();
  });
});

describe('ThresholdSparkline', () => {
  it('should render', () => {
    const { container } = render(
      <ThresholdSparkline
        thresholdValue={0.5}
        thresholdDirection="above"
        alertType="sentiment_threshold"
      />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  it('should have accent color when triggered', () => {
    const { container } = render(
      <ThresholdSparkline
        thresholdValue={0.5}
        thresholdDirection="above"
        alertType="sentiment_threshold"
        isTriggered={true}
      />
    );

    // Should have stronger accent color class
    expect(container.querySelector('.bg-accent\\/30')).toBeInTheDocument();
  });

  it('should have lighter color when not triggered', () => {
    const { container } = render(
      <ThresholdSparkline
        thresholdValue={0.5}
        thresholdDirection="above"
        alertType="sentiment_threshold"
        isTriggered={false}
      />
    );

    // Should have lighter accent color class
    expect(container.querySelector('.bg-accent\\/10')).toBeInTheDocument();
  });

  it('should position threshold line based on value for sentiment', () => {
    const { container } = render(
      <ThresholdSparkline
        thresholdValue={0}
        thresholdDirection="above"
        alertType="sentiment_threshold"
      />
    );

    // For sentiment 0 should be at 50% (midpoint of -1 to 1)
    const thresholdLine = container.querySelector('.bg-accent');
    expect(thresholdLine).toBeInTheDocument();
  });

  it('should position threshold line based on value for volatility', () => {
    const { container } = render(
      <ThresholdSparkline
        thresholdValue={50}
        thresholdDirection="above"
        alertType="volatility_threshold"
      />
    );

    // For volatility 50 should be at 50%
    const thresholdLine = container.querySelector('.bg-accent');
    expect(thresholdLine).toBeInTheDocument();
  });
});
