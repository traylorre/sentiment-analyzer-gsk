import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TickerInput } from '@/components/dashboard/ticker-input';

// Mock the tickers API
vi.mock('@/lib/api/tickers', () => ({
  tickersApi: {
    search: vi.fn(),
  },
}));

import { tickersApi } from '@/lib/api/tickers';

function renderWithProvider(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe('TickerInput', () => {
  const mockOnSelect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tickersApi.search).mockResolvedValue([]);
  });

  it('should render with placeholder', () => {
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    expect(
      screen.getByPlaceholderText(/search tickers/i)
    ).toBeInTheDocument();
  });

  it('should render custom placeholder', () => {
    renderWithProvider(
      <TickerInput onSelect={mockOnSelect} placeholder="Custom placeholder" />
    );

    expect(screen.getByPlaceholderText('Custom placeholder')).toBeInTheDocument();
  });

  it('should convert input to uppercase', async () => {
    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'aapl');

    expect(input).toHaveValue('AAPL');
  });

  it('should show dropdown when typing', async () => {
    vi.mocked(tickersApi.search).mockResolvedValue([
      { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
    ]);

    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'A');

    await waitFor(() => {
      expect(tickersApi.search).toHaveBeenCalledWith('A', 5);
    });
  });

  it('should display search results', async () => {
    vi.mocked(tickersApi.search).mockResolvedValue([
      { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
      { symbol: 'AMZN', name: 'Amazon.com Inc.', exchange: 'NASDAQ' },
    ]);

    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'A');

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      expect(screen.getByText('AMZN')).toBeInTheDocument();
    });
  });

  it('should call onSelect when result is clicked', async () => {
    vi.mocked(tickersApi.search).mockResolvedValue([
      { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
    ]);

    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'A');

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });

    await user.click(screen.getByText('AAPL'));

    expect(mockOnSelect).toHaveBeenCalledWith({
      symbol: 'AAPL',
      name: 'Apple Inc.',
      exchange: 'NASDAQ',
    });
  });

  it('should clear input after selection', async () => {
    vi.mocked(tickersApi.search).mockResolvedValue([
      { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' },
    ]);

    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'A');

    await waitFor(() => {
      expect(screen.getByText('AAPL')).toBeInTheDocument();
    });

    await user.click(screen.getByText('AAPL'));

    expect(input).toHaveValue('');
  });

  it('should show no results message when empty', async () => {
    vi.mocked(tickersApi.search).mockResolvedValue([]);

    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'XYZ');

    await waitFor(() => {
      expect(screen.getByText(/no tickers found/i)).toBeInTheDocument();
    });
  });

  it('should be disabled when disabled prop is true', () => {
    renderWithProvider(<TickerInput onSelect={mockOnSelect} disabled />);

    expect(screen.getByRole('combobox')).toBeDisabled();
  });

  it('should clear input when X button is clicked', async () => {
    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'AAPL');

    expect(input).toHaveValue('AAPL');

    // Find and click the clear button
    const clearButton = screen.getByRole('button');
    await user.click(clearButton);

    expect(input).toHaveValue('');
  });
});
