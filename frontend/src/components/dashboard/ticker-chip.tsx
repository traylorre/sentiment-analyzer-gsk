'use client';

import { motion } from 'framer-motion';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getSentimentColor, formatSentimentScore } from '@/lib/utils';
import { useHaptic } from '@/hooks/use-haptic';

interface TickerChipProps {
  symbol: string;
  name?: string;
  score?: number;
  isActive?: boolean;
  isLoading?: boolean;
  removable?: boolean;
  onClick?: () => void;
  onRemove?: () => void;
  className?: string;
}

export function TickerChip({
  symbol,
  name,
  score,
  isActive = false,
  isLoading = false,
  removable = false,
  onClick,
  onRemove,
  className,
}: TickerChipProps) {
  const haptic = useHaptic();

  const handleClick = () => {
    haptic.light();
    onClick?.();
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    haptic.medium();
    onRemove?.();
  };

  return (
    <motion.button
      type="button"
      onClick={handleClick}
      disabled={isLoading}
      className={cn(
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all',
        'text-sm font-medium',
        isActive
          ? 'bg-accent/20 border-accent text-accent'
          : 'bg-card border-border text-foreground hover:border-accent/50',
        isLoading && 'opacity-50 cursor-wait',
        className
      )}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      layout
    >
      {/* Symbol */}
      <span className={cn('font-semibold', isActive && 'text-accent')}>
        {symbol}
      </span>

      {/* Score indicator */}
      {score !== undefined && !isLoading && (
        <motion.span
          className="text-xs font-medium px-1.5 py-0.5 rounded"
          style={{
            backgroundColor: `${getSentimentColor(score)}20`,
            color: getSentimentColor(score),
          }}
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 500 }}
        >
          {formatSentimentScore(score)}
        </motion.span>
      )}

      {/* Loading indicator */}
      {isLoading && (
        <div className="w-3 h-3 border border-accent border-t-transparent rounded-full animate-spin" />
      )}

      {/* Remove button */}
      {removable && !isLoading && (
        <motion.button
          type="button"
          onClick={handleRemove}
          className="ml-1 p-0.5 rounded-full hover:bg-destructive/20 hover:text-destructive transition-colors"
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
        >
          <X className="h-3 w-3" />
        </motion.button>
      )}
    </motion.button>
  );
}

interface TickerChipListProps {
  tickers: Array<{
    symbol: string;
    name?: string;
    score?: number;
    isLoading?: boolean;
  }>;
  activeSymbol?: string;
  onSelect?: (symbol: string) => void;
  onRemove?: (symbol: string) => void;
  removable?: boolean;
  className?: string;
}

export function TickerChipList({
  tickers,
  activeSymbol,
  onSelect,
  onRemove,
  removable = false,
  className,
}: TickerChipListProps) {
  return (
    <motion.div
      className={cn('flex flex-wrap gap-2', className)}
      layout
    >
      {tickers.map((ticker, index) => (
        <motion.div
          key={ticker.symbol}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          transition={{ delay: index * 0.05 }}
          layout
        >
          <TickerChip
            symbol={ticker.symbol}
            name={ticker.name}
            score={ticker.score}
            isActive={ticker.symbol === activeSymbol}
            isLoading={ticker.isLoading}
            removable={removable}
            onClick={() => onSelect?.(ticker.symbol)}
            onRemove={() => onRemove?.(ticker.symbol)}
          />
        </motion.div>
      ))}
    </motion.div>
  );
}
