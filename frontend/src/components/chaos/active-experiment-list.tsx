'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Square } from 'lucide-react';
import { SCENARIO_NAMES, type Experiment } from '@/types/chaos';

interface ActiveExperimentListProps {
  experiments: Experiment[];
  stoppingId: string | null;
  onStop: (id: string) => void;
}

export function ActiveExperimentList({
  experiments,
  stoppingId,
  onStop,
}: ActiveExperimentListProps) {
  if (experiments.length === 0) return null;

  return (
    <Card data-testid="active-experiments">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Active Experiments ({experiments.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {experiments.map((exp) => (
          <div
            key={exp.experiment_id}
            data-testid={`active-experiment-${exp.experiment_id}`}
            className="flex items-center justify-between p-3 rounded-lg border border-border"
          >
            <div className="space-y-1">
              <p className="text-sm font-medium">
                {SCENARIO_NAMES[exp.scenario_type] ?? exp.scenario_type}
              </p>
              <p className="text-xs text-muted-foreground">
                Blast: {exp.blast_radius}% &middot; Duration: {exp.duration_seconds}s
                &middot; Status: {exp.status}
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              disabled={stoppingId === exp.experiment_id}
              onClick={() => onStop(exp.experiment_id)}
              data-testid={`stop-experiment-${exp.experiment_id}`}
            >
              <Square className="w-3 h-3 mr-1" />
              {stoppingId === exp.experiment_id ? 'Stopping...' : 'Stop'}
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
