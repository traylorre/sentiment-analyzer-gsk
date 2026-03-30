'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { VerdictBadge } from './verdict-badge';
import { SCENARIO_NAMES, type Report, type ScenarioType, type Verdict } from '@/types/chaos';

interface ReportListProps {
  reports: Report[];
  isLoading: boolean;
  error: Error | null;
  hasMore: boolean;
  onLoadMore: () => void;
  onViewDetail: (report: Report) => void;
  onViewTrends: (scenario: string) => void;
  selectedForDiff: string[];
  onToggleDiffSelect: (reportId: string) => void;
  onCompare: () => void;
  filters: { scenario_type: string; verdict: string };
  onFilterChange: (filters: { scenario_type: string; verdict: string }) => void;
}

export function ReportList({
  reports,
  isLoading,
  error,
  hasMore,
  onLoadMore,
  onViewDetail,
  onViewTrends,
  selectedForDiff,
  onToggleDiffSelect,
  onCompare,
  filters,
  onFilterChange,
}: ReportListProps) {
  return (
    <Card data-testid="report-list">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-sm">Reports</CardTitle>
          <div className="flex flex-wrap gap-2">
            <select
              data-testid="filter-scenario"
              className="text-xs border border-border rounded px-2 py-1 bg-background"
              value={filters.scenario_type}
              onChange={(e) => onFilterChange({ ...filters, scenario_type: e.target.value })}
            >
              <option value="">All Scenarios</option>
              {Object.entries(SCENARIO_NAMES).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <select
              data-testid="filter-verdict"
              className="text-xs border border-border rounded px-2 py-1 bg-background"
              value={filters.verdict}
              onChange={(e) => onFilterChange({ ...filters, verdict: e.target.value })}
            >
              <option value="">All Verdicts</option>
              <option value="CLEAN">Clean</option>
              <option value="COMPROMISED">Compromised</option>
              <option value="DRY_RUN_CLEAN">Dry Run</option>
              <option value="RECOVERY_INCOMPLETE">Recovery Incomplete</option>
              <option value="INCONCLUSIVE">Inconclusive</option>
            </select>
            {(filters.scenario_type || filters.verdict) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onFilterChange({ scenario_type: '', verdict: '' })}
              >
                Clear
              </Button>
            )}
          </div>
        </div>

        {selectedForDiff.length > 0 && (
          <div className="flex items-center gap-2 mt-2">
            <Button
              size="sm"
              disabled={selectedForDiff.length !== 2}
              onClick={onCompare}
              data-testid="compare-button"
            >
              Compare ({selectedForDiff.length}/2 selected)
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => selectedForDiff.forEach((id) => onToggleDiffSelect(id))}
            >
              Clear Selection
            </Button>
          </div>
        )}
      </CardHeader>

      <CardContent>
        {error && (
          <div
            data-testid="report-error"
            className="p-3 mb-3 rounded-lg border border-destructive/30 bg-destructive/5 text-sm flex items-center justify-between"
          >
            <span className="text-destructive">{error.message}</span>
            <Button variant="ghost" size="sm" onClick={onLoadMore}>Retry</Button>
          </div>
        )}

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-muted rounded animate-pulse" />
            ))}
          </div>
        ) : reports.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No reports found. Reports are generated after chaos experiments complete.
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="pb-2 w-8" />
                    <th className="pb-2 font-medium text-muted-foreground">Time</th>
                    <th className="pb-2 font-medium text-muted-foreground">Scenario</th>
                    <th className="pb-2 font-medium text-muted-foreground">Env</th>
                    <th className="pb-2 font-medium text-muted-foreground">Verdict</th>
                    <th className="pb-2 font-medium text-muted-foreground">Duration</th>
                    <th className="pb-2 font-medium text-muted-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((report) => (
                    <tr
                      key={report.report_id}
                      data-testid={`report-row-${report.report_id}`}
                      className="border-b border-border/50 last:border-0"
                    >
                      <td className="py-2">
                        <input
                          type="checkbox"
                          checked={selectedForDiff.includes(report.report_id)}
                          disabled={
                            selectedForDiff.length >= 2 &&
                            !selectedForDiff.includes(report.report_id)
                          }
                          onChange={() => onToggleDiffSelect(report.report_id)}
                          data-testid={`diff-checkbox-${report.report_id}`}
                        />
                      </td>
                      <td className="py-2 text-muted-foreground">
                        {new Date(report.created_at).toLocaleString()}
                      </td>
                      <td className="py-2">
                        {SCENARIO_NAMES[report.scenario_type as ScenarioType] ?? report.scenario_type}
                      </td>
                      <td className="py-2 text-muted-foreground">{report.environment}</td>
                      <td className="py-2">
                        <VerdictBadge verdict={report.verdict} />
                        {report.dry_run && (
                          <span className="ml-1 text-xs text-blue-500">DRY</span>
                        )}
                      </td>
                      <td className="py-2">{report.duration_seconds}s</td>
                      <td className="py-2">
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onViewDetail(report)}
                            data-testid={`view-report-${report.report_id}`}
                          >
                            View
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onViewTrends(report.scenario_type)}
                            data-testid={`view-trends-${report.report_id}`}
                          >
                            Trends
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {hasMore && (
              <div className="mt-3 text-center">
                <Button variant="outline" size="sm" onClick={onLoadMore}>
                  Load More
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
