'use client';

import { useState } from 'react';
import { useExperiments, useCreateExperiment, useStartExperiment, useStopExperiment } from '@/hooks/use-chaos-experiments';
import { SafetyControlsBar } from './safety-controls-bar';
import { ScenarioLibrary } from './scenario-library';
import { ExperimentConfigForm } from './experiment-config-form';
import { ActiveExperimentList } from './active-experiment-list';
import { ExperimentHistory } from './experiment-history';
import type { ScenarioType } from '@/types/chaos';

export function ExperimentsTab() {
  const { activeExperiments, historyExperiments, isLoading, hasActive } = useExperiments();
  const createMutation = useCreateExperiment();
  const startMutation = useStartExperiment();
  const stopMutation = useStopExperiment();

  const [selectedScenario, setSelectedScenario] = useState<ScenarioType | null>(null);
  const [stoppingId, setStoppingId] = useState<string | null>(null);

  // Re-enable polling when there are active experiments
  useExperiments();

  const handleCreateAndStart = (blastRadius: number, duration: number) => {
    if (!selectedScenario) return;
    createMutation.mutate(
      { scenario_type: selectedScenario, blast_radius: blastRadius, duration_seconds: duration },
      {
        onSuccess: (experiment) => {
          startMutation.mutate(experiment.experiment_id);
          setSelectedScenario(null);
        },
      }
    );
  };

  const handleStop = (id: string) => {
    setStoppingId(id);
    stopMutation.mutate(id, {
      onSettled: () => setStoppingId(null),
    });
  };

  return (
    <div className="space-y-6" data-testid="experiments-tab">
      <SafetyControlsBar />

      <section>
        <h2 className="text-sm font-medium mb-3">Chaos Scenarios</h2>
        <ScenarioLibrary
          selected={selectedScenario}
          onSelect={setSelectedScenario}
        />
      </section>

      {selectedScenario && (
        <ExperimentConfigForm
          scenario={selectedScenario}
          onSubmit={handleCreateAndStart}
          onCancel={() => setSelectedScenario(null)}
          isSubmitting={createMutation.isPending || startMutation.isPending}
        />
      )}

      <ActiveExperimentList
        experiments={activeExperiments}
        stoppingId={stoppingId}
        onStop={handleStop}
      />

      <ExperimentHistory
        experiments={historyExperiments}
        isLoading={isLoading}
      />
    </div>
  );
}
