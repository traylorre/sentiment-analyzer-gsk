'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type CandlestickData,
  type LineData,
  ColorType,
  LineStyle,
  CrosshairMode,
  CandlestickSeries,
  LineSeries,
} from 'lightweight-charts';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { formatSentimentScore, formatDateTime } from '@/lib/utils';
import { useChartData } from '@/hooks/use-chart-data';
import { useHaptic } from '@/hooks/use-haptic';
import type { TimeRange, OHLCResolution, ChartSentimentSource, PriceCandle, SentimentPoint } from '@/types/chart';
import { RESOLUTION_LABELS } from '@/types/chart';

interface PriceSentimentChartProps {
  ticker: string;
  className?: string;
  height?: number;
  interactive?: boolean;
  initialTimeRange?: TimeRange;
  initialResolution?: OHLCResolution;
  initialSentimentSource?: ChartSentimentSource;
}

interface TooltipData {
  date: string;
  price?: {
    open: number;
    high: number;
    low: number;
    close: number;
  };
  sentiment?: {
    score: number;
    label: string;
  };
}

/**
 * Dual-axis chart combining OHLC candlesticks (left axis) with sentiment line (right axis).
 *
 * Features:
 * - Price candles on left Y-axis with green/red coloring
 * - Sentiment line on right Y-axis (-1 to +1 scale)
 * - Unified crosshair showing both values
 * - Time range selector (1W, 1M, 3M, 6M, 1Y)
 * - Sentiment source dropdown
 * - Layer toggles for price/sentiment visibility
 */
