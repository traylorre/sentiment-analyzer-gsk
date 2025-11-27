'use client';

import { useRef, type ReactNode } from 'react';
import { motion, useMotionValue, useTransform, PanInfo } from 'framer-motion';
import { RefreshCw } from 'lucide-react';
import { useViewStore } from '@/stores/view-store';
import { useHaptic } from '@/hooks/use-haptic';
import { cn } from '@/lib/utils';

interface PullToRefreshProps {
  children: ReactNode;
  onRefresh: () => Promise<void>;
  className?: string;
  threshold?: number;
  disabled?: boolean;
}

export function PullToRefresh({
  children,
  onRefresh,
  className,
  threshold = 80,
  disabled = false,
}: PullToRefreshProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const {
    isPulling,
    pullProgress,
    isRefreshing,
    startPull,
    updatePull,
    triggerRefresh,
    endRefresh,
  } = useViewStore();
  const haptic = useHaptic();

  const y = useMotionValue(0);
  const indicatorY = useTransform(y, [0, threshold], [-40, 0]);
  const indicatorOpacity = useTransform(y, [0, threshold * 0.5, threshold], [0, 0.5, 1]);
  const indicatorRotation = useTransform(y, [0, threshold], [0, 180]);
  const indicatorScale = useTransform(y, [0, threshold * 0.8, threshold], [0.5, 0.8, 1]);

  const canPull = !disabled && !isRefreshing;

  const handleDrag = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (!canPull) return;

    // Only allow downward pull when at top
    if (info.offset.y <= 0) {
      y.set(0);
      return;
    }

    // Apply resistance
    const resistedY = info.offset.y * 0.5;
    y.set(Math.min(resistedY, threshold * 1.5));

    if (!isPulling) {
      startPull();
    }

    const progress = Math.min(resistedY / threshold, 1);
    updatePull(progress);

    // Haptic at threshold
    if (resistedY >= threshold && resistedY < threshold + 5) {
      haptic.light();
    }
  };

  const handleDragEnd = async () => {
    if (!canPull) return;

    const currentY = y.get();
    const shouldTrigger = currentY >= threshold;

    if (shouldTrigger) {
      haptic.medium();
      triggerRefresh();

      // Keep indicator visible during refresh
      y.set(threshold);

      try {
        await onRefresh();
      } finally {
        // Animate back
        y.set(0);
        endRefresh();
      }
    } else {
      // Animate back
      y.set(0);
      endRefresh();
    }
  };

  return (
    <div className={cn('relative overflow-hidden', className)}>
      {/* Pull indicator */}
      <motion.div
        className="absolute left-0 right-0 flex items-center justify-center pointer-events-none z-10"
        style={{
          y: indicatorY,
          opacity: indicatorOpacity,
        }}
      >
        <motion.div
          className={cn(
            'flex items-center justify-center w-10 h-10 rounded-full',
            'bg-card border border-border shadow-lg',
            isRefreshing && 'animate-pulse'
          )}
          style={{ scale: indicatorScale }}
        >
          <motion.div
            style={{ rotate: isRefreshing ? undefined : indicatorRotation }}
            className={isRefreshing ? 'animate-spin' : ''}
          >
            <RefreshCw
              className={cn(
                'w-5 h-5',
                pullProgress >= 1 || isRefreshing ? 'text-accent' : 'text-muted-foreground'
              )}
            />
          </motion.div>
        </motion.div>
      </motion.div>

      {/* Content */}
      <motion.div
        ref={containerRef}
        className="h-full"
        style={{ y }}
        drag={canPull ? 'y' : false}
        dragConstraints={{ top: 0, bottom: 0 }}
        dragElastic={0}
        onDrag={handleDrag}
        onDragEnd={handleDragEnd}
      >
        {children}
      </motion.div>
    </div>
  );
}

// Standalone refresh indicator for custom implementations
interface RefreshIndicatorProps {
  progress: number;
  isRefreshing: boolean;
  className?: string;
}

export function RefreshIndicator({ progress, isRefreshing, className }: RefreshIndicatorProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-center w-8 h-8 rounded-full',
        'bg-card border border-border',
        className
      )}
    >
      <motion.div
        animate={{ rotate: isRefreshing ? 360 : progress * 180 }}
        transition={isRefreshing ? { repeat: Infinity, duration: 1, ease: 'linear' } : { type: 'spring' }}
      >
        <RefreshCw
          className={cn(
            'w-4 h-4',
            progress >= 1 || isRefreshing ? 'text-accent' : 'text-muted-foreground'
          )}
        />
      </motion.div>
    </div>
  );
}
