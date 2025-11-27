import { api } from './client';
import type { TickerConfig } from '@/types/config';

export interface TickerSearchResult {
  symbol: string;
  name: string;
  exchange: 'NYSE' | 'NASDAQ' | 'AMEX';
}

export interface TickerValidationResult {
  valid: TickerConfig[];
  invalid: string[];
}

export const tickersApi = {
  /**
   * Search for tickers by symbol or name
   */
  search: (query: string, limit?: number) =>
    api.get<TickerSearchResult[]>('/api/v2/tickers/search', {
      params: { q: query, limit },
    }),

  /**
   * Validate a list of ticker symbols
   */
  validate: (symbols: string[]) =>
    api.post<TickerValidationResult>('/api/v2/tickers/validate', { symbols }),

  /**
   * Get ticker details
   */
  get: (symbol: string) =>
    api.get<TickerConfig>(`/api/v2/tickers/${symbol}`),
};
