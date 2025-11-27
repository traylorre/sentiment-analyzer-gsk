import { describe, it, expect, beforeEach } from 'vitest';
import { useChartStore } from '@/stores/chart-store';

describe('Chart Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useChartStore.getState().reset();
  });

  describe('setActiveConfig', () => {
    it('should update activeConfigId', () => {
      const { setActiveConfig } = useChartStore.getState();

      setActiveConfig('config-123');

      expect(useChartStore.getState().activeConfigId).toBe('config-123');
    });

    it('should accept null to clear', () => {
      const { setActiveConfig } = useChartStore.getState();

      setActiveConfig('config-123');
      setActiveConfig(null);

      expect(useChartStore.getState().activeConfigId).toBeNull();
    });
  });

  describe('setActiveTicker', () => {
    it('should update activeTicker', () => {
      const { setActiveTicker } = useChartStore.getState();

      setActiveTicker('AAPL');

      expect(useChartStore.getState().activeTicker).toBe('AAPL');
    });
  });

  describe('setActiveSource', () => {
    it('should update activeSource', () => {
      const { setActiveSource } = useChartStore.getState();

      setActiveSource('tiingo');

      expect(useChartStore.getState().activeSource).toBe('tiingo');
    });
  });

  describe('scrubbing', () => {
    it('should start scrubbing with position', () => {
      const { startScrub } = useChartStore.getState();

      startScrub(50);

      const state = useChartStore.getState();
      expect(state.isScrubbing).toBe(true);
      expect(state.scrubPosition).toBe(50);
    });

    it('should update scrub position, value, and timestamp', () => {
      const { startScrub, updateScrub } = useChartStore.getState();
      const timestamp = '2024-01-15T10:30:00Z';

      startScrub(50);
      updateScrub(75, 0.45, timestamp);

      const state = useChartStore.getState();
      expect(state.scrubPosition).toBe(75);
      expect(state.scrubValue).toBe(0.45);
      expect(state.scrubTimestamp).toBe(timestamp);
    });

    it('should end scrubbing and reset values', () => {
      const { startScrub, updateScrub, endScrub } = useChartStore.getState();

      startScrub(50);
      updateScrub(75, 0.45, '2024-01-15T10:30:00Z');
      endScrub();

      const state = useChartStore.getState();
      expect(state.isScrubbing).toBe(false);
      expect(state.scrubPosition).toBeNull();
      expect(state.scrubValue).toBeNull();
      expect(state.scrubTimestamp).toBeNull();
    });
  });

  describe('heat map', () => {
    it('should toggle heat map view', () => {
      const { setHeatMapView } = useChartStore.getState();

      expect(useChartStore.getState().heatMapView).toBe('sources');

      setHeatMapView('timeperiods');

      expect(useChartStore.getState().heatMapView).toBe('timeperiods');
    });

    it('should set hovered cell', () => {
      const { setHoveredCell } = useChartStore.getState();

      setHoveredCell({ ticker: 'AAPL', source: 'tiingo' });

      const state = useChartStore.getState();
      expect(state.hoveredCell).toEqual({ ticker: 'AAPL', source: 'tiingo' });
    });

    it('should clear hovered cell', () => {
      const { setHoveredCell } = useChartStore.getState();

      setHoveredCell({ ticker: 'AAPL', source: 'tiingo' });
      setHoveredCell(null);

      expect(useChartStore.getState().hoveredCell).toBeNull();
    });
  });

  describe('reset', () => {
    it('should reset all state to initial values', () => {
      const store = useChartStore.getState();

      store.setActiveConfig('config-123');
      store.setActiveTicker('AAPL');
      store.setActiveSource('tiingo');
      store.startScrub(50);
      store.setHeatMapView('timeperiods');

      store.reset();

      const state = useChartStore.getState();
      expect(state.activeConfigId).toBeNull();
      expect(state.activeTicker).toBeNull();
      expect(state.activeSource).toBeNull();
      expect(state.isScrubbing).toBe(false);
      expect(state.heatMapView).toBe('sources');
    });
  });
});
