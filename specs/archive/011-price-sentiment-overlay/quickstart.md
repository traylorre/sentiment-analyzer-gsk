# Quickstart Guide: Price-Sentiment Overlay Chart

**Feature**: 011-price-sentiment-overlay
**Date**: 2025-12-01

## Overview

This guide provides implementation patterns for adding the price-sentiment overlay chart feature. The feature consists of:

1. **Backend**: New OHLC endpoint + sentiment history extension
2. **Frontend**: Dual-axis chart component with controls

---

## Backend Implementation

### 1. OHLC Endpoint (`src/lambdas/dashboard/ohlc.py`)

```python
"""OHLC price data endpoint."""

from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.lambdas.shared.adapters.base import OHLCCandle
from src.lambdas.shared.adapters.tiingo import TiingoAdapter
from src.lambdas.shared.adapters.finnhub import FinnhubAdapter
from src.lambdas.shared.logging_utils import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v2/tickers", tags=["Price Data"])

ET = ZoneInfo("America/New_York")

TimeRange = Literal["1W", "1M", "3M", "6M", "1Y"]

TIME_RANGE_DAYS = {
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
}


class OHLCResponse(BaseModel):
    ticker: str
    candles: list[OHLCCandle]
    time_range: str
    start_date: date
    end_date: date
    count: int
    source: str
    cache_expires_at: datetime


def get_cache_expiration() -> datetime:
    """Calculate cache expiration based on market hours."""
    now = datetime.now(ET)
    # ... implementation from research.md
    return now + timedelta(hours=24)  # Simplified for quickstart


@router.get("/{ticker}/ohlc", response_model=OHLCResponse)
async def get_ohlc_data(
    ticker: str,
    range: TimeRange = Query("1M", description="Time range"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    tiingo: TiingoAdapter = Depends(),
    finnhub: FinnhubAdapter = Depends(),
) -> OHLCResponse:
    """Get OHLC candlestick data for a ticker."""
    ticker = ticker.upper()

    # Calculate date range
    if start_date and end_date:
        range_str = "custom"
    else:
        end_date = date.today()
        start_date = end_date - timedelta(days=TIME_RANGE_DAYS[range])
        range_str = range

    # Fetch from Tiingo (primary) with Finnhub fallback
    source = "tiingo"
    candles = await tiingo.get_ohlc(ticker, start_date, end_date)

    if not candles:
        logger.warning("Tiingo OHLC unavailable, trying Finnhub", extra={"ticker": ticker})
        source = "finnhub"
        candles = await finnhub.get_ohlc(ticker, start_date, end_date)

    if not candles:
        raise HTTPException(status_code=404, detail=f"No price data for {ticker}")

    return OHLCResponse(
        ticker=ticker,
        candles=candles,
        time_range=range_str,
        start_date=candles[0].date.date(),
        end_date=candles[-1].date.date(),
        count=len(candles),
        source=source,
        cache_expires_at=get_cache_expiration(),
    )
```

### 2. Register Router in Handler

Add to `src/lambdas/dashboard/handler.py`:

```python
from src.lambdas.dashboard.ohlc import router as ohlc_router

app.include_router(ohlc_router)
```

---

## Frontend Implementation

### 1. API Client (`frontend/src/services/ohlc-api.ts`)

```typescript
import { TimeRange, SentimentSource } from '@/types/chart';

export interface PriceCandle {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface OHLCResponse {
  ticker: string;
  candles: PriceCandle[];
  time_range: string;
  start_date: string;
  end_date: string;
  count: number;
  source: string;
  cache_expires_at: string;
}

export interface SentimentPoint {
  date: string;
  score: number;
  source: string;
  confidence?: number;
}

export interface SentimentHistoryResponse {
  ticker: string;
  source: string;
  history: SentimentPoint[];
  count: number;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function fetchOHLCData(
  ticker: string,
  range: TimeRange = '1M',
  userId: string
): Promise<OHLCResponse> {
  const response = await fetch(
    `${BASE_URL}/api/v2/tickers/${ticker}/ohlc?range=${range}`,
    {
      headers: { 'X-User-ID': userId },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch OHLC data: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchSentimentHistory(
  ticker: string,
  source: SentimentSource = 'aggregated',
  range: TimeRange = '1M',
  userId: string
): Promise<SentimentHistoryResponse> {
  const response = await fetch(
    `${BASE_URL}/api/v2/tickers/${ticker}/sentiment/history?source=${source}&range=${range}`,
    {
      headers: { 'X-User-ID': userId },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch sentiment history: ${response.statusText}`);
  }

  return response.json();
}
```

### 2. React Query Hook (`frontend/src/hooks/use-chart-data.ts`)

```typescript
import { useQuery } from '@tanstack/react-query';
import { fetchOHLCData, fetchSentimentHistory } from '@/services/ohlc-api';
import { useAuthStore } from '@/stores/auth-store';

