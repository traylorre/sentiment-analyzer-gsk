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
   * Validate a single ticker symbol
   */
  validate: (symbol: string) =>
    api.get<{ valid: boolean; ticker?: TickerConfig }>('/api/v2/tickers/validate', {
      params: { symbol },
    }),

  /**
   * Validate multiple ticker symbols (client-side batch)
   */
  validateMany: async (symbols: string[]): Promise<TickerValidationResult> => {
    const results = await Promise.all(
      symbols.map(async (symbol) => {
        try {
          const result = await tickersApi.validate(symbol);
          return { symbol, ...result };
        } catch {
          return { symbol, valid: false };
        }
      })
    );

    return {
      valid: results.filter((r) => r.valid && r.ticker).map((r) => r.ticker as TickerConfig),
      invalid: results.filter((r) => !r.valid).map((r) => r.symbol),
    };
  },
};
