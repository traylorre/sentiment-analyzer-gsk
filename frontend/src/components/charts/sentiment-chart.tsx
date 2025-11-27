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
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { getSentimentColor, formatSentimentScore, formatDateTime } from '@/lib/utils';
import { useChartStore } from '@/stores/chart-store';
import { useHaptic } from '@/hooks/use-haptic';
import type { SentimentTimeSeries } from '@/types/sentiment';

interface SentimentChartProps {
  data: SentimentTimeSeries[];
  ticker: string;
  className?: string;
  height?: number;
  showGradient?: boolean;
  interactive?: boolean;
}

export function SentimentChart({
  data,
  ticker,
  className,
  height = 300,
  showGradient = true,
  interactive = true,
}: SentimentChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const [isReady, setIsReady] = useState(false);

  const { startScrub, updateScrub, endScrub, isScrubbing, scrubValue, scrubTimestamp } =
    useChartStore();
  const haptic = useHaptic();

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
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: 'rgba(0, 255, 255, 0.1)',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#00FFFF',
      lineWidth: 2,
      topColor: showGradient ? 'rgba(0, 255, 255, 0.4)' : 'transparent',
      bottomColor: showGradient ? 'rgba(0, 255, 255, 0.0)' : 'transparent',
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 6,
      crosshairMarkerBackgroundColor: '#00FFFF',
      crosshairMarkerBorderColor: '#0a0a0a',
      crosshairMarkerBorderWidth: 2,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    // Handle crosshair movement for scrubbing
    if (interactive) {
      chart.subscribeCrosshairMove((param) => {
        if (!param.point || !param.time) {
          if (isScrubbing) {
            endScrub();
          }
          return;
        }

        const price = param.seriesData.get(series);
        if (price && typeof price === 'object' && 'value' in price) {
          const position = (param.point.x / containerRef.current!.clientWidth) * 100;
          updateScrub(
            position,
            price.value as number,
            new Date((param.time as number) * 1000).toISOString()
          );
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
  }, [height, showGradient, interactive]);

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
  const handleTouchStart = useCallback(() => {
    if (interactive) {
      startScrub(50);
      haptic.light();
    }
  }, [interactive, startScrub, haptic]);

  // Handle touch end
  const handleTouchEnd = useCallback(() => {
    if (interactive) {
      endScrub();
    }
  }, [interactive, endScrub]);

  const currentValue = scrubValue ?? (data.length > 0 ? data[data.length - 1].score : 0);
  const currentTimestamp = scrubTimestamp ?? (data.length > 0 ? data[data.length - 1].timestamp : null);

  return (
    <motion.div
      className={cn('relative', className)}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Value display */}
      <div className="flex items-baseline justify-between mb-4">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-foreground">{ticker}</span>
          <motion.span
            key={currentValue}
            className="text-3xl font-bold"
            style={{ color: getSentimentColor(currentValue) }}
            initial={{ scale: 1.2 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 300 }}
          >
            {formatSentimentScore(currentValue)}
          </motion.span>
        </div>
        {currentTimestamp && (
          <span className="text-sm text-muted-foreground">
            {isScrubbing ? formatDateTime(currentTimestamp) : 'Latest'}
          </span>
        )}
      </div>

      {/* Chart container */}
      <div
        ref={containerRef}
        className="w-full rounded-lg overflow-hidden focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        style={{ height }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onMouseDown={handleTouchStart}
        onMouseUp={handleTouchEnd}
        onMouseLeave={handleTouchEnd}
        role="img"
        aria-label={`Sentiment chart for ${ticker}. Current score: ${formatSentimentScore(currentValue)}. ${data.length} data points from ${data.length > 0 ? formatDateTime(data[0].timestamp) : 'no data'} to ${data.length > 0 ? formatDateTime(data[data.length - 1].timestamp) : 'no data'}.`}
        tabIndex={interactive ? 0 : -1}
      />

      {/* Loading overlay */}
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/80">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}
    </motion.div>
  );
}