export function useChartData(
  ticker: string,
  timeRange: TimeRange,
  sentimentSource: SentimentSource
) {
  const { userId } = useAuthStore();

  const ohlcQuery = useQuery({
    queryKey: ['ohlc', ticker, timeRange],
    queryFn: () => fetchOHLCData(ticker, timeRange, userId!),
    enabled: !!userId && !!ticker,
    staleTime: 1000 * 60 * 60, // 1 hour
  });

  const sentimentQuery = useQuery({
    queryKey: ['sentiment-history', ticker, sentimentSource, timeRange],
    queryFn: () => fetchSentimentHistory(ticker, sentimentSource, timeRange, userId!),
    enabled: !!userId && !!ticker,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  return {
    ohlcData: ohlcQuery.data,
    sentimentData: sentimentQuery.data,
    isLoading: ohlcQuery.isLoading || sentimentQuery.isLoading,
    error: ohlcQuery.error || sentimentQuery.error,
  };
}
```

### 3. Chart Component (`frontend/src/components/charts/price-sentiment-chart.tsx`)

```typescript
'use client';

import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  LineData,
  Time,
} from 'lightweight-charts';
import { useChartData } from '@/hooks/use-chart-data';

interface PriceSentimentChartProps {
  ticker: string;
  className?: string;
}

const TIME_RANGES = ['1W', '1M', '3M', '6M', '1Y'] as const;
const SENTIMENT_SOURCES = ['tiingo', 'finnhub', 'our_model', 'aggregated'] as const;

export function PriceSentimentChart({ ticker, className }: PriceSentimentChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const sentimentSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const [timeRange, setTimeRange] = useState<TimeRange>('1M');
  const [sentimentSource, setSentimentSource] = useState<SentimentSource>('aggregated');
  const [showCandles, setShowCandles] = useState(true);
  const [showSentiment, setShowSentiment] = useState(true);

  const { ohlcData, sentimentData, isLoading, error } = useChartData(
    ticker,
    timeRange,
    sentimentSource
  );

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#0a0a0a' },
        textColor: '#a0a0a0',
      },
      grid: {
        vertLines: { color: '#2a2a2a' },
        horzLines: { color: '#2a2a2a' },
      },
      rightPriceScale: {
        borderColor: '#2a2a2a',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: '#2a2a2a',
        timeVisible: true,
      },
      crosshair: {
        mode: 1, // Normal mode
      },
    });

    // Candlestick series on left axis
    const candleSeries = chart.addCandlestickSeries({
      priceScaleId: 'left',
      upColor: '#00d395',
      downColor: '#ff6b6b',
      borderUpColor: '#00d395',
      borderDownColor: '#ff6b6b',
      wickUpColor: '#00d395',
      wickDownColor: '#ff6b6b',
    });

    // Sentiment line on right axis
    const sentimentSeries = chart.addLineSeries({
      priceScaleId: 'right',
      color: '#00FFFF',
      lineWidth: 2,
      crosshairMarkerRadius: 4,
    });

    // Configure right scale for sentiment (-1 to 1)
    chart.priceScale('right').applyOptions({
      autoScale: false,
      scaleMargins: { top: 0.1, bottom: 0.1 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    sentimentSeriesRef.current = sentimentSeries;

    // Handle resize
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Update candlestick data
  useEffect(() => {
    if (!candleSeriesRef.current || !ohlcData) return;

    const candleData: CandlestickData<Time>[] = ohlcData.candles.map((c) => ({
      time: c.date as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    candleSeriesRef.current.setData(candleData);
    candleSeriesRef.current.applyOptions({ visible: showCandles });
  }, [ohlcData, showCandles]);

  // Update sentiment data
  useEffect(() => {
    if (!sentimentSeriesRef.current || !sentimentData) return;

    const lineData: LineData<Time>[] = sentimentData.history.map((s) => ({
      time: s.date as Time,
      value: s.score,
    }));

    sentimentSeriesRef.current.setData(lineData);
    sentimentSeriesRef.current.applyOptions({ visible: showSentiment });
  }, [sentimentData, showSentiment]);

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 bg-bg-card rounded-lg">
        <p className="text-accent-red">Failed to load chart data</p>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Controls */}
      <div className="flex gap-4 mb-4">
        {/* Time Range Selector */}
        <div className="flex gap-1 bg-bg-secondary rounded-lg p-1">
          {TIME_RANGES.map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 rounded text-sm ${
                timeRange === range
                  ? 'bg-accent-green text-bg-primary'
                  : 'text-text-secondary hover:bg-bg-hover'
              }`}
            >
              {range}
            </button>
          ))}
        </div>

        {/* Sentiment Source Dropdown */}
        <select
          value={sentimentSource}
          onChange={(e) => setSentimentSource(e.target.value as SentimentSource)}
          className="bg-bg-secondary text-text-primary rounded-lg px-3 py-1"
        >
          {SENTIMENT_SOURCES.map((source) => (
            <option key={source} value={source}>
              {source.charAt(0).toUpperCase() + source.slice(1)}
            </option>
          ))}
        </select>

        {/* Layer Toggles */}
        <div className="flex gap-2">
          <button
            onClick={() => setShowCandles(!showCandles)}
            className={`px-3 py-1 rounded text-sm ${
              showCandles ? 'bg-accent-green text-bg-primary' : 'bg-bg-secondary text-text-muted'
            }`}
          >
            Price
          </button>
          <button
            onClick={() => setShowSentiment(!showSentiment)}
            className={`px-3 py-1 rounded text-sm ${
              showSentiment ? 'bg-accent-blue text-bg-primary' : 'bg-bg-secondary text-text-muted'
            }`}
          >
            Sentiment
          </button>
        </div>
      </div>

      {/* Chart Container */}
      <div
        ref={containerRef}
        className="w-full h-[400px] rounded-lg overflow-hidden"
        style={{ position: 'relative' }}
      >
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg-card/80 z-10">
            <div className="animate-pulse text-text-secondary">Loading...</div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-2 text-sm text-text-secondary">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-accent-green rounded" />
          <span>Price (Left Axis)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-accent-blue rounded" />
          <span>Sentiment (Right Axis: -1 to +1)</span>
        </div>
      </div>
    </div>
  );
}
```

---

## Testing

### Backend Unit Test Pattern

```python
# tests/unit/dashboard/test_ohlc.py

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

from src.lambdas.dashboard.ohlc import get_ohlc_data, OHLCResponse
from src.lambdas.shared.adapters.base import OHLCCandle


@pytest.fixture
def mock_candles():
    return [
        OHLCCandle(
            date=datetime(2024, 11, 29),
            open=237.45,
            high=239.12,
            low=236.80,
            close=238.67,
            volume=45678900,
        ),
    ]


@pytest.mark.asyncio
async def test_get_ohlc_data_success(mock_candles):
    """Test successful OHLC data retrieval."""
    tiingo = AsyncMock()
    tiingo.get_ohlc.return_value = mock_candles

    finnhub = AsyncMock()

    response = await get_ohlc_data(
        ticker="AAPL",
        range="1M",
        tiingo=tiingo,
        finnhub=finnhub,
    )

    assert response.ticker == "AAPL"
    assert response.count == 1
    assert response.source == "tiingo"
    tiingo.get_ohlc.assert_called_once()
    finnhub.get_ohlc.assert_not_called()


@pytest.mark.asyncio
async def test_get_ohlc_data_fallback_to_finnhub(mock_candles):
    """Test fallback to Finnhub when Tiingo fails."""
    tiingo = AsyncMock()
    tiingo.get_ohlc.return_value = []  # Tiingo returns nothing

    finnhub = AsyncMock()
    finnhub.get_ohlc.return_value = mock_candles

    response = await get_ohlc_data(
        ticker="AAPL",
        range="1M",
        tiingo=tiingo,
        finnhub=finnhub,
    )

    assert response.source == "finnhub"
    tiingo.get_ohlc.assert_called_once()
    finnhub.get_ohlc.assert_called_once()
```

### Frontend Component Test Pattern

```typescript
// frontend/tests/unit/charts/price-sentiment-chart.test.tsx

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi } from 'vitest';

import { PriceSentimentChart } from '@/components/charts/price-sentiment-chart';
import * as ohlcApi from '@/services/ohlc-api';

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addCandlestickSeries: vi.fn(() => ({ setData: vi.fn(), applyOptions: vi.fn() })),
    addLineSeries: vi.fn(() => ({ setData: vi.fn(), applyOptions: vi.fn() })),
    priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    applyOptions: vi.fn(),
    remove: vi.fn(),
  })),
}));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

describe('PriceSentimentChart', () => {
  beforeEach(() => {
    vi.spyOn(ohlcApi, 'fetchOHLCData').mockResolvedValue({
      ticker: 'AAPL',
      candles: [{ date: '2024-11-29', open: 237, high: 239, low: 236, close: 238 }],
      time_range: '1M',
      start_date: '2024-11-01',
      end_date: '2024-11-29',
      count: 1,
      source: 'tiingo',
      cache_expires_at: '2024-12-02T14:30:00Z',
    });

    vi.spyOn(ohlcApi, 'fetchSentimentHistory').mockResolvedValue({
      ticker: 'AAPL',
      source: 'aggregated',
      history: [{ date: '2024-11-29', score: 0.65, source: 'aggregated' }],
      count: 1,
    });
  });

  it('renders time range buttons', async () => {
    render(<PriceSentimentChart ticker="AAPL" />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText('1W')).toBeInTheDocument();
      expect(screen.getByText('1M')).toBeInTheDocument();
      expect(screen.getByText('1Y')).toBeInTheDocument();
    });
  });

  it('toggles sentiment visibility', async () => {
    const user = userEvent.setup();
    render(<PriceSentimentChart ticker="AAPL" />, { wrapper });

    const sentimentButton = await screen.findByText('Sentiment');
    await user.click(sentimentButton);

    // Verify toggle state changed (button style would change)
    expect(sentimentButton).toHaveClass('bg-bg-secondary');
  });
});
```

---

## Next Steps

After implementing the above:

1. Run `/speckit.tasks` to generate detailed task breakdown
2. Create feature branch commits following constitution workflow
3. Run tests locally before pushing
4. Monitor CI pipeline after push
