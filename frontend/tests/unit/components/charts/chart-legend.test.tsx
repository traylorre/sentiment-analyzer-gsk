import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  ChartLegend,
  SentimentScaleLegend,
  ATRLegend,
  SourceLegend,
  TimeRangeLegend,
  ChartKey,
} from '@/components/charts/chart-legend';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, style, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div style={style as React.CSSProperties} {...props}>{children}</div>
    ),
    button: ({ children, disabled, ...props }: React.PropsWithChildren<{ disabled?: boolean }>) => (
      <button disabled={disabled} {...props}>{children}</button>
    ),
  },
}));

describe('ChartLegend', () => {
  const items = [
    { label: 'Series A', color: '#00FFFF' },
    { label: 'Series B', color: '#FF00FF', value: '42' },
    { label: 'Series C', color: '#FFFF00', active: false },
  ];

  it('should render all legend items', () => {
    render(<ChartLegend items={items} />);

    expect(screen.getByText('Series A')).toBeInTheDocument();
    expect(screen.getByText('Series B')).toBeInTheDocument();
    expect(screen.getByText('Series C')).toBeInTheDocument();
  });

  it('should display values when provided', () => {
    render(<ChartLegend items={items} />);

    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('should call onClick when item is clicked', () => {
    const onClick = vi.fn();
    const clickableItems = [
      { label: 'Clickable', color: '#00FFFF', onClick },
    ];

    render(<ChartLegend items={clickableItems} />);

    fireEvent.click(screen.getByText('Clickable'));

    expect(onClick).toHaveBeenCalled();
  });

  it('should apply vertical orientation', () => {
    const { container } = render(<ChartLegend items={items} orientation="vertical" />);

    expect(container.firstChild).toHaveClass('flex-col');
  });
});

describe('SentimentScaleLegend', () => {
  it('should render bearish and bullish labels', () => {
    render(<SentimentScaleLegend />);

    expect(screen.getByText('Bearish')).toBeInTheDocument();
    expect(screen.getByText('Bullish')).toBeInTheDocument();
  });

  it('should have gradient bar', () => {
    const { container } = render(<SentimentScaleLegend />);

    const gradientBar = container.querySelector('.bg-gradient-to-r');
    expect(gradientBar).toBeInTheDocument();
  });
});

describe('ATRLegend', () => {
  it('should render low, medium, high labels', () => {
    render(<ATRLegend />);

    expect(screen.getByText('Low')).toBeInTheDocument();
    expect(screen.getByText('Medium')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
  });
});

describe('SourceLegend', () => {
  const sources = [
    { name: 'Tiingo', color: '#00FFFF', active: true },
    { name: 'Finnhub', color: '#FF00FF', active: false },
  ];

  it('should render all sources', () => {
    render(<SourceLegend sources={sources} />);

    expect(screen.getByText('Tiingo')).toBeInTheDocument();
    expect(screen.getByText('Finnhub')).toBeInTheDocument();
  });

  it('should call onToggle when source is clicked', () => {
    const onToggle = vi.fn();
    render(<SourceLegend sources={sources} onToggle={onToggle} />);

    fireEvent.click(screen.getByText('Tiingo'));

    expect(onToggle).toHaveBeenCalledWith('Tiingo');
  });
});

describe('TimeRangeLegend', () => {
  const options = [
    { label: '1D', value: '1d' },
    { label: '1W', value: '1w' },
    { label: '1M', value: '1m' },
  ];

  it('should render all options', () => {
    render(<TimeRangeLegend options={options} selected="1d" onChange={() => {}} />);

    expect(screen.getByText('1D')).toBeInTheDocument();
    expect(screen.getByText('1W')).toBeInTheDocument();
    expect(screen.getByText('1M')).toBeInTheDocument();
  });

  it('should highlight selected option', () => {
    const { container } = render(
      <TimeRangeLegend options={options} selected="1w" onChange={() => {}} />
    );

    const selectedButton = screen.getByText('1W');
    expect(selectedButton).toHaveClass('bg-accent');
  });

  it('should call onChange when option is clicked', () => {
    const onChange = vi.fn();
    render(<TimeRangeLegend options={options} selected="1d" onChange={onChange} />);

    fireEvent.click(screen.getByText('1M'));

    expect(onChange).toHaveBeenCalledWith('1m');
  });
});

describe('ChartKey', () => {
  const items = [
    { type: 'line' as const, color: '#00FFFF', label: 'Sentiment' },
    { type: 'bar' as const, color: '#FF00FF', label: 'Volume' },
    { type: 'area' as const, color: '#FFFF00', label: 'Range' },
    { type: 'dot' as const, color: '#00FF00', label: 'Events' },
  ];

  it('should render all key items', () => {
    render(<ChartKey items={items} />);

    expect(screen.getByText('Sentiment')).toBeInTheDocument();
    expect(screen.getByText('Volume')).toBeInTheDocument();
    expect(screen.getByText('Range')).toBeInTheDocument();
    expect(screen.getByText('Events')).toBeInTheDocument();
  });
});
