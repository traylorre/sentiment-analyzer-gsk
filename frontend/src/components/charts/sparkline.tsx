'use client';

import { useEffect, useRef } from 'react';
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type AreaData,
  type Time,
  ColorType,
  AreaSeries,
} from 'lightweight-charts';
import { cn } from '@/lib/utils';
import { getSentimentColor } from '@/lib/utils';

interface SparklineProps {
  data: { timestamp: string; score: number }[];
  width?: number;
  height?: number;
  className?: string;
  color?: string;
}

export function Sparkline({
  data,
  width = 100,
  height = 32,
  className,
  color,
}: SparklineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);

  // Determine color from latest value if not provided
  const lineColor = color ?? (data.length > 0 ? getSentimentColor(data[data.length - 1].score) : '#00FFFF');

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'transparent',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      crosshair: {
        mode: 0, // Hidden
      },
      width,
      height,
      handleScale: false,
      handleScroll: false,
      rightPriceScale: {
        visible: false,
      },
      timeScale: {
        visible: false,
      },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor,
      lineWidth: 1,
      topColor: `${lineColor}40`,
      bottomColor: 'transparent',
      crosshairMarkerVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [width, height, lineColor]);

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

  return (
    <div
      ref={containerRef}
      className={cn('overflow-hidden', className)}
      style={{ width, height }}
    />
  );
}
