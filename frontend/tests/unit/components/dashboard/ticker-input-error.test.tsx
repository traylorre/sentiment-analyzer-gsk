import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TickerInput } from '@/components/dashboard/ticker-input';

// Mock the tickers API
vi.mock('@/lib/api/tickers', () => ({
  tickersApi: {
    search: vi.fn(),
  },
}));

// Mock the API client error utilities
const mockEmitErrorEvent = vi.fn();
vi.mock('@/lib/api/client', () => ({
  emitErrorEvent: (...args: unknown[]) => mockEmitErrorEvent(...args),
  ApiClientError: class ApiClientError extends Error {
    status: number;
    code: string;
    details?: Record<string, unknown>;
    constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
      super(message);
      this.name = 'ApiClientError';
      this.status = status;
      this.code = code;
      this.details = details;
    }
  },
}));

// Mock haptic hook
vi.mock('@/hooks/use-haptic', () => ({
  useHaptic: () => ({
    light: vi.fn(),
    medium: vi.fn(),
    heavy: vi.fn(),
    selection: vi.fn(),
    trigger: vi.fn(),
    isEnabled: false,
  }),
}));

import { tickersApi } from '@/lib/api/tickers';
import { ApiClientError } from '@/lib/api/client';

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

describe('TickerInput error states', () => {
  const mockOnSelect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tickersApi.search).mockResolvedValue([]);
  });

  it('should render "Unable to search" when useQuery returns a generic error', async () => {
    vi.mocked(tickersApi.search).mockRejectedValue(new Error('Network failure'));

    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'A');

    await waitFor(() => {
      expect(screen.getByText(/unable to search/i)).toBeInTheDocument();
    });
  });

  it('should render "Too many requests" when useQuery returns a 429 ApiClientError', async () => {
    vi.mocked(tickersApi.search).mockRejectedValue(
      new ApiClientError(429, 'CLIENT_ERROR', 'Rate limited')
    );

    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'A');

    await waitFor(() => {
      expect(screen.getByText(/too many requests/i)).toBeInTheDocument();
    });
  });

  it('should render "No tickers found" when useQuery returns empty results', async () => {
    vi.mocked(tickersApi.search).mockResolvedValue([]);

    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'XYZ');

    await waitFor(() => {
      expect(screen.getByText(/no tickers found/i)).toBeInTheDocument();
    });
  });

  it('should render ticker symbols when useQuery returns results', async () => {
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

  it('should call emitErrorEvent when error state renders', async () => {
    vi.mocked(tickersApi.search).mockRejectedValue(new Error('Server error'));

    const user = userEvent.setup();
    renderWithProvider(<TickerInput onSelect={mockOnSelect} />);

    const input = screen.getByRole('combobox');
    await user.type(input, 'A');

    await waitFor(() => {
      expect(screen.getByText(/unable to search/i)).toBeInTheDocument();
    });

    expect(mockEmitErrorEvent).toHaveBeenCalledWith(
      'search_error_displayed',
      expect.objectContaining({ endpoint: 'tickers/search' })
    );
  });
});
