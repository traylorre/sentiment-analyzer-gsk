import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConfigCard, ConfigCardCompact } from '@/components/dashboard/config-card';
import type { Configuration } from '@/types/config';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
    button: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <button {...props}>{children}</button>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

const mockConfig: Configuration = {
  configId: 'config-1',
  name: 'Tech Watchlist',
  tickers: [
    { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
    { symbol: 'GOOGL', name: 'Alphabet Inc.', exchange: 'NASDAQ' },
    { symbol: 'MSFT', name: 'Microsoft Corp.', exchange: 'NASDAQ' },
  ],
  timeframeDays: 7,
  includeExtendedHours: false,
  createdAt: '2024-01-15T10:00:00Z',
  updatedAt: new Date().toISOString(),
};

describe('ConfigCard', () => {
  it('should render config name', () => {
    render(<ConfigCard config={mockConfig} />);

    expect(screen.getByText('Tech Watchlist')).toBeInTheDocument();
  });

  it('should render ticker count', () => {
    render(<ConfigCard config={mockConfig} />);

    expect(screen.getByText('3 tickers')).toBeInTheDocument();
  });

  it('should render singular ticker text', () => {
    const singleTickerConfig = {
      ...mockConfig,
      tickers: [mockConfig.tickers[0]],
    };

    render(<ConfigCard config={singleTickerConfig} />);

    expect(screen.getByText('1 ticker')).toBeInTheDocument();
  });

  it('should render ticker symbols', () => {
    render(<ConfigCard config={mockConfig} />);

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('GOOGL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  it('should show +more for configs with many tickers', () => {
    const manyTickersConfig = {
      ...mockConfig,
      tickers: [
        { symbol: 'AAPL', name: 'Apple', exchange: 'NASDAQ' as const },
        { symbol: 'GOOGL', name: 'Google', exchange: 'NASDAQ' as const },
        { symbol: 'MSFT', name: 'Microsoft', exchange: 'NASDAQ' as const },
        { symbol: 'AMZN', name: 'Amazon', exchange: 'NASDAQ' as const },
        { symbol: 'META', name: 'Meta', exchange: 'NASDAQ' as const },
        { symbol: 'NVDA', name: 'Nvidia', exchange: 'NASDAQ' as const },
      ],
    };

    render(<ConfigCard config={manyTickersConfig} />);

    expect(screen.getByText('+1 more')).toBeInTheDocument();
  });

  it('should render timeframe', () => {
    render(<ConfigCard config={mockConfig} />);

    expect(screen.getByText('7d')).toBeInTheDocument();
  });

  it('should show active indicator when active', () => {
    const { container } = render(<ConfigCard config={mockConfig} isActive />);

    // The active class is applied
    expect(container.querySelector('.border-accent')).toBeInTheDocument();
  });

  it('should call onSelect when clicked', () => {
    const onSelect = vi.fn();

    render(<ConfigCard config={mockConfig} onSelect={onSelect} />);

    fireEvent.click(screen.getByText('Tech Watchlist'));

    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it('should call onEdit when edit button clicked', () => {
    const onEdit = vi.fn();
    const onSelect = vi.fn();

    render(<ConfigCard config={mockConfig} onEdit={onEdit} onSelect={onSelect} />);

    // Find and click the edit button by aria-label
    const editButton = screen.getByRole('button', { name: /edit tech watchlist/i });
    fireEvent.click(editButton);

    expect(onEdit).toHaveBeenCalledTimes(1);
    // Should not trigger select
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('should call onDelete when delete button clicked', () => {
    const onDelete = vi.fn();
    const onSelect = vi.fn();

    render(<ConfigCard config={mockConfig} onDelete={onDelete} onSelect={onSelect} />);

    // Find and click the delete button by aria-label
    const deleteButton = screen.getByRole('button', { name: /delete tech watchlist/i });
    fireEvent.click(deleteButton);

    expect(onDelete).toHaveBeenCalledTimes(1);
    // Should not trigger select
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('should display relative time for recent updates', () => {
    const recentConfig = {
      ...mockConfig,
      updatedAt: new Date(Date.now() - 60000).toISOString(), // 1 minute ago
    };

    render(<ConfigCard config={recentConfig} />);

    expect(screen.getByText(/1m ago/)).toBeInTheDocument();
  });
});

describe('ConfigCardCompact', () => {
  it('should render config name', () => {
    render(<ConfigCardCompact config={mockConfig} />);

    expect(screen.getByText('Tech Watchlist')).toBeInTheDocument();
  });

  it('should render ticker symbols as comma-separated list', () => {
    render(<ConfigCardCompact config={mockConfig} />);

    expect(screen.getByText('AAPL, GOOGL, MSFT')).toBeInTheDocument();
  });

  it('should show active indicator', () => {
    const { container } = render(<ConfigCardCompact config={mockConfig} isActive />);

    expect(container.querySelector('.bg-accent')).toBeInTheDocument();
  });

  it('should call onSelect when clicked', () => {
    const onSelect = vi.fn();

    render(<ConfigCardCompact config={mockConfig} onSelect={onSelect} />);

    fireEvent.click(screen.getByRole('button'));

    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});
