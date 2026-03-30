'use client';

import { useState } from 'react';
import { Activity, ShieldAlert, OctagonX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { useHealthCheck, useGateState, useSetGateState, useAndonCord } from '@/hooks/use-chaos-safety';
import { HealthCards } from './health-cards';
import type { HealthCheck as HealthCheckType, AndonResult } from '@/types/chaos';

const GATE_STYLES = {
  armed: 'text-amber-700 bg-amber-500/10 dark:text-amber-400',
  disarmed: 'text-muted-foreground bg-muted',
  triggered: 'text-destructive bg-destructive/10 animate-pulse',
} as const;

export function SafetyControlsBar() {
  const healthMutation = useHealthCheck();
  const { data: gateData } = useGateState();
  const setGateMutation = useSetGateState();
  const andonMutation = useAndonCord();

  const [healthResult, setHealthResult] = useState<HealthCheckType | null>(null);
  const [healthCooldown, setHealthCooldown] = useState(false);
  const [showGateDialog, setShowGateDialog] = useState(false);
  const [showAndonDialog, setShowAndonDialog] = useState(false);
  const [andonResult, setAndonResult] = useState<AndonResult | null>(null);

  const gateState = gateData?.state ?? 'disarmed';

  const handleHealthCheck = () => {
    healthMutation.mutate(undefined, {
      onSuccess: (data) => {
        setHealthResult(data);
        setHealthCooldown(true);
        setTimeout(() => setHealthCooldown(false), 3000);
      },
    });
  };

  const handleGateToggle = () => {
    const newState = gateState === 'armed' ? 'disarmed' : 'armed';
    setGateMutation.mutate(newState, {
      onSuccess: () => setShowGateDialog(false),
    });
  };

  const handleAndonCord = () => {
    andonMutation.mutate(undefined, {
      onSuccess: (data) => {
        setAndonResult(data);
        setShowAndonDialog(false);
      },
    });
  };

  return (
    <div data-testid="safety-controls" className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 p-3 rounded-lg border border-border bg-card">
        {/* Health Check */}
        <Button
          variant="outline"
          size="sm"
          onClick={handleHealthCheck}
          disabled={healthMutation.isPending || healthCooldown}
          data-testid="health-check-button"
        >
          <Activity className="w-4 h-4 mr-1" />
          {healthMutation.isPending ? 'Checking...' : 'Pre-Flight Check'}
        </Button>

        {/* Gate Toggle */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowGateDialog(true)}
            disabled={gateState === 'triggered' || setGateMutation.isPending}
            data-testid="gate-toggle-button"
          >
            <ShieldAlert className="w-4 h-4 mr-1" />
            {gateState === 'armed' ? 'Disarm Gate' : 'Arm Gate'}
          </Button>
          <span
            data-testid="gate-state-badge"
            className={cn(
              'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
              GATE_STYLES[gateState] ?? GATE_STYLES.disarmed
            )}
          >
            {gateState}
          </span>
        </div>

        {/* Andon Cord */}
        <Button
          variant="destructive"
          size="sm"
          onClick={() => setShowAndonDialog(true)}
          disabled={andonMutation.isPending}
          data-testid="andon-cord-button"
        >
          <OctagonX className="w-4 h-4 mr-1" />
          EMERGENCY STOP
        </Button>
      </div>

      {/* Health results */}
      <HealthCards health={healthResult} isLoading={healthMutation.isPending} />

      {/* Andon result */}
      {andonResult && (
        <div
          data-testid="andon-result"
          className="p-3 rounded-lg border border-destructive/30 bg-destructive/5 text-sm"
        >
          <p className="font-medium">Emergency Stop Result</p>
          <p className="text-muted-foreground">
            Kill switch: {andonResult.kill_switch_set ? 'set' : 'failed'} &middot;
            Found: {andonResult.experiments_found} &middot;
            Restored: {andonResult.restored} &middot;
            Failed: {andonResult.failed}
          </p>
          {andonResult.errors.length > 0 && (
            <ul className="mt-1 text-xs text-destructive">
              {andonResult.errors.map((err, i) => <li key={i}>{err}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Gate Confirmation Dialog */}
      <Dialog open={showGateDialog} onOpenChange={setShowGateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {gateState === 'armed' ? 'Disarm Chaos Gate?' : 'Arm Chaos Gate?'}
            </DialogTitle>
            <DialogDescription>
              {gateState === 'armed'
                ? 'Disarming the gate will prevent chaos injection. Experiments will run in dry-run mode.'
                : 'Arming the gate enables real fault injection. Experiments will modify live infrastructure.'}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowGateDialog(false)}>
              Cancel
            </Button>
            <Button
              variant={gateState === 'armed' ? 'default' : 'destructive'}
              onClick={handleGateToggle}
              disabled={setGateMutation.isPending}
            >
              {setGateMutation.isPending ? 'Updating...' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Andon Cord Confirmation Dialog */}
      <Dialog open={showAndonDialog} onOpenChange={setShowAndonDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-destructive">Emergency Stop</DialogTitle>
            <DialogDescription>
              This will immediately:
            </DialogDescription>
          </DialogHeader>
          <ol className="list-decimal pl-5 space-y-1 text-sm text-muted-foreground">
            <li>Set the kill switch to TRIGGERED</li>
            <li>Restore ALL chaos-injected configurations</li>
            <li>Block new experiment injection</li>
          </ol>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAndonDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleAndonCord}
              disabled={andonMutation.isPending}
              data-testid="confirm-andon-cord"
            >
              {andonMutation.isPending ? 'Stopping...' : 'Confirm Emergency Stop'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
