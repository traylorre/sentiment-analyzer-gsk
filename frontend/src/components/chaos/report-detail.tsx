'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { VerdictBadge } from './verdict-badge';
import { HealthCards } from './health-cards';
import type { Report } from '@/types/chaos';

interface ReportDetailProps {
  report: Report;
  onBack: () => void;
  onViewTrends: (scenario: string) => void;
}

type Section = 'config' | 'baseline' | 'postChaos' | 'verdict';

export function ReportDetail({ report, onBack, onViewTrends }: ReportDetailProps) {
  const [expanded, setExpanded] = useState<Record<Section, boolean>>({
    config: true,
    baseline: true,
    postChaos: true,
    verdict: true,
  });

  const toggle = (section: Section) =>
    setExpanded((prev) => ({ ...prev, [section]: !prev[section] }));

  return (
    <div className="space-y-4" data-testid="report-detail">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Reports
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onViewTrends(report.scenario_type)}
        >
          View Trends
        </Button>
      </div>

      {/* Header */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">{report.scenario_type}</CardTitle>
          <VerdictBadge verdict={report.verdict} size="md" />
        </CardHeader>
      </Card>

      {report.dry_run && (
        <div className="p-3 rounded-lg border border-blue-500/30 bg-blue-500/5 text-sm text-blue-700 dark:text-blue-400">
          This was a dry run — no actual fault was injected.
        </div>
      )}

      {/* Configuration */}
      <CollapsibleSection
        title="Configuration"
        expanded={expanded.config}
        onToggle={() => toggle('config')}
      >
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-muted-foreground">Environment</dt>
          <dd>{report.environment}</dd>
          <dt className="text-muted-foreground">Duration</dt>
          <dd>{report.duration_seconds}s</dd>
          <dt className="text-muted-foreground">Created</dt>
          <dd>{new Date(report.created_at).toLocaleString()}</dd>
          {report.experiment_id && (
            <>
              <dt className="text-muted-foreground">Experiment ID</dt>
              <dd className="font-mono text-xs">{report.experiment_id}</dd>
            </>
          )}
        </dl>
      </CollapsibleSection>

      {/* Baseline Health */}
      {report.baseline_health && (
        <CollapsibleSection
          title="Baseline Health (Pre-Chaos)"
          expanded={expanded.baseline}
          onToggle={() => toggle('baseline')}
        >
          <HealthCards health={{
            all_healthy: report.baseline_health.all_healthy ?? true,
            degraded_services: report.baseline_health.degraded_services ?? [],
            dependencies: report.baseline_health.dependencies,
          }} isLoading={false} />
        </CollapsibleSection>
      )}

      {/* Post-Chaos Health */}
      {report.post_chaos_health && (
        <CollapsibleSection
          title="Post-Chaos Health"
          expanded={expanded.postChaos}
          onToggle={() => toggle('postChaos')}
        >
          <HealthCards health={{
            all_healthy: report.post_chaos_health.all_healthy ?? true,
            degraded_services: report.post_chaos_health.degraded_services ?? [],
            dependencies: report.post_chaos_health.dependencies,
          }} isLoading={false} />
        </CollapsibleSection>
      )}

      {/* Verdict */}
      <CollapsibleSection
        title="Verdict"
        expanded={expanded.verdict}
        onToggle={() => toggle('verdict')}
      >
        <div className="space-y-2">
          <VerdictBadge verdict={report.verdict} size="md" />
          {report.verdict_reason && (
            <p className="text-sm text-muted-foreground">{report.verdict_reason}</p>
          )}
        </div>
      </CollapsibleSection>

      {/* Plan Report */}
      {report.plan_report && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Plan Report</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {report.plan_report.scenarios.map((s, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span>{s.scenario_type}</span>
                <VerdictBadge verdict={s.verdict} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function CollapsibleSection({
  title,
  expanded,
  onToggle,
  children,
}: {
  title: string;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <span className="text-sm font-medium">{title}</span>
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="w-4 h-4 text-muted-foreground" />
        )}
      </button>
      {expanded && <CardContent className="pt-0">{children}</CardContent>}
    </Card>
  );
}
