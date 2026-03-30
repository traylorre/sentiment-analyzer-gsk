'use client';

import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { SCENARIO_NAMES, type TrendDataPoint, type ScenarioType, type Verdict } from '@/types/chaos';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const VERDICT_COLORS: Record<Verdict, string> = {
  CLEAN: 'rgba(34, 197, 94, 0.8)',
  DRY_RUN_CLEAN: 'rgba(59, 130, 246, 0.8)',
  INCONCLUSIVE: 'rgba(156, 163, 175, 0.8)',
  RECOVERY_INCOMPLETE: 'rgba(245, 158, 11, 0.8)',
  COMPROMISED: 'rgba(239, 68, 68, 0.8)',
};

interface TrendChartProps {
  data: TrendDataPoint[];
  scenario: string | null;
  scenarios: string[];
  limit: number;
  onScenarioChange: (scenario: string) => void;
  onLimitChange: (limit: number) => void;
  isLoading: boolean;
}

export function TrendChart({
  data,
  scenario,
  scenarios,
  limit,
  onScenarioChange,
  onLimitChange,
  isLoading,
}: TrendChartProps) {
  const chartData = useMemo(() => {
    if (data.length < 3) return null;

    const labels = data.map((d) =>
      new Date(d.created_at).toLocaleDateString()
    );

    const verdicts: Verdict[] = [
      'CLEAN', 'DRY_RUN_CLEAN', 'INCONCLUSIVE', 'RECOVERY_INCOMPLETE', 'COMPROMISED',
    ];

    const datasets = verdicts.map((verdict) => ({
      label: verdict.replace(/_/g, ' '),
      data: data.map((d) => (d.verdict === verdict ? 1 : 0)),
      backgroundColor: VERDICT_COLORS[verdict],
    }));

    return { labels, datasets };
  }, [data]);

  return (
    <Card data-testid="trend-chart">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-sm">Verdict Trends</CardTitle>
          <div className="flex gap-2">
            <select
              data-testid="trend-scenario-select"
              className="text-xs border border-border rounded px-2 py-1 bg-background"
              value={scenario ?? ''}
              onChange={(e) => onScenarioChange(e.target.value)}
            >
              <option value="">Select scenario</option>
              {scenarios.map((s) => (
                <option key={s} value={s}>
                  {SCENARIO_NAMES[s as ScenarioType] ?? s}
                </option>
              ))}
            </select>
            <select
              data-testid="trend-limit-select"
              className="text-xs border border-border rounded px-2 py-1 bg-background"
              value={limit}
              onChange={(e) => onLimitChange(Number(e.target.value))}
            >
              <option value={10}>Last 10</option>
              <option value={20}>Last 20</option>
              <option value={50}>Last 50</option>
            </select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {!scenario ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            Select a scenario to view trends.
          </p>
        ) : isLoading ? (
          <div className="h-48 bg-muted rounded animate-pulse" />
        ) : data.length === 0 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No trend data available for this scenario.
          </p>
        ) : data.length < 3 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            Insufficient data for trend visualization (need at least 3 data points, have {data.length}).
          </p>
        ) : chartData ? (
          <div className="h-64">
            <Bar
              data={chartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                  x: { stacked: true },
                  y: { stacked: true, max: 1 },
                },
                plugins: {
                  legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 10 } } },
                },
              }}
            />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
