export interface TickerConfig {
  symbol: string;
  name: string;
  exchange: 'NYSE' | 'NASDAQ' | 'AMEX';
}

export interface Configuration {
  configId: string;
  name: string;
  tickers: TickerConfig[];
  timeframeDays: number;
  includeExtendedHours: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ConfigurationList {
  configurations: Configuration[];
  maxAllowed: number;
}

export interface CreateConfigRequest {
  name: string;
  tickers: string[];          // Just symbols, backend validates
  timeframeDays: number;
  includeExtendedHours: boolean;
}

export interface UpdateConfigRequest {
  name?: string;
  tickers?: string[];
  timeframeDays?: number;
  includeExtendedHours?: boolean;
}
