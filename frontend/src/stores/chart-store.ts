import { create } from 'zustand';
import type { SentimentSource } from '@/types/sentiment';
import type { HeatMapView } from '@/types/heatmap';

interface ChartState {
  // Active chart
  activeConfigId: string | null;
  activeTicker: string | null;
  activeSource: SentimentSource | null;

  // Interaction
  isScrubbing: boolean;
  scrubPosition: number | null;   // X position as percentage (0-100)
  scrubValue: number | null;      // Sentiment value at scrub position
  scrubTimestamp: string | null;

  // Heat map
  heatMapView: HeatMapView;
  hoveredCell: { ticker: string; source: string } | null;

  // Actions
  setActiveConfig: (configId: string | null) => void;
  setActiveTicker: (ticker: string | null) => void;
  setActiveSource: (source: SentimentSource | null) => void;
  startScrub: (position: number) => void;
  updateScrub: (position: number, value: number, timestamp: string) => void;
  endScrub: () => void;
  setHeatMapView: (view: HeatMapView) => void;
  setHoveredCell: (cell: ChartState['hoveredCell']) => void;
  reset: () => void;
}

const initialState = {
  activeConfigId: null,
  activeTicker: null,
  activeSource: null,
  isScrubbing: false,
  scrubPosition: null,
  scrubValue: null,
  scrubTimestamp: null,
  heatMapView: 'sources' as HeatMapView,
  hoveredCell: null,
};

export const useChartStore = create<ChartState>((set) => ({
  ...initialState,

  setActiveConfig: (configId) => {
    set({ activeConfigId: configId });
  },

  setActiveTicker: (ticker) => {
    set({ activeTicker: ticker });
  },

  setActiveSource: (source) => {
    set({ activeSource: source });
  },

  startScrub: (position) => {
    set({
      isScrubbing: true,
      scrubPosition: position,
    });
  },

  updateScrub: (position, value, timestamp) => {
    set({
      scrubPosition: position,
      scrubValue: value,
      scrubTimestamp: timestamp,
    });
  },

  endScrub: () => {
    set({
      isScrubbing: false,
      scrubPosition: null,
      scrubValue: null,
      scrubTimestamp: null,
    });
  },

  setHeatMapView: (view) => {
    set({ heatMapView: view });
  },

  setHoveredCell: (cell) => {
    set({ hoveredCell: cell });
  },

  reset: () => {
    set(initialState);
  },
}));
