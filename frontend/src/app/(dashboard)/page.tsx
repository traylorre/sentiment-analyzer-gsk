'use client';

import { useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, RefreshCw } from 'lucide-react';
import { TickerInput } from '@/components/dashboard/ticker-input';
import { TickerChipList } from '@/components/dashboard/ticker-chip';
import { SentimentChart } from '@/components/charts/sentiment-chart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChartSkeleton } from '@/components/ui/loading-skeleton';
import { PageTransition, AnimatedContainer } from '@/components/layout/page-transition';
import { cn } from '@/lib/utils';
import { useHaptic } from '@/hooks/use-haptic';
import type { TickerSearchResult } from '@/lib/api/tickers';
import type { SentimentTimeSeries } from '@/types/sentiment';

// Mock data for demo (will be replaced with real API calls)
const generateMockData = (days: number = 30): SentimentTimeSeries[] => {
  const data: SentimentTimeSeries[] = [];
  const now = Date.now();
  let value = 0;

  for (let i = days; i >= 0; i--) {
    // Random walk with mean reversion
    value += (Math.random() - 0.5) * 0.2;
    value = Math.max(-1, Math.min(1, value));
    value = value * 0.95; // Mean reversion

    data.push({
      timestamp: new Date(now - i * 24 * 60 * 60 * 1000).toISOString(),
      score: value + (Math.random() - 0.5) * 0.1,
      source: 'our_model',
    });
  }

  return data;
};

interface TickerData {
  symbol: string;
  name: string;
  data: SentimentTimeSeries[];
  latestScore: number;
  isLoading: boolean;
}

export default function DashboardPage() {
  const [tickers, setTickers] = useState<TickerData[]>([]);
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const haptic = useHaptic();

  // Handle ticker selection from search
  const handleTickerSelect = useCallback(
    (ticker: TickerSearchResult) => {
      // Check if already added
      if (tickers.some((t) => t.symbol === ticker.symbol)) {
        setActiveTicker(ticker.symbol);
        return;
      }

      // Add new ticker with mock data
      const mockData = generateMockData();
      const newTicker: TickerData = {
        symbol: ticker.symbol,
        name: ticker.name,
        data: mockData,
        latestScore: mockData[mockData.length - 1].score,
        isLoading: false,
      };

      setTickers((prev) => [...prev, newTicker]);
      setActiveTicker(ticker.symbol);
      haptic.medium();
    },
    [tickers, haptic]
  );

  // Handle ticker chip click
  const handleTickerClick = useCallback((symbol: string) => {
    setActiveTicker(symbol);
  }, []);

  // Handle ticker removal
  const handleTickerRemove = useCallback(
    (symbol: string) => {
      setTickers((prev) => prev.filter((t) => t.symbol !== symbol));
      if (activeTicker === symbol) {
        setActiveTicker(tickers.length > 1 ? tickers[0].symbol : null);
      }
      haptic.medium();
    },
    [activeTicker, tickers, haptic]
  );

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    haptic.light();

    // Simulate refresh delay
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Update all tickers with new mock data
    setTickers((prev) =>
      prev.map((t) => {
        const newData = generateMockData();
        return {
          ...t,
          data: newData,
          latestScore: newData[newData.length - 1].score,
        };
      })
    );

    setIsRefreshing(false);
    haptic.medium();
  }, [haptic]);

  // Get active ticker data
  const activeTickerData = useMemo(
    () => tickers.find((t) => t.symbol === activeTicker),
    [tickers, activeTicker]
  );

  // Prepare ticker chips data
  const tickerChips = useMemo(
    () =>
      tickers.map((t) => ({
        symbol: t.symbol,
        name: t.name,
        score: t.latestScore,
        isLoading: t.isLoading,
      })),
    [tickers]
  );

  return (
    <PageTransition className="space-y-6">
      {/* Search and ticker chips */}
      <AnimatedContainer delay={0.1}>
        <Card className="glass">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-accent" />
                Sentiment Analysis
              </CardTitle>
              {tickers.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                  className="text-muted-foreground hover:text-accent"
                >
                  <RefreshCw
                    className={cn('h-4 w-4', isRefreshing && 'animate-spin')}
                  />
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <TickerInput
              onSelect={handleTickerSelect}
              placeholder="Search tickers (e.g., AAPL, MSFT, GOOGL)"
            />

            {tickers.length > 0 && (
              <TickerChipList
                tickers={tickerChips}
                activeSymbol={activeTicker ?? undefined}
                onSelect={handleTickerClick}
                onRemove={handleTickerRemove}
                removable
              />
            )}
          </CardContent>
        </Card>
      </AnimatedContainer>

      {/* Chart section */}
      <AnimatePresence mode="wait">
        {activeTickerData ? (
          <AnimatedContainer key={activeTickerData.symbol} delay={0.2}>
            <Card className="glass">
              <CardContent className="pt-6">
                <SentimentChart
                  data={activeTickerData.data}
                  ticker={activeTickerData.symbol}
                  height={350}
                />
              </CardContent>
            </Card>
          </AnimatedContainer>
        ) : tickers.length === 0 ? (
          <AnimatedContainer delay={0.2}>
            <Card className="glass">
              <CardContent className="py-12">
                <motion.div
                  className="text-center space-y-4"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.3 }}
                >
                  <div className="w-16 h-16 mx-auto rounded-full bg-accent/10 flex items-center justify-center">
                    <TrendingUp className="h-8 w-8 text-accent" />
                  </div>
                  <div className="space-y-2">
                    <h3 className="text-xl font-semibold text-foreground">
                      Track Sentiment
                    </h3>
                    <p className="text-muted-foreground max-w-md mx-auto">
                      Search for a ticker symbol above to view real-time sentiment
                      analysis from multiple sources.
                    </p>
                  </div>
                </motion.div>
              </CardContent>
            </Card>
          </AnimatedContainer>
        ) : (
          <AnimatedContainer delay={0.2}>
            <Card className="glass">
              <CardContent className="pt-6">
                <ChartSkeleton />
              </CardContent>
            </Card>
          </AnimatedContainer>
        )}
      </AnimatePresence>
    </PageTransition>
  );
}
