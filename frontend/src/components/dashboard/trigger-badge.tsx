'use client';

import { motion } from 'framer-motion';
import { Bell, TrendingUp, TrendingDown, Activity, Mail, CheckCircle, XCircle, Clock } from 'lucide-react';
import type { Notification, AlertType } from '@/types/alert';
import { cn } from '@/lib/utils';

interface TriggerBadgeProps {
  notification: Notification;
  onClick?: () => void;
  className?: string;
}

export function TriggerBadge({ notification, onClick, className }: TriggerBadgeProps) {
  const isSentiment = notification.alertType === 'sentiment_threshold';
  const isAbove = notification.triggeredValue > notification.thresholdValue;

  return (
    <motion.button
      type="button"
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 rounded-full border transition-colors',
        'hover:bg-muted/50',
        notification.status === 'sent'
          ? 'border-green-500/30 bg-green-500/5'
          : notification.status === 'failed'
          ? 'border-red-500/30 bg-red-500/5'
          : 'border-border bg-card',
        className
      )}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      {/* Icon */}
      <div
        className={cn(
          'w-5 h-5 rounded-full flex items-center justify-center',
          isSentiment ? 'bg-blue-500/10' : 'bg-purple-500/10'
        )}
      >
        {isSentiment ? (
          isAbove ? (
            <TrendingUp className="w-3 h-3 text-blue-500" />
          ) : (
            <TrendingDown className="w-3 h-3 text-blue-500" />
          )
        ) : (
          <Activity className="w-3 h-3 text-purple-500" />
        )}
      </div>

      {/* Ticker */}
      <span className="font-medium text-sm text-foreground">{notification.ticker}</span>

      {/* Value */}
      <span className="text-xs text-muted-foreground">
        {isSentiment
          ? notification.triggeredValue.toFixed(2)
          : `${notification.triggeredValue.toFixed(1)}%`}
      </span>

      {/* Status indicator */}
      <StatusIcon status={notification.status} />
    </motion.button>
  );
}

// Status icon component
function StatusIcon({ status }: { status: Notification['status'] }) {
  switch (status) {
    case 'sent':
      return <CheckCircle className="w-3 h-3 text-green-500" />;
    case 'failed':
      return <XCircle className="w-3 h-3 text-red-500" />;
    case 'pending':
      return <Clock className="w-3 h-3 text-muted-foreground animate-pulse" />;
  }
}

// Full notification card
interface NotificationCardProps {
  notification: Notification;
  onClick?: () => void;
  className?: string;
}

export function NotificationCard({ notification, onClick, className }: NotificationCardProps) {
  const isSentiment = notification.alertType === 'sentiment_threshold';
  const isAbove = notification.triggeredValue > notification.thresholdValue;

  return (
    <motion.div
      className={cn(
        'p-3 rounded-lg border border-border bg-card cursor-pointer',
        'hover:bg-muted/30 transition-colors',
        className
      )}
      onClick={onClick}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className={cn(
            'w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0',
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

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-bold text-foreground">{notification.ticker}</span>
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
            <StatusBadge status={notification.status} />
          </div>

          <p className="text-sm text-muted-foreground line-clamp-1">
            {notification.subject}
          </p>

          <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
            <span>
              Value:{' '}
              <span className="font-medium text-foreground">
                {isSentiment
                  ? notification.triggeredValue.toFixed(2)
                  : `${notification.triggeredValue.toFixed(1)}%`}
              </span>
            </span>
            <span>
              Threshold:{' '}
              <span className="font-medium text-foreground">
                {isSentiment
                  ? notification.thresholdValue.toFixed(2)
                  : `${notification.thresholdValue.toFixed(1)}%`}
              </span>
            </span>
            <span>{formatRelativeTime(notification.sentAt)}</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// Status badge
function StatusBadge({ status }: { status: Notification['status'] }) {
  const config = {
    sent: {
      icon: Mail,
      text: 'Sent',
      className: 'bg-green-500/10 text-green-500',
    },
    failed: {
      icon: XCircle,
      text: 'Failed',
      className: 'bg-red-500/10 text-red-500',
    },
    pending: {
      icon: Clock,
      text: 'Pending',
      className: 'bg-muted text-muted-foreground',
    },
  }[status];

  const Icon = config.icon;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs',
        config.className
      )}
    >
      <Icon className="w-3 h-3" />
      {config.text}
    </span>
  );
}

// Recent triggers list
interface RecentTriggersProps {
  notifications: Notification[];
  onViewAll?: () => void;
  className?: string;
}

export function RecentTriggers({
  notifications,
  onViewAll,
  className,
}: RecentTriggersProps) {
  if (notifications.length === 0) {
    return (
      <div className={cn('text-center py-6', className)}>
        <Bell className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">No recent triggers</p>
      </div>
    );
  }

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-foreground">Recent Triggers</h3>
        {onViewAll && (
          <button
            onClick={onViewAll}
            className="text-xs text-accent hover:underline"
          >
            View all
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {notifications.slice(0, 5).map((notification) => (
          <TriggerBadge key={notification.notificationId} notification={notification} />
        ))}
      </div>
    </div>
  );
}

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
