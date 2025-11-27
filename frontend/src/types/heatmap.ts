import type { SentimentSource } from './sentiment';

export type TimePeriod = 'today' | '1w' | '1m' | '3m';
export type HeatMapView = 'sources' | 'timeperiods';

export interface HeatMapCell {
  source?: SentimentSource;      // For sources view
  period?: TimePeriod;           // For timeperiods view
  score: number;
  color: string;                 // Computed hex color
}

export interface HeatMapRow {
  ticker: string;
  cells: HeatMapCell[];
}

export interface HeatMapData {
  view: HeatMapView;
  matrix: HeatMapRow[];
  legend: {
    positive: { range: [number, number]; color: string };
    neutral: { range: [number, number]; color: string };
    negative: { range: [number, number]; color: string };
  };
}
