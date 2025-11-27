'use client';

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn, interpolateSentimentColor } from '@/lib/utils';
import { useChartStore } from '@/stores/chart-store';
import { HeatMapCell, HeatMapCellSkeleton, HeatMapEmptyCell } from './heat-map-cell';
import { HeatMapLegend } from './heat-map-legend';
import type { HeatMapData, HeatMapCell as HeatMapCellType, TimePeriod, HeatMapView } from '@/types/heatmap';
import type { SentimentSource } from '@/types/sentiment';

interface HeatMapGridProps {
  data: HeatMapData;
  onCellClick?: (ticker: string, cell: HeatMapCellType) => void;
  isLoading?: boolean;
  className?: string;
}

const SOURCE_LABELS: Record<SentimentSource, string> = {
  tiingo: 'Tiingo',
  finnhub: 'Finnhub',
  our_model: 'Our Model',
};

const PERIOD_LABELS: Record<TimePeriod, string> = {
  today: 'Today',
  '1w': '1 Week',
  '1m': '1 Month',
  '3m': '3 Months',
};

export function HeatMapGrid({
  data,
  onCellClick,
  isLoading = false,
  className,
}: HeatMapGridProps) {
  const [hoveredCell, setHoveredCell] = useState<{
    ticker: string;
    cell: HeatMapCellType;
  } | null>(null);

  const { heatMapView } = useChartStore();

  // Get column headers based on view
  const columnHeaders = useMemo(() => {
    if (data.view === 'sources') {
      return Object.entries(SOURCE_LABELS).map(([key, label]) => ({
        key,
        label,
      }));
    }
    return Object.entries(PERIOD_LABELS).map(([key, label]) => ({
      key,
      label,
    }));
  }, [data.view]);

  // Handle cell hover
  const handleCellHover = (ticker: string, cell: HeatMapCellType | null) => {
    if (cell) {
      setHoveredCell({ ticker, cell });
    } else {
      setHoveredCell(null);
    }
  };

  if (isLoading) {
    return (
      <div className={cn('space-y-4', className)}>
        {/* Header skeleton */}
        <div className="flex gap-2 ml-20">
          {[1, 2, 3].map((i) => (
            <div key={i} className="w-14 h-6 bg-muted rounded animate-pulse" />
          ))}
        </div>
        {/* Rows skeleton */}
        {[1, 2, 3, 4, 5].map((row) => (
          <div key={row} className="flex items-center gap-2">
            <div className="w-16 h-6 bg-muted rounded animate-pulse" />
            {[1, 2, 3].map((col) => (
              <HeatMapCellSkeleton key={col} />
            ))}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Legend */}
      <HeatMapLegend />

      {/* Grid */}
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-1">
          {/* Header row */}
          <thead>
            <tr>
              <th className="w-20 text-left text-xs font-medium text-muted-foreground p-2">
                Ticker
              </th>
              {columnHeaders.map(({ key, label }) => (
                <th
                  key={key}
                  className="text-center text-xs font-medium text-muted-foreground p-2 min-w-[56px]"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>

          {/* Data rows */}
          <tbody>
            <AnimatePresence mode="popLayout">
              {data.matrix.map((row, rowIndex) => (
                <motion.tr
                  key={row.ticker}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ delay: rowIndex * 0.05 }}
                >
                  {/* Ticker label */}
                  <td className="p-2">
                    <span className="font-semibold text-foreground text-sm">
                      {row.ticker}
                    </span>
                  </td>

                  {/* Cells */}
                  {row.cells.map((cell, cellIndex) => (
                    <td key={cellIndex} className="p-0.5">
                      {cell ? (
                        <HeatMapCell
                          data={cell}
                          ticker={row.ticker}
                          isHovered={
                            hoveredCell?.ticker === row.ticker &&
                            hoveredCell?.cell === cell
                          }
                          onClick={
                            onCellClick
                              ? () => onCellClick(row.ticker, cell)
                              : undefined
                          }
                          onHover={(c) => handleCellHover(row.ticker, c)}
                        />
                      ) : (
                        <HeatMapEmptyCell />
                      )}
                    </td>
                  ))}
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>

      {/* Hover tooltip */}
      <AnimatePresence>
        {hoveredCell && (
          <motion.div
            className="fixed z-50 pointer-events-none"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <HeatMapTooltip
              ticker={hoveredCell.ticker}
              cell={hoveredCell.cell}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Floating tooltip for hovered cell
interface HeatMapTooltipProps {
  ticker: string;
  cell: HeatMapCellType;
}

function HeatMapTooltip({ ticker, cell }: HeatMapTooltipProps) {
  const label = cell.source
    ? SOURCE_LABELS[cell.source]
    : cell.period
    ? PERIOD_LABELS[cell.period]
    : 'Unknown';

  return (
    <div
      className={cn(
        'px-3 py-2 rounded-lg',
        'bg-card/95 backdrop-blur-md',
        'border border-border shadow-xl'
      )}
    >
      <div className="flex items-center gap-3">
        <span className="font-semibold text-foreground">{ticker}</span>
        <span className="text-muted-foreground">{label}</span>
        <span
          className="font-bold"
          style={{ color: interpolateSentimentColor(cell.score) }}
        >
          {cell.score >= 0 ? '+' : ''}
          {cell.score.toFixed(2)}
        </span>
      </div>
    </div>
  );
}

// Compact grid for mobile
interface CompactHeatMapGridProps {
  data: HeatMapData;
  onCellClick?: (ticker: string, cell: HeatMapCellType) => void;
  className?: string;
}

export function CompactHeatMapGrid({
  data,
  onCellClick,
  className,
}: CompactHeatMapGridProps) {
  return (
    <div className={cn('space-y-2', className)}>
      {data.matrix.map((row) => (
        <div key={row.ticker} className="flex items-center gap-2">
          <span className="w-14 text-xs font-semibold text-foreground truncate">
            {row.ticker}
          </span>
          <div className="flex-1 flex gap-1">
            {row.cells.map((cell, index) => (
              <div
                key={index}
                className="flex-1 h-6 rounded"
                style={{ backgroundColor: interpolateSentimentColor(cell.score) }}
                onClick={() => onCellClick?.(row.ticker, cell)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
