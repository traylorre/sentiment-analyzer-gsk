'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { SCENARIO_NAMES, type ScenarioType } from '@/types/chaos';

interface ExperimentConfigFormProps {
  scenario: ScenarioType;
  onSubmit: (blastRadius: number, duration: number) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function ExperimentConfigForm({
  scenario,
  onSubmit,
  onCancel,
  isSubmitting,
}: ExperimentConfigFormProps) {
  const [blastRadius, setBlastRadius] = useState(25);
  const [duration, setDuration] = useState(60);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(blastRadius, duration);
  };

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="experiment-form"
      className="space-y-4 p-4 border border-border rounded-lg bg-card"
    >
      <h3 className="font-medium text-sm">
        Configure: {SCENARIO_NAMES[scenario]}
      </h3>

      <div className="space-y-2">
        <Label htmlFor="blast-radius">Blast Radius: {blastRadius}%</Label>
        <Slider
          id="blast-radius"
          data-testid="blast-radius-slider"
          min={10}
          max={100}
          step={10}
          value={[blastRadius]}
          onValueChange={([v]) => setBlastRadius(v)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="duration">Duration (seconds)</Label>
        <Input
          id="duration"
          data-testid="duration-input"
          type="number"
          min={5}
          max={300}
          value={duration}
          onChange={(e) => setDuration(Number(e.target.value))}
        />
      </div>

      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          data-testid="cancel-experiment"
        >
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={isSubmitting}
          data-testid="start-experiment"
        >
          {isSubmitting ? 'Starting...' : 'Start Experiment'}
        </Button>
      </div>
    </form>
  );
}
