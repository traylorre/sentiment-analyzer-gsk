import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PriceSentimentChart } from '@/components/charts/price-sentiment-chart';

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addSeries: vi.fn(() => ({
      setData: vi.fn(),
      applyOptions: vi.fn(),
      attachPrimitive: vi.fn(),
      detachPrimitive: vi.fn(),
    })),
    applyOptions: vi.fn(),
    priceScale: vi.fn(() => ({
      applyOptions: vi.fn(),
    })),
    timeScale: vi.fn(() => ({
      fitContent: vi.fn(),
      setVisibleLogicalRange: vi.fn(),
    })),
    subscribeCrosshairMove: vi.fn(),
    remove: vi.fn(),
  })),
  ColorType: { Solid: 'Solid' },
  LineStyle: { Solid: 'Solid', Dashed: 'Dashed' },
  CrosshairMode: { Normal: 'Normal', Hidden: 'Hidden' },
  CandlestickSeries: 'CandlestickSeries',
  LineSeries: 'LineSeries',
}));

// Default mock data for useChartData
const defaultChartData = {
  priceData: [
    { date: 1704067200, open: 150, high: 155, low: 148, close: 153 },
    { date: 1704153600, open: 153, high: 158, low: 151, close: 156 },
  ],
  sentimentData: [
    { date: 1704067200, score: 0.5 },
    { date: 1704153600, score: 0.6 },
  ],
  isLoading: false,
  error: null,
  refetch: vi.fn(),
  resolutionFallback: false,
  fallbackMessage: null as string | null,
};

// Track calls to useChartData
let useChartDataCalls: any[] = [];
let mockChartDataOverride: typeof defaultChartData | null = null;

vi.mock('@/hooks/use-chart-data', () => ({
  useChartData: (params: any) => {
    useChartDataCalls.push(params);
    return mockChartDataOverride || defaultChartData;
  },
}));

// Mock useHaptic hook
vi.mock('@/hooks/use-haptic', () => ({
  useHaptic: () => ({
    light: vi.fn(),
    medium: vi.fn(),
    heavy: vi.fn(),
  }),
}));

// Mock sessionStorage
let sessionStorageData: Record<string, string> = {};
const mockSessionStorage = {
  getItem: vi.fn((key: string) => sessionStorageData[key] || null),
  setItem: vi.fn((key: string, value: string) => {
    sessionStorageData[key] = value;
  }),
  removeItem: vi.fn((key: string) => {
    delete sessionStorageData[key];
  }),
  clear: vi.fn(() => {
    sessionStorageData = {};
  }),
};

Object.defineProperty(window, 'sessionStorage', {
  value: mockSessionStorage,
});

