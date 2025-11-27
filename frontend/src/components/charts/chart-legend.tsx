'use client';

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface LegendItem {
  label: string;
  color: string;
  value?: string | number;
  active?: boolean;
  onClick?: () => void;
}

interface ChartLegendProps {
  items: LegendItem[];
  orientation?: 'horizontal' | 'vertical';
  size?: 'sm' | 'md';
  className?: string;
}

export function ChartLegend({
  items,
  orientation = 'horizontal',
  size = 'md',
  className,
}: ChartLegendProps) {
  const sizeStyles = {
    sm: 'text-xs gap-3',
    md: 'text-sm gap-4',
  };

  const dotSizes = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
  };

  return (
    <div
      className={cn(
        'flex items-center',
        orientation === 'vertical' && 'flex-col items-start',
        sizeStyles[size],
        className
      )}
    >
      {items.map((item, index) => (
        <motion.button
          key={item.label}
          onClick={item.onClick}
          disabled={!item.onClick}
          className={cn(
            'flex items-center gap-2 transition-opacity',
            item.onClick && 'cursor-pointer hover:opacity-80',
            item.active === false && 'opacity-40'
          )}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: item.active === false ? 0.4 : 1, x: 0 }}
          transition={{ delay: index * 0.05 }}
        >
          {/* Color dot */}
          <motion.div
            className={cn('rounded-full', dotSizes[size])}
            style={{ backgroundColor: item.color }}
            animate={{
              scale: item.active === false ? 0.8 : 1,
            }}
          />

          {/* Label */}
          <span className="text-muted-foreground">{item.label}</span>

          {/* Value */}
          {item.value !== undefined && (
            <span className="font-medium text-foreground">{item.value}</span>
          )}
        </motion.button>
      ))}
    </div>
  );
}

// Sentiment scale legend
export function SentimentScaleLegend({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="text-xs text-muted-foreground">Bearish</span>
      <div className="flex-1 h-2 rounded-full overflow-hidden bg-gradient-to-r from-red-500 via-yellow-500 to-green-500" />
      <span className="text-xs text-muted-foreground">Bullish</span>
    </div>
  );
}

// ATR volatility legend
export function ATRLegend({ className }: { className?: string }) {
  const items = [
    { label: 'Low', color: '#22C55E' },
    { label: 'Medium', color: '#EAB308' },
    { label: 'High', color: '#EF4444' },
  ];

  return (
    <ChartLegend items={items} size="sm" className={className} />
  );
}

// Source color legend
interface SourceLegendProps {
  sources: Array<{ name: string; color: string; active?: boolean }>;
  onToggle?: (source: string) => void;
  className?: string;
}

export function SourceLegend({ sources, onToggle, className }: SourceLegendProps) {
  const items: LegendItem[] = sources.map((source) => ({
    label: source.name,
    color: source.color,
    active: source.active,
    onClick: onToggle ? () => onToggle(source.name) : undefined,
  }));

  return <ChartLegend items={items} className={className} />;
}

// Time range selector (styled like a legend)
interface TimeRangeOption {
  label: string;
  value: string;
}

interface TimeRangeLegendProps {
  options: TimeRangeOption[];
  selected: string;
  onChange: (value: string) => void;
  className?: string;
}

export function TimeRangeLegend({
  options,
  selected,
  onChange,
  className,
}: TimeRangeLegendProps) {
  return (
    <div className={cn('flex items-center gap-1', className)}>
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            'px-3 py-1 rounded-lg text-xs font-medium transition-all',
            selected === option.value
              ? 'bg-accent text-background'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

// Mini chart key for compact displays
interface ChartKeyProps {
  items: Array<{
    type: 'line' | 'bar' | 'area' | 'dot';
    color: string;
    label: string;
  }>;
  className?: string;
}

export function ChartKey({ items, className }: ChartKeyProps) {
  return (
    <div className={cn('flex items-center gap-4 text-xs', className)}>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          {item.type === 'line' && (
            <div className="w-4 h-0.5 rounded-full" style={{ backgroundColor: item.color }} />
          )}
          {item.type === 'bar' && (
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: item.color }} />
          )}
          {item.type === 'area' && (
            <div
              className="w-3 h-3 rounded-sm"
              style={{
                background: `linear-gradient(180deg, ${item.color}, transparent)`,
              }}
            />
          )}
          {item.type === 'dot' && (
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
          )}
          <span className="text-muted-foreground">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
