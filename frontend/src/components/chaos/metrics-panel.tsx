'use client';

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useMetrics } from '@/hooks/use-chaos-metrics';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

export function MetricsPanel() {
  const { data, isLoading, isUnavailable, isRateLimited, error, refetch } = useMetrics();

  if (isUnavailable) {
    return (
      <Card data-testid="metrics-panel">
        <CardContent className="py-6 text-center">
          <p className="text-sm text-muted-foreground">
            Metrics not available in this environment.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="metrics-panel">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">System Metrics</CardTitle>
          <div className="flex items-center gap-2">
            {isRateLimited && (
              <span className="text-xs text-amber-600">Rate limited — retrying...</span>
            )}
            {error && !isRateLimited && !isUnavailable && (
              <span className="text-xs text-destructive">Error loading metrics</span>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetch()}
              disabled={isLoading}
              data-testid="refresh-metrics"
            >
              <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && !data ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-48 bg-muted rounded animate-pulse" />
            ))}
          </div>
        ) : data?.groups.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-4">
            No metrics data available.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data?.groups.map((group, idx) => (
              <div key={idx} className="h-48">
                <p className="text-xs font-medium mb-1">{group.title}</p>
                <Line
                  data={{
                    labels: group.series[0]?.timestamps.map((t) =>
                      new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    ) ?? [],
                    datasets: group.series.map((s) => ({
                      label: s.label,
                      data: s.values,
                      borderColor: s.color,
                      backgroundColor: s.color + '20',
                      fill: true,
                      tension: 0.3,
                      pointRadius: 0,
                    })),
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                      x: { ticks: { maxTicksLimit: 6, font: { size: 9 } } },
                      y: { beginAtZero: true, ticks: { font: { size: 9 } } },
                    },
                    plugins: {
                      legend: {
                        display: group.series.length > 1,
                        labels: { boxWidth: 8, font: { size: 9 } },
                      },
                      tooltip: { mode: 'index' as const, intersect: false },
                    },
                  }}
                />
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
