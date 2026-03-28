'use client';

import { useRef, useEffect } from 'react';
import { Clock, AlertTriangle } from 'lucide-react';
import { useDataFreshness, formatCompact, type FreshnessState } from '@/hooks/use-data-freshness';

/**
 * Data Freshness Indicator (Feature 1266, Issue #816).
 *
 * Shows when dashboard data was last updated and warns when it becomes stale.
 * - Fresh: default text, no warning
 * - Stale (>2x refresh interval): amber warning
 * - Critical (>4x refresh interval): red critical warning
 *
 * Desktop: "Last updated 3 minutes ago"
 * Mobile (<640px): "3m ago" with tooltip
 *
 * Accessibility:
 * - aria-live="polite" announces state transitions only
 * - aria-label provides full context on compact mobile form
 */

interface DataFreshnessIndicatorProps {
  lastUpdated: string | null;
  className?: string;
}

const stateStyles: Record<Exclude<FreshnessState, 'loading'>, {
  container: string;
  icon: string;
  showIcon: boolean;
}> = {
  fresh: {
    container: 'text-muted-foreground',
    icon: '',
    showIcon: false,
  },
  stale: {
    container: 'text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 px-2 py-0.5 rounded-md',
    icon: 'text-amber-600 dark:text-amber-400',
    showIcon: true,
  },
  critical: {
    container: 'text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950/30 px-2 py-0.5 rounded-md',
    icon: 'text-red-600 dark:text-red-400',
    showIcon: true,
  },
};

export function DataFreshnessIndicator({
  lastUpdated,
  className = '',
}: DataFreshnessIndicatorProps) {
  const { ageMs, state, formattedAge } = useDataFreshness(lastUpdated);
  const prevStateRef = useRef<FreshnessState>(state);
  const announceRef = useRef<string>('');

  // Track state transitions for aria-live announcements
  useEffect(() => {
    if (state !== prevStateRef.current && state !== 'loading') {
      const label = state === 'fresh'
        ? 'Data connection restored'
        : state === 'stale'
          ? 'Data may be outdated'
          : 'Data is significantly outdated';
      announceRef.current = label;
      prevStateRef.current = state;
    }
  }, [state]);

  // Loading state: hidden
  if (state === 'loading' || !lastUpdated) {
    return null;
  }

  const styles = stateStyles[state];
  const compactAge = formatCompact(ageMs);
  const fullText = `Last updated ${formattedAge}`;
  const ariaLabel = state === 'fresh'
    ? fullText
    : `${fullText}, ${state === 'stale' ? 'data may be outdated' : 'data is significantly outdated'}`;

  return (
    <div
      data-testid="data-freshness-indicator"
      data-freshness-state={state}
      className={`flex items-center gap-1 text-xs transition-colors duration-300 ${styles.container} ${className}`}
      role="status"
    >
      {/* State transition announcements only */}
      <span className="sr-only" aria-live="polite">
        {announceRef.current}
      </span>

      {/* Warning icon for stale/critical states */}
      {styles.showIcon && (
        <AlertTriangle className={`h-3 w-3 flex-shrink-0 ${styles.icon}`} aria-hidden="true" />
      )}

      {/* Clock icon for fresh state */}
      {!styles.showIcon && (
        <Clock className="h-3 w-3 flex-shrink-0 text-muted-foreground" aria-hidden="true" />
      )}

      {/* Desktop: full text */}
      <span className="hidden sm:inline" aria-label={ariaLabel}>
        {fullText}
      </span>

      {/* Mobile: compact form */}
      <span
        className="sm:hidden"
        title={fullText}
        aria-label={ariaLabel}
      >
        {compactAge}
      </span>
    </div>
  );
}
