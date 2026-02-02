'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { tickersApi, type TickerSearchResult } from '@/lib/api/tickers';
import { useHaptic } from '@/hooks/use-haptic';

interface TickerInputProps {
  onSelect: (ticker: TickerSearchResult) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

export function TickerInput({
  onSelect,
  placeholder = 'Search tickers (e.g., AAPL)',
  className,
  disabled,
}: TickerInputProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const haptic = useHaptic();

  // Debounced search query
  const { data: results = [], isLoading } = useQuery({
    queryKey: ['ticker-search', query],
    queryFn: () => tickersApi.search(query, 5),
    enabled: query.length >= 1,
    staleTime: 30000, // Cache for 30 seconds
  });

  // Handle input change
  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.toUpperCase();
    setQuery(value);
    setIsOpen(value.length >= 1);
    setHighlightedIndex(0);
  }, []);

  // Handle ticker selection
  const handleSelect = useCallback(
    (ticker: TickerSearchResult) => {
      haptic.medium();
      onSelect(ticker);
      setQuery('');
      setIsOpen(false);
      inputRef.current?.blur();
    },
    [onSelect, haptic]
  );

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setHighlightedIndex((i) => Math.min(i + 1, results.length - 1));
          haptic.light();
          break;
        case 'ArrowUp':
          e.preventDefault();
          setHighlightedIndex((i) => Math.max(i - 1, 0));
          haptic.light();
          break;
        case 'Enter':
          e.preventDefault();
          if (results[highlightedIndex]) {
            handleSelect(results[highlightedIndex]);
          }
          break;
        case 'Escape':
          setIsOpen(false);
          inputRef.current?.blur();
          break;
      }
    },
    [isOpen, results, highlightedIndex, handleSelect, haptic]
  );

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        inputRef.current &&
        !inputRef.current.contains(e.target as Node) &&
        listRef.current &&
        !listRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className={cn('relative', className)}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-controls="ticker-search-listbox"
          aria-expanded={isOpen}
          aria-activedescendant={
            isOpen && results.length > 0
              ? `ticker-option-${results[highlightedIndex]?.symbol}`
              : undefined
          }
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => query.length >= 1 && setIsOpen(true)}
          placeholder={placeholder}
          className="pl-10 pr-10 bg-card border-border focus:border-accent focus:ring-accent"
          disabled={disabled}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="characters"
          spellCheck={false}
        />
        {query && (
          <button
            type="button"
            onClick={() => {
              setQuery('');
              setIsOpen(false);
              inputRef.current?.focus();
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Autocomplete dropdown */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            ref={listRef}
            role="listbox"
            id="ticker-search-listbox"
            aria-label="Ticker search results"
            className="absolute z-50 w-full mt-1 bg-card border border-border rounded-lg shadow-lg overflow-hidden"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.15 }}
          >
            {isLoading ? (
              <div className="p-4 text-center text-muted-foreground" role="status" aria-live="polite">
                <div className="inline-block w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                <span className="sr-only">Searching...</span>
              </div>
            ) : results.length > 0 ? (
              <ul className="max-h-60 overflow-auto py-1" role="presentation">
                {results.map((ticker, index) => (
                  <motion.li
                    key={ticker.symbol}
                    role="option"
                    id={`ticker-option-${ticker.symbol}`}
                    aria-selected={highlightedIndex === index}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.03 }}
                    onClick={() => handleSelect(ticker)}
                    onMouseEnter={() => setHighlightedIndex(index)}
                    className={cn(
                      'w-full px-4 py-2 text-left flex items-center justify-between transition-colors cursor-pointer',
                      highlightedIndex === index
                        ? 'bg-accent/10 text-accent'
                        : 'hover:bg-muted/50'
                    )}
                  >
                    <div>
                      <span className="font-medium">{ticker.symbol}</span>
                      <span className="ml-2 text-sm text-muted-foreground">
                        {ticker.name}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {ticker.exchange}
                    </span>
                  </motion.li>
                ))}
              </ul>
            ) : query.length >= 1 ? (
              <div className="p-4 text-center text-muted-foreground" role="status">
                No tickers found for &quot;{query}&quot;
              </div>
            ) : null}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Export alias for backwards compatibility
export { TickerInput as TickerSearch };
