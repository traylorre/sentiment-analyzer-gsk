'use client';

import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { VerdictBadge } from './verdict-badge';
import { cn } from '@/lib/utils';
import type { ComparisonResult } from '@/types/chaos';

interface ReportDiffProps {
  comparison: ComparisonResult;
  onBack: () => void;
}

export function ReportDiff({ comparison, onBack }: ReportDiffProps) {
  return (
    <div className="space-y-4" data-testid="report-diff">
      <Button variant="ghost" size="sm" onClick={onBack}>
        <ArrowLeft className="w-4 h-4 mr-1" /> Back to Reports
      </Button>

      {/* Verdict comparison */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Verdict Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center gap-4">
            <div className="text-center">
              <p className="text-xs text-muted-foreground mb-1">Baseline</p>
              <VerdictBadge verdict={comparison.baseline.verdict} size="md" />
            </div>
            <span className="text-muted-foreground">&rarr;</span>
            <div className="text-center">
              <p className="text-xs text-muted-foreground mb-1">Current</p>
              <VerdictBadge verdict={comparison.current.verdict} size="md" />
            </div>
          </div>
          <p className={cn(
            'text-center mt-2 text-sm font-medium',
            comparison.direction === 'improved' && 'text-green-600 dark:text-green-400',
            comparison.direction === 'regressed' && 'text-destructive',
            comparison.direction === 'neutral' && 'text-muted-foreground',
          )}>
            {comparison.direction === 'improved' && 'Improved'}
            {comparison.direction === 'regressed' && 'Regressed'}
            {comparison.direction === 'neutral' && 'No change'}
          </p>
        </CardContent>
      </Card>

      {/* Dependency changes */}
      {comparison.changes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Dependency Changes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {comparison.changes.map((change, i) => (
              <div
                key={i}
                className={cn(
                  'flex items-center justify-between p-2 rounded-lg text-sm',
                  change.direction === 'improved' && 'bg-green-500/5',
                  change.direction === 'regressed' && 'bg-destructive/5',
                )}
              >
                <span className="font-medium capitalize">{change.dependency}</span>
                <span className="text-muted-foreground">
                  {change.from_status} &rarr; {change.to_status}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Side-by-side health */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-xs text-muted-foreground">
              Baseline ({new Date(comparison.baseline.created_at).toLocaleDateString()})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {Object.entries(comparison.baseline.post_chaos_health.dependencies).map(
              ([name, dep]) => (
                <div key={name} className="flex justify-between text-sm py-1">
                  <span className="capitalize">{name}</span>
                  <span className={dep.status === 'healthy' ? 'text-green-600 dark:text-green-400' : 'text-destructive'}>
                    {dep.status}
                  </span>
                </div>
              )
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-xs text-muted-foreground">
              Current ({new Date(comparison.current.created_at).toLocaleDateString()})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {Object.entries(comparison.current.post_chaos_health.dependencies).map(
              ([name, dep]) => (
                <div key={name} className="flex justify-between text-sm py-1">
                  <span className="capitalize">{name}</span>
                  <span className={dep.status === 'healthy' ? 'text-green-600 dark:text-green-400' : 'text-destructive'}>
                    {dep.status}
                  </span>
                </div>
              )
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
