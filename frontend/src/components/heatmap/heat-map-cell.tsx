'use client';

import { motion } from 'framer-motion';
import { cn, formatSentimentScore, interpolateSentimentColor } from '@/lib/utils';
import { useChartStore } from '@/stores/chart-store';
import { useHaptic } from '@/hooks/use-haptic';
import type { HeatMapCell as HeatMapCellType } from '@/types/heatmap';

interface HeatMapCellProps {
  data: HeatMapCellType;
  ticker: string;
  isHovered?: boolean;
  onClick?: () => void;
  onHover?: (data: HeatMapCellType | null) => void;
  size?: 'sm' | 'md' | 'lg';
  showValue?: boolean;
  className?: string;
}

export function HeatMapCell({
  data,
  ticker,
  isHovered = false,
  onClick,
  onHover,
  size = 'md',
  showValue = true,
  className,
}: HeatMapCellProps) {
  const { setHoveredCell } = useChartStore();
  const haptic = useHaptic();

  const color = interpolateSentimentColor(data.score);

  const sizeStyles = {
    sm: 'w-10 h-10 text-[10px]',
    md: 'w-14 h-14 text-xs',
    lg: 'w-20 h-20 text-sm',
  };

  const handleMouseEnter = () => {
    // For chart store, use source for both views (use period as source in timeperiods view)
    const sourceValue = data.source ?? data.period;
    if (sourceValue) {
      setHoveredCell({ ticker, source: sourceValue });
    }
    onHover?.(data);
  };

  const handleMouseLeave = () => {
    setHoveredCell(null);
    onHover?.(null);
  };

  const handleClick = () => {
    if (onClick) {
      haptic.medium();
      onClick();
    }
  };

  // Generate aria-label based on available data
  const sentimentLabel = data.score >= 0.3 ? 'bullish' : data.score <= -0.3 ? 'bearish' : 'neutral';
  const sourceLabel = data.source ?? data.period ?? 'unknown';
  const ariaLabel = `${ticker} ${sourceLabel}: ${formatSentimentScore(data.score)}, ${sentimentLabel} sentiment`;

  return (
    <motion.button
      className={cn(
        'relative rounded-md flex items-center justify-center',
        'transition-all duration-200',
        'font-medium tabular-nums',
        sizeStyles[size],
        onClick && 'cursor-pointer',
        isHovered && 'ring-2 ring-accent ring-offset-2 ring-offset-background z-10',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        className
      )}
      style={{ backgroundColor: color }}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleMouseEnter}
      onBlur={handleMouseLeave}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && onClick) {
          e.preventDefault();
          handleClick();
        }
      }}
      whileHover={{ scale: 1.05 }}
      whileTap={onClick ? { scale: 0.95 } : undefined}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      aria-label={ariaLabel}
      role="gridcell"
      tabIndex={0}
    >
      {showValue && (
        <span
          className={cn(
            'font-semibold',
            // Use white or black text based on background brightness
            data.score > 0.2 || data.score < -0.2 ? 'text-white' : 'text-gray-900'
          )}
        >
          {formatSentimentScore(data.score)}
        </span>
      )}

      {/* Hover glow effect */}
      {isHovered && (
        <motion.div
          className="absolute inset-0 rounded-md"
          style={{
            boxShadow: `0 0 20px ${color}`,
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.5 }}
        />
      )}
    </motion.button>
  );
}

// Skeleton cell for loading state
export function HeatMapCellSkeleton({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizeStyles = {
    sm: 'w-10 h-10',
    md: 'w-14 h-14',
    lg: 'w-20 h-20',
  };

  return (
    <div
      className={cn(
        'rounded-md bg-muted animate-pulse',
        sizeStyles[size]
      )}
    />
  );
}

// Empty cell placeholder
export function HeatMapEmptyCell({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizeStyles = {
    sm: 'w-10 h-10',
    md: 'w-14 h-14',
    lg: 'w-20 h-20',
  };

  return (
    <div
      className={cn(
        'rounded-md bg-muted/30 border border-dashed border-muted',
        'flex items-center justify-center text-muted-foreground text-xs',
        sizeStyles[size]
      )}
    >
      N/A
    </div>
  );
}
