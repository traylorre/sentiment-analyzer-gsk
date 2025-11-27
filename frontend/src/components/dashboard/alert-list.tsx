'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Bell, BellOff, Mail, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AlertCard } from './alert-card';
import type { AlertRule } from '@/types/alert';
import { cn } from '@/lib/utils';

interface AlertListProps {
  alerts: AlertRule[];
  dailyEmailQuota: {
    used: number;
    limit: number;
    resetsAt: string;
  };
  isLoading?: boolean;
  onToggle: (alertId: string, isEnabled: boolean) => void;
  onEdit: (alert: AlertRule) => void;
  onDelete: (alertId: string) => void;
  onCreate: () => void;
  className?: string;
}

export function AlertList({
  alerts,
  dailyEmailQuota,
  isLoading = false,
  onToggle,
  onEdit,
  onDelete,
  onCreate,
  className,
}: AlertListProps) {
  const enabledCount = alerts.filter((a) => a.isEnabled).length;
  const quotaPercentage = (dailyEmailQuota.used / dailyEmailQuota.limit) * 100;
  const isQuotaLow = quotaPercentage >= 80;

  if (isLoading) {
    return (
      <div className={cn('space-y-4', className)}>
        {[...Array(3)].map((_, i) => (
          <AlertCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <EmptyState onCreateClick={onCreate} className={className} />
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header with quota */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Alerts</h2>
          <p className="text-sm text-muted-foreground">
            {enabledCount} of {alerts.length} active
          </p>
        </div>

        <Button onClick={onCreate} size="sm" className="gap-2">
          <Plus className="w-4 h-4" />
          New Alert
        </Button>
      </div>

      {/* Email quota indicator */}
      <QuotaIndicator quota={dailyEmailQuota} />

      {/* Alert cards */}
      <motion.div layout className="space-y-3">
        <AnimatePresence mode="popLayout">
          {alerts.map((alert) => (
            <AlertCard
              key={alert.alertId}
              alert={alert}
              onToggle={onToggle}
              onEdit={() => onEdit(alert)}
              onDelete={() => onDelete(alert.alertId)}
            />
          ))}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

// Quota indicator component
interface QuotaIndicatorProps {
  quota: {
    used: number;
    limit: number;
    resetsAt: string;
  };
  className?: string;
}

export function QuotaIndicator({ quota, className }: QuotaIndicatorProps) {
  const percentage = Math.min((quota.used / quota.limit) * 100, 100);
  const isLow = percentage >= 80;
  const isExhausted = percentage >= 100;

  // Format reset time
  const resetTime = new Date(quota.resetsAt);
  const now = new Date();
  const hoursUntilReset = Math.max(
    0,
    Math.ceil((resetTime.getTime() - now.getTime()) / (1000 * 60 * 60))
  );

  return (
    <div
      className={cn(
        'p-3 rounded-lg border',
        isExhausted
          ? 'border-red-500/30 bg-red-500/5'
          : isLow
          ? 'border-amber-500/30 bg-amber-500/5'
          : 'border-border bg-card',
        className
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Mail
            className={cn(
              'w-4 h-4',
              isExhausted
                ? 'text-red-500'
                : isLow
                ? 'text-amber-500'
                : 'text-muted-foreground'
            )}
          />
          <span className="text-sm font-medium text-foreground">
            Daily Email Quota
          </span>
        </div>
        <span
          className={cn(
            'text-sm font-medium',
            isExhausted
              ? 'text-red-500'
              : isLow
              ? 'text-amber-500'
              : 'text-muted-foreground'
          )}
        >
          {quota.used}/{quota.limit}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <motion.div
          className={cn(
            'h-full rounded-full',
            isExhausted
              ? 'bg-red-500'
              : isLow
              ? 'bg-amber-500'
              : 'bg-accent'
          )}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>

      {/* Reset info */}
      <p className="text-xs text-muted-foreground mt-2">
        Resets in {hoursUntilReset}h
        {isExhausted && (
          <span className="text-red-500 ml-2">
            - Email alerts paused until reset
          </span>
        )}
      </p>
    </div>
  );
}

// Empty state component
interface EmptyStateProps {
  onCreateClick: () => void;
  className?: string;
}

function EmptyState({ onCreateClick, className }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'flex flex-col items-center justify-center py-12 text-center',
        className
      )}
    >
      <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-4">
        <BellOff className="w-8 h-8 text-muted-foreground" />
      </div>

      <h3 className="text-lg font-semibold text-foreground mb-1">
        No alerts configured
      </h3>

      <p className="text-sm text-muted-foreground mb-6 max-w-xs">
        Create alerts to get notified when sentiment or volatility crosses your
        thresholds.
      </p>

      <Button onClick={onCreateClick} className="gap-2">
        <Plus className="w-4 h-4" />
        Create Alert
      </Button>
    </motion.div>
  );
}

// Skeleton loader
function AlertCardSkeleton() {
  return (
    <div className="p-4 rounded-lg border border-border bg-card animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-muted rounded-full" />
          <div className="space-y-2">
            <div className="h-5 w-20 bg-muted rounded" />
            <div className="h-3 w-32 bg-muted rounded" />
          </div>
        </div>
        <div className="w-11 h-6 bg-muted rounded-full" />
      </div>

      <div className="flex gap-4 mb-3">
        <div className="h-3 w-16 bg-muted rounded" />
        <div className="h-3 w-24 bg-muted rounded" />
      </div>

      <div className="flex gap-2">
        <div className="h-9 flex-1 bg-muted rounded" />
        <div className="h-9 w-9 bg-muted rounded" />
      </div>
    </div>
  );
}

// Summary stats bar
interface AlertSummaryProps {
  alerts: AlertRule[];
  className?: string;
}

export function AlertSummary({ alerts, className }: AlertSummaryProps) {
  const stats = {
    total: alerts.length,
    active: alerts.filter((a) => a.isEnabled).length,
    triggered: alerts.filter((a) => a.triggerCount > 0).length,
    sentiment: alerts.filter((a) => a.alertType === 'sentiment_threshold').length,
    volatility: alerts.filter((a) => a.alertType === 'volatility_threshold').length,
  };

  return (
    <div
      className={cn(
        'grid grid-cols-2 sm:grid-cols-4 gap-3',
        className
      )}
    >
      <div className="p-3 rounded-lg bg-card border border-border">
        <div className="flex items-center gap-2 mb-1">
          <Bell className="w-4 h-4 text-accent" />
          <span className="text-xs text-muted-foreground">Active</span>
        </div>
        <span className="text-xl font-bold text-foreground">
          {stats.active}/{stats.total}
        </span>
      </div>

      <div className="p-3 rounded-lg bg-card border border-border">
        <div className="flex items-center gap-2 mb-1">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <span className="text-xs text-muted-foreground">Triggered</span>
        </div>
        <span className="text-xl font-bold text-foreground">{stats.triggered}</span>
      </div>

      <div className="p-3 rounded-lg bg-card border border-border">
        <div className="text-xs text-muted-foreground mb-1">Sentiment</div>
        <span className="text-xl font-bold text-blue-500">{stats.sentiment}</span>
      </div>

      <div className="p-3 rounded-lg bg-card border border-border">
        <div className="text-xs text-muted-foreground mb-1">Volatility</div>
        <span className="text-xl font-bold text-purple-500">{stats.volatility}</span>
      </div>
    </div>
  );
}
