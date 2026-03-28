import { api } from './client';
import { snakeToCamel } from './transform';
import type { SentimentData, SentimentTimeSeries, SentimentSource } from '@/types/sentiment';

export interface SentimentHistoryParams {
  source?: SentimentSource;
  days?: number;
}

export const sentimentApi = {
  /**
   * Get current sentiment data for a configuration
   */
  get: (configId: string) =>
    api.get(`/api/v2/configurations/${configId}/sentiment`)
      .then((data) => snakeToCamel(data) as SentimentData),

  /**
   * Get sentiment time series history for a specific ticker
   */
  getHistory: (configId: string, ticker: string, params?: SentimentHistoryParams) =>
    api.get<SentimentTimeSeries[]>(
      `/api/v2/configurations/${configId}/sentiment/${ticker}/history`,
      { params: params as Record<string, string | number | boolean | undefined> }
    ),

  /**
   * Force refresh sentiment data for a configuration
   */
  refresh: (configId: string) =>
    api.post<SentimentData>(`/api/v2/configurations/${configId}/refresh`),
};
