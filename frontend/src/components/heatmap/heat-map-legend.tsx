'use client';

import { motion } from 'framer-motion';
import { cn, interpolateSentimentColor } from '@/lib/utils';

interface HeatMapLegendProps {
  className?: string;
  orientation?: 'horizontal' | 'vertical';
  showLabels?: boolean;
}

export function HeatMapLegend({
  className,
  orientation = 'horizontal',
  showLabels = true,
}: HeatMapLegendProps) {
  // Generate gradient stops
  const gradientStops = [];
  for (let i = -1; i <= 1; i += 0.1) {
    gradientStops.push(interpolateSentimentColor(i));
  }

  const gradient =
    orientation === 'horizontal'
      ? `linear-gradient(to right, ${gradientStops.join(', ')})`
      : `linear-gradient(to bottom, ${gradientStops.reverse().join(', ')})`;

  return (
    <div
      className={cn(
        'flex items-center gap-2',
        orientation === 'vertical' && 'flex-col',
        className
      )}
    >
      {showLabels && (
        <span className="text-xs text-muted-foreground whitespace-nowrap">
          Bearish
        </span>
      )}

      <motion.div
        className={cn(
          'rounded-full overflow-hidden',
          orientation === 'horizontal' ? 'h-2 flex-1 min-w-[100px]' : 'w-2 h-24'
        )}
        style={{ background: gradient }}
        initial={{ opacity: 0, scaleX: 0 }}
        animate={{ opacity: 1, scaleX: 1 }}
        transition={{ duration: 0.5 }}
      />

      {showLabels && (
        <span className="text-xs text-muted-foreground whitespace-nowrap">
          Bullish
        </span>
      )}
    </div>
  );
}

// Detailed legend with value markers
interface DetailedHeatMapLegendProps {
  className?: string;
}

export function DetailedHeatMapLegend({ className }: DetailedHeatMapLegendProps) {
  const markers = [
    { value: -1, label: '-1.0' },
    { value: -0.5, label: '-0.5' },
    { value: 0, label: '0.0' },
    { value: 0.5, label: '+0.5' },
    { value: 1, label: '+1.0' },
  ];

  return (
    <div className={cn('space-y-2', className)}>
      {/* Gradient bar */}
      <HeatMapLegend showLabels={false} />

      {/* Value markers */}
      <div className="flex justify-between px-1">
        {markers.map(({ value, label }) => (
          <div key={value} className="flex flex-col items-center">
            <div
              className="w-3 h-3 rounded-sm mb-1"
              style={{ backgroundColor: interpolateSentimentColor(value) }}
            />
            <span className="text-[10px] text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Compact legend with color squares
interface CompactHeatMapLegendProps {
  className?: string;
}

export function CompactHeatMapLegend({ className }: CompactHeatMapLegendProps) {
  const items = [
    { label: 'Bearish', value: -0.7 },
    { label: 'Neutral', value: 0 },
    { label: 'Bullish', value: 0.7 },
  ];

  return (
    <div className={cn('flex items-center gap-4', className)}>
      {items.map(({ label, value }) => (
        <div key={label} className="flex items-center gap-1.5">
          <div
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: interpolateSentimentColor(value) }}
          />
          <span className="text-xs text-muted-foreground">{label}</span>
        </div>
      ))}
    </div>
  );
}
