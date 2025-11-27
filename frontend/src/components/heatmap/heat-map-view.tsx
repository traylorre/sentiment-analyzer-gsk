'use client';

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Grid3x3, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useChartStore } from '@/stores/chart-store';
import { useHaptic } from '@/hooks/use-haptic';
import { HeatMapGrid, CompactHeatMapGrid } from './heat-map-grid';
import { DetailedHeatMapLegend } from './heat-map-legend';
import type { HeatMapData, HeatMapCell, HeatMapView as HeatMapViewType, HeatMapRow } from '@/types/heatmap';
import type { SentimentSource, TickerSentiment } from '@/types/sentiment';

interface HeatMapViewProps {
  tickers: TickerSentiment[];
  onCellClick?: (ticker: string, cell: HeatMapCell) => void;
  isLoading?: boolean;
  className?: string;
}

export function HeatMapView({
  tickers,
  onCellClick,
  isLoading = false,
  className,
}: HeatMapViewProps) {
  const { heatMapView, setHeatMapView } = useChartStore();
  const haptic = useHaptic();

  // Transform tickers data into heat map format
  const heatMapData = useMemo((): HeatMapData => {
    const matrix: HeatMapRow[] = tickers.map((ticker) => {
      if (heatMapView === 'sources') {
        // Sources view: columns are data sources
        const cells: HeatMapCell[] = [
          {
            source: 'tiingo' as SentimentSource,
            score: ticker.sentiment.tiingo.score,
            color: '', // Will be computed by cell
          },
          {
            source: 'finnhub' as SentimentSource,
            score: ticker.sentiment.finnhub.score,
            color: '',
          },
          {
            source: 'our_model' as SentimentSource,
            score: ticker.sentiment.ourModel.score,
            color: '',
          },
        ];
        return { ticker: ticker.symbol, cells };
      } else {
        // Time periods view: would need historical data
        // For now, show placeholder with mock data
        const cells: HeatMapCell[] = [
          { period: 'today', score: ticker.sentiment.tiingo.score, color: '' },
          { period: '1w', score: ticker.sentiment.tiingo.score * 0.9, color: '' },
          { period: '1m', score: ticker.sentiment.tiingo.score * 0.8, color: '' },
          { period: '3m', score: ticker.sentiment.tiingo.score * 0.7, color: '' },
        ];
        return { ticker: ticker.symbol, cells };
      }
    });

    return {
      view: heatMapView,
      matrix,
      legend: {
        positive: { range: [0.33, 1], color: '#22C55E' },
        neutral: { range: [-0.33, 0.33], color: '#EAB308' },
        negative: { range: [-1, -0.33], color: '#EF4444' },
      },
    };
  }, [tickers, heatMapView]);

  const handleViewToggle = (view: HeatMapViewType) => {
    haptic.light();
    setHeatMapView(view);
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* View toggle */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">
          Sentiment Heat Map
        </h3>

        <ViewToggle
          activeView={heatMapView}
          onViewChange={handleViewToggle}
        />
      </div>

      {/* Legend */}
      <DetailedHeatMapLegend />

      {/* Grid */}
      <AnimatePresence mode="wait">
        <motion.div
          key={heatMapView}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
        >
          {/* Desktop grid */}
          <div className="hidden sm:block">
            <HeatMapGrid
              data={heatMapData}
              onCellClick={onCellClick}
              isLoading={isLoading}
            />
          </div>

          {/* Mobile compact grid */}
          <div className="sm:hidden">
            <CompactHeatMapGrid
              data={heatMapData}
              onCellClick={onCellClick}
            />
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// View toggle component
interface ViewToggleProps {
  activeView: HeatMapViewType;
  onViewChange: (view: HeatMapViewType) => void;
}

function ViewToggle({ activeView, onViewChange }: ViewToggleProps) {
  const views: { id: HeatMapViewType; label: string; icon: typeof Grid3x3 }[] = [
    { id: 'sources', label: 'Sources', icon: Grid3x3 },
    { id: 'timeperiods', label: 'Time', icon: Calendar },
  ];

  return (
    <div className="flex items-center p-1 bg-muted rounded-lg">
      {views.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => onViewChange(id)}
          className={cn(
            'relative flex items-center gap-1.5 px-3 py-1.5 rounded-md',
            'text-sm font-medium transition-colors',
            activeView === id
              ? 'text-foreground'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          {activeView === id && (
            <motion.div
              layoutId="view-toggle-bg"
              className="absolute inset-0 bg-card rounded-md shadow-sm"
              transition={{ type: 'spring', stiffness: 500, damping: 30 }}
            />
          )}
          <Icon className="relative z-10 w-4 h-4" />
          <span className="relative z-10 hidden sm:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}

// Empty state
export function HeatMapEmptyState({ className }: { className?: string }) {
  return (
    <div className={cn('text-center py-12', className)}>
      <Grid3x3 className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
      <h3 className="text-lg font-semibold text-foreground mb-2">
        No sentiment data
      </h3>
      <p className="text-muted-foreground max-w-sm mx-auto">
        Add tickers to your configuration to see sentiment data visualized in a heat map.
      </p>
    </div>
  );
}
