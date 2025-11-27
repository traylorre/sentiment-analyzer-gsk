'use client';

import { useState, useCallback, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, TrendingUp, TrendingDown, Activity, AlertCircle, Bell } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import type { AlertRule, AlertType, ThresholdDirection, CreateAlertRequest } from '@/types/alert';
import type { Configuration } from '@/types/config';
import { cn } from '@/lib/utils';

interface AlertFormProps {
  isOpen: boolean;
  editingAlert?: AlertRule | null;
  configurations: Configuration[];
  onClose: () => void;
  onSubmit: (data: CreateAlertRequest) => void;
  isLoading?: boolean;
}

export function AlertForm({
  isOpen,
  editingAlert,
  configurations,
  onClose,
  onSubmit,
  isLoading = false,
}: AlertFormProps) {
  const isEditing = !!editingAlert;

  // Form state
  const [configId, setConfigId] = useState<string>('');
  const [ticker, setTicker] = useState<string>('');
  const [alertType, setAlertType] = useState<AlertType>('sentiment_threshold');
  const [thresholdValue, setThresholdValue] = useState<number>(0.5);
  const [thresholdDirection, setThresholdDirection] = useState<ThresholdDirection>('above');
  const [error, setError] = useState<string | null>(null);

  // Get available tickers from selected config
  const availableTickers = useMemo(() => {
    const config = configurations.find((c) => c.configId === configId);
    return config?.tickers ?? [];
  }, [configurations, configId]);

  // Initialize form when editing
  useEffect(() => {
    if (editingAlert) {
      setConfigId(editingAlert.configId);
      setTicker(editingAlert.ticker);
      setAlertType(editingAlert.alertType);
      setThresholdValue(editingAlert.thresholdValue);
      setThresholdDirection(editingAlert.thresholdDirection);
    } else {
      // Reset for create mode
      setConfigId(configurations[0]?.configId ?? '');
      setTicker('');
      setAlertType('sentiment_threshold');
      setThresholdValue(0.5);
      setThresholdDirection('above');
    }
    setError(null);
  }, [editingAlert, isOpen, configurations]);

  // Update ticker when config changes
  useEffect(() => {
    if (!isEditing && availableTickers.length > 0 && !availableTickers.some(t => t.symbol === ticker)) {
      setTicker(availableTickers[0].symbol);
    }
  }, [availableTickers, ticker, isEditing]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();

      if (!configId) {
        setError('Please select a configuration');
        return;
      }

      if (!ticker) {
        setError('Please select a ticker');
        return;
      }

      onSubmit({
        configId,
        ticker,
        alertType,
        thresholdValue,
        thresholdDirection,
      });
    },
    [configId, ticker, alertType, thresholdValue, thresholdDirection, onSubmit]
  );

  // Threshold range based on alert type
  const thresholdConfig = useMemo(() => {
    if (alertType === 'sentiment_threshold') {
      return { min: -1, max: 1, step: 0.01, format: (v: number) => v.toFixed(2) };
    }
    return { min: 0, max: 100, step: 0.5, format: (v: number) => `${v.toFixed(1)}%` };
  }, [alertType]);

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
                <div className="flex items-center gap-2">
                  <Bell className="w-5 h-5 text-accent" />
                  <h2 className="text-lg font-semibold text-foreground">
                    {isEditing ? 'Edit Alert' : 'New Alert'}
                  </h2>
                </div>
                <button
                  onClick={onClose}
                  className="p-1 rounded-md hover:bg-muted transition-colors"
                  disabled={isLoading}
                >
                  <X className="w-5 h-5 text-muted-foreground" />
                </button>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="p-4 space-y-5">
                {/* Configuration selector */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Configuration
                  </label>
                  <select
                    value={configId}
                    onChange={(e) => setConfigId(e.target.value)}
                    disabled={isLoading || isEditing}
                    className="w-full px-3 py-2 rounded-md border border-border bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-accent"
                  >
                    <option value="">Select a configuration...</option>
                    {configurations.map((config) => (
                      <option key={config.configId} value={config.configId}>
                        {config.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Ticker selector */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Ticker
                  </label>
                  <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                    {availableTickers.map((t) => (
                      <button
                        key={t.symbol}
                        type="button"
                        onClick={() => setTicker(t.symbol)}
                        disabled={isLoading || isEditing}
                        className={cn(
                          'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                          ticker === t.symbol
                            ? 'bg-accent text-accent-foreground'
                            : 'bg-muted text-muted-foreground hover:bg-muted/80',
                          (isLoading || isEditing) && 'opacity-50 cursor-not-allowed'
                        )}
                      >
                        {t.symbol}
                      </button>
                    ))}
                  </div>
                  {availableTickers.length === 0 && configId && (
                    <p className="text-sm text-muted-foreground">
                      No tickers in selected configuration
                    </p>
                  )}
                </div>

                {/* Alert type selector */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Alert Type
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        setAlertType('sentiment_threshold');
                        setThresholdValue(0.5);
                      }}
                      disabled={isLoading}
                      className={cn(
                        'flex items-center gap-3 p-3 rounded-lg border transition-colors',
                        alertType === 'sentiment_threshold'
                          ? 'border-accent bg-accent/5'
                          : 'border-border hover:border-muted-foreground/50'
                      )}
                    >
                      <div className="w-10 h-10 rounded-full bg-blue-500/10 flex items-center justify-center">
                        <TrendingUp className="w-5 h-5 text-blue-500" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-sm">Sentiment</p>
                        <p className="text-xs text-muted-foreground">Score threshold</p>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setAlertType('volatility_threshold');
                        setThresholdValue(25);
                      }}
                      disabled={isLoading}
                      className={cn(
                        'flex items-center gap-3 p-3 rounded-lg border transition-colors',
                        alertType === 'volatility_threshold'
                          ? 'border-accent bg-accent/5'
                          : 'border-border hover:border-muted-foreground/50'
                      )}
                    >
                      <div className="w-10 h-10 rounded-full bg-purple-500/10 flex items-center justify-center">
                        <Activity className="w-5 h-5 text-purple-500" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-sm">Volatility</p>
                        <p className="text-xs text-muted-foreground">ATR threshold</p>
                      </div>
                    </button>
                  </div>
                </div>

                {/* Direction selector */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Trigger Direction
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setThresholdDirection('above')}
                      disabled={isLoading}
                      className={cn(
                        'flex items-center justify-center gap-2 p-3 rounded-lg border transition-colors',
                        thresholdDirection === 'above'
                          ? 'border-accent bg-accent/5'
                          : 'border-border hover:border-muted-foreground/50'
                      )}
                    >
                      <TrendingUp className="w-4 h-4" />
                      <span className="font-medium text-sm">Above</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setThresholdDirection('below')}
                      disabled={isLoading}
                      className={cn(
                        'flex items-center justify-center gap-2 p-3 rounded-lg border transition-colors',
                        thresholdDirection === 'below'
                          ? 'border-accent bg-accent/5'
                          : 'border-border hover:border-muted-foreground/50'
                      )}
                    >
                      <TrendingDown className="w-4 h-4" />
                      <span className="font-medium text-sm">Below</span>
                    </button>
                  </div>
                </div>

                {/* Threshold slider */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-foreground">
                      Threshold Value
                    </label>
                    <span className="text-lg font-bold text-accent">
                      {thresholdConfig.format(thresholdValue)}
                    </span>
                  </div>

                  <div className="space-y-2">
                    <input
                      type="range"
                      min={thresholdConfig.min}
                      max={thresholdConfig.max}
                      step={thresholdConfig.step}
                      value={thresholdValue}
                      onChange={(e) => setThresholdValue(parseFloat(e.target.value))}
                      disabled={isLoading}
                      className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-accent"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>{thresholdConfig.format(thresholdConfig.min)}</span>
                      <span>{thresholdConfig.format(thresholdConfig.max)}</span>
                    </div>
                  </div>

                  {/* Visual indicator */}
                  <div className="relative h-2 bg-muted rounded-full overflow-hidden">
                    <motion.div
                      className={cn(
                        'absolute h-full',
                        thresholdDirection === 'above'
                          ? 'right-0 bg-gradient-to-l from-accent to-accent/20'
                          : 'left-0 bg-gradient-to-r from-accent to-accent/20'
                      )}
                      initial={false}
                      animate={{
                        width: `${
                          ((thresholdValue - thresholdConfig.min) /
                            (thresholdConfig.max - thresholdConfig.min)) *
                          100
                        }%`,
                      }}
                      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    />
                  </div>
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
                    disabled={isLoading || !configId || !ticker}
                  >
                    {isLoading ? (
                      <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    ) : isEditing ? (
                      'Save Changes'
                    ) : (
                      'Create Alert'
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