describe('PriceSentimentChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorageData = {};
    useChartDataCalls = [];
    mockChartDataOverride = null;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('T022: Resolution selector rendering', () => {
    it('should render all resolution options', () => {
      render(<PriceSentimentChart ticker="AAPL" />);

      // Labels are: 1m, 5m, 15m, 30m, 1h, Day (from RESOLUTION_LABELS)
      // Use exact string matching to avoid regex overlaps
      expect(screen.getByRole('button', { name: '1m resolution' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '5m resolution' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '15m resolution' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '30m resolution' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '1h resolution' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Day resolution' })).toBeInTheDocument();
    });

    it('should highlight selected resolution', () => {
      render(<PriceSentimentChart ticker="AAPL" initialResolution="5" />);

      const fiveMinButton = screen.getByRole('button', { name: '5m resolution' });
      expect(fiveMinButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('should use default Daily resolution when not specified', () => {
      render(<PriceSentimentChart ticker="AAPL" />);

      const dailyButton = screen.getByRole('button', { name: 'Day resolution' });
      expect(dailyButton).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('T023: Resolution change triggers data refetch', () => {
    it('should call useChartData with new resolution when changed', async () => {
      render(<PriceSentimentChart ticker="AAPL" />);

      // Initial call with default 'D' resolution
      expect(useChartDataCalls[0]).toEqual(
        expect.objectContaining({ resolution: 'D' })
      );

      // Click 5-minute resolution
      const fiveMinButton = screen.getByRole('button', { name: '5m resolution' });
      fireEvent.click(fiveMinButton);

      // Should be called with new resolution
      await waitFor(() => {
        const lastCall = useChartDataCalls[useChartDataCalls.length - 1];
        expect(lastCall).toEqual(
          expect.objectContaining({ resolution: '5' })
        );
      });
    });

    it('should update selected state when resolution changes', async () => {
      render(<PriceSentimentChart ticker="AAPL" />);

      // Click 15-minute resolution
      const fifteenMinButton = screen.getByRole('button', { name: '15m resolution' });
      fireEvent.click(fifteenMinButton);

      await waitFor(() => {
        expect(fifteenMinButton).toHaveAttribute('aria-pressed', 'true');
      });

      // Daily should no longer be pressed
      const dailyButton = screen.getByRole('button', { name: 'Day resolution' });
      expect(dailyButton).toHaveAttribute('aria-pressed', 'false');
    });
  });

  describe('T027: Resolution preference persistence', () => {
    it('should save resolution to sessionStorage when changed', async () => {
      render(<PriceSentimentChart ticker="AAPL" />);

      // Click 5-minute resolution
      const fiveMinButton = screen.getByRole('button', { name: '5m resolution' });
      fireEvent.click(fiveMinButton);

      await waitFor(() => {
        expect(mockSessionStorage.setItem).toHaveBeenCalledWith(
          'ohlc_preferred_resolution',
          '5'
        );
      });
    });

    it('should save each resolution change to sessionStorage', async () => {
      render(<PriceSentimentChart ticker="AAPL" />);

      // Click through different resolutions
      fireEvent.click(screen.getByRole('button', { name: '1h resolution' }));

      await waitFor(() => {
        expect(mockSessionStorage.setItem).toHaveBeenCalledWith(
          'ohlc_preferred_resolution',
          '60'
        );
      });

      fireEvent.click(screen.getByRole('button', { name: '1m resolution' }));

      await waitFor(() => {
        expect(mockSessionStorage.setItem).toHaveBeenCalledWith(
          'ohlc_preferred_resolution',
          '1'
        );
      });
    });
  });

  describe('T028: Initial resolution from sessionStorage', () => {
    it('should use resolution from sessionStorage on mount', () => {
      sessionStorageData['ohlc_preferred_resolution'] = '15';

      render(<PriceSentimentChart ticker="AAPL" />);

      expect(useChartDataCalls[0]).toEqual(
        expect.objectContaining({ resolution: '15' })
      );
    });

    it('should highlight stored resolution on mount', () => {
      sessionStorageData['ohlc_preferred_resolution'] = '60';

      render(<PriceSentimentChart ticker="AAPL" />);

      const hourButton = screen.getByRole('button', { name: '1h resolution' });
      expect(hourButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('should fallback to initialResolution if sessionStorage is empty', () => {
      render(<PriceSentimentChart ticker="AAPL" initialResolution="30" />);

      expect(useChartDataCalls[0]).toEqual(
        expect.objectContaining({ resolution: '30' })
      );
    });

    it('should fallback to Daily if sessionStorage has invalid value', () => {
      sessionStorageData['ohlc_preferred_resolution'] = 'invalid';

      render(<PriceSentimentChart ticker="AAPL" />);

      expect(useChartDataCalls[0]).toEqual(
        expect.objectContaining({ resolution: 'D' })
      );
    });
  });

  describe('T031: Synchronized resolution between price and sentiment', () => {
    it('should pass same resolution to useChartData for both price and sentiment', () => {
      render(<PriceSentimentChart ticker="AAPL" initialResolution="5" />);

      // useChartData is called once with params containing resolution
      // Both priceData and sentimentData should use same resolution
      expect(useChartDataCalls[0]).toEqual(
        expect.objectContaining({
          ticker: 'AAPL',
          resolution: '5',
        })
      );
    });

    it('should update both price and sentiment when resolution changes', async () => {
      render(<PriceSentimentChart ticker="AAPL" />);

      // Change resolution
      fireEvent.click(screen.getByRole('button', { name: '15m resolution' }));

      await waitFor(() => {
        // New call should have updated resolution for both layers
        const lastCall = useChartDataCalls[useChartDataCalls.length - 1];
        expect(lastCall).toEqual(
          expect.objectContaining({
            ticker: 'AAPL',
            resolution: '15',
          })
        );
      });
    });

    it('should maintain synchronized resolution when toggling layers', async () => {
      render(<PriceSentimentChart ticker="AAPL" initialResolution="60" />);

      // Toggle price off
      const priceButton = screen.getByRole('button', { name: /Toggle price candles/i });
      fireEvent.click(priceButton);

      // Resolution should still be passed to useChartData
      const callAfterPriceToggle = useChartDataCalls[useChartDataCalls.length - 1];
      expect(callAfterPriceToggle).toEqual(
        expect.objectContaining({ resolution: '60' })
      );

      // Toggle sentiment off
      const sentimentButton = screen.getByRole('button', { name: /Toggle sentiment line/i });
      fireEvent.click(sentimentButton);

      // Resolution still synchronized
      const lastCall = useChartDataCalls[useChartDataCalls.length - 1];
      expect(lastCall).toEqual(
        expect.objectContaining({ resolution: '60' })
      );
    });
  });

  describe('Loading and error states', () => {
    it('should show loading indicator when isLoading is true', () => {
      mockChartDataOverride = {
        priceData: [],
        sentimentData: [],
        isLoading: true,
        error: null,
        refetch: vi.fn(),
        resolutionFallback: false,
        fallbackMessage: null,
      };

      render(<PriceSentimentChart ticker="AAPL" />);

      expect(screen.getByText(/Loading chart data/i)).toBeInTheDocument();
    });

    it('should show fallback message when resolution falls back', () => {
      mockChartDataOverride = {
        priceData: [{ date: 1704067200, open: 150, high: 155, low: 148, close: 153 }],
        sentimentData: [],
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        resolutionFallback: true,
        fallbackMessage: 'Intraday data unavailable, showing daily candles',
      };

      render(<PriceSentimentChart ticker="AAPL" />);

      expect(screen.getByText(/Intraday data unavailable/i)).toBeInTheDocument();
    });
  });
});
