import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChartSyncStore } from '@/hooks/use-chart-sync';

// Mock lightweight-charts types
const createMockChart = () => ({
  timeScale: () => ({
    timeToCoordinate: vi.fn(),
    setVisibleRange: vi.fn(),
    subscribeVisibleTimeRangeChange: vi.fn(),
  }),
  subscribeCrosshairMove: vi.fn(),
});

describe('useChartSyncStore', () => {
  beforeEach(() => {
    // Reset store state
    useChartSyncStore.setState({
      charts: new Map(),
      syncGroups: new Map(),
      crosshairTime: null,
    });
  });

  describe('registerChart', () => {
    it('should register a chart', () => {
      const mockChart = createMockChart();
      const { registerChart } = useChartSyncStore.getState();

      registerChart('chart1', mockChart as any);

      const { charts } = useChartSyncStore.getState();
      expect(charts.has('chart1')).toBe(true);
    });

    it('should add chart to default group', () => {
      const mockChart = createMockChart();
      const { registerChart } = useChartSyncStore.getState();

      registerChart('chart1', mockChart as any);

      const { syncGroups } = useChartSyncStore.getState();
      expect(syncGroups.get('default')?.has('chart1')).toBe(true);
    });

    it('should add chart to specified group', () => {
      const mockChart = createMockChart();
      const { registerChart } = useChartSyncStore.getState();

      registerChart('chart1', mockChart as any, 'custom-group');

      const { syncGroups } = useChartSyncStore.getState();
      expect(syncGroups.get('custom-group')?.has('chart1')).toBe(true);
    });

    it('should register multiple charts to same group', () => {
      const mockChart1 = createMockChart();
      const mockChart2 = createMockChart();
      const { registerChart } = useChartSyncStore.getState();

      registerChart('chart1', mockChart1 as any, 'group1');
      registerChart('chart2', mockChart2 as any, 'group1');

      const { syncGroups } = useChartSyncStore.getState();
      const group = syncGroups.get('group1');
      expect(group?.size).toBe(2);
      expect(group?.has('chart1')).toBe(true);
      expect(group?.has('chart2')).toBe(true);
    });
  });

  describe('unregisterChart', () => {
    it('should remove chart from charts map', () => {
      const mockChart = createMockChart();
      const { registerChart, unregisterChart } = useChartSyncStore.getState();

      registerChart('chart1', mockChart as any);
      unregisterChart('chart1');

      const { charts } = useChartSyncStore.getState();
      expect(charts.has('chart1')).toBe(false);
    });

    it('should remove chart from sync groups', () => {
      const mockChart = createMockChart();
      const { registerChart, unregisterChart } = useChartSyncStore.getState();

      registerChart('chart1', mockChart as any, 'group1');
      unregisterChart('chart1');

      const { syncGroups } = useChartSyncStore.getState();
      expect(syncGroups.get('group1')?.has('chart1')).toBe(false);
    });
  });

  describe('setCrosshairTime', () => {
    it('should update crosshair time', () => {
      const mockChart = createMockChart();
      const { registerChart, setCrosshairTime } = useChartSyncStore.getState();
      const time = 1704067200 as any; // Unix timestamp

      // Need to register a chart first so the group exists
      registerChart('chart1', mockChart as any, 'default');
      setCrosshairTime(time);

      expect(useChartSyncStore.getState().crosshairTime).toBe(time);
    });

    it('should clear crosshair time when null', () => {
      const { setCrosshairTime } = useChartSyncStore.getState();

      setCrosshairTime(1704067200 as any);
      setCrosshairTime(null);

      expect(useChartSyncStore.getState().crosshairTime).toBeNull();
    });
  });

  describe('syncTimeScale', () => {
    it('should sync time scale to charts in same group', () => {
      const mockChart1 = createMockChart();
      const mockChart2 = createMockChart();
      const mockSetVisibleRange = vi.fn();
      mockChart2.timeScale = () => ({
        timeToCoordinate: vi.fn(),
        setVisibleRange: mockSetVisibleRange,
        subscribeVisibleTimeRangeChange: vi.fn(),
      });

      const { registerChart, syncTimeScale } = useChartSyncStore.getState();

      registerChart('chart1', mockChart1 as any, 'group1');
      registerChart('chart2', mockChart2 as any, 'group1');

      const range = { from: 1704067200 as any, to: 1704153600 as any };
      syncTimeScale('chart1', range);

      expect(mockSetVisibleRange).toHaveBeenCalledWith(range);
    });

    it('should not sync time scale to source chart', () => {
      const mockChart1 = createMockChart();
      const mockSetVisibleRange = vi.fn();
      mockChart1.timeScale = () => ({
        timeToCoordinate: vi.fn(),
        setVisibleRange: mockSetVisibleRange,
        subscribeVisibleTimeRangeChange: vi.fn(),
      });

      const { registerChart, syncTimeScale } = useChartSyncStore.getState();

      registerChart('chart1', mockChart1 as any, 'group1');

      const range = { from: 1704067200 as any, to: 1704153600 as any };
      syncTimeScale('chart1', range);

      // Should not be called because chart1 is the source
      expect(mockSetVisibleRange).not.toHaveBeenCalled();
    });

    it('should not sync to charts in different groups', () => {
      const mockChart1 = createMockChart();
      const mockChart2 = createMockChart();
      const mockSetVisibleRange = vi.fn();
      mockChart2.timeScale = () => ({
        timeToCoordinate: vi.fn(),
        setVisibleRange: mockSetVisibleRange,
        subscribeVisibleTimeRangeChange: vi.fn(),
      });

      const { registerChart, syncTimeScale } = useChartSyncStore.getState();

      registerChart('chart1', mockChart1 as any, 'group1');
      registerChart('chart2', mockChart2 as any, 'group2');

      const range = { from: 1704067200 as any, to: 1704153600 as any };
      syncTimeScale('chart1', range);

      // Should not be called because chart2 is in a different group
      expect(mockSetVisibleRange).not.toHaveBeenCalled();
    });
  });
});
