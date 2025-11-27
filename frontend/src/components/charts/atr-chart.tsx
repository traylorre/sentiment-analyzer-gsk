'use client';

import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type HistogramData,
  type Time,
  ColorType,
  CrosshairMode,
  HistogramSeries,
} from 'lightweight-charts';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useChartStore } from '@/stores/chart-store';
import type { ATRData } from '@/types/sentiment';

interface ATRChartProps {
  data: ATRData[];
  ticker: string;
  className?: string;
  height?: number;
  syncId?: string;
}

// Color scale for ATR volatility (low = green, high = red)
function getATRColor(value: number, min: number, max: number): string {
  const normalized = (value - min) / (max - min);

  if (normalized < 0.33) {
    return '#22C55E'; // Green - low volatility
  } else if (normalized < 0.66) {
    return '#EAB308'; // Yellow - medium volatility
  } else {
    return '#EF4444'; // Red - high volatility
  }
}

export function ATRChart({
  data,
  ticker,
  className,
  height = 150,
  syncId,
}: ATRChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [hoveredValue, setHoveredValue] = useState<number | null>(null);

  const { isScrubbing, scrubTimestamp } = useChartStore();

  // Calculate min/max for color scaling
  const minATR = Math.min(...data.map((d) => d.atr));
  const maxATR = Math.max(...data.map((d) => d.atr));

  // Find current value based on scrub position
  const currentValue = scrubTimestamp
    ? data.find((d) => d.timestamp === scrubTimestamp)?.atr ?? data[data.length - 1]?.atr
    : hoveredValue ?? data[data.length - 1]?.atr;

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#a3a3a3',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: 'rgba(0, 255, 255, 0.05)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#00FFFF',
          width: 1,
          labelVisible: false,
        },
        horzLine: {
          visible: false,
        },
      },
      width: containerRef.current.clientWidth,
      height,
      handleScale: false,
      handleScroll: false,
      rightPriceScale: {
        borderColor: 'rgba(0, 255, 255, 0.1)',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        visible: false,
        borderColor: 'rgba(0, 255, 255, 0.1)',
      },
    });

    const series = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: 'price',
        precision: 4,
        minMove: 0.0001,
      },
    });

    chartRef.current = chart;
    seriesRef.current = series;

    // Handle crosshair movement
    chart.subscribeCrosshairMove((param) => {
      if (!param.point || !param.time) {
        setHoveredValue(null);
        return;
      }

      const price = param.seriesData.get(series);
      if (price && typeof price === 'object' && 'value' in price) {
        setHoveredValue(price.value as number);
      }
    });

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
  }, [height]);

  // Update data
  useEffect(() => {
    if (!seriesRef.current || !data.length) return;

    const chartData: HistogramData<Time>[] = data.map((point) => ({
      time: Math.floor(new Date(point.timestamp).getTime() / 1000) as Time,
      value: point.atr,
      color: getATRColor(point.atr, minATR, maxATR),
    }));

    seriesRef.current.setData(chartData);
    chartRef.current?.timeScale().fitContent();
  }, [data, minATR, maxATR]);

  return (
    <motion.div
      className={cn('relative', className)}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {/* Header */}
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-sm font-medium text-muted-foreground">ATR Volatility</span>
        {currentValue !== undefined && (
          <motion.span
            key={currentValue}
            className="text-sm font-bold"
            style={{ color: getATRColor(currentValue, minATR, maxATR) }}
            initial={{ scale: 1.1 }}
            animate={{ scale: 1 }}
          >
            {currentValue.toFixed(4)}
          </motion.span>
        )}
      </div>

      {/* Chart container */}
      <div
        ref={containerRef}
        className="w-full rounded-lg overflow-hidden"
        style={{ height }}
      />

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-2">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-green-500" />
          <span className="text-xs text-muted-foreground">Low</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-yellow-500" />
          <span className="text-xs text-muted-foreground">Medium</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm bg-red-500" />
          <span className="text-xs text-muted-foreground">High</span>
        </div>
      </div>

      {/* Loading overlay */}
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-card/80">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}
    </motion.div>
  );
}