export function PriceSentimentChart({
  ticker,
  className,
  height = 400,
  interactive = true,
  initialTimeRange = '1M',
  initialResolution = 'D',
  initialSentimentSource = 'aggregated',
}: PriceSentimentChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const sentimentSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const [isReady, setIsReady] = useState(false);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>(initialTimeRange);
  // T024: Read initial resolution from sessionStorage
  const [resolution, setResolution] = useState<OHLCResolution>(() => {
    if (typeof window !== 'undefined') {
      const stored = sessionStorage.getItem('ohlc_preferred_resolution');
      if (stored && ['1', '5', '15', '30', '60', 'D'].includes(stored)) {
        return stored as OHLCResolution;
      }
    }
    return initialResolution;
  });
  const [sentimentSource, setSentimentSource] = useState<ChartSentimentSource>(initialSentimentSource);
  const [showCandles, setShowCandles] = useState(true);
  const [showSentiment, setShowSentiment] = useState(true);

  const haptic = useHaptic();

  // T025: Persist resolution to sessionStorage when it changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('ohlc_preferred_resolution', resolution);
    }
  }, [resolution]);

  // Fetch chart data with resolution support (T020)
  const {
    priceData,
    sentimentData,
    isLoading,
    error,
    refetch,
    resolutionFallback,
    fallbackMessage,
  } = useChartData({
    ticker,
    timeRange,
    resolution,
    sentimentSource,
  });

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#a3a3a3',
      },
      grid: {
        vertLines: { color: 'rgba(0, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(0, 255, 255, 0.05)' },
      },
      crosshair: {
        mode: interactive ? CrosshairMode.Normal : CrosshairMode.Hidden,
        vertLine: {
          color: '#00FFFF',
          style: LineStyle.Solid,
          width: 1,
          labelBackgroundColor: '#00FFFF',
        },
        horzLine: {
          color: '#00FFFF',
          style: LineStyle.Dashed,
          width: 1,
          labelBackgroundColor: '#00FFFF',
        },
      },
      width: containerRef.current.clientWidth,
      height,
      handleScale: interactive,
      handleScroll: interactive,
      // Left price scale for candlesticks (price)
      leftPriceScale: {
        visible: true,
        borderColor: 'rgba(0, 255, 255, 0.1)',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      // Right price scale for sentiment (-1 to +1)
      rightPriceScale: {
        visible: true,
        borderColor: 'rgba(0, 255, 255, 0.1)',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: 'rgba(0, 255, 255, 0.1)',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Candlestick series on left axis (price)
    const candleSeries = chart.addSeries(CandlestickSeries, {
      priceScaleId: 'left',
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    // Line series on right axis (sentiment)
    const sentimentSeries = chart.addSeries(LineSeries, {
      priceScaleId: 'right',
      color: '#00FFFF',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
      crosshairMarkerBackgroundColor: '#00FFFF',
      crosshairMarkerBorderColor: '#0a0a0a',
      crosshairMarkerBorderWidth: 2,
    });

    // Configure right scale for sentiment range (-1 to +1)
    chart.priceScale('right').applyOptions({
      autoScale: false,
      scaleMargins: { top: 0.1, bottom: 0.1 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    sentimentSeriesRef.current = sentimentSeries;

    // Handle crosshair movement for tooltip
    if (interactive) {
      chart.subscribeCrosshairMove((param) => {
        if (!param.point || !param.time) {
          setTooltip(null);
          return;
        }

        const candleData = param.seriesData.get(candleSeries);
        const sentimentValue = param.seriesData.get(sentimentSeries);

        const tooltipData: TooltipData = {
          date: formatDateTime(new Date((param.time as number) * 1000).toISOString()),
        };

        if (candleData && typeof candleData === 'object' && 'open' in candleData) {
          const candle = candleData as CandlestickData<Time>;
          tooltipData.price = {
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
          };
        }

        if (sentimentValue && typeof sentimentValue === 'object' && 'value' in sentimentValue) {
          const score = (sentimentValue as LineData<Time>).value;
          tooltipData.sentiment = {
            score,
            label: score >= 0.33 ? 'Positive' : score <= -0.33 ? 'Negative' : 'Neutral',
          };
        }

        setTooltip(tooltipData);
      });
    }

    // Handle resize
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    setIsReady(true);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      sentimentSeriesRef.current = null;
    };
  }, [height, interactive]);

  // Update candlestick data
  useEffect(() => {
    if (!candleSeriesRef.current || !priceData.length) return;

    const chartData: CandlestickData<Time>[] = priceData.map((candle: PriceCandle) => ({
      time: candle.date as Time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }));

    candleSeriesRef.current.setData(chartData);
  }, [priceData]);

  // Update sentiment data
  useEffect(() => {
    if (!sentimentSeriesRef.current || !sentimentData.length) return;

    const chartData: LineData<Time>[] = sentimentData.map((point: SentimentPoint) => ({
      time: point.date as Time,
      value: point.score,
    }));

    sentimentSeriesRef.current.setData(chartData);
  }, [sentimentData]);

  // Fit content when data changes
  useEffect(() => {
    if (chartRef.current && (priceData.length || sentimentData.length)) {
      chartRef.current.timeScale().fitContent();
    }
  }, [priceData, sentimentData]);

  // Update series visibility
  useEffect(() => {
    if (candleSeriesRef.current) {
      candleSeriesRef.current.applyOptions({ visible: showCandles });
    }
  }, [showCandles]);

  useEffect(() => {
    if (sentimentSeriesRef.current) {
      sentimentSeriesRef.current.applyOptions({ visible: showSentiment });
    }
  }, [showSentiment]);

  // Handle time range change
  const handleTimeRangeChange = useCallback(
    (newRange: TimeRange) => {
      setTimeRange(newRange);
      haptic.light();
    },
    [haptic]
  );

  // Handle resolution change (T019)
  const handleResolutionChange = useCallback(
    (newResolution: OHLCResolution) => {
      setResolution(newResolution);
      haptic.light();
    },
    [haptic]
  );

  // Handle sentiment source change
  const handleSourceChange = useCallback(
    (newSource: ChartSentimentSource) => {
      setSentimentSource(newSource);
      haptic.light();
    },
    [haptic]
  );

  // Get current price and sentiment
  const currentPrice = priceData.length > 0 ? priceData[priceData.length - 1].close : null;
  const currentSentiment = sentimentData.length > 0 ? sentimentData[sentimentData.length - 1].score : null;

  const timeRanges: TimeRange[] = ['1W', '1M', '3M', '6M', '1Y'];
  const resolutions: OHLCResolution[] = ['1', '5', '15', '30', '60', 'D'];
  const sentimentSources: { value: ChartSentimentSource; label: string }[] = [
    { value: 'aggregated', label: 'Aggregated' },
    { value: 'tiingo', label: 'Tiingo' },
    { value: 'finnhub', label: 'Finnhub' },
    { value: 'our_model', label: 'Our Model' },
  ];

  return (
    <motion.div
      className={cn('relative', className)}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header with ticker and current values */}
      <div className="flex items-baseline justify-between mb-4">
        <div className="flex items-baseline gap-3">
          <span className="text-2xl font-bold text-foreground">{ticker}</span>
          {currentPrice !== null && (
            <span className="text-xl font-semibold text-foreground">
              ${currentPrice.toFixed(2)}
            </span>
          )}
          {currentSentiment !== null && (
            <span
              className="text-lg font-medium"
              style={{
                color:
                  currentSentiment >= 0.33
                    ? '#22c55e'
                    : currentSentiment <= -0.33
                    ? '#ef4444'
                    : '#eab308',
              }}
            >
              {formatSentimentScore(currentSentiment)}
            </span>
          )}
        </div>
      </div>

      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-4 mb-4">
        {/* Time range selector */}
        <div className="flex gap-1 bg-card/50 rounded-lg p-1">
          {timeRanges.map((range) => (
            <button
              key={range}
              onClick={() => handleTimeRangeChange(range)}
              className={cn(
                'px-3 py-1 text-sm font-medium rounded-md transition-colors',
                timeRange === range
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-card'
              )}
              aria-pressed={timeRange === range}
              aria-label={`${range} time range`}
            >
              {range}
            </button>
          ))}
        </div>

        {/* Resolution selector (T019) */}
        <div className="flex gap-1 bg-card/50 rounded-lg p-1">
          {resolutions.map((res) => (
            <button
              key={res}
              onClick={() => handleResolutionChange(res)}
              className={cn(
                'px-2 py-1 text-sm font-medium rounded-md transition-colors',
                resolution === res
                  ? 'bg-purple-500/20 border border-purple-500 text-purple-400'
                  : 'text-muted-foreground hover:text-foreground hover:bg-card'
              )}
              aria-pressed={resolution === res}
              aria-label={`${RESOLUTION_LABELS[res]} resolution`}
            >
              {RESOLUTION_LABELS[res]}
            </button>
          ))}
        </div>

        {/* Sentiment source dropdown */}
        <select
          value={sentimentSource}
          onChange={(e) => handleSourceChange(e.target.value as ChartSentimentSource)}
          className="bg-card/50 border border-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          aria-label="Sentiment source"
        >
          {sentimentSources.map((source) => (
            <option key={source.value} value={source.value}>
              {source.label}
            </option>
          ))}
        </select>

        {/* Layer toggles */}
        <div className="flex gap-2">
          <button
            onClick={() => setShowCandles(!showCandles)}
            className={cn(
              'px-3 py-1 text-sm font-medium rounded-md transition-colors border',
              showCandles
                ? 'bg-green-500/20 border-green-500 text-green-500'
                : 'bg-card/50 border-border text-muted-foreground'
            )}
            aria-pressed={showCandles}
            aria-label="Toggle price candles"
          >
            Price
          </button>
          <button
            onClick={() => setShowSentiment(!showSentiment)}
            className={cn(
              'px-3 py-1 text-sm font-medium rounded-md transition-colors border',
              showSentiment
                ? 'bg-cyan-500/20 border-cyan-500 text-cyan-500'
                : 'bg-card/50 border-border text-muted-foreground'
            )}
            aria-pressed={showSentiment}
            aria-label="Toggle sentiment line"
          >
            Sentiment
          </button>
        </div>
      </div>

      {/* Resolution fallback message (T021) */}
      {resolutionFallback && fallbackMessage && (
        <div className="mb-4 px-3 py-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-sm text-yellow-500">
          {fallbackMessage}
        </div>
      )}

      {/* Tooltip */}
      <AnimatePresence>
        {tooltip && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="absolute top-24 left-4 z-10 bg-card/95 backdrop-blur-sm border border-border rounded-lg p-3 shadow-lg"
          >
            <div className="text-xs text-muted-foreground mb-2">{tooltip.date}</div>
            {tooltip.price && (
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm mb-2">
                <span className="text-muted-foreground">Open:</span>
                <span className="text-foreground">${tooltip.price.open.toFixed(2)}</span>
                <span className="text-muted-foreground">High:</span>
                <span className="text-green-500">${tooltip.price.high.toFixed(2)}</span>
                <span className="text-muted-foreground">Low:</span>
                <span className="text-red-500">${tooltip.price.low.toFixed(2)}</span>
                <span className="text-muted-foreground">Close:</span>
                <span className="text-foreground">${tooltip.price.close.toFixed(2)}</span>
              </div>
            )}
            {tooltip.sentiment && (
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground text-sm">Sentiment:</span>
                <span
                  className="font-medium"
                  style={{
                    color:
                      tooltip.sentiment.score >= 0.33
                        ? '#22c55e'
                        : tooltip.sentiment.score <= -0.33
                        ? '#ef4444'
                        : '#eab308',
                  }}
                >
                  {formatSentimentScore(tooltip.sentiment.score)} ({tooltip.sentiment.label})
                </span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Chart container */}
      <div
        ref={containerRef}
        className="w-full rounded-lg overflow-hidden focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        style={{ height }}
        role="img"
        aria-label={`Price and sentiment chart for ${ticker}. ${priceData.length} price candles and ${sentimentData.length} sentiment points.`}
        tabIndex={interactive ? 0 : -1}
      />

      {/* Legend */}
      <div className="flex items-center justify-end gap-6 mt-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 rounded-sm" />
          <span>Price Up</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-red-500 rounded-sm" />
          <span>Price Down</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-0.5 bg-cyan-500" />
          <span>Sentiment</span>
        </div>
      </div>

      {/* Loading overlay */}
      {(isLoading || !isReady) && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/80 rounded-lg">
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-muted-foreground">Loading chart data...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && !isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/80 rounded-lg">
          <div className="flex flex-col items-center gap-3 text-center px-4">
            <span className="text-red-500 text-sm">{error}</span>
            <button
              onClick={() => refetch()}
              className="px-4 py-2 bg-accent text-accent-foreground rounded-lg text-sm font-medium hover:bg-accent/90 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      )}
    </motion.div>
  );
}
