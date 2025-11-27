'use client';

import { motion } from 'framer-motion';
import { cn, getSentimentColor, formatSentimentScore, formatDateTime } from '@/lib/utils';

interface ChartTooltipProps {
  x: number;
  y: number;
  score: number;
  timestamp: string | null;
  articleCount?: number;
  className?: string;
}

export function ChartTooltip({
  x,
  y,
  score,
  timestamp,
  articleCount,
  className,
}: ChartTooltipProps) {
  // Adjust position to prevent overflow
  const tooltipWidth = 180;
  const tooltipHeight = 100;
  const padding = 16;

  // Check if tooltip would overflow right side
  const adjustedX = x + tooltipWidth + padding > window.innerWidth
    ? x - tooltipWidth - padding
    : x + padding;

  // Check if tooltip would overflow bottom
  const adjustedY = y + tooltipHeight + padding > window.innerHeight
    ? y - tooltipHeight - padding
    : y + padding;

  return (
    <motion.div
      className={cn(
        'absolute z-50 pointer-events-none',
        'p-4 rounded-xl',
        // Glassmorphism effect
        'bg-card/80 backdrop-blur-xl',
        'border border-white/10',
        'shadow-2xl shadow-black/50',
        className
      )}
      style={{
        left: adjustedX,
        top: adjustedY,
        minWidth: tooltipWidth,
      }}
      initial={{ opacity: 0, scale: 0.9, y: -10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9, y: -10 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
    >
      {/* Gradient glow effect */}
      <div
        className="absolute inset-0 rounded-xl opacity-30"
        style={{
          background: `radial-gradient(circle at center, ${getSentimentColor(score)}33, transparent 70%)`,
        }}
      />

      {/* Content */}
      <div className="relative space-y-3">
        {/* Score */}
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wider text-muted-foreground">
            Sentiment
          </span>
          <motion.span
            className="text-2xl font-bold"
            style={{ color: getSentimentColor(score) }}
            initial={{ scale: 1.2 }}
            animate={{ scale: 1 }}
            key={score}
          >
            {formatSentimentScore(score)}
          </motion.span>
        </div>

        {/* Sentiment bar */}
        <div className="relative h-1.5 rounded-full bg-muted overflow-hidden">
          <motion.div
            className="absolute inset-y-0 left-0 rounded-full"
            style={{ backgroundColor: getSentimentColor(score) }}
            initial={{ width: 0 }}
            animate={{ width: `${((score + 1) / 2) * 100}%` }}
            transition={{ type: 'spring', stiffness: 300 }}
          />
        </div>

        {/* Timestamp */}
        {timestamp && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Time</span>
            <span className="text-foreground font-medium">
              {formatDateTime(timestamp)}
            </span>
          </div>
        )}

        {/* Article count */}
        {articleCount !== undefined && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Articles</span>
            <span className="text-foreground font-medium">{articleCount}</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// Simplified inline tooltip for sparklines
interface InlineTooltipProps {
  value: number;
  label?: string;
  className?: string;
}

export function InlineTooltip({ value, label, className }: InlineTooltipProps) {
  return (
    <motion.div
      className={cn(
        'px-2 py-1 rounded-lg',
        'bg-card/90 backdrop-blur-md',
        'border border-border',
        'text-xs font-medium',
        className
      )}
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 5 }}
    >
      {label && <span className="text-muted-foreground mr-1">{label}:</span>}
      <span style={{ color: getSentimentColor(value) }}>
        {formatSentimentScore(value)}
      </span>
    </motion.div>
  );
}
