'use client';

import { memo } from 'react';
import { motion } from 'framer-motion';
import { Bell, BellOff, TrendingUp, TrendingDown, Trash2, Settings, Activity } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { AlertRule } from '@/types/alert';
import { cn } from '@/lib/utils';

interface AlertCardProps {
  alert: AlertRule;
  onToggle?: (alertId: string, isEnabled: boolean) => void;
  onEdit?: () => void;
  onDelete?: () => void;
  isUpdating?: boolean;
  className?: string;
}

export const AlertCard = memo(function AlertCard({
  alert,
  onToggle,
  onEdit,
  onDelete,
  isUpdating = false,
  className,
}: AlertCardProps) {
  const isAbove = alert.thresholdDirection === 'above';
  const isSentiment = alert.alertType === 'sentiment_threshold';

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95, height: 0 }}
      transition={{ duration: 0.2 }}
    >
      <Card
        className={cn(
          'relative overflow-hidden transition-all',
          !alert.isEnabled && 'opacity-60',
          className
        )}
      >
        {/* Enabled indicator bar */}
        <div
          className={cn(
            'absolute left-0 top-0 bottom-0 w-1 transition-colors',
            alert.isEnabled ? 'bg-accent' : 'bg-muted'
          )}
        />

        <div className="p-4 pl-5">
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-3">
              {/* Alert type icon */}
              <div
                className={cn(
                  'w-10 h-10 rounded-full flex items-center justify-center',
                  isSentiment ? 'bg-blue-500/10' : 'bg-purple-500/10'
                )}
              >
                {isSentiment ? (
                  isAbove ? (
                    <TrendingUp className="w-5 h-5 text-blue-500" />
                  ) : (
                    <TrendingDown className="w-5 h-5 text-blue-500" />
                  )
                ) : (
                  <Activity className="w-5 h-5 text-purple-500" />
                )}
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-foreground">{alert.ticker}</span>
                  <span
                    className={cn(
                      'px-1.5 py-0.5 text-xs rounded',
                      isSentiment
                        ? 'bg-blue-500/10 text-blue-500'
                        : 'bg-purple-500/10 text-purple-500'
                    )}
                  >
                    {isSentiment ? 'Sentiment' : 'Volatility'}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Alert when {isAbove ? 'above' : 'below'}{' '}
                  <span className="font-medium text-foreground">
                    {isSentiment
                      ? alert.thresholdValue.toFixed(2)
                      : `${alert.thresholdValue.toFixed(1)}%`}
                  </span>
                </p>
              </div>
            </div>

            {/* Toggle switch */}
            <button
              type="button"
              role="switch"
              aria-checked={alert.isEnabled}
              onClick={() => onToggle?.(alert.alertId, !alert.isEnabled)}
              disabled={isUpdating}
              className={cn(
                'relative w-11 h-6 rounded-full transition-colors',
                alert.isEnabled ? 'bg-accent' : 'bg-muted',
                isUpdating && 'opacity-50 cursor-not-allowed'
              )}
            >
              <motion.span
                className="absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm"
                animate={{ left: alert.isEnabled ? '1.5rem' : '0.25rem' }}
                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              />
            </button>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-4 text-xs text-muted-foreground mb-3">
            <div className="flex items-center gap-1">
              <Bell className="w-3 h-3" />
              <span>
                {alert.triggerCount} trigger{alert.triggerCount !== 1 ? 's' : ''}
              </span>
            </div>
            {alert.lastTriggeredAt && (
              <span>
                Last: {formatRelativeTime(alert.lastTriggeredAt)}
              </span>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="flex-1 gap-2"
              onClick={onEdit}
            >
              <Settings className="w-4 h-4" />
              Edit
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-red-500 hover:text-red-600 hover:bg-red-500/10"
              onClick={onDelete}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </Card>
    </motion.div>
  );
});

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

// Compact card for list views
interface AlertCardCompactProps {
  alert: AlertRule;
  onToggle?: (alertId: string, isEnabled: boolean) => void;
  onClick?: () => void;
  className?: string;
}

export function AlertCardCompact({
  alert,
  onToggle,
  onClick,
  className,
}: AlertCardCompactProps) {
  const isAbove = alert.thresholdDirection === 'above';
  const isSentiment = alert.alertType === 'sentiment_threshold';

  return (
    <motion.div
      className={cn(
        'flex items-center justify-between p-3 rounded-lg border border-border bg-card',
        'hover:bg-muted/30 transition-colors cursor-pointer',
        !alert.isEnabled && 'opacity-60',
        className
      )}
      onClick={onClick}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'w-2 h-2 rounded-full',
            alert.isEnabled ? 'bg-accent' : 'bg-muted-foreground/30'
          )}
        />
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm">{alert.ticker}</span>
            {isAbove ? (
              <TrendingUp className="w-3 h-3 text-muted-foreground" />
            ) : (
              <TrendingDown className="w-3 h-3 text-muted-foreground" />
            )}
            <span className="text-sm text-muted-foreground">
              {isSentiment
                ? alert.thresholdValue.toFixed(2)
                : `${alert.thresholdValue.toFixed(1)}%`}
            </span>
          </div>
        </div>
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={alert.isEnabled}
        onClick={(e) => {
          e.stopPropagation();
          onToggle?.(alert.alertId, !alert.isEnabled);
        }}
        className={cn(
          'relative w-9 h-5 rounded-full transition-colors',
          alert.isEnabled ? 'bg-accent' : 'bg-muted'
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform',
            alert.isEnabled ? 'translate-x-[1.1rem]' : 'translate-x-0.5'
          )}
        />
      </button>
    </motion.div>
  );
}

// Status badge for enabled/disabled
interface AlertStatusBadgeProps {
  isEnabled: boolean;
  className?: string;
}

export function AlertStatusBadge({ isEnabled, className }: AlertStatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        isEnabled
          ? 'bg-green-500/10 text-green-500'
          : 'bg-muted text-muted-foreground',
        className
      )}
    >
      {isEnabled ? (
        <>
          <Bell className="w-3 h-3" />
          Active
        </>
      ) : (
        <>
          <BellOff className="w-3 h-3" />
          Paused
        </>
      )}
    </span>
  );
}
