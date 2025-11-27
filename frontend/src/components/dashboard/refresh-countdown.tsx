'use client';

import { motion } from 'framer-motion';
import { RefreshCw } from 'lucide-react';
import { useRefreshCountdown, REFRESH_INTERVAL_MS } from '@/hooks/use-refresh-countdown';
import { cn } from '@/lib/utils';

interface RefreshCountdownProps {
  onRefresh?: () => void | Promise<void>;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const sizes = {
  sm: { container: 'w-8 h-8', stroke: 2, icon: 'w-3 h-3', text: 'text-[10px]' },
  md: { container: 'w-10 h-10', stroke: 2.5, icon: 'w-4 h-4', text: 'text-xs' },
  lg: { container: 'w-12 h-12', stroke: 3, icon: 'w-5 h-5', text: 'text-sm' },
};

export function RefreshCountdown({
  onRefresh,
  className,
  size = 'md',
}: RefreshCountdownProps) {
  const {
    progress,
    formattedTime,
    isRefreshing,
    refresh,
  } = useRefreshCountdown({
    onRefresh,
    intervalMs: REFRESH_INTERVAL_MS,
  });

  const sizeConfig = sizes[size];

  // SVG circle parameters
  const radius = 16;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference * (1 - progress);

  return (
    <div className={cn('relative', className)}>
      <button
        onClick={refresh}
        disabled={isRefreshing}
        className={cn(
          'relative flex items-center justify-center rounded-full',
          'transition-transform hover:scale-105 active:scale-95',
          'disabled:cursor-not-allowed disabled:opacity-70',
          sizeConfig.container
        )}
        aria-label={isRefreshing ? 'Refreshing...' : `Refresh in ${formattedTime}`}
      >
        {/* Background circle */}
        <svg
          className="absolute inset-0 -rotate-90"
          viewBox="0 0 40 40"
        >
          {/* Track */}
          <circle
            cx="20"
            cy="20"
            r={radius}
            fill="transparent"
            stroke="currentColor"
            strokeWidth={sizeConfig.stroke}
            className="text-muted/20"
          />
          {/* Progress */}
          <motion.circle
            cx="20"
            cy="20"
            r={radius}
            fill="transparent"
            stroke="currentColor"
            strokeWidth={sizeConfig.stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="text-accent"
            initial={false}
            animate={{ strokeDashoffset }}
            transition={{ duration: 0.3, ease: 'linear' }}
          />
        </svg>

        {/* Center content */}
        <div className="relative z-10 flex items-center justify-center">
          {isRefreshing ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            >
              <RefreshCw className={cn(sizeConfig.icon, 'text-accent')} />
            </motion.div>
          ) : (
            <span className={cn('font-mono font-medium text-muted-foreground', sizeConfig.text)}>
              {formattedTime}
            </span>
          )}
        </div>
      </button>
    </div>
  );
}

// Compact version for header
interface RefreshTimerProps {
  onRefresh?: () => void | Promise<void>;
  className?: string;
}

export function RefreshTimer({ onRefresh, className }: RefreshTimerProps) {
  const {
    formattedTime,
    isRefreshing,
    refresh,
  } = useRefreshCountdown({
    onRefresh,
    intervalMs: REFRESH_INTERVAL_MS,
  });

  return (
    <button
      onClick={refresh}
      disabled={isRefreshing}
      className={cn(
        'flex items-center gap-1.5 px-2 py-1 rounded-md',
        'text-xs text-muted-foreground',
        'transition-colors hover:bg-muted/50 hover:text-foreground',
        'disabled:cursor-not-allowed',
        className
      )}
      aria-label={isRefreshing ? 'Refreshing...' : `Refresh in ${formattedTime}`}
    >
      <motion.div
        animate={isRefreshing ? { rotate: 360 } : { rotate: 0 }}
        transition={
          isRefreshing
            ? { duration: 1, repeat: Infinity, ease: 'linear' }
            : { duration: 0 }
        }
      >
        <RefreshCw className="w-3.5 h-3.5" />
      </motion.div>
      <span className="font-mono">{isRefreshing ? 'Updating...' : formattedTime}</span>
    </button>
  );
}
