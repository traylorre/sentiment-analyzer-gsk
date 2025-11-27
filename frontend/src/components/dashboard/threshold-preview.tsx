'use client';

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import type { AlertType, ThresholdDirection } from '@/types/alert';
import { cn } from '@/lib/utils';

interface ThresholdPreviewProps {
  thresholdValue: number;
  thresholdDirection: ThresholdDirection;
  alertType: AlertType;
  currentValue?: number;
  historicalValues?: number[];
  className?: string;
}

export function ThresholdPreview({
  thresholdValue,
  thresholdDirection,
  alertType,
  currentValue,
  historicalValues,
  className,
}: ThresholdPreviewProps) {
  // Generate sample data if not provided
  const values = useMemo(() => {
    if (historicalValues && historicalValues.length > 0) {
      return historicalValues;
    }
    // Generate random walk data centered around the threshold
    const points = 20;
    const data: number[] = [];
    let value = thresholdValue;

    for (let i = 0; i < points; i++) {
      const range = alertType === 'sentiment_threshold' ? 0.3 : 15;
      value += (Math.random() - 0.5) * range;

      // Keep within bounds
      if (alertType === 'sentiment_threshold') {
        value = Math.max(-1, Math.min(1, value));
      } else {
        value = Math.max(0, Math.min(100, value));
      }

      data.push(value);
    }

    return data;
  }, [historicalValues, thresholdValue, alertType]);

  // Calculate bounds
  const { min, max } = useMemo(() => {
    if (alertType === 'sentiment_threshold') {
      return { min: -1, max: 1 };
    }
    return { min: 0, max: 100 };
  }, [alertType]);

  // Normalize value to 0-100 range for positioning
  const normalizeY = (value: number) => {
    return ((value - min) / (max - min)) * 100;
  };

  // Generate SVG path
  const pathD = useMemo(() => {
    if (values.length === 0) return '';

    return values
      .map((v, i) => {
        const x = (i / (values.length - 1)) * 100;
        const y = 100 - normalizeY(v);
        return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
      })
      .join(' ');
  }, [values, min, max]);

  // Threshold line position
  const thresholdY = 100 - normalizeY(thresholdValue);

  // Current value position
  const currentY = currentValue !== undefined ? 100 - normalizeY(currentValue) : null;

  // Determine which areas are "triggered"
  const triggerAreaY = thresholdDirection === 'above' ? 0 : thresholdY;
  const triggerAreaHeight =
    thresholdDirection === 'above' ? thresholdY : 100 - thresholdY;

  return (
    <div className={cn('relative h-24 w-full', className)}>
      <svg
        className="w-full h-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        {/* Trigger zone fill */}
        <rect
          x="0"
          y={triggerAreaY}
          width="100"
          height={triggerAreaHeight}
          fill="currentColor"
          className="text-accent/10"
        />

        {/* Grid lines */}
        {[25, 50, 75].map((y) => (
          <line
            key={y}
            x1="0"
            y1={y}
            x2="100"
            y2={y}
            stroke="currentColor"
            strokeWidth="0.5"
            className="text-muted/30"
          />
        ))}

        {/* Threshold line */}
        <motion.line
          x1="0"
          x2="100"
          strokeWidth="1.5"
          strokeDasharray="4 2"
          className="text-accent"
          stroke="currentColor"
          initial={{ y1: 50, y2: 50 }}
          animate={{ y1: thresholdY, y2: thresholdY }}
          transition={{ type: 'spring', stiffness: 200, damping: 25 }}
        />

        {/* Data line */}
        <path
          d={pathD}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-muted-foreground/50"
        />

        {/* Current value indicator */}
        {currentY !== null && (
          <motion.g
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <circle
              cx="100"
              cy={currentY}
              r="3"
              fill="currentColor"
              className="text-foreground"
            />
            <line
              x1="95"
              y1={currentY}
              x2="100"
              y2={currentY}
              stroke="currentColor"
              strokeWidth="1"
              className="text-foreground"
            />
          </motion.g>
        )}
      </svg>

      {/* Labels */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Threshold label */}
        <motion.div
          className="absolute right-0 -translate-y-1/2 flex items-center gap-1"
          initial={{ top: '50%' }}
          animate={{ top: `${thresholdY}%` }}
          transition={{ type: 'spring', stiffness: 200, damping: 25 }}
        >
          <div className="h-px w-2 bg-accent" />
          <span className="text-xs font-medium text-accent bg-background px-1 rounded">
            {alertType === 'sentiment_threshold'
              ? thresholdValue.toFixed(2)
              : `${thresholdValue.toFixed(0)}%`}
          </span>
        </motion.div>

        {/* Direction label */}
        <div
          className={cn(
            'absolute right-2 text-xs text-accent/70',
            thresholdDirection === 'above' ? 'top-1' : 'bottom-1'
          )}
        >
          {thresholdDirection === 'above' ? 'Alert zone ↑' : 'Alert zone ↓'}
        </div>
      </div>
    </div>
  );
}

// Compact sparkline version
interface ThresholdSparklineProps {
  thresholdValue: number;
  thresholdDirection: ThresholdDirection;
  alertType: AlertType;
  isTriggered?: boolean;
  className?: string;
}

export function ThresholdSparkline({
  thresholdValue,
  thresholdDirection,
  alertType,
  isTriggered = false,
  className,
}: ThresholdSparklineProps) {
  // Normalize threshold to 0-100
  const normalizedThreshold = useMemo(() => {
    if (alertType === 'sentiment_threshold') {
      return ((thresholdValue + 1) / 2) * 100;
    }
    return thresholdValue;
  }, [thresholdValue, alertType]);

  return (
    <div className={cn('relative h-4 w-16 rounded-full bg-muted overflow-hidden', className)}>
      {/* Trigger zone */}
      <div
        className={cn(
          'absolute h-full transition-colors',
          isTriggered ? 'bg-accent/30' : 'bg-accent/10'
        )}
        style={{
          [thresholdDirection === 'above' ? 'right' : 'left']: 0,
          width: `${thresholdDirection === 'above' ? 100 - normalizedThreshold : normalizedThreshold}%`,
        }}
      />

      {/* Threshold line */}
      <div
        className="absolute top-0 bottom-0 w-0.5 bg-accent"
        style={{ left: `${normalizedThreshold}%` }}
      />
    </div>
  );
}
