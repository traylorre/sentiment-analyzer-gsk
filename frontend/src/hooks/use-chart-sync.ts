'use client';

import { useEffect, useRef, useCallback } from 'react';
import type { IChartApi, Time } from 'lightweight-charts';
import { create } from 'zustand';

// Store for syncing multiple charts
interface ChartSyncState {
  charts: Map<string, IChartApi>;
  syncGroups: Map<string, Set<string>>;
  crosshairTime: Time | null;

  registerChart: (id: string, chart: IChartApi, groupId?: string) => void;
  unregisterChart: (id: string) => void;
  setCrosshairTime: (time: Time | null, sourceId?: string) => void;
  syncTimeScale: (sourceId: string, range: { from: Time; to: Time }) => void;
}

export const useChartSyncStore = create<ChartSyncState>((set, get) => ({
  charts: new Map(),
  syncGroups: new Map(),
  crosshairTime: null,

  registerChart: (id, chart, groupId = 'default') => {
    const { charts, syncGroups } = get();
    const newCharts = new Map(charts);
    newCharts.set(id, chart);

    const newGroups = new Map(syncGroups);
    if (!newGroups.has(groupId)) {
      newGroups.set(groupId, new Set());
    }
    newGroups.get(groupId)!.add(id);

    set({ charts: newCharts, syncGroups: newGroups });
  },

  unregisterChart: (id) => {
    const { charts, syncGroups } = get();
    const newCharts = new Map(charts);
    newCharts.delete(id);

    const newGroups = new Map(syncGroups);
    newGroups.forEach((group) => group.delete(id));

    set({ charts: newCharts, syncGroups: newGroups });
  },

  setCrosshairTime: (time, sourceId) => {
    const { charts, syncGroups } = get();

    // Find which group the source belongs to
    let targetGroup: Set<string> | undefined;
    syncGroups.forEach((group) => {
      if (!sourceId || group.has(sourceId)) {
        targetGroup = group;
      }
    });

    if (!targetGroup) return;

    // Sync crosshair to all charts in the same group
    targetGroup.forEach((chartId) => {
      if (chartId !== sourceId) {
        const chart = charts.get(chartId);
        if (chart && time) {
          // Move crosshair to the same time
          const timeScale = chart.timeScale();
          const coordinate = timeScale.timeToCoordinate(time);
          if (coordinate !== null) {
            // Note: lightweight-charts doesn't have a direct setCrosshair API
            // This would require custom implementation
          }
        }
      }
    });

    set({ crosshairTime: time });
  },

  syncTimeScale: (sourceId, range) => {
    const { charts, syncGroups } = get();

    // Find which group the source belongs to
    let targetGroup: Set<string> | undefined;
    syncGroups.forEach((group) => {
      if (group.has(sourceId)) {
        targetGroup = group;
      }
    });

    if (!targetGroup) return;

    // Sync time scale to all charts in the same group
    targetGroup.forEach((chartId) => {
      if (chartId !== sourceId) {
        const chart = charts.get(chartId);
        if (chart) {
          chart.timeScale().setVisibleRange(range);
        }
      }
    });
  },
}));

// Hook for registering a chart with sync
interface UseChartSyncOptions {
  chartId: string;
  groupId?: string;
  syncCrosshair?: boolean;
  syncTimeScale?: boolean;
}

export function useChartSync(options: UseChartSyncOptions) {
  const { chartId, groupId = 'default', syncCrosshair = true, syncTimeScale = true } = options;
  const chartRef = useRef<IChartApi | null>(null);
  const { registerChart, unregisterChart, setCrosshairTime, syncTimeScale: syncRange } =
    useChartSyncStore();

  // Register chart when mounted
  const setChart = useCallback(
    (chart: IChartApi | null) => {
      if (chartRef.current) {
        unregisterChart(chartId);
      }

      chartRef.current = chart;

      if (chart) {
        registerChart(chartId, chart, groupId);

        // Subscribe to crosshair moves if syncing
        if (syncCrosshair) {
          chart.subscribeCrosshairMove((param) => {
            if (param.time) {
              setCrosshairTime(param.time as Time, chartId);
            }
          });
        }

        // Subscribe to visible range changes if syncing
        if (syncTimeScale) {
          chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
            if (range) {
              syncRange(chartId, range as { from: Time; to: Time });
            }
          });
        }
      }
    },
    [chartId, groupId, registerChart, unregisterChart, setCrosshairTime, syncRange, syncCrosshair, syncTimeScale]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      unregisterChart(chartId);
    };
  }, [chartId, unregisterChart]);

  return { setChart, chartRef };
}

// Hook to get synced crosshair time
export function useCrosshairTime() {
  return useChartSyncStore((state) => state.crosshairTime);
}

// Hook to sync multiple charts together (simplified version)
export function useSyncedCharts(chartIds: string[], groupId?: string) {
  const { registerChart, unregisterChart } = useChartSyncStore();
  const chartsRef = useRef<Map<string, IChartApi>>(new Map());

  const registerChartFn = useCallback(
    (id: string, chart: IChartApi) => {
      chartsRef.current.set(id, chart);
      registerChart(id, chart, groupId);
    },
    [groupId, registerChart]
  );

  useEffect(() => {
    return () => {
      chartIds.forEach((id) => unregisterChart(id));
    };
  }, [chartIds, unregisterChart]);

  return { registerChart: registerChartFn };
}
