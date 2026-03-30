'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { VerdictBadge } from './verdict-badge';
import { SCENARIO_NAMES, type Experiment, type Verdict } from '@/types/chaos';

interface ExperimentHistoryProps {
  experiments: Experiment[];
  isLoading: boolean;
}

export function ExperimentHistory({ experiments, isLoading }: ExperimentHistoryProps) {
  return (
    <Card data-testid="experiment-history">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Experiment History</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-muted rounded animate-pulse" />
            ))}
          </div>
        ) : experiments.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No experiments yet. Start your first chaos test above!
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="pb-2 font-medium text-muted-foreground">Time</th>
                  <th className="pb-2 font-medium text-muted-foreground">Scenario</th>
                  <th className="pb-2 font-medium text-muted-foreground">Status</th>
                  <th className="pb-2 font-medium text-muted-foreground">Blast</th>
                  <th className="pb-2 font-medium text-muted-foreground">Duration</th>
                </tr>
              </thead>
              <tbody>
                {experiments.map((exp) => (
                  <tr
                    key={exp.experiment_id}
                    data-testid={`history-row-${exp.experiment_id}`}
                    className="border-b border-border/50 last:border-0"
                  >
                    <td className="py-2 text-muted-foreground">
                      {new Date(exp.created_at).toLocaleString()}
                    </td>
                    <td className="py-2">
                      {SCENARIO_NAMES[exp.scenario_type] ?? exp.scenario_type}
                    </td>
                    <td className="py-2">
                      <VerdictBadge verdict={exp.status.toUpperCase() as Verdict} />
                    </td>
                    <td className="py-2">{exp.blast_radius}%</td>
                    <td className="py-2">{exp.duration_seconds}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
