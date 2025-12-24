'use client';

import { useState, useCallback, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp } from 'lucide-react';
import { TickerInput } from '@/components/dashboard/ticker-input';
import { TickerChipList } from '@/components/dashboard/ticker-chip';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartSkeleton } from '@/components/ui/loading-skeleton';
import { PageTransition, AnimatedContainer } from '@/components/layout/page-transition';
import { useHaptic } from '@/hooks/use-haptic';
import type { TickerSearchResult } from '@/lib/api/tickers';

// Dynamic import for heavy chart component - reduces initial bundle size
const PriceSentimentChart = dynamic(
  () => import('@/components/charts/price-sentiment-chart').then((mod) => ({ default: mod.PriceSentimentChart })),
  {
    loading: () => <ChartSkeleton />,
    ssr: false, // Lightweight Charts requires browser APIs
  }
);

interface TickerInfo {
  symbol: string;
  name: string;
}

export default function DashboardPage() {
  const [tickers, setTickers] = useState<TickerInfo[]>([]);
  const [activeTicker, setActiveTicker] = useState<string | null>(null);
  const haptic = useHaptic();

  // Handle ticker selection from search
  const handleTickerSelect = useCallback(
    (ticker: TickerSearchResult) => {
      // Check if already added
      if (tickers.some((t) => t.symbol === ticker.symbol)) {
        setActiveTicker(ticker.symbol);
        return;
      }

      // Add new ticker
      setTickers((prev) => [...prev, { symbol: ticker.symbol, name: ticker.name }]);
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

  // Prepare ticker chips data (simplified - no scores needed, chart fetches its own data)
  const tickerChips = useMemo(
    () =>
      tickers.map((t) => ({
        symbol: t.symbol,
        name: t.name,
        score: 0, // Placeholder - PriceSentimentChart handles data fetching
        isLoading: false,
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
                Price & Sentiment Analysis
              </CardTitle>
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
        {activeTicker ? (
          <AnimatedContainer key={activeTicker} delay={0.2}>
            <Card className="glass">
              <CardContent className="pt-6">
                <PriceSentimentChart
                  ticker={activeTicker}
                  height={450}
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
                      Track Price & Sentiment
                    </h3>
                    <p className="text-muted-foreground max-w-md mx-auto">
                      Search for a ticker symbol above to view OHLC candlesticks
                      with sentiment overlay. Select time resolutions from 1-minute to daily.
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
