'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn, getSentimentColor, formatSentimentScore, getSentimentLabel } from '@/lib/utils';

interface SentimentPillProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  showTrend?: boolean;
  previousScore?: number;
  animated?: boolean;
  className?: string;
}

export function SentimentPill({
  score,
  size = 'md',
  showLabel = true,
  showTrend = false,
  previousScore,
  animated = false,
  className,
}: SentimentPillProps) {
  const color = getSentimentColor(score);
  const label = getSentimentLabel(score);

  // Calculate trend if previous score provided
  const trend =
    previousScore !== undefined
      ? score > previousScore
        ? 'up'
        : score < previousScore
        ? 'down'
        : 'neutral'
      : null;

  const sizeStyles = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-3 py-1 text-sm gap-1.5',
    lg: 'px-4 py-2 text-base gap-2',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const PillContent = () => (
    <>
      {/* Glow effect */}
      <div
        className="absolute inset-0 rounded-full opacity-20 blur-md"
        style={{ backgroundColor: color }}
      />

      {/* Score */}
      <motion.span
        className="relative z-10 font-bold tabular-nums"
        style={{ color }}
        key={animated ? score : undefined}
        initial={animated ? { scale: 1.2 } : undefined}
        animate={animated ? { scale: 1 } : undefined}
      >
        {formatSentimentScore(score)}
      </motion.span>

      {/* Label */}
      {showLabel && (
        <span className="relative z-10 text-muted-foreground">{label}</span>
      )}

      {/* Trend indicator */}
      {showTrend && trend && (
        <motion.span
          className="relative z-10"
          initial={{ opacity: 0, x: -5 }}
          animate={{ opacity: 1, x: 0 }}
        >
          {trend === 'up' && (
            <TrendingUp className={cn(iconSizes[size], 'text-green-500')} />
          )}
          {trend === 'down' && (
            <TrendingDown className={cn(iconSizes[size], 'text-red-500')} />
          )}
          {trend === 'neutral' && (
            <Minus className={cn(iconSizes[size], 'text-muted-foreground')} />
          )}
        </motion.span>
      )}
    </>
  );

  return (
    <div
      className={cn(
        'relative inline-flex items-center rounded-full',
        'bg-card border border-border',
        sizeStyles[size],
        className
      )}
    >
      {animated ? (
        <AnimatePresence mode="wait">
          <motion.div
            key={score}
            className="flex items-center gap-inherit"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
          >
            <PillContent />
          </motion.div>
        </AnimatePresence>
      ) : (
        <PillContent />
      )}
    </div>
  );
}

// Mini score badge for lists and cards
interface ScoreBadgeProps {
  score: number;
  className?: string;
}

export function ScoreBadge({ score, className }: ScoreBadgeProps) {
  const color = getSentimentColor(score);

  return (
    <motion.div
      className={cn(
        'w-10 h-10 rounded-lg flex items-center justify-center',
        'text-sm font-bold',
        className
      )}
      style={{
        backgroundColor: `${color}20`,
        color,
      }}
      whileHover={{ scale: 1.05 }}
    >
      {formatSentimentScore(score)}
    </motion.div>
  );
}

// Large hero-style score display
interface HeroScoreProps {
  score: number;
  ticker: string;
  source?: string;
  animated?: boolean;
  className?: string;
}

export function HeroScore({
  score,
  ticker,
  source,
  animated = true,
  className,
}: HeroScoreProps) {
  const color = getSentimentColor(score);
  const label = getSentimentLabel(score);

  return (
    <div className={cn('text-center', className)}>
      {/* Ticker */}
      <h2 className="text-lg font-medium text-muted-foreground mb-2">{ticker}</h2>

      {/* Large score */}
      <motion.div
        className="text-6xl md:text-7xl font-bold mb-2"
        style={{ color }}
        initial={animated ? { scale: 0.8, opacity: 0 } : undefined}
        animate={animated ? { scale: 1, opacity: 1 } : undefined}
        key={animated ? score : undefined}
      >
        {formatSentimentScore(score)}
      </motion.div>

      {/* Label */}
      <div className="flex items-center justify-center gap-2 text-sm">
        <span
          className="px-2 py-0.5 rounded-full font-medium"
          style={{ backgroundColor: `${color}20`, color }}
        >
          {label}
        </span>
        {source && (
          <span className="text-muted-foreground">via {source}</span>
        )}
      </div>
    </div>
  );
}

// Compact score display for data tables
interface CompactScoreProps {
  score: number;
  change?: number;
  className?: string;
}

export function CompactScore({ score, change, className }: CompactScoreProps) {
  const color = getSentimentColor(score);
  const changeColor = change && change > 0 ? '#22C55E' : change && change < 0 ? '#EF4444' : '#A3A3A3';

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="font-bold tabular-nums" style={{ color }}>
        {formatSentimentScore(score)}
      </span>
      {change !== undefined && (
        <span className="text-xs tabular-nums" style={{ color: changeColor }}>
          {change > 0 ? '+' : ''}{(change * 100).toFixed(1)}%
        </span>
      )}
    </div>
  );
}
