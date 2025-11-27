'use client';

import { memo } from 'react';
import { motion } from 'framer-motion';
import { Settings, Trash2, MoreVertical, TrendingUp, Clock } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { Configuration } from '@/types/config';
import { cn } from '@/lib/utils';

interface ConfigCardProps {
  config: Configuration;
  isActive?: boolean;
  onSelect?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  className?: string;
}

export const ConfigCard = memo(function ConfigCard({
  config,
  isActive = false,
  onSelect,
  onEdit,
  onDelete,
  className,
}: ConfigCardProps) {
  const tickerCount = config.tickers.length;

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
          'relative overflow-hidden cursor-pointer transition-all',
          'hover:border-accent/50',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          isActive && 'border-accent ring-1 ring-accent/30',
          className
        )}
        onClick={onSelect}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && onSelect) {
            e.preventDefault();
            onSelect();
          }
        }}
        role="button"
        tabIndex={0}
        aria-pressed={isActive}
        aria-label={`Configuration: ${config.name}. ${config.tickers.length} ticker${config.tickers.length !== 1 ? 's' : ''}: ${config.tickers.map((t) => t.symbol).join(', ')}.${isActive ? ' Currently active.' : ''}`}
      >
        {/* Active indicator */}
        {isActive && (
          <motion.div
            className="absolute left-0 top-0 bottom-0 w-1 bg-accent"
            layoutId="activeIndicator"
          />
        )}

        <div className="p-4">
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-foreground truncate">
                {config.name}
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                {tickerCount} ticker{tickerCount !== 1 ? 's' : ''}
              </p>
            </div>

            {/* Actions menu */}
            <div className="flex items-center gap-1 ml-2" role="group" aria-label="Configuration actions">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit?.();
                }}
                aria-label={`Edit ${config.name}`}
              >
                <Settings className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-500/10"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete?.();
                }}
                aria-label={`Delete ${config.name}`}
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          </div>

          {/* Tickers */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {config.tickers.slice(0, 5).map((ticker) => (
              <span
                key={ticker.symbol}
                className="px-2 py-0.5 text-xs font-medium rounded-full bg-muted text-muted-foreground"
              >
                {ticker.symbol}
              </span>
            ))}
            {config.tickers.length > 5 && (
              <span className="px-2 py-0.5 text-xs text-muted-foreground">
                +{config.tickers.length - 5} more
              </span>
            )}
          </div>

          {/* Sparkline placeholder */}
          <div className="h-8 bg-muted/30 rounded flex items-center justify-center">
            <Sparkline />
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between mt-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span>{config.timeframeDays}d</span>
            </div>
            <span>
              Updated {formatRelativeTime(config.updatedAt)}
            </span>
          </div>
        </div>
      </Card>
    </motion.div>
  );
});

// Simple sparkline placeholder
function Sparkline() {
  // Generate random sparkline points
  const points = Array.from({ length: 12 }, () => Math.random() * 100);
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = max - min || 1;

  const pathD = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * 100;
      const y = 100 - ((p - min) / range) * 100;
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');

  return (
    <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
      <path
        d={pathD}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        className="text-accent/50"
      />
    </svg>
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

// Compact card variant for lists
interface ConfigCardCompactProps {
  config: Configuration;
  isActive?: boolean;
  onSelect?: () => void;
  className?: string;
}

export function ConfigCardCompact({
  config,
  isActive = false,
  onSelect,
  className,
}: ConfigCardCompactProps) {
  return (
    <motion.button
      type="button"
      className={cn(
        'w-full text-left p-3 rounded-lg transition-colors',
        'hover:bg-muted/50',
        isActive && 'bg-accent/10 border border-accent/30',
        className
      )}
      onClick={onSelect}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'w-2 h-2 rounded-full',
            isActive ? 'bg-accent' : 'bg-muted-foreground/30'
          )}
        />
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm truncate">{config.name}</p>
          <p className="text-xs text-muted-foreground">
            {config.tickers.map((t) => t.symbol).join(', ')}
          </p>
        </div>
        <TrendingUp className="h-4 w-4 text-muted-foreground" />
      </div>
    </motion.button>
  );
}
