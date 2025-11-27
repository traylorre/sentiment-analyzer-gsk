'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type AreaData,
  type Time,
  ColorType,
  LineStyle,
  CrosshairMode,
  AreaSeries,
} from 'lightweight-charts';
import { motion, AnimatePresence } from 'framer-motion';
import { cn, getSentimentColor, formatSentimentScore, formatDateTime } from '@/lib/utils';
import { useChartStore } from '@/stores/chart-store';
import { useHaptic } from '@/hooks/use-haptic';
import type { SentimentTimeSeries } from '@/types/sentiment';
import { ChartTooltip } from './chart-tooltip';
import { SentimentPill } from './sentiment-pill';

interface SentimentTimelineProps {
  data: SentimentTimeSeries[];
  ticker: string;
  source?: string;
  className?: string;
  height?: number;
  showTooltip?: boolean;
  showPill?: boolean;
  interactive?: boolean;
  onScrubChange?: (data: SentimentTimeSeries | null) => void;
}

export function SentimentTimeline({
  data,
  ticker,
  source,
  className,
  height = 300,
  showTooltip = true,
  showPill = true,
  interactive = true,
  onScrubChange,
}: SentimentTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);

  const {
    startScrub,
    updateScrub,
    endScrub,
    isScrubbing,
    scrubValue,
    scrubTimestamp,
    scrubPosition,
  } = useChartStore();
  const haptic = useHaptic();

  // Get current displayed value
  const currentValue = scrubValue ?? (data.length > 0 ? data[data.length - 1].score : 0);
  const currentTimestamp = scrubTimestamp ?? (data.length > 0 ? data[data.length - 1].timestamp : null);
  const currentData = scrubTimestamp
    ? data.find((d) => d.timestamp === scrubTimestamp)
    : data[data.length - 1];

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
      rightPriceScale: {
        borderColor: 'rgba(0, 255, 255, 0.1)',
        scaleMargins: { top: 0.2, bottom: 0.2 },
      },
      timeScale: {
        borderColor: 'rgba(0, 255, 255, 0.1)',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Dynamic gradient based on sentiment
    const series = chart.addSeries(AreaSeries, {
      lineColor: '#00FFFF',
      lineWidth: 2,
      topColor: 'rgba(0, 255, 255, 0.4)',
      bottomColor: 'rgba(0, 255, 255, 0.0)',
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 8,
      crosshairMarkerBackgroundColor: '#00FFFF',
      crosshairMarkerBorderColor: '#0a0a0a',
      crosshairMarkerBorderWidth: 2,
      priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
      },
    });

    chartRef.current = chart;
    seriesRef.current = series;

    // Handle crosshair movement for scrubbing
    if (interactive) {
      chart.subscribeCrosshairMove((param) => {
        if (!param.point || !param.time) {
          setTooltipPosition(null);
          if (isScrubbing) {
            endScrub();
            onScrubChange?.(null);
          }
          return;
        }

        const price = param.seriesData.get(series);
        if (price && typeof price === 'object' && 'value' in price) {
          const position = (param.point.x / containerRef.current!.clientWidth) * 100;
          const timestamp = new Date((param.time as number) * 1000).toISOString();
          const value = price.value as number;

          updateScrub(position, value, timestamp);
          setTooltipPosition({ x: param.point.x, y: param.point.y });

          // Find matching data point
          const matchingPoint = data.find((d) => d.timestamp === timestamp);
          if (matchingPoint) {
            onScrubChange?.(matchingPoint);
          }
        }
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
      seriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [height, interactive]);

  // Update data
  useEffect(() => {
    if (!seriesRef.current || !data.length) return;

    const chartData: AreaData<Time>[] = data.map((point) => ({
      time: Math.floor(new Date(point.timestamp).getTime() / 1000) as Time,
      value: point.score,
    }));

    seriesRef.current.setData(chartData);
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  // Handle touch start for scrubbing
  const handleTouchStart = useCallback(
    (e: React.TouchEvent | React.MouseEvent) => {
      if (!interactive) return;

      const rect = containerRef.current?.getBoundingClientRect();
      if (rect) {
        const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
        const position = ((clientX - rect.left) / rect.width) * 100;
        startScrub(position);
        haptic.light();
      }
    },
    [interactive, startScrub, haptic]
  );

  // Handle touch end
  const handleTouchEnd = useCallback(() => {
    if (interactive) {
      endScrub();
      setTooltipPosition(null);
      onScrubChange?.(null);
    }
  }, [interactive, endScrub, onScrubChange]);

  return (
    <motion.div
      className={cn('relative', className)}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header with ticker and current value */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-foreground">{ticker}</span>
          {source && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
              {source}
            </span>
          )}
        </div>
        {showPill && <SentimentPill score={currentValue} animated />}
      </div>

      {/* Chart container */}
      <div className="relative">
        <div
          ref={containerRef}
          className="w-full rounded-lg overflow-hidden cursor-crosshair"
          style={{ height }}
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
          onMouseDown={handleTouchStart}
          onMouseUp={handleTouchEnd}
          onMouseLeave={handleTouchEnd}
        />

        {/* Tooltip */}
        <AnimatePresence>
          {showTooltip && tooltipPosition && isScrubbing && currentData && (
            <ChartTooltip
              x={tooltipPosition.x}
              y={tooltipPosition.y}
              score={currentValue}
              timestamp={currentTimestamp}
              articleCount={currentData.articleCount}
            />
          )}
        </AnimatePresence>
      </div>

      {/* Timestamp display */}
      {currentTimestamp && (
        <div className="flex justify-between mt-2 text-xs text-muted-foreground">
          <span>{isScrubbing ? formatDateTime(currentTimestamp) : 'Latest'}</span>
          <span>
            {data.length > 0 &&
              `${data.length} data points`}
          </span>
        </div>
      )}

      {/* Loading overlay */}
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/80">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}
    </motion.div>
  );
}
