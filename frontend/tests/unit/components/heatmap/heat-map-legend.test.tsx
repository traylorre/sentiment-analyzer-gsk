import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  HeatMapLegend,
  DetailedHeatMapLegend,
  CompactHeatMapLegend,
} from '@/components/heatmap/heat-map-legend';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, style, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div style={style as React.CSSProperties} {...props}>{children}</div>
    ),
  },
}));

describe('HeatMapLegend', () => {
  it('should render bearish and bullish labels', () => {
    render(<HeatMapLegend />);

    expect(screen.getByText('Bearish')).toBeInTheDocument();
    expect(screen.getByText('Bullish')).toBeInTheDocument();
  });

  it('should hide labels when showLabels is false', () => {
    render(<HeatMapLegend showLabels={false} />);

    expect(screen.queryByText('Bearish')).not.toBeInTheDocument();
    expect(screen.queryByText('Bullish')).not.toBeInTheDocument();
  });

  it('should apply vertical orientation', () => {
    const { container } = render(<HeatMapLegend orientation="vertical" />);

    expect(container.firstChild).toHaveClass('flex-col');
  });
});

describe('DetailedHeatMapLegend', () => {
  it('should render value markers', () => {
    render(<DetailedHeatMapLegend />);

    expect(screen.getByText('-1.0')).toBeInTheDocument();
    expect(screen.getByText('-0.5')).toBeInTheDocument();
    expect(screen.getByText('0.0')).toBeInTheDocument();
    expect(screen.getByText('+0.5')).toBeInTheDocument();
    expect(screen.getByText('+1.0')).toBeInTheDocument();
  });
});

describe('CompactHeatMapLegend', () => {
  it('should render sentiment labels', () => {
    render(<CompactHeatMapLegend />);

    expect(screen.getByText('Bearish')).toBeInTheDocument();
    expect(screen.getByText('Neutral')).toBeInTheDocument();
    expect(screen.getByText('Bullish')).toBeInTheDocument();
  });
});
