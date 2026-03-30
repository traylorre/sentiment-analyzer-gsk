'use client';

import { cn } from '@/lib/utils';
import type { HealthCheck } from '@/types/chaos';

interface HealthCardsProps {
  health: HealthCheck | null;
  isLoading: boolean;
}

export function HealthCards({ health, isLoading }: HealthCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-16 bg-muted rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (!health) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
      {Object.entries(health.dependencies).map(([name, dep]) => (
        <div
          key={name}
          data-testid={`health-card-${name}`}
          className={cn(
            'p-3 rounded-lg border text-sm',
            dep.status === 'healthy'
              ? 'border-green-500/30 bg-green-500/5'
              : 'border-destructive/30 bg-destructive/5'
          )}
        >
          <p className="font-medium capitalize">{name}</p>
          <p
            className={cn(
              'text-xs',
              dep.status === 'healthy' ? 'text-green-600 dark:text-green-400' : 'text-destructive'
            )}
          >
            {dep.status}
            {dep.latency_ms != null && ` · ${dep.latency_ms}ms`}
          </p>
        </div>
      ))}
    </div>
  );
}
