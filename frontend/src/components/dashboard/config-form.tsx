'use client';

import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Plus, Trash2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { TickerSearch } from '@/components/dashboard/ticker-input';
import type { Configuration, CreateConfigRequest, UpdateConfigRequest } from '@/types/config';
import type { TickerConfig } from '@/types/config';
import { cn } from '@/lib/utils';

interface ConfigFormProps {
  isOpen: boolean;
  editingConfig?: Configuration | null;
  onClose: () => void;
  onSubmit: (data: CreateConfigRequest | UpdateConfigRequest) => void;
  isLoading?: boolean;
  maxTickers?: number;
}

export function ConfigForm({
  isOpen,
  editingConfig,
  onClose,
  onSubmit,
  isLoading = false,
  maxTickers = 5,
}: ConfigFormProps) {
  const isEditing = !!editingConfig;

  // Form state
  const [name, setName] = useState('');
  const [tickers, setTickers] = useState<TickerConfig[]>([]);
  const [timeframeDays, setTimeframeDays] = useState(7);
  const [includeExtendedHours, setIncludeExtendedHours] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize form when editing
  useEffect(() => {
    if (editingConfig) {
      setName(editingConfig.name);
      setTickers(editingConfig.tickers);
      setTimeframeDays(editingConfig.timeframeDays);
      setIncludeExtendedHours(editingConfig.includeExtendedHours);
    } else {
      // Reset for create mode
      setName('');
      setTickers([]);
      setTimeframeDays(7);
      setIncludeExtendedHours(false);
    }
    setError(null);
  }, [editingConfig, isOpen]);

  const handleAddTicker = useCallback(
    (ticker: TickerConfig) => {
      if (tickers.length >= maxTickers) {
        setError(`Maximum ${maxTickers} tickers allowed`);
        return;
      }
      if (tickers.some((t) => t.symbol === ticker.symbol)) {
        setError('Ticker already added');
        return;
      }
      setTickers((prev) => [...prev, ticker]);
      setError(null);
    },
    [tickers, maxTickers]
  );

  const handleRemoveTicker = useCallback((symbol: string) => {
    setTickers((prev) => prev.filter((t) => t.symbol !== symbol));
    setError(null);
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();

      if (!name.trim()) {
        setError('Configuration name is required');
        return;
      }

      if (tickers.length === 0) {
        setError('At least one ticker is required');
        return;
      }

      const data = {
        name: name.trim(),
        tickers: tickers.map((t) => t.symbol),
        timeframeDays,
        includeExtendedHours,
      };

      onSubmit(data);
    },
    [name, tickers, timeframeDays, includeExtendedHours, onSubmit]
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 p-4"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
          >
            <Card className="overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-border">
                <h2 className="text-lg font-semibold text-foreground">
                  {isEditing ? 'Edit Configuration' : 'New Configuration'}
                </h2>
                <button
                  onClick={onClose}
                  className="p-1 rounded-md hover:bg-muted transition-colors"
                  disabled={isLoading}
                >
                  <X className="w-5 h-5 text-muted-foreground" />
                </button>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="p-4 space-y-4">
                {/* Name */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Configuration Name
                  </label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="My Watchlist"
                    maxLength={50}
                    disabled={isLoading}
                  />
                </div>

                {/* Tickers */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-foreground">
                      Tickers
                    </label>
                    <span className="text-xs text-muted-foreground">
                      {tickers.length}/{maxTickers}
                    </span>
                  </div>

                  {/* Ticker list */}
                  <div className="flex flex-wrap gap-2 min-h-[36px]">
                    <AnimatePresence mode="popLayout">
                      {tickers.map((ticker) => (
                        <motion.div
                          key={ticker.symbol}
                          layout
                          initial={{ opacity: 0, scale: 0.8 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.8 }}
                          className="flex items-center gap-1 px-2 py-1 rounded-full bg-accent/10 text-accent"
                        >
                          <span className="text-sm font-medium">
                            {ticker.symbol}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleRemoveTicker(ticker.symbol)}
                            className="p-0.5 rounded-full hover:bg-accent/20"
                            disabled={isLoading}
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>

                  {/* Add ticker */}
                  {tickers.length < maxTickers && (
                    <TickerSearch
                      onSelect={handleAddTicker}
                      disabled={isLoading}
                      placeholder="Search for a ticker..."
                    />
                  )}
                </div>

                {/* Timeframe */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Timeframe
                  </label>
                  <div className="flex gap-2">
                    {[7, 14, 30].map((days) => (
                      <button
                        key={days}
                        type="button"
                        onClick={() => setTimeframeDays(days)}
                        disabled={isLoading}
                        className={cn(
                          'flex-1 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                          timeframeDays === days
                            ? 'bg-accent text-accent-foreground'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80'
                        )}
                      >
                        {days} days
                      </button>
                    ))}
                  </div>
                </div>

                {/* Extended hours toggle */}
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-foreground">
                    Include extended hours
                  </label>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={includeExtendedHours}
                    onClick={() => setIncludeExtendedHours(!includeExtendedHours)}
                    disabled={isLoading}
                    className={cn(
                      'relative w-11 h-6 rounded-full transition-colors',
                      includeExtendedHours ? 'bg-accent' : 'bg-muted'
                    )}
                  >
                    <span
                      className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                        includeExtendedHours ? 'left-6' : 'left-1'
                      )}
                    />
                  </button>
                </div>

                {/* Error message */}
                <AnimatePresence>
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="flex items-center gap-2 p-3 rounded-md bg-red-500/10 text-red-500 text-sm"
                    >
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      <span>{error}</span>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Actions */}
                <div className="flex gap-3 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    className="flex-1"
                    onClick={onClose}
                    disabled={isLoading}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    className="flex-1"
                    disabled={isLoading || !name.trim() || tickers.length === 0}
                  >
                    {isLoading ? (
                      <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    ) : isEditing ? (
                      'Save Changes'
                    ) : (
                      'Create'
                    )}
                  </Button>
                </div>
              </form>
            </Card>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
