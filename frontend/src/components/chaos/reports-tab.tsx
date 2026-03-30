'use client';

import { useState } from 'react';
import { useReports, useReport, useCompareReports, useTrends } from '@/hooks/use-chaos-reports';
import { ReportList } from './report-list';
import { ReportDetail } from './report-detail';
import { ReportDiff } from './report-diff';
import { TrendChart } from './trend-chart';
import { SCENARIO_NAMES, type Report, type ScenarioType } from '@/types/chaos';

type ReportsView = 'list' | 'detail' | 'diff' | 'trends';

export function ReportsTab() {
  const [view, setView] = useState<ReportsView>('list');
  const [filters, setFilters] = useState({ scenario_type: '', verdict: '' });
  const [selectedReport, setSelectedReport] = useState<Report | null>(null);
  const [diffSelection, setDiffSelection] = useState<string[]>([]);
  const [trendScenario, setTrendScenario] = useState<string | null>(null);
  const [trendLimit, setTrendLimit] = useState(20);

  const { data: reportsData, isLoading, error } = useReports({
    scenario_type: filters.scenario_type || undefined,
    verdict: filters.verdict || undefined,
  });

  const { data: detailReport } = useReport(
    view === 'detail' && selectedReport ? selectedReport.report_id : null
  );

  const { data: comparison } = useCompareReports(
    view === 'diff' && diffSelection.length === 2 ? diffSelection[1] : null,
    view === 'diff' && diffSelection.length === 2 ? diffSelection[0] : null
  );

  const { data: trendData, isLoading: trendLoading } = useTrends(
    view === 'trends' ? trendScenario : null,
    trendLimit
  );

  const handleViewDetail = (report: Report) => {
    setSelectedReport(report);
    setView('detail');
  };

  const handleViewTrends = (scenario: string) => {
    setTrendScenario(scenario);
    setView('trends');
  };

  const handleToggleDiffSelect = (reportId: string) => {
    setDiffSelection((prev) =>
      prev.includes(reportId)
        ? prev.filter((id) => id !== reportId)
        : prev.length < 2
          ? [...prev, reportId]
          : prev
    );
  };

  const handleCompare = () => {
    if (diffSelection.length === 2) setView('diff');
  };

  const handleBackToList = () => {
    setView('list');
    setSelectedReport(null);
  };

  const scenarios = Object.keys(SCENARIO_NAMES);

  if (view === 'detail' && (detailReport || selectedReport)) {
    const report = detailReport ?? selectedReport!;
    return (
      <ReportDetail
        report={report}
        onBack={handleBackToList}
        onViewTrends={handleViewTrends}
      />
    );
  }

  if (view === 'diff' && comparison) {
    return <ReportDiff comparison={comparison} onBack={handleBackToList} />;
  }

  if (view === 'trends') {
    return (
      <div className="space-y-4" data-testid="reports-tab">
        <TrendChart
          data={trendData ?? []}
          scenario={trendScenario}
          scenarios={scenarios}
          limit={trendLimit}
          onScenarioChange={setTrendScenario}
          onLimitChange={setTrendLimit}
          isLoading={trendLoading}
        />
        <button
          className="text-sm text-muted-foreground hover:text-foreground"
          onClick={handleBackToList}
        >
          &larr; Back to report list
        </button>
      </div>
    );
  }

  return (
    <div data-testid="reports-tab">
      <ReportList
        reports={reportsData?.reports ?? []}
        isLoading={isLoading}
        error={error}
        hasMore={!!reportsData?.next_cursor}
        onLoadMore={() => {/* cursor pagination — TODO in follow-up */}}
        onViewDetail={handleViewDetail}
        onViewTrends={handleViewTrends}
        selectedForDiff={diffSelection}
        onToggleDiffSelect={handleToggleDiffSelect}
        onCompare={handleCompare}
        filters={filters}
        onFilterChange={setFilters}
      />
    </div>
  );
}
